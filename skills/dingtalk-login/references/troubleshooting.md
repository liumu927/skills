# 排障速查(全部来自实测案例)

## 报错 → 原因(按关键词直接查)

| 现象/报错 | 原因 → 处置 |
|---|---|
| 授权页 `应用不存在 Code:900103` | 应用没开「登录」能力(登录与分享 → 重定向 URL 未配置) |
| 授权页 `redirect_uri参数错误`(浮动 toast,几秒消失,**别截图找它**) | redirect_uri 与登记条目不匹配:域名没登记 / 用了裸 IP 而登记的是域名 / IP URL 逐字符不符(端口、路径差一点都不行) |
| 改了回调域名后仍按旧配置判定 | **没点「发布版本」**——开放平台改配置不发布不生效,头号常见原因 |
| 取用户信息 `403 ... AccessTokenPermissionDenied` | 没加 `Contact.User.Read` 权限,或加了**没发布版本** |
| 服务端日志 `换 token 失败(400) ... clientId或者clientSecret错误` | Client ID/Secret 不对或环境变量没生效。**授权页能打开只证明 client_id 对,扫码后失败几乎必然卡在 secret**。systemd 场景:改了 env 文件必须 `daemon-reload` 再 `restart`(只 restart 不重读单元文件) |
| 登录页没有钉钉按钮 / 点按钮 503 | `/status` 返回 configured:false → 三个必填变量没配全 |
| 回调 302 带 `error=dingtalk_bad_state` | state 过期(>10 分钟)或跨进程(多实例/服务重启)→ 重试;多实例部署需把 state 换共享存储 |
| 回调 302 带 `error=dingtalk_exchange_failed` | 看服务端日志:多为 `api.dingtalk.com` 出站被拦(防火墙/安全组),或 secret 不对(上一行) |
| 扫码页本身打不开 | 用户设备到 `login.dingtalk.com` 不通(办公网出站策略) |
| 回调后落到 404 `{"success":false,"message":"not found"}` | **这不是本系统的响应**——浏览器把回调域名解析到了别处(旧公网 IP/别的服务)。`nslookup <回调域名>` 应返回登记时规划的地址;不对就查 DNS/代理,见下节 |
| `nslookup` 返回正确,浏览器仍 404/打不开 | 浏览器没走系统 DNS:代理分流 / DoH / 浏览器 host 缓存。跑 `scripts/client-dns-check.ps1` 逐通道定位,或 hosts 兜底 |
| **无痕窗口能用、普通窗口不能用** | 差异只在"窗口自己的东西":①扩展(无痕默认不加载,带 proxy/webRequest/declarativeNetRequest 权限的是头号嫌疑)②普通窗口自己的 DNS 缓存/连接池/HTTP 缓存。处置:禁扩展 + 清浏览器 DNS 缓存(edge://net-internals/#dns)+ 强刷 |
| 内网裸 IP 能开页面,登录完 404 | 同一故障:裸 IP 只能开页面(手动放行证书告警后),但回调走的是**登记的域名**,域名解析错了就到不了源站。不是两个独立故障 |
| 证书告警 / TLS `alert number 46` | 客户端拒绝证书:裸 IP 访问(域名证书无 IP SAN,必然)或该域名不在证书覆盖内。服务端日志看 `sni=`:空 = 裸 IP;有域名 = 域名没装对应证书 |
| 登录成功但按姓名匹配的业务查不到 | 自动建号 display_name 取的是钉钉昵称,可能与业务姓名不一致 → 人工校正 display_name(注意:重复登录只刷新 dingtalk_nick,不会覆盖人工校正) |
| `ping 域名` 通但浏览器打不开 | ping 走系统解析器,浏览器可能走 DoH 且把请求交给系统代理,两条路径完全不同。直接按"代理分流"排查:代理规则里给域名加 DIRECT |
| 同网段有人能登有人不能 | 服务端一般无网段策略;几乎总是**那台机器用的网址**或**那台机器的代理/DNS**差异。让同事报地址栏完整 URL + 跑排障脚本 |

## 万能判定顺序(任何"登录不了")

1. **源站日志里有没有那条请求?**(日志应带客户端 IP + Host)
   - 一条都没有 → 请求没到源站:客户端侧断了(DNS/代理/证书),按上表客户端类条目查;
   - 有,带 error → 按 error 码查上表;
   - 有且 200/302 正常 → 源站没问题,查客户端缓存/扩展/旧书签。
2. **看服务端日志的三个关键点**:`start 302`(发起)、`callback`(回调到达)、`exchange 200`(换 token 成功)。
   缺 callback = 钉钉侧拒绝或客户端没回来;有 callback 无 exchange = 前端没执行(看浏览器控制台)。
3. **区分"配置没生效"与"配置错了"**:凡动过钉钉后台 → 先确认**发布版本**;凡动过 systemd env →
   先确认 **daemon-reload**。这两步漏掉的概率远高于配置本身写错。

## 客户端排障脚本

`scripts/client-dns-check.ps1`(参数化通用版),在**出问题的那台机器**上跑:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File client-dns-check.ps1 -Domain <登录域名> -OriginIp <源站IP> [-Port 4322] [-Scheme https|http]
```

它逐项输出:各网卡 DNS、DHCP 下发 vs 手工、逐台解析器实测(含耗时,Chromium 用先返回者)、
系统代理与绕过列表、常见代理进程/端口监听(走代理 vs 直连对照)、系统 DNS 缓存、
源站连通性、IPv6 DNS、虚拟网卡、hosts、浏览器扩展风险扫描、无痕对照实验指引。

适用:路径 A(域名+拆分或公网解析指内网)场景;路径 B(裸 IP+HTTP)无 DNS 问题,
重点看脚本第 4 节(代理)与证书拦截页。公网部署(路径 C)一般只有代理/证书两类问题。

## 换密钥/改配置后的标准动作

| 改了什么 | 必须做什么 |
|---|---|
| 钉钉后台(回调域名/权限) | 点「发布版本」,再端到端验证一次 |
| systemd 单元/override/env 文件 | `daemon-reload` **再** `restart`(顺序不能反,只 restart 不重读单元) |
| 证书文件 | 重启服务;`openssl s_client -servername` 复验各域名;确认回源/相关链路仍正常 |
| Client Secret | 生产 env 与本地联调 env 是两个副本,都要改;改完用 accessToken 探测验证(dingtalk-side.md 有命令) |
