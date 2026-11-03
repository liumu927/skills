# S7 钉钉登录（人员身份侧）

这一段管"人怎么进系统"，与 S1–S6 的"数据怎么流"正交。**两条线可以共用一个企业应用，也可以分开——推荐分开。**

## 核心认知（三条，决定整个方案形态）

1. **回调地址是"用户浏览器被 302 过去"的，钉钉服务器只校验它、不访问它。**
   所以回调可以指向内网地址——登录这一步完全不需要把业务系统暴露到公网。
   **已实测：钉钉（企业内部应用）可以直接登记 `http://<办公网IP>:<端口>/...` 这样的内网 IP 地址**，
   连域名和证书都不需要（代价：只能在内网登录）。
   服务端唯一需要的出站是访问 `api.dingtalk.com`（换 token / 取用户信息）。
2. **登录成功后签发的是本系统自己的 JWT**（与密码登录同一套密钥、同一载荷格式），
   业务侧对"用户是怎么登录的"零感知。钉钉的用户标识（openId/unionId）只落库做账号关联。
3. **唯一作数的验证 = 完整走完一次登录**（start 302 → 扫码授权 → callback → exchange 200）。
   "授权页能打开"是假信号——未登记回调域名时授权页照样渲染。改动生效与否看全链，不看首屏。

## 与审批链路的关系

| | 审批链路（S1–S6） | 登录链路（S7） |
|---|---|---|
| 钉钉应用 | 自建应用 + 连接器 | 企业内部应用 + 「登录」能力 |
| 凭据 | 连接器 OAuth2.0（应用 token） | Client ID/Secret + `Contact.User.Read` |
| 令牌 | 边缘令牌/内部令牌（自定义） | userAccessToken（钉钉）→ 自签 JWT（我方） |
| 回调地址 | 公网中间件域名（钉钉云端调） | 登录域名（**用户浏览器**调） |
| 失败影响 | 数据不同步 | 用户进不来 |

**两者用不同应用**：审批 HTTP 节点根本不需要钉钉应用凭据（静态令牌即可）；登录只开「登录」能力。轮换登录密钥不打断审批，反之亦然。**清理旧应用前先确认审批连接流挂在哪，别误删。**

## 第零步：场景判定（先做完再动手）

```
Q1 目标系统是否与某个已接入钉钉登录的系统同域名？
   是 → 路径 0：同域名复用。钉钉按主机校验回调、端口可自选（已实测），
        域名/DNS/证书/钉钉登记全部不动，直接跳到「主流程」，
        DINGTALK_REDIRECT_URI 填 https://<同域名>:<新端口>/api/auth/dingtalk/callback。
   否 ↓
Q2 目标系统部署在哪？
   内网（数据不出网）→ 默认走路径 B（内网 IP 直连），除非命中下面三条例外：
        ① 需要外网/手机/出差登录     → 路径 A（域名+TLS）或 C
        ② 要在钉钉客户端工作台打开   → 先实测 http 能否在 webview 加载；不行则路径 A
        ③ 生产平台且组织强制 TLS     → 路径 A
        都不命中 → 路径 B：钉钉后台直接登记 http://<办公网IP>:<端口>/...，零域名零证书，
                   约 30 分钟；代价是只能在办公网内登录
   公网 → 路径 C：公网部署（常规 OAuth 部署）
```

| 路径 | 入口形态 | 验证状态 | 详细步骤 |
|---|---|---|---|
| 0 | 同域名换端口/路径 | 实测（端口可自选） | 主流程即可，基础设施零改动 |
| A | 内网 + 公网域名解析到内网 IP + HTTPS | 生产完整验证，多人实测 | [07a-login-intranet.md](07a-login-intranet.md) |
| B | 内网 IP 直连（`http://<办公网IP>:<端口>/...`） | **本组织实测（2026-11）**，只能在办公网登录 | [07a-login-intranet.md](07a-login-intranet.md) §路径B |
| C | 公网部署 + 公网域名 | **未实测骨架** | [07b-login-public.md](07b-login-public.md) |

**关键实测结论（2026-11，本组织多人复验）：钉钉企业内部应用的「重定向 URL」可以直接登记 `http://<办公网IP>:<端口>/api/auth/dingtalk/callback` 这样的完整内网地址，登录全流程跑通。** 此前"裸 IP 必被拒"的教训实为"IP 与**域名**登记条目匹配不上"；直接登记 IP URL 即通过。代价只有一个：**只能在办公网内登录**。已实测协议仅 `http`，`https`+IP 未实测（需 IP SAN 证书）。

**选型速查**（默认就走第一条）：

- **没有特殊需求 → 路径 B（内网 IP 直连）**：零域名、零 DNS、零证书，约 30 分钟，且天然没有"回调域名被审批占用"的冲突。内部工具、只在办公网用，这就是最优解。
- 只有这三种情况需要离开 B：**要外网/手机登录**（→ A/C）、**要在钉钉工作台内打开**（先实测 webview，不行 → A）、**组织强制 TLS**（→ A）。
- 生产平台（密码登录/管理员权限/API 令牌/真实数据）若坚持走 B，明文 JWT 的风险要组织书面确认；不接受就升级到 A，别"先用 B 以后再说"。
- 要 HTTPS（浏览器无"不安全"警告、可用 `crypto.subtle`/剪贴板/摄像头等）、将来有第二个系统、或在意运维弹性（域名下换端口不用回钉钉后台改）→ 路径 A。
- 存量 HTTPS 想改裸 IP：先过三道约束（端口别降级、https+裸 IP 必卡证书拦截页、别挪用被公网职责占用的域名），见 [07a](07a-login-intranet.md) §存量系统。
- 路径 B 隐藏代价：redirect_uri 按 IP URL **逐字符严格匹配**，换端口/换机器都要回钉钉后台改并**重新发布版本**；IP 靠 DHCP 必须做保留。
- **域名职责冲突只对路径 A/C 存在**：若某域名已被审批回调占用（公网解析指向腾讯云边缘），拿它当登录回调会 404。走路径 B 则完全没有这个问题（IP 不可能指向边缘服务器）——这是 B 在"混合接入"场景下的额外优势。若必须用域名，登录另开一个子域（见 [07a](07a-login-intranet.md) §存量系统约束 3）。

## 主流程（四条路径共用）

### 第 1 步：钉钉开放平台侧（约 10 分钟）

1. 钉钉开放平台 → 创建/进入**企业内部应用**，记录 `Client ID`(AppKey) 与 `Client Secret`(AppSecret)。
2. **应用开发 → 登录与分享 → 添加「重定向 URL」**。不开这一步，授权页直接报 `应用不存在 Code:900103`。
   - 登记条目支持两种形态（均已实测）：
     - **域名**（如 `<system>.example.com`）：按**主机**匹配，`redirect_uri` 的端口可自选、可随时换；
     - **完整 URL 含内网 IP**（如 `http://10.1.2.20:8080/api/auth/dingtalk/callback`）：按**逐字符**匹配，换端口/路径/机器都要回来改。
   - 不匹配报 `redirect_uri参数错误,请修改或在钉钉开放平台的「应用开发」-「登录与分享」中配置相应的回调域名`。
3. **权限管理 → 添加「通讯录个人信息读权限」`Contact.User.Read`**。不加，取用户信息返回 `403 ... AccessTokenPermissionDenied`。
4. **点「发布版本」**。不点发布等于没改，回调仍按旧配置判定——"地址都对、配置也填了、但就是登录不了"的最常见原因。

> ⚠️ 假信号：「授权页能打开」≠「回调已登记」。未登记时授权页照常渲染、外观一致；`redirect_uri参数错误` 是几秒消失的浮动 toast，截图慢一点就抓不到。唯一作数的验证 = 从系统页面点登录 → 同意 → 浏览器被打回 `<callback>?authCode=...&state=...` → 落到 `/?dingtalk_code=...` 并换到 token。**在服务端盯日志判定**，浏览器截图不可靠。

### 第 2 步：环境变量

`DINGTALK_CLIENT_ID` / `DINGTALK_CLIENT_SECRET` / `DINGTALK_REDIRECT_URI` 必填；`DINGTALK_LANDING_URL`、`DINGTALK_DEFAULT_ROLE` 可选。

凭据红线：Secret 只走 env 文件（0600 / systemd `EnvironmentFile=`），**不入库、不进代码、不进文档、不进仓库**。生产 env 与本地联调 env 是两个副本，改一个别忘另一个；systemd 场景改完必须 `daemon-reload` **再** `restart`（只 restart 不重读单元文件）。

换密钥后快速自检（在服务器上，不打印明文）：

```bash
node -e "fetch('https://api.dingtalk.com/v1.0/oauth2/accessToken',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({appKey:process.env.DINGTALK_CLIENT_ID,appSecret:process.env.DINGTALK_CLIENT_SECRET})}).then(async r=>console.log(r.status,(await r.text()).slice(0,120)))"
# 200 且含 accessToken → 凭据有效；400 invalidClientIdOrSecret → 不对（多半是没 daemon-reload）
```

### 第 3 步：服务端实现

从 `assets/templates/` 复制 `dingtalk_login.js` + `routes-dingtalk.js`，挂到 `app.use('/api/auth', ...)`，补 users 表三列 + openId 唯一索引。→ [07c-login-server.md](07c-login-server.md)

### 第 4 步：前端接入

登录页放 `<div class="dingtalk-login-slot"></div>` + 引入 `frontend-dingtalk-login.js`（自动探测未配置则隐藏按钮；自动处理回跳换 token）。→ [07d-login-frontend.md](07d-login-frontend.md)

### 第 5 步：验证

`GET /api/auth/dingtalk/diag`（配置齐全 + 三个钉钉域名出站连通）→ 完整走一次登录 → 源站日志确认 `start 302 → callback → exchange 200` 三条都在 → 同一用户二次登录复用同一账号、无重复建号。

## 账号模型红线（所有路径一致）

- 幂等键 = `dingtalk_open_id`（唯一索引）。**跨应用关联同一人用 unionId**——openId 是应用级的，换应用同一人的 openId 就变了。
- 首登自动建号：用户名 `dt_<openId前10位>`、随机密码哈希占位（不可密码登录）、角色默认最低权限（viewer），管理员再提权。
- **绝不按姓名/手机号自动贴靠已有账号**——避免"同名即接管"越权。
- 重复登录只刷新 `dingtalk_nick`，不覆盖人工维护的 `display_name`。

## 工作台免登（可选）

应用加进钉钉工作台 + 申请 JSAPI 免登权限（企业 corpId）后，钉钉内嵌 H5 可用 JSAPI 拿 authCode 直接 POST 到服务端换 token（跳过 302 流程）。对应路由模板里的 `POST /dingtalk/workbench`。若钉钉后台配过「工作台首页地址」，注意与实际访问域名一致。

## 排障

先查 [09-troubleshooting.md](09-troubleshooting.md) §登录类。涉及"时灵时不灵 / nslookup 对但浏览器打不开 / 无痕正常普通窗口不正常 / 回调落到 404"，在**出问题的那台机器**跑：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/client-dns-check.ps1 -Domain <域名> -OriginIp <源站IP> [-Port 4322] [-Scheme https|http]
```

服务端万能三连：①源站日志里有没有那条请求（没有 → 客户端侧断了）②有且带 error → 按 error 码查 ③`换 token 失败(400)` → 八成 Secret 不对或 env 没生效。
