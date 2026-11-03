---
name: dingtalk-integration
description: >-
  钉钉审批与自有系统之间的整条链路：多维表数据接进审批表单（动态下拉/回显/按项目派单）、
  审批通过后把表单数据接出（触发时机与触发机制选择）、连接器 OAuth2.0 与自建应用鉴权、
  连接平台连接流编排、腾讯云边界中间件的两种形态（透明转发+OpenVPN / 落盘+办公网主动拉取）、
  办公网内网系统接入，以及网页系统接入钉钉扫码登录/工作台免登。
  当用户提到：钉钉审批表单选项读多维表、连接器、连接流、AI表格自动化、审批节点按负责人派单、
  审批数据同步到自有系统、腾讯云中间件/边缘服务器/nginx/relay/OpenVPN/断链补偿/数据落盘拉取、
  unionId 与 userId 转换、钉钉扫码登录、免登、redirect_uri 参数错误、应用不存在 900103、
  回调 404，或贴出钉钉报错（permission deny、fail to find field、fields_error、
  fetch_token_result_not_mapping_config、conditions 相关错误）时使用。
  不用于机器人、小程序开发、审批 OpenAPI 直调的事件订阅开发本身。
---

# 钉钉审批 ↔ 自有系统整条链路

这是一套**配置陪跑 + 排错诊断**的知识包，不是让 Agent 直接操作钉钉后台。钉钉开发者后台、连接平台、OA 审批后台、AI 表格自动化、云服务器都是 GUI / 命令行，操作由用户完成；Agent 负责选型、给逐项配置值、生成表达式/JSON/契约、核对配置、按报错定位。每一步都要说清"在哪个后台点什么"。

## 第零步：分诊

先定位到"段"，只读那一段。**不要一上来把 references 全读一遍。**

| 我要做的事 | 段 | 读 |
|---|---|---|
| 表单选项要从多维表动态读 / 选完自动回显表里字段 | S2 | [02-aitable-into-form.md](references/02-aitable-into-form.md) |
| 审批节点要按表里的项目负责人自动派单 | S2 | 同上（§流程派单两段式） |
| 表里只有 unionId，但表单/节点要 userId | S2 | 02 §人员标识回填 + [04b](references/04b-aitable-automation.md) |
| 审批通过后要把数据取出来 / 不知道什么时候取、怎么触发 | S3 | [03-form-data-out.md](references/03-form-data-out.md) |
| 要循环、条件分支、逐条判重写回 | S4 | [04-connection-flow.md](references/04-connection-flow.md) |
| 表里 unionId 批量换 userId（定时批处理） | S4 | [04b-aitable-automation.md](references/04b-aitable-automation.md) |
| 数据要出钉钉 → 腾讯云中间件 → 办公网自有系统 | S5/S6 | [05](references/05-edge-middleware.md) + [06](references/06-office-lan-pull.md) |
| 现在走 OpenVPN 转发，想改成落盘+内网拉取 | S5/S6 | [11-migration-push-to-pull.md](references/11-migration-push-to-pull.md) |
| **落盘方案能不能过合规**（数据留在公网服务器） | S0 | [12-compliance-gate.md](references/12-compliance-gate.md) |
| 网页系统要接钉钉扫码登录 / 免登 / SSO | S7 | [07-login.md](references/07-login.md) |
| 已经配了但报错/数据不对 | — | [09-troubleshooting.md](references/09-troubleshooting.md) |
| 不确定整条链路怎么搭、为什么这么设计 | S0 | [00-pipeline.md](references/00-pipeline.md) |

涉及"这个位置要哪套 ID、字段值长什么样、时间为什么 +1 天"→ [08-data-model.md](references/08-data-model.md)。需要**填空用的参数模板**（每项从哪取、怎么验证）→ [10-project-instance.md](references/10-project-instance.md)（脱敏，可外发）；本组织**已实测的真实值**在 [10b-instance-values.md](references/10b-instance-values.md)（含内部域名/ID，勿外发）。

## 六段流水线

```
S0 决策：两条数据流向、四套鉴权、边界形态（推送 or 拉取）
S1 基建：企业内部应用 + 连接器鉴权 + 发布链（配一次，全程复用）
        │
        ▼
S2 多维表 ──连接器──▶ S3/S4 表单与审批 ──HTTP 节点/连接流──▶ S5 边界中间件 ──▶ S6 办公网系统
   ▲   (表单级/流程级)         │                              腾讯云              内网
   │                           │                          转发(legacy) or 落盘   主动拉取
   └────────── 反写：userId 回填 / 状态回填 ◀──────────────────────┘

S7 钉钉登录：用户身份侧，与上面数据链路正交（用独立应用，别复用审批应用）
```

一句话分工：**S2 是"表 → 表单"，S3/S4 是"表单 → 外面"，S5 是安检口与暂存地，S6 是数据真正落地的地方，S7 管"人怎么进来"。**

## 跨场景铁律（每条都对应真实事故）

1. **发布链**：连接器动作 → 保存并发布动作 → 发布连接器 → 审批模板重新发布。任缺一环都不生效。AI 表格自动化流程例外（改完即生效）。
2. **连接流用创建时的快照**：连接器动作/请求头改完，只重新发布动作不够，**必须重建连接流**才用新配置——"调试成功、真实触发还是旧地址"就是这个。
3. **出参必须自己声明**。官方 AI 表格连接器不暴露字段值（只有记录 ID/是否更多/游标）；要在表单回填就得自建 HTTP 连接器，用真实响应 JSON 导入出参。
4. **表单下拉两行映射缺一不可**：`值列表 ← 字段值数组`、`ID列表 ← 记录 ID 数组`，长度一致。
5. **数组映射要取下标**：`records` 是数组、文本控件是标量，映射 `records[0].fields.xxx`。
6. **编码禁止手抄**。审批字段编码（`TextField_xxx`）随模板走，删控件/复制模板都会变。从"执行详情 → 入参 → 复制 JSON"照抄；不截图 OCR、不用中文显示名当键。
7. **循环内容选整条记录**（含 `id`），循环体内引用"当前循环项"。选到 `.字段` 那层会退化成反复处理第一条（全绿无报错）。
8. **`conditions` 是顶层数组**，子项 `{field, operator, value}`，`value` 必须非空数组。多套一层 object 报 JSON Array parsing error。
9. **写表时 `fields` 的键 = 表格列头**，一字不差；参数名只能出现在值里。人员列直连 API 用 `[{"unionId":"..."}]`；下拉取 `.label`；日期 `LEFT(时间,10)` 存文本列。
10. **两套 ID 各管一段**：表单联系人控件与审批节点要 **userId**；多维表人员列与 `operatorId` 要 **unionId**。表单级绑定不能链式调用，转换只能落到文本控件由流程节点做，或提前把 userId 写进表。
11. **`operatorId` 是服务身份**，不是当前用户。固定一个长期不动的账号的 unionId 即正确设计。
12. **边界只认幂等键**：进中间件的每条数据都必须带 `external_id`（用**审批实例 ID**），重推/重放/重试一律靠它去重。没有幂等键的推送方案迟早产生重复数据。
13. **同步转发 vs 异步落盘，选一个并写进文档**。透明转发（隧道常连、请求同步穿透到内网）耦合重、钉钉侧超时约 5s；落盘+拉取把"接住"和"处理"解耦，是新项目默认。**不要两种混着用却没有明确哪条是主路径**。
14. **登录与审批用不同应用**：审批链路的 HTTP 节点不需要钉钉应用凭据（静态令牌即可）；登录只开「登录」能力。轮换登录密钥不打断审批，反之亦然。

## 两种边界形态（一句话选型）

| | 形态 A：透明转发（现状/legacy） | 形态 B：落盘 + 拉取（目标/推荐） |
|---|---|---|
| 链路 | 钉钉 → nginx → relay → OpenVPN → 内网应用 | 钉钉 → nginx → 中间件落盘 → 内网应用**出站拉取** |
| 成功语义 | 内网应用真的处理完才 200 | 中间件落盘即 200，处理另算 |
| 依赖 | VPN 常连（断则全线停） | 内网能出站 HTTPS 即可 |
| 补偿 | 仅断链期内存/落盘队列 | 天然可重放、可对账、可审计 |
| 适用 | 已上线、不想动钉钉侧 | 新系统、或要甩掉 VPN 数据面 |

细节与迁移路径见 [05](references/05-edge-middleware.md)、[06](references/06-office-lan-pull.md)、[11](references/11-migration-push-to-pull.md)。

## 工作方式

**新建配置时**：①用分诊表定位段 → ②先列前置条件清单（应用权限/表权限/控件/发布状态/域名/服务器），缺什么让用户先补 → ③按手册逐阶段给值，每步说明"哪个后台、哪个菜单、填什么、容易错在哪" → ④每阶段让用户先验证（动作调试 200 / 表单回显有值 / 循环 index 跑满 / curl 打中间件 200）→ ⑤按该篇末尾验证清单收尾。

**排错时**：①先查 [09-troubleshooting.md](references/09-troubleshooting.md)，按现象查不凭印象 → ②先要三样之一：完整报错文本、执行详情"复制"的入参 JSON、配置页截图；没有就先要 → ③按"现象 → 原因 → 验证 → 解决"给结论，一次只改一个变量 → ④改完提醒走发布链/重建连接流，再复测。

**调试三板斧**：复制 JSON（拿权威键名）· 切换循环执行次数（两轮入参该不同）· 二分定位（只留嫌疑字段跑一轮）。

## 边界

不覆盖：机器人、小程序、审批 OpenAPI / 事件订阅接口本身的开发、钉钉后台组织架构管理、OpenVPN 服务端与 nginx 的通用运维教学（本包只给与本链路相关的配置要点与坑）。

## 文件索引

| 文件 | 内容 |
|---|---|
| `00-pipeline.md` | 全景、六段职责、三套鉴权对照、ADR 决策记录、风险登记 |
| `01-app-and-connector-auth.md` | 自建应用、连接器 OAuth2.0 五步、HTTP 动作、发布链、三套身份区别 |
| `02-aitable-into-form.md` | 多维表→表单：动态下拉、字段回显、流程派单两段式、人员 userId 回填 |
| `03-form-data-out.md` | 取数：四种触发机制对比、取到什么、何时最可靠、落点选择 |
| `04-connection-flow.md` | 连接流：循环、条件分支、明细取值、判重更新、表达式与 19 条坑 |
| `04b-aitable-automation.md` | AI 表格自动化：定时批处理、unionId→userId 回写 |
| `05-edge-middleware.md` | 边界中间件：形态 A 转发（备案/解析/证书/补偿）、形态 B 落盘拉取、鉴权与幂等 |
| `06-office-lan-pull.md` | 办公网拉取接入：租约+ack、游标、失败语义、调度方式选型、监控 |
| `07-login.md` | 钉钉登录总纲：四路径分诊、主流程、账号模型红线 |
| `07a-login-intranet.md` | 内网三条入口路径（0/A/B）与存量系统约束 |
| `07b-login-public.md` | 公网部署（未实测骨架） |
| `07c-login-server.md` | 服务端四端点实现、安全机制、验证清单 |
| `07d-login-frontend.md` | 前端接入脚本与错误文案 |
| `08-data-model.md` | userId/unionId/operatorId、多维表 API、字段值形态、时间假 Z |
| `09-troubleshooting.md` | 合并排错总表（配置类 + 登录类）与决策树 |
| `10-project-instance.md` | 实例参数**填空模板**（占位符 + 从哪取 + 怎么验证），脱敏可外发 |
| `10b-instance-values.md` | 本组织**真实实例值**（内部域名/表 ID/unionId/IP），勿外发 |
| `11-migration-push-to-pull.md` | 转发→落盘拉取迁移 runbook、双通道灰度、回退 |
| `12-compliance-gate.md` | **合规闸门**：落盘前的五问、三种结论与预案（含字段级加密绕行）、评审清单与签字表 |
| `assets/deploy/` | **可执行部署骨架**：relay 参考实现、puller、nginx、systemd、.env.example、Postgres schema（已冒烟自测） |
| `assets/templates/` | 登录三件套模板（服务端协议、路由、前端） |
| `scripts/client-dns-check.ps1` | 登录客户端 DNS/代理逐通道排障脚本 |

## 沿革（2026-11 两包合并）

原 `dingtalk-integration` + `dingtalk-login` 合并为本包，按流水线段重组。旧路径对照（供老笔记/老链接换算）：

| 旧文件 | 新位置 |
|---|---|
| `dingtalk-integration/01-connector-oauth2.md` | `01-app-and-connector-auth.md` |
| `dingtalk-integration/02-approval-form.md` | `02-aitable-into-form.md` |
| `dingtalk-integration/03-approval-process.md` | 并入 `02-aitable-into-form.md`（§流程派单） |
| `dingtalk-integration/04-connection-flow.md` | 不变 |
| `dingtalk-integration/05-aitable-automation.md` | `04b-aitable-automation.md` |
| `dingtalk-integration/06-data-model.md` | `08-data-model.md` |
| `dingtalk-integration/07-troubleshooting.md` | `09-troubleshooting.md`（并入登录类） |
| `dingtalk-integration/08-project-instance.md` | `10-project-instance.md` |
| `dingtalk-integration/09-http-callback-edge-relay.md` | `05-edge-middleware.md`（保留形态 A，新增形态 B） |
| `dingtalk-login/SKILL.md` | `07-login.md` |
| `dingtalk-login/references/dingtalk-side.md` | 并入 `07-login.md` §第 1 步 |
| `dingtalk-login/references/scenario-intranet.md` | `07a-login-intranet.md` |
| `dingtalk-login/references/scenario-public.md` | `07b-login-public.md` |
| `dingtalk-login/references/server-impl.md` | `07c-login-server.md` |
| `dingtalk-login/references/frontend-impl.md` | `07d-login-frontend.md` |
| `dingtalk-login/references/troubleshooting.md` | 并入 `09-troubleshooting.md` §登录类 |
| `dingtalk-login/assets/*`、`scripts/*` | 原样移到本包 `assets/`、`scripts/` |

新增：`00-pipeline.md`、`03-form-data-out.md`、`06-office-lan-pull.md`、`11-migration-push-to-pull.md`。
