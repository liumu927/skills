# 服务端实现(OAuth2 授权码 + 自签 JWT)

模板:`assets/templates/dingtalk_login.js`(协议逻辑)+ `assets/templates/routes-dingtalk.js`(路由)。
两者已在内网生产环境完整验证,直接复制改造;依赖宿主提供 `./db`、`./middleware/auth`、`./password`
三个模块(见模板头部注释)。

## 端点规格(最小四条 + 两条推荐)

| 方法 | 路径 | 职责 |
|---|---|---|
| GET | `/dingtalk/status` | 是否已配置;前端据此决定显示不显示按钮(不泄露任何密钥内容) |
| GET | `/dingtalk/start` | 生成 state → 302 到 `https://login.dingtalk.com/oauth2/auth` |
| GET | `/dingtalk/callback` | 校验 state → 换 token → 取用户 → 账号关联 → 302 回前端带一次性码 |
| POST | `/dingtalk/exchange` | 一次性码换 `{token, user, return_to}` |
| POST | `/dingtalk/workbench` | 工作台免登(JSAPI authCode 直接换,跳过 302)——可选 |
| GET | `/dingtalk/diag` | 配置齐全性 + 到三个钉钉域名出站连通性探测——可选但强烈建议 |

## 钉钉 API 调用细节

```
授权地址  GET https://login.dingtalk.com/oauth2/auth
          ?redirect_uri=<DINGTALK_REDIRECT_URI>&response_type=code
          &client_id=<AppKey>&scope=openid&state=<state>&prompt=consent

换 token  POST https://api.dingtalk.com/v1.0/oauth2/userAccessToken
          {"clientId","clientSecret","code":<authCode>,"grantType":"authorization_code"}
          → { accessToken, expiresIn, refreshToken }

取用户    GET https://api.dingtalk.com/v1.0/contact/users/me
          header: x-acs-dingtalk-access-token: <userAccessToken>
          → { openId, unionId, nick, avatarUrl, mobile }
```

回调参数名钉钉两种都发过:`authCode` 与 `code`,两个都兼容读。

## 必须照抄的安全机制(每条都对应一个真实风险)

1. **state 防 CSRF**:随机 16 字节 hex,10 分钟 TTL,进程内存 Map,一次性消费(取出即删)。
   多实例部署换成共享存储(Redis)。
2. **开放重定向防护**:`return_to` 只接受站内相对路径——必须以 `/` 开头,且拒绝 `//` 和 `/\`
   开头(协议相对 URL)。回调时把 return_to 随一次性码带回前端。
3. **JWT 不进 URL**:callback 签发 JWT 后立即换成一次性码(随机 24 字节 hex,2 分钟 TTL,
   **取出即失效**),URL 里只出现一次性码——避免 JWT 进浏览器历史和访问日志。
4. **账号幂等**:唯一键 `dingtalk_open_id`(建唯一索引 `WHERE dingtalk_open_id IS NOT NULL`)。
   命中 → 只刷新 `dingtalk_nick`、`display_name` 仅在为空时补;未命中 → 建号。
   **绝不按姓名/手机号自动贴靠既有账号**(防"同名即接管")。
5. **自动建号最小权限**:角色默认 viewer(可配 `DINGTALK_DEFAULT_ROLE`,白名单校验);
   用户名 `dt_<openId过滤非字母数字后前10位>`,碰撞兜底加 `_n` 后缀;
   密码哈希用随机字节的哈希占位——"无人知道明文",等效不可密码登录;
   `auth_provider='dingtalk'` 落库。
6. **users 表迁移**(幂等,启动自动补齐):
   `ALTER TABLE users ADD COLUMN dingtalk_open_id/union_id/nick TEXT` + openId 唯一索引。

## 环境变量

| 变量 | 必填 | 说明 |
|---|---|---|
| `DINGTALK_CLIENT_ID` | 是 | AppKey |
| `DINGTALK_CLIENT_SECRET` | 是 | AppSecret,只走 env 文件注入 |
| `DINGTALK_REDIRECT_URI` | 是 | 回调地址,必须与钉钉登记条目匹配(见 dingtalk-side.md) |
| `DINGTALK_LANDING_URL` | 否 | 登录回跳落点,默认 `/` |
| `DINGTALK_DEFAULT_ROLE` | 否 | 首登建号角色,默认 viewer |

## 上线前验证清单(无真实钉钉凭据即可跑的断言)

对照以下断言自测(参考实现见仓库 scripts/dev-dingtalk-test.mjs 的写法——内存库 + 直接调用模块):

- [ ] 首次登录自动建号:角色=默认最低权限、username 以 `dt_` 开头、auth_provider=dingtalk
- [ ] 同 openId 重复登录不新建账号(幂等)、返回同一账号 id
- [ ] 重复登录不覆盖人工 display_name,只刷新 dingtalk_nick
- [ ] 不同 openId 建不同账号
- [ ] JWT 载荷含 id/username/role/display_name,可用本系统密钥验签
- [ ] 一次性码可换回 token/user/return_to,且只能用一次;伪造码无效
- [ ] state 首次校验通过且一次性(重放失败)、不匹配返回 null
- [ ] return_to 为绝对 URL / `//` 开头时被丢弃(开放重定向防护)
- [ ] 真机:`GET /diag` 配置齐全、三个钉钉域名出站 200/可达
- [ ] 真机端到端:走完一次登录;日志 `start 302 → callback → exchange 200`;二次登录复用账号

## 已知运维项

- state/一次性码在进程内存:重启只作废"进行中的登录",不影响已登录用户(JWT 自包含)。
- 首登建号的角色是最低权限,需要写权限的用户由管理员在账号管理里提权。
- 若系统有"按姓名匹配"的业务(如成果归属),提醒用户:钉钉昵称 ≠ display_name,
  建号时 display_name 取钉钉昵称,可能需要人工校正一次。
