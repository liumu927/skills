# S5 边界中间件（腾讯云）

钉钉在公网、业务系统在办公网，中间这一层只做三件事：**安检（鉴权+白名单）、暂存（接住数据）、交付（让内网取走）**。业务逻辑一律不下沉到这一层。

本篇同时记录**两种形态**：A 是已跑通的现状（透明转发 + OpenVPN），B 是推荐目标（落盘 + 内网拉取）。A 的知识全部保留——它仍是回退路径，也是理解链路的基础。

## 一、两种形态

| | 形态 A：透明转发（legacy，已上线跑通） | 形态 B：落盘 + 拉取（目标） |
|---|---|---|
| 数据是否落盘 | **不落盘**（只在断链时临时排队） | 每条都落盘，带状态机 |
| 内网角色 | 被动接收（VPN 隧道内的目标） | **主动出站拉取** |
| 依赖 | OpenVPN 常连 | 无 VPN 数据面；内网能出站 HTTPS 即可 |
| 钉钉拿到的 200 | 内网真的处理完 | 中间件落盘成功 |
| 超时风险 | 高（钉钉约 5s，内网慢就超时） | 低（落盘毫秒级） |
| 可对账 | 弱（无落盘，事后无法回溯） | 强（状态机 + 游标 + 死信） |
| 内网暴露面 | 一条常驻加密通路进内网 | **零入站** |

选型与迁移见 06、11。新项目直接从 B 起步。

---

## 二、形态 A：透明转发 + OpenVPN（保留记录）

### 2.1 链路

```
钉钉自建应用（OA 审批模板 + 连接器 HTTP 节点）
   │  审批通过/撤回 → HTTPS 调公网域名
   │  POST https://<domain>/api/<system>/upsert
   │  请求头 X-API-Token: 边缘令牌
   ▼
公网 DNS：<domain> → 腾讯云服务器公网 IP（备案接入商=腾讯云，不被合规拦截）
   ▼
腾讯云边缘服务器（无状态中转）
    nginx:443    TLS 终结（正式证书）+ 限流 + 仅回调路径白名单，其余一律 404
    relay:4330   ①校验边缘令牌 ②换发内部令牌 ③转发/回传响应 ④断链落盘队列→恢复后重放
   ▼  OpenVPN 加密隧道（VPN 账号 ACL 仅放行 <内网主机>:<端口> 一个目标）
办公网主机（事实源，数据不出网）
   <内网系统> :<端口>   upsert 幂等入库 / external-delete 撤销删除+留档 / 查询接口
   ▼
响应原路流式返回 → 连接器节点拿到真实成败（不加缓存不篡改）
```

各角色一句话：钉钉侧只做"配置"；公网服务器只做"安检口 + 转发"；业务系统一直在办公网内。

### 2.2 设计动机（为什么当初这么选）

| 现实约束 | 结论 |
|---|---|
| 域名 ICP 备案接入商登记在腾讯云 | 服务必须落在**腾讯云大陆服务器**；放阿里云会被合规系统拦截 |
| 内网系统不能整体暴露公网 | 公网入口只保留回调 API 的几条路径 |
| 数据合规 | 数据库只在办公网，边缘服务器无状态、不落业务数据，单一事实源 |
| frp 类裸端口转发 | 等于把内网端口原样发布公网，任何客户端可直达；本方案用 VPN 隧道 + 应用层白名单/令牌替代 |

### 2.3 relay 行为速查（本项目实测）

| 环节 | 行为 |
|---|---|
| 接收 | 仅 nginx 转来的回调路径（本项目 5 条：upsert / external-delete / DELETE external/:id / GET external/:id / GET revoked）+ 本机 `/healthz` |
| 校验 | ①边缘令牌（失败 401，**不解析 body、不触达源站**）②方法+路径白名单（403）③仅接受 JSON（415）、限请求体大小 |
| 转发 | 同方法+同路径+同 body；`X-API-Token` **换成内部令牌**（边缘令牌不出 VPN）；带来源 IP；keep-alive；超时 8s（须小于钉钉节点超时约 5s，实测后收紧） |
| 输出 | 源站响应**原样透传**（钉钉拿到真实成败，不假 200）；隧道断+写操作 → 503（`retryable:true`）并落盘队列；隧道断+只读 → 502 不排队 |
| 补偿 | 每 30s 探测源站；恢复后 FIFO 重放：2xx 删文件；删除重放遇 404=成功；4xx 转死信并告警；5xx 保持顺序重试、超限转死信 |
| 幂等 | 源站以 `external_id` 为唯一键 |
| 告警 | 隧道断开/恢复、重放完成、死信产生 → 钉钉群机器人 webhook |

### 2.4 形态 A 的风险（这就是要换成 B 的原因）

| # | 风险 | 后果 |
|---|---|---|
| A1 | VPN 常连 = 内网常驻一条通路 | 账号/证书泄露即等于进了内网；ACL 漂移难发现 |
| A2 | 边缘不落盘 | 钉钉重试与真实结果无记录，事后无法对账 |
| A3 | 同步穿透 + 5s 超时 | 内网慢就超时，但数据可能已处理 → 重复推送与"到底成没成"的扯皮 |
| A4 | 断链补偿只在断链期有效 | 队列文件在边缘机器上，机器重装/VPN 长期断 → 数据只能靠钉钉重试 |
| A5 | 强耦合 | VPN 一断全线停；内网应用一改接口，边缘白名单/令牌要同步 |
| A6 | 只读请求不排队 | 查询接口断链直接 502，前端体验断 |

---

## 三、形态 B：落盘 + 内网拉取（目标）

### 3.1 链路

```
钉钉连接器 HTTP 节点
   ▼ POST https://<domain>/api/inbound/<consumer>/<event>   X-API-Token: 边缘令牌
腾讯云边缘中间件
   nginx:443  TLS + 白名单 + 限流（其余 404）
   inbound    ①验令牌 ②验 schema ③按 external_id upsert 落盘 → 立即 200 {receipt_id, duplicate:false}
              （落盘失败才 5xx，让钉钉重试）
   pull       内网应用出站调用：GET /api/pull/<consumer>?limit=...&lease=60
              → 发放租约，返回未投递记录；应用处理完 ack
   admin      对账/查询/重放/死信读取（仅内网或带管理令牌）
   ▼ 出站方向：中间件不主动连内网，只等内网来取
办公网自有系统（或一个小型 puller 常驻进程）
   定时/长轮询 → 拉取 → 落本地库（按 external_id 幂等）→ ack
```

**关键点：中间件不再需要 OpenVPN。** 数据面变成"内网 → 公网 HTTPS 出站"，不需要公网能进内网。

### 3.2 消息模型（中间件侧表结构建议）

```
inbound_message
  id            自增主键
  external_id   幂等键（审批实例 ID）+ UNIQUE(consumer, external_id)   ← 冲突即 duplicate:true
  consumer      目标系统标识（多系统隔离）
  event         upsert / delete / revoke
  payload       JSON（原始请求体，原样保存，便于重放与追溯）
  headers       精简后的来源信息（IP、时间）
  status        pending / leased / delivered / dead
  attempts      尝试次数
  lease_until   租约到期时间（可空）
  lease_token   本次租约令牌（ack 时校验，防串）
  created_at / delivered_at / last_error
```

状态机：

```
       ┌──────── 落盘 ────────┐
       ▼                      │
   pending ──发放租约──▶ leased ──ack──▶ delivered（终态，定期归档）
       ▲                    │
       │             租约到期/处理失败
       └────────────────────┘
                            └─ attempts 超限 ──▶ dead（需人工/告警）
```

### 3.3 接口契约

**入库（钉钉侧调用）**

```
POST /api/inbound/:consumer/:event
Headers: X-API-Token: <边缘令牌>, Content-Type: application/json
Body:    { "external_id": "<审批实例ID>", ...业务字段 }
200:     { "ok": true, "receipt_id": 12345, "duplicate": false }
200:     { "ok": true, "receipt_id": 12345, "duplicate": true }    ← 幂等命中，不是错误
400/415/401/403: 校验失败（钉钉会视为失败）
5xx:     落盘失败，请重试
```

**拉取（内网侧调用）**

```
GET /api/pull/:consumer?limit=20&lease=60&event=upsert
Headers: Authorization: Bearer <消费方令牌>
200: { "items": [ { "id":1, "external_id":"...", "event":"upsert", "payload":{...}, "lease_token":"..." } ],
       "has_more": true }
```

**确认**

```
POST /api/ack/:consumer
Body: { "acks":[{"id":1,"lease_token":"..."}], "nacks":[{"id":2,"lease_token":"...","error":"校验失败"}] }
200:  { "acked":1, "nacked":1 }
```

**运维接口**：`GET /api/admin/stats`（各状态计数）、`GET /api/admin/dead`、`POST /api/admin/replay/:id`、`GET /healthz`。

### 3.4 投递语义（必须明确写下来）

- **至少一次（at-least-once）**，不是恰好一次。消费方必须按 `external_id` 幂等，重复投递是常态。
- **租约制**：拉取即加锁 `lease_until`，处理超时则回到 `pending` 重投（因此同一条可能被两个 worker 先后拿到，幂等兜底）。
- **顺序**：不保证全局顺序；同一 `external_id` 的 upsert/delete 建议按 `created_at` 处理，或消费方自行取最新状态。
- **重试**：`attempts` 超限（建议 5–8 次）转 `dead` 并告警，**不要无限重试**（旧数据晚于新数据落库更难收拾）。
- **保留**：`delivered` 归档 30–90 天（按合规要求定），`pending` 不删，`dead` 保留到人工处理。

### 3.5 鉴权

| 接口 | 令牌 | 说明 |
|---|---|---|
| `inbound` | 边缘令牌 `X-API-Token` | 钉钉连接器请求头里那一枚；一 consumer 一枚，可并行轮换 |
| `pull` / `ack` | 消费方令牌 `Authorization: Bearer` | 与边缘令牌分离，泄露一个不影响另一个 |
| `admin` | 管理令牌 + 网络限制 | 只允许内网或运维通道访问 |

双令牌的意义：边缘令牌出现在钉钉后台（多人可见），消费方令牌只出现在内网主机环境变量里。两者独立轮换。

### 3.6 数据安全（落盘后新增的责任）

形态 B 把数据留在了公网服务器上，这是与 A 最大的性质差异，必须配套：

1. **静态加密**：云盘加密 + 应用层字段级加密（至少手机号等敏感字段）。
2. **最小字段**：只存业务必需字段；密码/身份证等敏感项考虑不入库、走引用。
3. **保留期**：`delivered` 到期删除，别当数据库长期存。
4. **访问审计**：谁拉走、什么时候、多少条，要留日志。
5. **合规确认**：数据落到公网服务器前，先确认组织/等保要求允许（这是形态 B 的唯一硬前置，不能拍脑袋）。**判定方法与三种结论的预案见 [12-compliance-gate.md](12-compliance-gate.md)。**

### 3.7 可执行骨架

上面的契约有对应实现，别从零写：`assets/deploy/`（relay 参考实现 + puller + nginx + systemd + `.env.example` + Postgres schema，已按本契约做冒烟自测）。部署顺序与验证命令见 `assets/deploy/README.md`。**它是参考实现，不是免评审代码**：单文件事件日志适合中小流量，上量或多实例请换 `sql/schema.postgresql.sql`。

---

## 四、两种形态共用的网络与部署要点

### 4.1 备案、域名、证书

1. **同父域新增子域不需要新增备案**——新开 `xxx.<父域>` 沿用既有备案；变更接入商才要动备案。
2. **拆分解析（形态 A 必需，形态 B 可选）**：
   - 公网 DNS（DNSPod）：A 记录 → 腾讯云公网 IP，**钉钉云端走这条**；
   - 办公网内网 DNS：同名解析 → 内网 IP，同事在办公室直连不绕公网；
   - 同一域名、同一张证书，两边各一份。
3. **边缘服务器 `/etc/hosts` 固定**（形态 A）：把回调域名指向 VPN 可达的内网 IP，中间件转发时域名/SNI/证书校验全部照常工作。
4. **接入第二个系统**：父域下新子域 → 新证书（单域名证书需新签或换通配符）→ nginx 加 server 块与路径白名单 → relay 扩展白名单或新起实例 → （A）VPN ACL 放行目标 / （B）新建 consumer → 目标系统签发令牌。
5. **证书必须是正式的**：钉钉云端校验 HTTPS 证书，自签（mkcert）不可用。

### 4.2 nginx（两种形态一致）

```nginx
server {
    listen 443 ssl;
    server_name <domain>;
    ssl_certificate     /etc/nginx/certs/<domain>.crt;
    ssl_certificate_key /etc/nginx/certs/<domain>.key;

    # 只放行明确路径，其余一律 404
    location /api/inbound/ { proxy_pass http://127.0.0.1:4330; proxy_set_header X-Real-IP $remote_addr; }
    location /api/pull/    { proxy_pass http://127.0.0.1:4330; }
    location /healthz      { proxy_pass http://127.0.0.1:4330; }
    location / { return 404; }
}
```

**白名单两处都要改**：nginx `location` 与 relay 内部 `ROUTES`（漏一处就是"403 路径不允许"）。

### 4.3 多个中间件并存（你问的"可以建立不同的中间件"）

推荐"**一系统一 consumer，物理上可合可拆**"：

| 粒度 | 做法 | 适合 |
|---|---|---|
| 逻辑隔离（推荐起点） | 同一实例，不同 `consumer` + 不同路径 + 不同令牌 + 独立队列语义 | 3–5 个系统，运维最省 |
| 物理隔离 | 独立 relay 实例 / 独立端口 / 独立域名子域 | 数据敏感度不同、要独立升级回滚、要独立配额 |
| 完全隔离 | 独立服务器 | 强合规要求 |

命名规范：`<系统>-<环境>`，如 `<system>-prod`、`assets-test`。路径 `/api/inbound/<consumer>/<event>`，event 用 `upsert|delete|revoke`。**一个 consumer 只对应一个系统的一个数据方向**，别混。

钉钉侧怎么指向不同中间件：连接器动作里 URL 不同即可（一个动作一个目标）；同一审批要扇出到两个系统，用连接流并行两个动作节点。

---

## 五、验证与排障

### 5.1 不改线上 DNS 就能验证（切换前必做）

```bash
curl --resolve <域名>:443:<腾讯云IP> https://<域名>/api/inbound/<consumer>/upsert \
  -H "X-API-Token: <边缘令牌>" -H "Content-Type: application/json" \
  -d '{"external_id":"manual-test-001"}'
```

形态 B 追加三步：`GET /api/pull/...` 能取到 → `POST /api/ack` 能确认 → 重复 POST 同 `external_id` 返回 `duplicate:true`。

### 5.2 排障表

| 现象 | 排查 |
|---|---|
| 连接器报 TLS/证书错误 | nginx 证书无效/过期；确认公网解析确实指向腾讯云 |
| 401 | 边缘令牌不匹配（连接器请求头 vs 中间件 `EDGE_TOKENS`） |
| 403 路径/方法不允许 | 新路径没进白名单——nginx `location` 与 relay `ROUTES` **两处都要加** |
| 415 | 缺 `Content-Type: application/json`，或 body 不是 JSON |
| 502 | （A）隧道断 + 只读请求：`curl 127.0.0.1:4330/healthz` 看 `tunnel.up`；`journalctl -u openvpn-client@office` |
| 503 `retryable:true` | 落盘失败或（A）隧道断+写请求已排队；看 `spool/pending/` 或 DB 状态计数 |
| 推送成功但内网没数据 | （B）看 `GET /api/admin/stats`：`pending` 堆积=内网没拉；`leased` 卡住=消费方没 ack；`dead`=超重试 |
| 内网拉到重复数据 | 预期内的至少一次投递；消费方没做 `external_id` 幂等 |
| 推送成功但列表没变 | （A）被幂等去重：先 `GET /api/external/<id>` 查 |
| 改钉钉配置不生效 | 连接流快照——必须**重建连接流**（见 03） |
| DNS 方向不对 | 公网 `nslookup` 应出腾讯云 IP；办公网内应出内网 IP（拆分解析） |

### 5.3 参考仓库

| 仓库 | 内容 |
|---|---|
| `<system>`（业务系统主仓库） | `docs/edge-relay-plan.md`（方案+威胁模型+切换 runbook+OpenVPN 客户端配置）、`docs/dingtalk-connector.md`（钉钉侧逐项配置）、`server/routes/<system>.js`（被调接口与幂等实现） |
| `<system>-relay`（边缘中间件） | 中间件源码、`.env.example`、`deploy/`（systemd + nginx）、README |

两个仓库在团队内部 git 服务上，需权限找业务系统维护人。
