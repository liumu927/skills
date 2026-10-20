# 钉钉开放平台侧配置(所有部署路径通用)

## 前提:登录应用与审批应用是分开的两个

审批链路(连接器 HTTP 节点 + API 令牌回调)根本不用钉钉应用凭据。登录只开「登录」能力,
权限面最小化;轮换登录密钥不打断审批。**清理旧应用前先确认审批连接流挂在哪,别误删。**

## 配置步骤(约 10 分钟)

1. 钉钉开放平台 → 创建/进入**企业内部应用**,记录 `Client ID`(AppKey)与 `Client Secret`(AppSecret)。
2. **应用开发 → 登录与分享 → 添加「重定向 URL」/回调域名**。不开这一步,授权页直接报
   `应用不存在 Code:900103`。
   - 登记条目支持两种形态(均已实测可行):
     - **域名**(如 `patents.example.com`):按**主机**匹配,`redirect_uri` 的端口可自选、可随时换;
     - **完整 URL 含内网 IP**(如 `http://192.168.3.20:8080/api/auth/dingtalk/callback`):
       按**逐字符**匹配——换端口/换路径/换机器都要回这里改。
   - 判断依据:redirect_uri 的主机(或整个 URL)必须与登记条目匹配,不匹配报
     `redirect_uri参数错误,请修改或在钉钉开放平台的「应用开发」-「登录与分享」中配置相应的回调域名`。
3. **权限管理 → 添加「通讯录个人信息读权限」(`Contact.User.Read`)**。不加,取用户信息返回
   `403 Forbidden.AccessDenied.AccessTokenPermissionDenied`。
4. **点「发布版本」**。开放平台顶部会提示"版本发布后,当前修改才能生效"——**不点发布等于没改**,
   回调仍按旧配置判定。这是"地址都对、配置也填了、但就是登录不了"的最常见原因。

## ⚠️ 假信号:「授权页能打开」≠「回调已登记」

| 实测 | 结果 |
|---|---|
| `redirect_uri参数错误` 提示形态 | 浮动 toast,几秒自动消失,截图慢一点就抓不到 |
| 同一未登记域名连续访问 | 第一次有提示,之后不再出现 |
| 未登记时授权页是否渲染 | **照常渲染**,与已登记时外观一致 |

唯一作数的验证 = 从系统页面点登录 → 钉钉授权页点同意 → 浏览器被打回
`<callback>?authCode=...&state=...` → 最终落到 `/?dingtalk_code=...` 并成功换到 token。
建议在**服务端**盯日志判定(浏览器侧截图不可靠)。

## 凭据管理红线

- `DINGTALK_CLIENT_SECRET` 只走环境变量(env 文件 0600 / systemd `EnvironmentFile=`),
  **不入库、不进代码、不进文档、不进仓库**。
- 密钥存在两个独立副本时(生产 env + 本地联调 env),改一个不同步另一个;
  改完 systemd 场景必须 `daemon-reload` 再 `restart`(只 restart 不重读单元文件)。
- 换密钥后快速自检(在服务器上,不打印明文):

```bash
node -e "fetch('https://api.dingtalk.com/v1.0/oauth2/accessToken',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({appKey:process.env.DINGTALK_CLIENT_ID,appSecret:process.env.DINGTALK_CLIENT_SECRET})}).then(async r=>console.log(r.status,(await r.text()).slice(0,120)))"
# HTTP 200 且含 accessToken → 凭据有效;400 invalidClientIdOrSecret → 不对(多半是没 daemon-reload)
```

## 钉钉侧报错 → 原因速查

| 报错 | 原因 |
|---|---|
| `应用不存在 Code:900103` | 应用没开「登录」能力(重定向 URL 未配置) |
| `redirect_uri参数错误` | redirect_uri 与登记条目不匹配(域名没登记/没发布版本/IP URL 逐字符不符) |
| 取用户信息 `403 ... Contact.User.Read` | 权限没加,或加了**没发布版本** |
| 换 token 400 `invalidParameter.idOrSecret.notFound` | clientId/clientSecret 错误或环境变量没生效 |
| 授权页能打开、扫码后失败 | client_id 是对的所以授权页正常,**几乎必然卡在 secret 上** |

## 工作台免登(可选)

应用加进钉钉工作台 + 申请 JSAPI 免登权限(企业 corpId)后,钉钉内嵌 H5 可用 JSAPI 拿 authCode
直接 POST 到服务端换 token(跳过 302 流程)。对应路由模板里的 `POST /dingtalk/workbench`。
若钉钉后台配过「工作台首页地址」,注意与实际访问域名一致。
