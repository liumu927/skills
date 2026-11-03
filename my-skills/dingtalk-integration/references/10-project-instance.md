# 10 实例参数模板（脱敏，可外发）

这是**填空模板**：把 `<...>` 换成你的值即可。真实填写后的值请放到 `10b-instance-values.md`（内部文件，勿外发），不要把实值写回本文件——这样整个 skill 包可以安全地给同事、进公开仓库。

每个值都标了**从哪取**和**怎么验证**，避免"抄了一个不知道对不对的 ID"。

## 一、钉钉应用与连接器

| 项 | 占位符 | 从哪取 | 怎么验证 |
|---|---|---|---|
| 自建应用名 | `<app-name>` | 开发者后台应用列表 | — |
| Client ID（AppKey） | `<client-id>` | 应用详情 → 凭证 | 连接器鉴权调试 200 |
| Client Secret | **不落文件** | 凭证页/密码管理器 | `accessToken` 探测 200 |
| 应用权限点 | `<permissions>` | 应用 → 权限管理 | 读表 200 即证明 |
| 应用能力 | 网页应用（占位首页可） | 应用 → 添加应用能力 | 授权页不报 900103 |
| 连接器名 | `<connector-name>` | 连接平台 → 我的连接器 | 动作调试 200 |
| 连接器 ID | `<connector-id>` | 连接器详情页 | — |
| 鉴权方式 | OAuth2.0 凭证 | 连接器 → 鉴权设置 | 凭证状态非"待更新" |
| 授权回调地址 | `<connector-callback>` | 鉴权设置第 2 步自动生成 | 与应用「重定向 URL」一致 |
| Token 刷新周期 | `5400` 秒 | 鉴权设置 | 临时调 300 秒连刷 2–3 次成功 |

## 二、多维表

| 项 | 占位符 | 从哪取 | 怎么验证 |
|---|---|---|---|
| baseId | `<base-id>` | 表链接 / 文档信息面板 | `GET /sheets` 200 |
| 数据表 ID（优先） | `<sheet-id>` | `GET /sheets` 返回的短 ID | 用它替代中文表名 |
| 数据表名 | `<sheet-name>` | 表标签页 | 仅备查 |
| `operatorId`（unionId） | `<operator-union-id>` | 「查询用户详情」按人查 | 读表 200 |
| 表格列头（`fields` 键） | `<col-a>, <col-b>` | 表列标题 | 写入 200 无 `fail to find field` |
| 人员列 | `<person-col>` | 表列 | 写入用 `[{"unionId":"..."}]` |

## 三、审批模板

| 项 | 占位符 | 从哪取 | 怎么验证 |
|---|---|---|---|
| 审批模板名 | `<template-name>` | OA 审批后台 | — |
| 字段编码（每控件一个） | `TextField_<...>` 等 | **执行详情 → 入参 → 复制 JSON** | 表单回显/写入有值 |
| 明细控件编码 | `<detail-field-code>` | 同上 | 循环能取到数组 |
| 审批实例 ID 字段 | `external_id` ← 审批实例 ID | 流程节点变量 | 重复推送 `duplicate:true` |

> 编码**禁止手抄/OCR**：删控件、复制模板都会换编码，每次从执行入参 JSON 复制。

## 四、边界中间件（形态 B；形态 A 见 05 §2）

| 项 | 占位符 | 从哪取 | 怎么验证 |
|---|---|---|---|
| 回调域名 | `<domain>` | 你自己的 DNS | `dig +short <domain>` |
| 公网 IP | `<edge-ip>` | 云控制台 | `curl --resolve` 通 |
| consumer 名 | `<system>-<env>` | 自定义，如 `<system>-prod` | 与 env 里键一致 |
| 边缘令牌 | `<edge-token>` | `openssl rand -hex 24` | 入库 200；错令牌 401 |
| 消费方令牌 | `<consumer-token>` | 同上，**换一个** | 拉取 200；错令牌 401 |
| admin 令牌 | `<admin-token>` | 同上，**再换一个** | `/api/admin/stats` 200 |
| 数据目录 | `/var/lib/dingtalk-relay` | `.env` `DATA_DIR` | `ls` 有 `messages.log` |
| 保留期 | `<n>` 天 | `.env` `RETENTION_DAYS` | 到期后 `delivered` 被清 |
| 证书 | `<domain>.fullchain.pem` | 云证书/DV | `openssl s_client` 链完整 |
| 内网出口 | 放行 443 → `<domain>` | 防火墙策略 | 内网 `curl https://<domain>/healthz` |
| 内网系统地址 | `http://<nuc-ip>:<port>` | 内网固定 IP | 本机 curl 通 |
| 内网落库表/路径 | `<local-store>` | 你的系统 | 条数与 `delivered` 一致 |

## 五、登录（若一并接入）

| 项 | 占位符 | 从哪取 | 怎么验证 |
|---|---|---|---|
| 登录应用 Client ID/Secret | `<login-client-id>` / `<login-secret>` | 开放平台（**与审批应用分开**） | `/diag` 配置齐全 |
| 重定向 URL | `<https://domain/api/auth/dingtalk/callback>` | 登录与分享 | 与 `DINGTALK_REDIRECT_URI` 逐字符一致 |
| 权限 | `Contact.User.Read` | 权限管理 | 取用户信息 200 |
| 发布状态 | 已发布 | 版本管理 | 改完必须重发版 |
| DHCP 保留 | `<ip>` → `<mac>` | 路由器 | 重启后 IP 不变 |

## 六、填写顺序（有依赖，别乱序）

```
1 建自建应用 + 权限 + 网页应用能力
2 建连接器 → 拿到授权回调地址 → 回填到应用「重定向 URL」→ 发版
3 OAuth2.0 五步 + 添加账户 + 鉴权调试 200
4 取 baseId / sheetId / operatorId（GET /sheets、查询用户详情）
5 建执行动作 → 导入真实响应 JSON 声明出参 → 发布动作 + 发布连接器
6 审批模板加控件 → 配表单映射 / 流程节点 → 发版
7 跑一轮审批 → 从执行详情复制字段编码（此时才拿得到）
8 中间件：域名/证书/令牌 → 入库 + 拉取 + ack 三接口验证
9 钉钉 HTTP 节点指向中间件 → 重建连接流 → 端到端
10（可选）登录：另开子域 → 四端点 → 前端 → 端到端
```

## 七、换组织/换表时的替换清单

换一套环境时以下值**全部重取**，不要沿用：

1. Client ID/Secret + 权限点 + 发版
2. 连接器回调地址 → 应用「重定向 URL」→ 发版 → 重新添加账户
3. baseId、sheetId（`GET /sheets`）
4. `operatorId` 的 unionId
5. 审批模板全部字段编码（跑一轮取 JSON）
6. 表格列头名称
7. 中间件：域名/证书、三套令牌、consumer 名
8. 内网出口放行、内网系统地址
9. （若接登录）重定向 URL、`DINGTALK_REDIRECT_URI`、证书、DHCP 保留

## 八、验证"填对了"

不需要真实审批也能做的自检：

- [ ] 连接器动作调试页点一次 → 200 且返回真实字段（证明应用/权限/表对了）
- [ ] `curl --resolve` 打中间件 `/healthz` → `{"ok":true}`（证明域名/DNS/证书对了）
- [ ] 入库一条 → 重复一条 → `duplicate:true`（证明幂等键对了）
- [ ] 内网拉一次 → ack → `stats.delivered == 1`（证明三套令牌对了）
