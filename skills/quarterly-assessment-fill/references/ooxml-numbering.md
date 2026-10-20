# 季度考核表 XML 编号机制与填写规则

季度考核表的"计划任务/完成情况"两列用 Word 自动编号（numbering.xml）。填错 numId 会破坏整表编号，是本流程最大的坑。改 XML 前先读懂本文件。

## 表内编号结构（以 2026 年第三季度杨凯丽表为例）

- **计划任务列**：每行第一段（"K4 V1.0项目："、"信息化建设工作："等大标题）全部用同一个 `numId=1`，指向 `abstractNumId=11`，格式 `%1.`，渲染为连续的 1. 2. 3. … 7.。行内子项各用一个独立 numId（格式 `(%1)`）。
- **完成情况列**：每行 C3 有一个空段落，pPr 自带 numPr（格式 `(%1)`）。注意不同行的空段落可能**共用同一个 numId**（如第 3、4 行共用 numId=5）——同一 numId 跨单元格会连续编号，第 4 行会从 (4) 开始。

## 铁律

1. **总述段绝不能复用表内已有 abstractNum 指向的 numId**。曾把总述段新建的 numId 指向计划任务列大标题的 abstractNum 并加 `startOverride=1`，结果 Word 里同一 abstractNum 的 startOverride 会重置整个序列的计数器，计划任务列的 1.~7. 被破坏成 1,2,2,2,…。
   **正确做法**：在 numbering.xml 新建一个全新的 `abstractNum`（定义复制自 `%1.` 格式那条：`numFmt=decimal`、`lvlText=%1.`、`ind left=425 hanging=425`，换一个未占用的 abstractNumId 和 nsid），**必须插在所有 `w:num` 元素之前**；再为每行总述建独立 numId 指向它，每个带 `<w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/></w:lvlOverride>`，这样每行总述都渲染为"1."且互不影响。

2. **每行分条用独立 numId**（编号递增的新 numId 指向该行原有 abstractNum，带 `startOverride=1`），保证每行分条从 (1) 重新开始，且不会与同表其他 numId 连号。

3. **不要动原有 numId 的引用对象**——只在待填单元格的空段落上改 numId；如果某原有 numId 从此不再被引用也没关系，留着不删。

## 新增段落模板

总述段（改现有空段落的 numId 并追加 run）：

```xml
<w:p>
  <w:pPr>
    <w:numPr><w:ilvl w:val="0"/><w:numId w:val="101"/></w:numPr>
    <w:spacing w:line="240" w:lineRule="auto"/>
    <w:ind w:firstLineChars="0"/>
    <w:rPr><w:rFonts w:ascii="楷体_GB2312" w:eastAsia="楷体_GB2312"/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>
  </w:pPr>
  <w:r>
    <w:rPr><w:rFonts w:hint="eastAsia" w:ascii="楷体_GB2312" w:hAnsi="Calibri" w:eastAsia="楷体_GB2312" w:cs="楷体_GB2312"/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>
    <w:t>完成，包括：</w:t>
  </w:r>
</w:p>
```

分条段落结构相同，numId 换成该行分条编号。run 的 rPr 从原表现有 run 原样复制（不同表字体可能不是楷体_GB2312，先看再抄）。

numbering.xml 新增（abstractNum 在前、num 在后）：

```xml
<w:abstractNum w:abstractNumId="20">
  <w:nsid w:val="7161D5F1"/><w:multiLevelType w:val="singleLevel"/><w:tmpl w:val="7161D5F1"/>
  <w:lvl w:ilvl="0" w:tentative="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/>
    <w:lvlJc w:val="left"/><w:pPr><w:ind w:left="425" w:hanging="425"/></w:pPr>
    <w:rPr><w:rFonts w:hint="default"/></w:rPr></w:lvl>
</w:abstractNum>
...
<w:num w:numId="101"><w:abstractNumId w:val="20"/>
  <w:lvlOverride w:ilvl="0"><w:startOverride w:val="1"/></w:lvlOverride></w:num>
```

## 工作作风 / 改革创新 / 总体评价

这三行是普通单元格（无编号）：工作作风、改革创新是单个空段落，直接追加 run；总体评价单元格内已有"取得成果：/成长进步：/亮点工作：/不足之处："四个段落，在每段**末尾追加 run**（内容跟在冒号后，不新起段落）。

## 验证手段

- 分析结构用 minidom 逐行打印每段 pPr 的 numId 与文本，确认待填位置。
- 渲染必须过 Word COM（`Fields.Update()` 后导 PDF），不要只看 XML——编号问题是渲染时才暴露的。
- 验收重点：计划任务列大标题 1.~7. 连续不乱、每行总述"1."、分条各行从 (1) 起、跨页时同行分条允许连续。
