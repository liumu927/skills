# 前端接入

模板:`assets/templates/frontend-dingtalk-login.js`(原生 JS,零依赖,已生产验证)。

## 三步接入

1. 登录页放容器(可放多个):
   ```html
   <div class="dingtalk-login-slot"></div>
   ```
2. 引入脚本(路径按项目调整,注意脚本顶部 `var API = '/api/auth'` 与服务端路由前缀一致):
   ```html
   <script src="/js/dingtalk-login.js"></script>
   ```
3. 完成。脚本行为:
   - 自动 `GET /api/auth/dingtalk/status` 探测;未配置时整块隐藏(不显示点不动的死按钮);
   - 已配置时渲染"或 / 钉钉扫码登录"按钮 + 错误提示框;
   - 点击 → `location.href = /api/auth/dingtalk/start?return_to=<当前路径+hash>`;
   - 页面带 `?dingtalk_code=xxx` 回跳时,自动 `POST /exchange` 换 token,
     写 `localStorage.token` / `localStorage.currentUser`(与密码登录同一套键),
     `history.replaceState` 清掉 URL 参数(防刷新重复消费),再跳回 return_to。

## 约定与可定制点

- localStorage 键名与密码登录一致(`token`/`currentUser`),现有鉴权拦截逻辑零改动。
- `window.DINGTALK_AFTER_LOGIN = '/xxx/'` 可覆盖默认登录落点。
- hash 路由的子平台 SPA 会动态插入 slot:模板用 MutationObserver 兜住,无需手工时机。
- 错误文案表(可按需汉化/扩展):
  | error 码 | 文案 |
  |---|---|
  | dingtalk_not_configured | 钉钉登录未配置,请联系管理员 |
  | dingtalk_no_code | 未获取到钉钉授权码,请重试 |
  | dingtalk_bad_state | 登录会话已过期(state 校验失败),请重试 |
  | dingtalk_no_openid | 未获取到钉钉用户标识,请重试 |
  | dingtalk_exchange_failed | 钉钉登录失败,请重试或改用账号密码登录 |

  兜底顺序:页面有 `#dingtalk-error` 显示在框内 → 否则调用全局 toast。

## 与服务端的分工边界

前端只做三件事:探测配置、发起跳转、用一次性码换 token。**一切身份判定都在服务端**;
前端拿到 token 后与密码登录走完全相同的后续路径,不解析、不信任 URL 里除一次性码外的任何参数。
