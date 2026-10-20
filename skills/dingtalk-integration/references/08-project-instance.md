# 本项目实例参数

本文件记录已实测环境的具体值，便于在同一套钉钉组织内复用。**这些值只对当前组织有效**，换组织/换表一律重新获取。Client Secret 不落盘，使用时从开发者后台凭证页或密码管理器取。

## 项目数据（审批下拉 + 负责人路由）

| 项 | 值 |
|---|---|
| 自建应用 | 项目数据服务 |
| Client ID | `ding8vwz0di7edxrxmsl` |
| 关键权限点 | `Notable.Base.Read.All` |
| 应用能力 | 网页应用（首页可占位） |
| 连接器 | 获取项目名称列表（`G-CONN-103B54B327CB213ED4CB000K`） |
| 多维表 baseId | `pYLaezmVNe3zb6d2UKBKRvNeWrMqPxX6` |
| 数据表名 | `数据表` |
| **数据表 ID（推荐）** | `hERWDMS` |
| operatorId（unionId） | `qjNMZ4ANpODx0AykniirswQiEiE` |

已验证：

- 应用 token 调 `records/list` 读多维表：200
- 平台凭证自动换 token + 注入请求头：200
- 5400 秒自动刷新 + 400 兜底：已配置（建议补 401）
- 表单下拉动态选项 + 负责人回显 + 流程节点派单：全链路跑通
- 已知数据问题：项目名有重复（如"图形工作站"×2），需治理；重复名会影响下拉显示和派单正确性

## 资产领用/变更（连接流判重更新）

审批模板字段编码（**对应写作时模板，换模板必须重取**）：

| 表格列 | 表单字段 | 编码 |
|---|---|---|
| 设备序列号（领用单） | 产品序列号 | `TextField_1L08T4SNTE328` |
| 规格型号（领用单） | 资产型号 | `TextField_31IT80NMT2S0` |
| 唯一识别码（领用单） | 唯一识别码 | `TextField_1ESSHW5Y7VVGG` |
| 资产名称 | 资产名称 | `TextField-K2AD4O5B` |
| 设备序列号（变更单） | 产品序列号 | `TextField_1TW0Q7XAFFFK0` |
| 唯一识别码（变更单） | 唯一识别码 | `TextField_10FNEYF39M800` |
| 位置（变更单） | 后存放位置 | `DDSelectField_V97PQRFM2KG0` |
| 使用人（变更单） | 后使用人 | `InnerContactField_NUD2OJMLF400` |
| 前使用人 | — | `TextField_SWG0Q82YBAO0` |
| 前存放位置 | — | `DDSelectField_H5JBHE7M87K0` |

已验证：

- 循环内 chip + 原始编码取值：✅；中文显示名取值：❌
- `JACKSONJSONPATHEVAL` 处理连字符编码/数组下标/两级 label：✅
- 人员列直连 API `[{"unionId":...}]`：✅；裸字符串、字符串数组：❌
- `LIST()` 构造数组、单引号键对象字面量：✅
- 查询 `records/list` 的 `filter.conditions` 顶层数组 + `value` 非空数组：✅
- 时间 `2026-10-19T16:41Z` = 本地时间 16:41，跨零点写入 +1 天：❌ 直写日期列
- 自定义连接器开"入参映射"不配规则 → 参数静默丢失：✅ 实测
- 循环内子节点均计量，判重更新约每条明细 2~3 次调用：✅

## 成果审批管理（自动化回写 userid）

| 项 | 值 |
|---|---|
| 表 baseId | `GZLxjv9VGqmMZwOgHZ19Mxm186EDybno` |
| 表名 | `数据表` |
| 节点2 pageSize | 100 |
| 循环内容 | `节点2:结果.记录[*]` |
| 最大循环条数 | 100（界面默认，最多 500） |

已验证：

- 循环内容选 `记录[*]` + 体内引用循环当前项.id：✅ 每条依次回写
- 选 `记录[*].字段`：❌ 循环项无 id，退化为反复处理第一条（全节点绿、无报错）
- 循环出参 index 跑到 N-1 = 跑满 N 次：✅
- 通讯录连接器在自动化流程里同样可用：✅

## 复用时的替换清单

换组织或换表时，以下值必须全部重取，不要沿用：

1. Client ID / Secret + 应用权限 + 发版
2. 连接平台授权回调地址 → 应用到安全设置 → 发版
3. baseId、表 ID（用 `GET /sheets` 取）
4. operatorId 的 unionId
5. 审批模板的所有字段编码（跑一轮取执行入参 JSON）
6. 表格列头名称（`fields` 的键）
