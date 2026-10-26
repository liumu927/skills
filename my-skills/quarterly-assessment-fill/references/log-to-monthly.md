# 模式 B：按工作日志细化「月考核登记表」

月度表通常由系统预填"计划任务"列和评价员评语，**完成情况列的初稿往往是自动汇总的笼统话**（"部分完成，推进XX"）。业主真正要的是：把当月日志里干过的活拆到每个计划行下、按条目列清、带量化数字，让工作量看得见。

## 输入

| 输入 | 用途 | 缺失时 |
|---|---|---|
| 月考核登记表 docx | 目标文件；计划任务列已预填 | 必须提供，不猜路径 |
| Obsidian「待办导出-YYYY-MM.md」 | 事实来源（按日期分组、带勾选状态与子项层级） | 向业主要，或用当月月报/周报替代 |
| 工作区日志/工作总结（可选） | 计划行写不细时的补充（如 K4 这类项目的中期总结） | 日志够用就不找 |

日志用 `scripts/parse_todo_log.py` 解析成按日期分组的树，先通读再动笔。

### 补充材料：工作区里的「今日工作总结」

计划行写不细时（例：K4 那行只写得出"统一三条构建链"），工作区里常有一份按当天代码改动重建的工作总结，量化数据都在里面。它在 DSH 里是**一条会话**（标题即"今日工作总结"），不在文件系统里：

```bash
# 1) 找会话：workspace.json 里按 path 找工作区 → 其 sessionIds
python -c "import json;d=json.load(open(r'C:\Users\User\.dsh\storages\workspace.json',encoding='utf-8'));print(json.dumps(d['tables']['workspaces'],ensure_ascii=False)[:2000])"
# 2) 会话正文是 zstd 压缩的 jsonl，解压后取最后一条 assistant/message 的 text
python - <<'EOF'
import zstandard as zstd, json
p=r'C:\Users\User\.dsh\sessions\--E-project-k4-ui-refactor--\session-XXXX\session.v4.jsonl.zstd'
data=zstd.ZstdDecompressor().stream_reader(open(p,'rb')).read().decode('utf-8')
txt=''
for line in data.splitlines():
    o=json.loads(line)
    if o.get('type')=='assistant/message':
        for c in o['data']['message']['content']:
            if c.get('type')=='text': txt=c['text']
print(txt)
EOF
```

引用时只取其中的**量化结论**（测试例数、耗时对比、缺陷条数），不要整段搬进考核表。

### 补充材料：工作区会话里的「还没做完的活」（做模式 C 时必查）

生成下月计划前，光看任务清单不够——工作区会话里常留着"发现了但没修"的清单（例：K4 会话里一句"代码级问题，一个都没修"+优先级表，就是最好的下月素材）。做法：

```bash
# 1) 列出该工作区所有会话（目录名即 cwd 的转义）
ls "C:/Users/User/.dsh/sessions/--E-project-k4-ui-refactor--"
# 2) 逐个解压，抓两类证据
python - <<'EOF'
import json, zstandard as zstd, os, re
base=r'C:\Users\User\.dsh\sessions\--E-project-k4-ui-refactor--'
pat=re.compile(r'(待你决策|未做|遗留|待修复|没修|下一步|代办清单|待办)')
for d in sorted(os.listdir(base)):
    fp=os.path.join(base,d,'session.v4.jsonl.zstd')
    if not os.path.exists(fp): continue
    data=zstd.ZstdDecompressor().stream_reader(open(fp,'rb')).read().decode('utf-8')
    todos=[]
    for line in data.splitlines():
        o=json.loads(line)
        if o.get('type')=='assistant/message':
            for c in o['data']['message'].get('content',[]):
                if c.get('type')=='tool-call' and c.get('name')=='todo_write':
                    todos.append(json.loads(c.get('arguments','{}')))
                if c.get('type')=='text' and pat.search(c.get('text','')):
                    print('---', d); print(c['text'][:1500])
    if todos:  # todo_write 最后一份就是当前状态；只关心非 completed 的
        for it in todos[-1].get('todos',[]):
            if it.get('status')!='completed':
                print('[未完成]', it.get('content'))
EOF
```

读的时候注意区分三种状态：**清单里已 `completed`**（别再排）、**文字里说了"没修/待决策"**（该排）、**等别人**（如算法侧版本号、等业主点头的事项，别占计划行）。

## 铁律

1. **一行一事，不要把两件事并成一句**。计划任务列怎么分词，完成情况就怎么分段。
   典型坑：`推进资产管理信息可视化开发和「钉钉OA流程定制化开发」` 被写成一条 ——
   两者是**不同任务**，资产相关的 OA 审批只是实现"资产可视化"的一种手段：
   - 资产可视化行写**成果与数据链路**（审批数据 → 台账/多维表 → 看板可查），
   - 钉钉OA行写**工程实现**（表单、连接器、连接流）并**按对接的业务子系统分项**（资产台账、内部管理平台、在研表…）。
   两边都提资产不算重复：一边是"做成了什么"，一边是"怎么搭的"。
2. **勾选状态只作参考，口径是"考核截止日期之前"**。业主说"27 号之前的日志无论是否勾选都写进去，我这两天会做完"，就按完成写；但**措辞要留余地**（"已开展/已启动/已定位待修复"），别写"已验收"。
3. **不瞎编**。每条都要能在日志里找到出处；日志只写了"预算系统测试"，就别编出"输出测试报告、提 12 个缺陷"。
4. **量化优先**。能数字化的写数字（87→139 例、31.6ms vs 185.2ms、6 类审批、3 个构建链），这是"突出工作量"最省字的手段。
5. **未完成的行如实写**。计划有、日志无 → "本周期未开展相关工作"，并在总体评价里呼应；不要为了好看把"未完成"改成"推进中"。

## 写法

```text
完成，<一句总述（可含量化范围），按对接子系统分项落地：>
(1) <子系统A>：<做了什么、达成什么效果>
(2) <子系统B>：……
(3) ……
```

- 总述结尾用"："，分条用半角 `(1)` `(2)`（与原表既有写法一致）。
- 每条 40~70 字，一句话讲完"做了什么 + 结果"；**不要写成流水账**（"然后…然后…"）。
- 待收尾的单独放最后一条，用"尚待打通/已定位待修复/待后续完成"，不混进已完成条目。

## 排版（与季度表不同！）

月度表的完成情况列**没有 Word 自动编号**，实现方式和季度表正好相反：

- 每条**独立段落**，编号 `(1)` 直接写在文字里，不要新建 `numId`（月表往往只有一个 `numId` 给计划任务列的 1.~5. 用，动了必炸）。
- 段落格式从该单元格**原有首段/首个 run** 复制（本表是微软雅黑 sz=18，即 9pt，`color=000000`）。
- 以 `(` 开头的段落加**悬挂缩进** `left=170 hanging=170`，换行后与条目文字对齐；总述段不加。
- **列宽只有约 4.5cm**：一行放不下 14 个字，500 字就会占掉半页。单行控制在 300~550 字，整表页数不超过原表的 2 倍；写完必须渲染看页数，超标就删修饰词而不是删事实。
- 表格样式常是 `jc=both`（两端对齐），窄栏里会把中英混排的空格拉得很开。**中英文/数字之间不要留空格**（"139例""OA表单""userId版本"），比改对齐方式更安全。

## 绝对不能动

- 计划任务列（含自动编号 `1.~N.`）；
- 评价意见列的 Wingdings 2 勾选符号（`w:sym char=0052`=☑ / `00A3`=□）；
- 考核内容/评估要点/评分/总分四列（评语由评价人写）；
- 签字栏；**浮动签名图片**（`wp:anchor` + `wrapNone` 绝对偏移）在签名段里锚定，行高变化时它跟着走，删改签名段会丢签名。

## 验收清单

1. `fill_cells.py` 只改了目标单元格 —— 用单元格级哈希对比确认（见下）。
2. Word COM 渲染 → PNG 逐页看：分条编号连续、无截断、签名图片仍在签名行内、无跨页割裂的半行。
3. 页数在可接受范围（本例 2 页 → 4 页，最后一页只放考核结论区，属正常）。
4. 回写前查 `~$` 临时文件（共享盘/桌面都可能被 Word 占用），回写后 MD5 校验。

```bash
# 单元格级差异确认：只有目标单元格变了
python - <<'EOF'
import zipfile
from lxml import etree
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
q=lambda t:'{%s}%s'%(W,t)
def cells(p):
    root=etree.fromstring(zipfile.ZipFile(p).read('word/document.xml'))
    tbl=root.xpath('//w:tbl',namespaces={'w':W})[0]
    return {(ri,ci):etree.tostring(tc)
            for ri,tr in enumerate(tbl.findall(q('tr')))
            for ci,tc in enumerate(tr.findall(q('tc')))}
a,b=cells('work/原表备份.docx'),cells('work/output.docx')
print(sorted(k for k in a if a[k]!=b.get(k)))
EOF
```

## 本例参考（2026-10 表）

| 计划行 | 分条依据 | 条数 |
|---|---|---|
| k4项目：联调链路自动化测试 | 日志 10-22 "统一三条构建链"、10-23 "联调链路自动化测试体系落地/卡顿与状态失真根因修复/控制台重构" + 工作区工作总结里的量化数据（87→139、43→156、31.6ms vs 185.2ms） | 5 |
| 资产管理信息可视化 | 10-14~10-20 资产申领/变更/归还审批自动同步 + 10-23/26 钉钉数据摆渡调研 | 4（含 1 条尚待打通） |
| 预算管理系统测试 | 10-27 "预算系统测试"（未勾选，按业主口径计入） | 1 |
| 钉钉OA流程定制化 | 按对接子系统切 4 组：资产台账/多维表、内部管理平台、在研表、通用治理 | 4 |
| 其他计划外 | 内部管理平台建设、考核表系统、qr-ferry 三块 | 3 |
