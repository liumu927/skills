# 边界中间件部署骨架（形态 B：落盘 + 拉取）

对应 [05-edge-middleware.md §三](../../references/05-edge-middleware.md)、[06-office-lan-pull.md](../../references/06-office-lan-pull.md)、[11-migration-push-to-pull.md](../../references/11-migration-push-to-pull.md)。

**先过 [12-compliance-gate.md](../../references/12-compliance-gate.md) 的合规闸门再部署到生产。** 这套骨架让数据在公网服务器上停留，合规结论未签之前只允许在测试环境跑。

## 这是什么 / 不是什么

| 是 | 不是 |
|---|---|
| 一套能直接跑起来的**参考实现**（零外部依赖，Node ≥ 20） | 经过你们安全评审的生产代码 |
| nginx / systemd / env 的完整骨架 | 整套高可用方案（无多实例、无 DB 事务） |
| 把 05 的接口契约落成可验证的东西 | 替代 `<system>-relay`（那个是形态 A 的现网实现） |

参考实现的价值是把"契约"变成"可跑的对照物"：你们的实现或采购方案可以用它做行为对齐，也能以此写集成测试。

## 目录

```
deploy/
├── relay/server.mjs            # 中间件本体：inbound / pull / ack / admin / healthz
├── puller/pull.mjs             # 内网拉取器：拉取→本地幂等落库→ack（可当模板改成业务落库）
├── nginx/dingtalk-edge.conf    # TLS + 路径白名单 + 限流 + admin 仅内网
├── systemd/
│   ├── dingtalk-relay.service  # 中间件常驻（含最小权限加固）
│   ├── dingtalk-pull.service   # 拉取器 oneshot
│   └── dingtalk-pull.timer     # 每 30 秒触发
├── env/.env.example            # 三套令牌 + 保留期 + 投递语义
└── sql/schema.postgresql.sql   # 换 DB 时的表结构与并发安全领取语句
```

## 部署顺序（腾讯云单机）

### 1. 账号与目录

```bash
sudo useradd --system --no-create-home --shell /usr/sbin/nologin dingtalk-relay
sudo mkdir -p /opt/dingtalk-relay /etc/dingtalk-relay /var/lib/dingtalk-relay
sudo cp relay/server.mjs /opt/dingtalk-relay/
sudo chown -R root:root /opt/dingtalk-relay
sudo chown -R dingtalk-relay:dingtalk-relay /var/lib/dingtalk-relay
```

### 2. Node 版本

```bash
node -v      # 需 >= 20（用到全局 fetch 与 node: 前缀模块）
```

### 3. 配置

```bash
sudo cp env/.env.example /etc/dingtalk-relay/.env
sudo vi /etc/dingtalk-relay/.env       # 改三套令牌、DATA_DIR、保留期
sudo chmod 600 /etc/dingtalk-relay/.env
sudo chown root:dingtalk-relay /etc/dingtalk-relay/.env
```

令牌生成：

```bash
openssl rand -hex 24    # 每套令牌各生成一个，不要复用
```

### 4. systemd

```bash
sudo cp systemd/dingtalk-relay.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dingtalk-relay
sudo systemctl status dingtalk-relay
sudo journalctl -u dingtalk-relay -f      # 应看到 listening on http://127.0.0.1:4330
```

### 5. nginx

```bash
sudo cp nginx/dingtalk-edge.conf /etc/nginx/conf.d/
sudo vi /etc/nginx/conf.d/dingtalk-edge.conf   # 替换 <domain> 与证书路径
sudo nginx -t && sudo systemctl reload nginx
```

**白名单两处都要有**：nginx 的 `location` 与 relay 内部的 `:event` 校验（只认 upsert/delete/revoke）。漏一处就是 403/400。

### 6. 内网拉取器（在办公网那台机器上，不是在腾讯云）

```bash
sudo mkdir -p /opt/dingtalk-puller/data /etc/dingtalk-puller
sudo cp puller/pull.mjs /opt/dingtalk-puller/
# /etc/dingtalk-puller/.env 里配 EDGE_BASE / CONSUMER / CONSUMER_TOKEN / LOCAL_DIR
sudo cp systemd/dingtalk-pull.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dingtalk-pull.timer
sudo systemctl list-timers dingtalk-pull.timer
```

## 验证（照抄，逐条应通过）

不碰钉钉、不改 DNS，直接打边缘：

```bash
D=<domain>; IP=<腾讯云公网IP>; ET=<边缘令牌>; CT=<消费方令牌>; ADMIN=<admin令牌>

# 1) 存活
curl -s --resolve $D:443:$IP https://$D/healthz

# 2) 入库
curl -s --resolve $D:443:$IP https://$D/api/inbound/<system>-prod/upsert \
  -H "X-API-Token: $ET" -H 'Content-Type: application/json' \
  -d '{"external_id":"manual-test-001","name":"测试"}'
# 期望 {"ok":true,"receipt_id":1,"duplicate":false}

# 3) 幂等：重复同一条
#    期望 duplicate:true

# 4) 拉取
curl -s --resolve $D:443:$IP "https://$D/api/pull/<system>-prod?limit=10" \
  -H "Authorization: Bearer $CT"
# 期望 items[] 含刚推的记录 + lease_token

# 5) 确认（用上一步的 id / lease_token）
curl -s --resolve $D:443:$IP -X POST https://$D/api/ack/<system>-prod \
  -H "Authorization: Bearer $CT" -H 'Content-Type: application/json' \
  -d '{"acks":[{"id":1,"lease_token":"<上一步的值>"}]}'

# 6) 统计（pending 应为 0，delivered 为 1）
curl -s --resolve $D:443:$IP https://$D/api/admin/stats -H "Authorization: Bearer $ADMIN"

# 7) 负向：错令牌 401、非 JSON 415、缺 external_id 400、未登记路径 404
curl -s -o /dev/null -w '%{http_code}\n' --resolve $D:443:$IP -X POST https://$D/api/inbound/<system>-prod/upsert \
  -H "X-API-Token: wrong" -H 'Content-Type: application/json' -d '{"external_id":"x"}'
```

## 已自测的行为（2026-11-03，本机 Node 22.16）

参考实现按上面接口跑过一轮冒烟，以下都是实测结果：

- [x] 入库落盘即 200，返回 `receipt_id`
- [x] 同一 `external_id` 重复推送 → `duplicate:true`，不产生第二条（**跨进程重启仍成立**）
- [x] 错误边缘令牌 → 401；缺 `Content-Type: application/json` → 415；缺 `external_id` → 400
- [x] 拉取发放租约（`lease_token` 每次不同），`has_more` 正确
- [x] ack 后状态转 `delivered`；`stats` 计数正确；重启后 `delivered` 仍保留
- [x] nack 累计 8 次 → `dead`，`/api/admin/dead` 可查、`last_error` 留存
- [x] 拉取器端到端：拉 2 条 → 本地 NDJSON 落库 → ack 2 条 → 再拉为空
- [x] 拉取器重启后不重复落库（本地按 `external_id` 幂等）

**未验证**（需要你在真实环境补）：
- nginx 配置的 `nginx -t`（本机无 nginx，按标准写法给，务必在目标机先 `nginx -t`）
- 证书链与钉钉云端校验（必须正式证书）
- systemd 加固项在你的发行版上是否全部支持（老内核可能不支持某些 `Protect*`，用 `systemd-analyze security dingtalk-relay` 看评分）
- 真实钉钉连接器打通（依赖审批模板配置，见 03 / 05 §三）

## 上生产前必做（别跳过）

1. **合规签字** —— [12-compliance-gate.md](../../references/12-compliance-gate.md) 的登记表。
2. **换存储** —— 删掉 NDJSON，改 `sql/schema.postgresql.sql`；参考实现的单文件日志不适合多实例与大数据量。
3. **日志脱敏** —— `payload` 不得进应用日志/nginx body 日志；`journalctl` 里只能出现 id 与状态。
4. **三套令牌分开轮换** —— 观察期用双值并存（新增 consumer 别名 → 切 → 删旧）。
5. **监控接入** —— `stats.pending` 与 `oldest_pending_at`、`dead` 计数必须告警（06 §五）。
6. **备份策略** —— 如果结论是"允许落盘"，明确备份是否也含业务数据、备份保留期是否与主库一致。

## 回滚

- relay 停掉 → 钉钉侧拿到 5xx（**不要**为了让钉钉"看着成功"而返回 200）
- 回形态 A：把钉钉连接器 URL 改回原转发路径 → **重建连接流** → 重启 VPN 客户端（见 11 §回退矩阵）
- 参考实现的 `DATA_DIR` 整体打包即可搬迁/取证
