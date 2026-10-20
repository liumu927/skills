---
name: dingtalk-login
description: >-
  网页系统接入钉钉扫码登录 / 工作台免登（OAuth2 授权码模式）的完整落地与排障。
  覆盖：钉钉开放平台配置（登录能力、重定向 URL、Contact.User.Read、发布版本）、
  服务端四端点实现（state 防 CSRF、一次性码、openId 幂等建号、自签 JWT）、
  前端接入、四种部署入口（同域名复用 / 内网+公网域名+证书 / 内网+裸IP+HTTP 轻量 /
  公网部署）、redirect_uri/state/回调 404/证书等报错排查、客户端 DNS 与代理排障。
  当用户提到：接入钉钉登录、钉钉扫码登录、钉钉 OAuth/免登、redirect_uri 参数错误、
  应用不存在 900103、Contact.User.Read 403、钉钉回调 404、扫码后登录失败、
  内网系统要接钉钉 —— 即使用户没同时说"钉钉"和"登录"，也应触发。
  注意：钉钉审批表单/连接器/连接流/AI 表格/低代码集成不归本 skill（用 dingtalk-integration）；
  本 skill 只管"把登录这一步接到钉钉"。
---

# 钉钉登录接入（OAuth2 授权码 / 扫码 / 工作台免登）

## 核心认知（三条，决定了整个方案形态）

1. **回调地址是"用户浏览器被 302 过去"的，钉钉服务器只校验它、不访问它。**
   所以回调可以指向内网地址——登录这一步完全不需要把业务系统暴露到公网。
   服务端唯一需要的出站是访问 `api.dingtalk.com`（换 token / 取用户信息）。
2. **登录成功后签发的是本系统自己的 JWT**（与密码登录同一套密钥、同一载荷格式），
   业务侧对"用户是怎么登录的"零感知。钉钉的用户标识（openId/unionId）只落库做账号关联。
3. **唯一作数的验证 = 完整走完一次登录**（start 302 → 扫码授权 → callback → exchange 200）。
   "授权页能打开"是假信号——未登记回调域名时授权页照样渲染。改动生效与否看全链，不看首屏。

## 第零步：场景判定（先做完再动手）

按顺序问三个问题，落到一条路径：

```
Q1 目标系统是否与某个已接入钉钉登录的系统同域名？
   是 → 路径 0：同域名复用。钉钉按主机校验回调、端口可自选（已实测），
        域名/DNS/证书/钉钉登记全部不动，直接跳到「主流程」，
        DINGTALK_REDIRECT_URI 填 https://<同域名>:<新端口>/api/auth/dingtalk/callback。
   否 ↓
Q2 目标系统部署在哪？
   内网（数据不出网）→ 先问：要在钉钉客户端里打开吗（工作台免登/内嵌 webview）？
        要 → 直接选路径 A：内嵌 webview 对证书问题没有"继续访问"手动放行，
             证书必须干净；纯 http 在 webview 里的兼容性需实测（普通浏览器能开不代表钉钉里能开）
        不进钉钉客户端 → 再按系统性质选：
             全新工具型小系统（无密码登录/无特权账号/无 API 令牌，数据容忍明文）
               且只要单系统快速接入 → 路径 B：裸 IP + HTTP（最轻，约 30 分钟）
             生产平台（有密码登录/管理员权限/令牌/真实业务数据）→ TLS 是底线，选路径 A；
               且若现有端口/域名已背着其他职责（如被反代/边缘按证书回源校验），
               该端口**不可降级为 http**——裸 IP 只能附加新 http 端口并存
               （逐条约束与双入口过渡见 references/scenario-intranet.md §存量系统）
             要 HTTPS / 多系统长期演进 → 路径 A：独立域名 + 公网 DNS 指内网 + 证书
   公网 → 路径 C：公网部署（常规 OAuth 部署）
```

| 路径 | 入口形态 | 验证状态 | 详细步骤 |
|---|---|---|---|
| 0 | 同域名换端口/路径 | 实测（端口可自选） | 主流程即可，基础设施零改动 |
| A | 内网 + 公网域名解析到内网 IP + HTTPS | 本机生产完整验证，多人实测 | 读 references/scenario-intranet.md |
| B | 内网 + 裸 IP + HTTP | 他系统实测可行（2026-10 确认） | 读 references/scenario-intranet.md §路径B |
| C | 公网部署 + 公网域名 | **未实测骨架**（按标准 OAuth 写） | 读 references/scenario-public.md |

**关键实测结论（2026-10-20 确认）：钉钉的「重定向 URL」可以直接登记 `http://<内网IP>:<端口>/...`
这样的完整地址**——此前"裸 IP 必被拒"的经验源于登记的是域名字段、IP 与之匹配不上；
直接登记 IP URL 则匹配通过。选 IP 就是选了这条轻量路径，不是被逼的。

**选型速查（用户问"该用哪种"时）**：
- 全新工具型小系统、内网、无特权凭据、页面用不到 secure-context Web API → 路径 B，最快。
- 生产平台（密码登录/管理员权限/API 令牌/真实业务数据）→ TLS 是底线，路径 A；
  JWT 或管理员口令走 http 明文 = 同网段抓包即可冒用身份/提权，安全加固被削掉一半。
- 要 HTTPS（浏览器无"不安全"警告、可用 crypto.subtle/剪贴板/摄像头等）、
  或将来有第二个系统要接、或在意运维弹性（域名下换端口不用回钉钉后台改）→ 路径 A。
- 存量 HTTPS 系统想改走路径 B：先过三道约束——背其他链路的端口不可降级 http、
  https+裸 IP 必卡证书拦截页、被公网职责占用的域名不可挪用；可行做法是
  "附加 http 端口 + 钉钉双登记 + 双入口过渡"，见 scenario-intranet.md §存量系统。
- "省一个域名"不是路径 B 的真实收益：公网 DNS 指内网的域名方案已无解析歧义，
  年维护 ≈ 一张免费证书 + 一条 DNS 记录；裸 IP 省的只有这张证书，
  付出的是明文传输与 DHCP 命门（IP 变 = 书签与钉钉登记双重断）。
- 路径 B 的隐藏代价：redirect_uri 按 IP URL **逐字符严格匹配**，换端口/换机器都要回
  钉钉后台改配置并**重新发布版本**；IP 靠 DHCP 时必须做保留，否则换 IP 全断。
- 公网部署额外的第一决策是暴露面（只放行登录链路 vs 整系统公开），见 scenario-public.md。

## 主流程（四条路径共用，细节在 references）

1. **钉钉开放平台侧**（~10 分钟）：确认应用开启「登录」能力、登记重定向 URL（域名或 IP URL）、
   `Contact.User.Read` 权限、**发布版本**。→ references/dingtalk-side.md
2. **环境变量**：`DINGTALK_CLIENT_ID` / `DINGTALK_CLIENT_SECRET` / `DINGTALK_REDIRECT_URI`
   必填；`DINGTALK_LANDING_URL`、`DINGTALK_DEFAULT_ROLE` 可选。密钥只走 env 文件注入，
   不进代码/文档/仓库。
3. **服务端实现**：从 assets/templates/ 复制 `dingtalk_login.js` + `routes-dingtalk.js`，
   挂到 `app.use('/api/auth', ...)`，补 users 表三列 + openId 唯一索引。安全要点照抄模板
   （state 防 CSRF、一次性码、openId 幂等、绝不按姓名贴靠、最低权限建号）。→ references/server-impl.md
4. **前端接入**：登录页放 `<div class="dingtalk-login-slot"></div>` + 引入
   `frontend-dingtalk-login.js`（自动探测未配置则隐藏按钮；自动处理回跳换 token）。→ references/frontend-impl.md
5. **验证**：`GET /api/auth/dingtalk/diag`（配置齐全 + 三个钉钉域名出站连通）→
   完整走一次登录 → 源站日志确认 `start 302 → callback → exchange 200` 三条都在 →
   同一用户二次登录应复用同一账号、无重复建号。

## 账号模型红线（所有路径一致）

- 幂等键 = `dingtalk_open_id`（唯一索引）。**跨应用关联同一人用 unionId**——openId 是应用级的，
  换个钉钉应用同一人的 openId 就变了。
- 首登自动建号：用户名 `dt_<openId前10位>`、随机密码哈希占位（不可密码登录）、
  角色默认最低权限（viewer），管理员再在账号管理里提权。
- **绝不按姓名/手机号自动贴靠已有账号**——避免"同名即接管"越权。
- 重复登录只刷新 `dingtalk_nick`，不覆盖人工维护的 `display_name`
  （按姓名匹配业务的系统，人工校对过的姓名不能被钉钉昵称冲掉）。

## 排障

先看 references/troubleshooting.md 的报错速查表（按报错关键词直接查）。
涉及"时灵时不灵 / nslookup 对但浏览器打不开 / 无痕正常普通窗口不正常 / 回调落到 404"，
在出问题的那台机器上跑 `scripts/client-dns-check.ps1 -Domain <域名> -OriginIp <源站IP>`
（内网拆解析的场景；裸 IP+HTTP 场景无 DNS 问题，重点查代理与证书拦截页）。

服务端相关万能三连：
1. 源站日志里有没有那条请求？没有 → 请求没到源站（客户端 DNS/代理/证书断了）；
2. 有且带 error → 按 error 码查速查表；
3. `换 token 失败(400)` → 八成是 Client Secret 不对或环境变量没生效（systemd 改完要
   `daemon-reload` 再 restart，只 restart 不重读单元文件）。
