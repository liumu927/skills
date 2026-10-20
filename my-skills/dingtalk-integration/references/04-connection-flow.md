# 连接流：循环、判重、写 AI 表格

适用：审批通过后，把审批明细表格控件里的每一行逐条写进 AI 表格，并按某个键判重——已存在则更新该行，不存在则新增。也适用于任何"循环内多次调用连接器"的场景。

前置：`01-connector-oauth2.md` 的基建 + 两个自定义连接器动作（单条新增、按键查询）已发布。

## 架构（以资产领用/变更为例）

**流程一：批量新增（领用单 → 逐条新增）**

```
1. 实例通过(高级版)时触发
   ↓ 出参.申领资产详情[*]（明细数组）
2. 根据userid获取用户unionId（通讯录）
3. 循环执行（循环内容 = 节点1:出参.申领资产详情[*]）
   └─ 4. 新增单条记录（自定义连接器 → AI表格 新增记录）
        入参 root{unionId, sn, assetsName, type, uniqueId}
        operatorId ← root.unionId；records→子项→fields(object)
        fields 四个子字段：key=表格列名，值←root.四字段
```

**流程二：判重更新（变更单 → 存在则更新）**

```
1. 实例通过(高级版)时触发
2. 获取单个审批实例详情（审批）
   ↓ 明细数组（接口原始返回是 rowValue 标签式，平台转成 keyed 对象）
3. 根据userid获取用户unionId（通讯录，供 ELSE 新增分支用）
4. 循环执行（循环内容 = 节点2 出参的明细数组[*]）
   ├─ 5. 按序列号查记录（自定义连接器 → records/list）
   │     入参 root{sn}；筛选 field=设备序列号, operator=equal, value=[root.sn]
   │     出参 root.records[].id
   ├─ 6. 根据userid获取用户unionId（循环体内！入参 userid ← 后使用人[0]）
   └─ 7. 条件分支：节点5出参.records[0].id 非空？
        ├─ 是 → 更新数据表多行记录（官方 v9）
        │        记录id ← 节点5.records[0].id
        │        fields = {'位置': ..., '使用人': [{'unionId': 节点6.unionId}]}
        └─ 否 → 新增（领用语义才保留；变更场景建议留空或告警）
```

一句话：**循环内容选整条明细；循环体内一律"本次循环数据 chip + 原始字段编码"取值；判重用"按键精确查询"直接拿记录 id；人员列传 unionId 对象数组；时间字段截前 10 位存文本列。**

## 键名与编码

**编码跟着审批模板控件走**：删控件重加、复制模板都会换编码。每次配置前先跑一轮，从"执行详情 → 入参 → 复制 JSON"照抄，禁止截图 OCR/手抄。

示例（仅为格式示意，实际以当前模板为准）：

| 表格列 | 表单字段 | 编码 | 值形态 |
|---|---|---|---|
| 设备序列号 | 产品序列号 | `TextField_1L08T4SNTE328` | 文本 |
| 规格型号 | 资产型号 | `TextField_31IT80NMT2S0` | 文本 |
| 唯一识别码 | 唯一识别码 | `TextField_1ESSHW5Y7VVGG` | 文本 |
| 资产名称 | 资产名称 | `TextField-K2AD4O5B` | 文本（含连字符） |
| 位置 | 后存放位置 | `DDSelectField_V97PQRFM2KG0` | 对象 `{label, value}` |
| 使用人 | 后使用人 | `InnerContactField_NUD2OJMLF400` | **数组** `["userId"]` |

新表单 = 全套新编码，必须重新拿。

## 取值表达式（连接流公式编辑器）

chip = 从变量树点选插入的蓝色变量，**禁止手打变量路径**。预览若原样回显表达式文本 = 没被求值。

| 用途 | 写法 |
|---|---|
| 下划线编码子字段 | `4.本次循环内容.本次循环数据.TextField_编码` |
| 连字符编码子字段 | `JACKSONJSONPATHEVAL(4.本次循环内容.本次循环数据,'$["TextField-K2AD4O5B"]')` |
| 下拉取显示值 | `JACKSONJSONPATHEVAL(4.本次循环内容.本次循环数据,'$.DDSelectField_编码.label')` |
| 联系人取第一个人 | `JACKSONJSONPATHEVAL(4.本次循环内容.本次循环数据,'$.InnerContactField_编码[0]')` |
| 人员列传值（直连 API） | `'使用人': [{'unionId': 流程参数.当前员工UserId}]` |
| 数组构造 | `LIST(元素)` 或 `[元素]` |
| 构造 fields 对象 | **单引号键**、压成一行 |
| 日期防 +1 天 | `LEFT(时间字段, 10)` → 存文本列 |

完整的"是"分支 fields 示例：

```
{'位置': JACKSONJSONPATHEVAL(4.本次循环内容.本次循环数据,'$.DDSelectField_V97PQRFM2KG0.label'),'使用人': [{'unionId': 流程参数.当前员工UserId}]}
```

## 两个连接器动作的配置基准

### 动作 1：新增单条记录

- 执行动作入参：`root{unionId, sn, assetsName, type, uniqueId}`
- API：`POST .../v1.0/notable/bases/{baseId}/sheets/{sheetIdOrName}/records`
- 映射：`baseId / sheetIdOrName ← 输入值`；`operatorId ← root.unionId`（**别写死**）；`records→子项→fields(object)→{列名: ←root.四字段}`

### 动作 2：按键查记录

- 执行动作入参：`root{sn}`
- API：`POST .../v1.0/notable/bases/{baseId}/sheets/{sheetIdOrName}/records/list`
- API 入参结构（**层级必须与接口一致，conditions 是顶层数组**）：

```
root (object)
├─ maxResults (number)
└─ filter (object)
   ├─ combination (string)          ← "and"
   └─ conditions (array)            ← 必须是 array，不能 object 套 Items
      └─ 子项 (object)
         ├─ field    (string)       ← "设备序列号"（表格列名）
         ├─ operator (string)       ← "equal"
         └─ value    (array)        ← 子项[0] ← root.sn（必须非空数组）
```

- 出参：`root.records[].id`（+fields，按需声明）
- **入参映射开关打开后，映射规则必须配齐**；调试页"API 入参结果"显示真正发出的请求体，排查就靠它。

为什么不"拉全量序列号在流程里比对"：列表里只有 SN 没有 recordId，集合比对难写。建"按键查记录"动作精确查询直接返回 id 更稳。

## 踩坑

| # | 现象 | 原因 | 解决 |
|---|---|---|---|
| 1 | 循环跑 N 次，写的都是第一条明细 | 循环体内引用了上游数组而不是循环项 | 引用"本次循环数据"+ 原始编码；切换"循环执行次数"看入参是否变化 |
| 2 | 表里出现多条同样数据；或一格塞进数组 | 引用了整个数组（`[*]`），数组语义是**聚合**，把所有值收进一个格子 | 逐条写入必须走循环项；聚合不是"差一步拆开" |
| 3 | "本次循环数据"展不开，只能选整个对象 | 循环项是无结构 object，不继承元素 schema | 整对象传给自定义连接器后端映射；或 chip+原始编码取子字段 |
| 4 | 表达式用中文显示名取值为空 | 运行时键是审批字段编码 | 一律用原始编码 |
| 5 | 编码抄错，不报错但该列为空 | 形近编码手抄/OCR 出错 | 复制入参 JSON 照抄；哪列空先核编码 |
| 6 | 流程侧配了入参，接口收到却缺字段（静默） | 自定义连接器开了"入参映射"但没配规则 | 开映射必须配齐；"莫名取空"先查这里 |
| 7 | `JSON Array parsing error` / InvalidConditions | `conditions` 声明成 object 多套了一层 Items | 改平：`conditions(array)→子项{field,operator,value(array)}` |
| 8 | `Missingfield: field is mandatory` | 结构改平后子项映射丢失 | 补齐三个映射；用调试页核对请求体 |
| 9 | `condition value should be an array` | 查询 sn 为空（新表单编码不同/取空） | 换当前表单真实编码 |
| 10 | `fail to find field 'TextField_xxx'` | fields 的键是审批编码，接口只认表格列名 | 键改列头，一字不差 |
| 11 | `fail to find field 'unionId'` | 键写成了参数名 | 键=列头，参数名只能出现在值里 |
| 12 | `fields_error`（人员列格式不正确） | 人员列传了裸字符串或字符串数组 | 用 `[{"unionId":"..."}]` 对象数组 |
| 13 | 人员格式对了还是不认 | unionId 与 userId 混用 | 直连 API 用 unionId 对象数组；官方连接器字段槽位填用户 ID 字符串 |
| 14 | 其余列都对，加一列后报错 | 新列值结构不对（下拉传整对象、日期传 ISO 串） | 下拉取 `.label`；日期截前 10 位；二分法定位 |
| 15 | 写入日期 +1 天 | 连接器时间是本地时间 + 假 Z 后缀，日期列按 UTC 解析 | `LEFT(,10)` 存文本列 |
| 16 | 下拉/联系人值没法直接用 | 下拉=`{label,value}` 对象；联系人=userId 数组 | `JACKSONJSONPATHEVAL` + JSONPath |
| 17 | fields 表达式整体退化成文本 | 对象键用了双引号或写成多行 | 单引号键、压一行；预览必须显示对象形态 |
| 18 | 循环内的转换节点删不删 | 循环外转"当前操作员工"（整单一次），循环内转"后使用人"（每条一次），语义不同 | 看下游还有没有引用；没人引用才删 |
| 19 | 循环内子节点调用费翻倍 | 循环内所有子节点均计量 | 判重查询无可避免；写入尽量精简；批量审批前评估计量 |

## 复用

- 换审批模板/表单：全部编码从新表单执行入参 JSON 重新拿。
- 换判重键：查询动作映射里 `field` 改目标列名 + sn 表达式换编码，动作重新发布。
- 多列更新：fields 表达式/映射子字段按列加，键=列头；人员列按对象数组格式。
- 无判重需求：砍掉查询+分支，保留"循环→新增"。
- 真正的批量 upsert（一次调用）：连接器需直连自有服务，后端收整组数组做查+判+写；直连 AI 表格 API 做不了，老老实实循环内判重。

## 调试三板斧

1. **复制 JSON**：执行详情 → 入参 → "复制"，拿权威键名与实际值。
2. **切换循环执行次数**：循环体内节点逐轮对比入参，两轮不同才对。
3. **二分定位**：fields 报格式错时只留嫌疑字段跑一轮。
