# 自建应用 + OAuth2.0 连接器

适用：连接器要调用钉钉开放平台 API（多维表 Notable 为主），需要平台自动换取/缓存/刷新 token。这是所有场景的共享基建，配一次，其余场景复用。

## 角色分工

- **自建应用** = 调用 API 的身份。三样东西：Client ID/Secret（凭证）、API 权限点、组织内登记（应用能力、重定向 URL、发布状态）。
- **连接器** = 动作封装 + 鉴权方式配置。
- 一个连接器的鉴权配置绑定一个应用；多个连接器可共用一个应用。换应用 = 换身份 = 重新过权限/文档访问/应用状态三道校验。

应用侧故障只查三道门：

1. 权限点是否开通、修改后是否发版；
2. 目标多维表是否对应用/组织可见（个人文档需共享）；
3. 应用是否已上线，Client Secret 是否被重置（重置即所有凭证失效，需重新授权）。

## 前置条件

- [ ] 开发者后台（open-dev.dingtalk.com）开发者权限
- [ ] 目标 AI 表格文档已建好，含目标数据表和字段
- [ ] 文档对组织可见（个人文档需共享，否则 403）
- [ ] 知道目标表的 baseId；表 ID 建议通过 `GET /sheets` 获取
- [ ] 一个操作人 unionId 作为 `operatorId`（用"查询用户详情"查，固定服务身份）

## 阶段 A：创建自建应用

1. 开发者后台 → 应用开发 → 创建应用。
2. 权限管理：开通 `Notable.Base.Read.All`（读），需要写表时加 `Notable.Base.Write.All` 或对应写权限。
3. 添加应用能力 → 网页应用（首页地址可先占位，如 `https://www.dingtalk.com`）。
4. 安全设置 → 重定向 URL：填连接平台鉴权设置第 2 步生成的授权回调地址。**连接器重建/鉴权重置后回调地址会重新生成**，必须回来同步成最新值。
5. 版本管理与发布：创建新版本并发布。**任何修改必须发版才生效。**

## 阶段 B：创建自建连接器 + OAuth2.0 鉴权

入口：开发者后台 → 开放能力 → 连接平台 → 我的连接器 → 创建连接器。

### B1 基本信息

- 名称/描述随意。
- "关联应用"下拉若显示"暂无数据"是平台 bug，**不用管**——用 OAuth2.0 凭证方案绕过。
- 高级设置全部关闭，尤其"动态出参"（开了表单无法映射出参）。

### B2 鉴权设置：OAuth2.0 五步向导

| 步骤 | 配置 |
|---|---|
| 1 鉴权字段 | 不填，直接下一步 |
| 2 OAuth 授权参数 | Client ID、Client Secret；**复制页面自动生成的授权回调地址** |
| 3 OAuth 接口参数 | 见下表三接口 |
| 4 鉴权请求参数 | HTTP 请求头：key=`x-acs-dingtalk-access-token`，值=`$.Body.accessToken` |
| 5 鉴权调试 | 填真实只读接口 → 添加账户 → 钉钉授权页登录/选组织/同意 → 凭证出现 → 选账户 → 鉴权调试 200 |

第 3 步三接口：

| 接口 | 方式 | 地址 | 参数 |
|---|---|---|---|
| 授权接口（必填） | GET | `https://login.dingtalk.com/oauth2/auth`（裸地址） | **URL 查询参数**网格逐行填：`redirect_uri`=回调**裸**地址；`response_type`=code；`client_id`=<ClientID>；`scope`=openid corpid；`prompt`=consent（可选） |
| 获取 Token（必填） | POST | `https://api.dingtalk.com/v1.0/oauth2/accessToken` | **HTTP 请求体**两行：`appKey`=<ClientID>；`appSecret`=<Secret> |
| 刷新 Token | POST | 同上 | 同上两行，必须同样放在**HTTP 请求体**分类下；两接口都补请求头 `Content-Type: application/json` |

自动刷新配置：勾选开启；周期 `5400` 秒（须小于 token 有效期 7200）；失效判断：系统字段/Http 状态码/等于 `400`，再点"+"加一条 `401`（钉钉过期 token 返回 401 ExpiredAccessToken）。

关键规则：

- 授权接口参数必须齐全（client_id/redirect_uri/response_type/scope）。只填裸地址不带参数会报 `client_id is blank`。
- 编码规则二选一，别混用：网格填法 → `redirect_uri` 填裸地址，编码交给平台；内联写法 → 手动预编码。预编码后再走网格 = 双重编码。
- 刷新 Token 的 `appKey/appSecret` 误放到"请求头"分类，会表现为"刚配完好一阵、一到刷新就持续报 appKey is mandatory"。

### B3 执行动作

以读多维表为例：

- 类型 HTTP，方式 POST。
- 接口路径：`https://api.dingtalk.com/v1.0/notable/bases/{baseId}/sheets/{sheetIdOrName}/records/list`
- URL 路径参数：`baseId`（必填）、`sheetIdOrName`（必填，用表 ID 避免中文编码问题）
- URL 查询参数：`operatorId`（必填，操作人 unionId）
- HTTP 请求体：`maxResults`（Integer，≤100）。需要筛选时加 `filter`（结构见 `04-connection-flow.md`）。
- **HTTP 请求头保持空**——token 由凭证自动注入，手动加必填头会导致表单要求填 token 并与自动注入冲突。
- 出参：点"导入 json"粘贴真实响应示例，字段名必须是表里真实存在的；调用成功规范 = HTTP 200；出参映射开关保持关闭。

出参 json 示例：

```json
{"records":[{"id":"abc123","fields":{"项目名称":"示例项目"}}],"hasMore":false,"nextCursor":""}
```

调试：选账户 → 填参数 → 返回 200 + 数据 → **保存并发布动作和连接器**。

推荐先用无中文的鉴权调试接口：

```
GET https://api.dingtalk.com/v1.0/notable/bases/<baseId>/sheets?operatorId=<unionId>
```

返回 200 并列出数据表（含表 ID），后续用表 ID 代替中文表名。

### 写操作动作

- 新增记录：`POST .../v1.0/notable/bases/{baseId}/sheets/{sheetIdOrName}/records`
- 更新记录：`PUT .../records`（按记录 ID）
- 入参映射：`operatorId ← root.unionId` 之类，别写死；`records → 子项 → fields(object)`，键=表格列头。

## 发布链

连接器动作保存并发布 → 连接器发布 → 审批模板重新发布（若绑了表单/流程）。只发一半等于没改。

改鉴权配置后：临时把刷新周期调到 300 秒，观察执行记录连续 2~3 次自动刷新成功，再调回 5400。

## 本场景独有踩坑

| 现象 | 原因 | 解决 |
|---|---|---|
| 授权页 `client_id is blank` | 授权接口只有裸地址，没配查询参数 | 地址填裸地址，参数在 URL 查询参数网格逐行填 |
| 授权页 `应用不存在`(900103) | 无网页应用能力/回调未登记/未发版 | 加网页应用能力 + 登记回调 + 发版 |
| 授权页 redirect_uri 错误 | 网格里填了预编码值，平台又编码一次 | 改填裸地址 |
| Token 接口 `MissingappKey: appKey is mandatory` | 钉钉只认 JSON body，平台默认未按 JSON 发 | 获取/刷新接口各加 `Content-Type: application/json` |
| `fetch_token_result_not_mapping_config`，刚配完正常、过段时间起持续报 | 刷新 Token 的 appKey/appSecret 误填在请求头，刷新路径请求体为空 | 两行移回请求体 + Content-Type → 发布 → 小周期验证 |
| 配完就报/重新授权也报同样的错 | 连接平台回调地址变了，与应用安全设置不一致 | 复制第 2 步最新回调 → 更新应用重定向 URL → 发版 → 重新添加账户 |
| 保存鉴权提示"较大变动"后凭证变灰 | 平台机制：鉴权大改会把已授权账户标记为待更新 | 点凭证旁"更新账户"重新授权；弹窗被拦截就在自己浏览器打开授权链接 |
| 授权回调页 `ERR_NAME_NOT_RESOLVED` | 内置浏览器 DNS 抖动，授权码已送达 | 不影响结果；刷新连接器页检查凭证状态 |
| 关联应用下拉"暂无数据" | 平台 bug | 用 OAuth2.0 凭证方案，不依赖关联应用 |
| 改配置后行错位、值丢失 | 向导频繁重渲染，按索引填值会串行 | 每次修改后按行回读校验；必要时刷新页面重来 |

## 换需求复用

- 换表/换字段：改动作的 baseId/表 ID + 重新导入出参 json + 改表单映射。
- 换外部系统（非钉钉表）：OAuth2.0 向导通用——按对方文档配三个接口 + 失效判断 + 请求头注入。
- 目标系统有官方连接器且出参带展示字段时，优先用官方，别自建。
- 关联应用 bug 修复后可改回"关联应用 + 应用托管 token"标准形态；现有凭证方案稳定则非必要不动。
