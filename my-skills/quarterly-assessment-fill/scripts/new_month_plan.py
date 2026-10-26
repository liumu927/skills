# -*- coding: utf-8 -*-
"""以已填好的月考核登记表为模板，生成下个月的空白计划表。

用法:
    python new_month_plan.py <解包目录> <plan.json>

plan.json:
{
  "month": "2026.11",           # 考核月份单元格文本
  "tasks": ["k4项目：……", "信息化工作：……", "其他计划外任务。"],
  "date": "",                   # 签字行日期；留空则清空
  "clear_eval": true,           # 清空"考核内容/评估要点"里的评语
  "clear_signature": true,      # 去掉浮动签名图片与日期
  "keep_eval_block": true       # 考核结论块整体不跨页（默认 true）
}

做的事：
1. 考核月份 → month；
2. 计划任务行按 tasks 数量增删（克隆/删除行，保持 numId 自动编号 1.~N.）；
   克隆行会继承来源行的高 trHeight（原"计划外任务"行常是 1525），
   统一压回计划区间最小行高，否则清空内容后仍留一大片空白；
3. 计划任务列写入新任务（保留编号格式），完成情况列清空；
4. 评价意见列四项全部取消勾选（Wingdings 2 char 0052 → 00A3）；
5. 评估要点评语清空（那是上月评价，不能带到下月）；
6. 考核结论块加 cantSplit + keepNext，避免"考核内容"表头留在上页页脚；
   注意 keepNext 要下沉到单元格内的 w:p/w:pPr（段落嵌在 w:tc 里）；
7. 去掉签名图片、清空日期，留空白待签。

行定位不写死行号：靠"考核月份""计划任务/完成情况""考核内容""领导签字"这些
表头文本定位，换一张模板也能用。
"""
import json
import sys
from copy import deepcopy

from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W}
q = lambda t: '{%s}%s' % (W, t)
CHECKED, UNCHECKED = '0052', '00A3'  # Wingdings 2: ☑ / □


def para_text(p):
    return ''.join(t.text or '' for t in p.iter(q('t')))


def cell_text(tc):
    return ''.join(para_text(p) for p in tc.findall(q('p')))


def set_cell_text(tc, text):
    """保留首段 pPr（含 numPr/jc/字体），只换文字。"""
    paras = tc.findall(q('p'))
    if not paras:
        p = etree.SubElement(tc, q('p'))
        paras = [p]
    first = paras[0]
    for extra in paras[1:]:
        tc.remove(extra)
    runs = first.findall(q('r'))
    rPr = None
    if runs:
        r = runs[0].find(q('rPr'))
        rPr = deepcopy(r) if r is not None else None
    for r in runs:
        first.remove(r)
    for other in list(first):
        if other.tag not in (q('pPr'),):
            first.remove(other)
    if text:
        run = etree.SubElement(first, q('r'))
        if rPr is not None:
            run.append(rPr)
        t = etree.SubElement(run, q('t'))
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        t.text = text


def uncheck(tc):
    for sym in tc.iter(q('sym')):
        if sym.get(q('char')) == CHECKED:
            sym.set(q('char'), UNCHECKED)


def find_row(rows, *needles):
    for i, tr in enumerate(rows):
        txt = ''.join(cell_text(c) for c in tr.findall(q('tc')))
        if all(n in txt for n in needles):
            return i
    return -1


def build(unpack_dir, spec_path):
    doc = f'{unpack_dir.rstrip("/")}/word/document.xml'
    tree = etree.parse(doc)
    root = tree.getroot()
    tbl = root.xpath('//w:tbl', namespaces=NS)[0]
    rows = tbl.findall(q('tr'))
    spec = json.load(open(spec_path, encoding='utf-8'))
    tasks = spec['tasks']

    # 1) 考核月份
    i = find_row(rows, '考核月份')
    if i >= 0:
        cells = rows[i].findall(q('tc'))
        for ci, c in enumerate(cells):
            if '考核月份' in cell_text(c) and ci + 1 < len(cells):
                set_cell_text(cells[ci + 1], spec['month'])
                break

    # 2) 计划任务行区间
    hdr = find_row(rows, '计划任务', '完成情况')
    end = find_row(rows, '考核内容')
    if hdr < 0 or end < 0:
        sys.exit('没找到"计划任务/完成情况"或"考核内容"表头行')
    plan = rows[hdr + 1:end]
    if not plan:
        sys.exit('表头之间没有计划任务行')
    # 3) 行数对齐
    while len(plan) < len(tasks):
        new = deepcopy(plan[-1])
        plan[-1].addnext(new)
        plan.append(new)
        rows.insert(end, new)
        end += 1
    while len(plan) > len(tasks):
        plan[-1].getparent().remove(plan[-1])
        plan.pop()
    # 4) 行高对齐：克隆行会带来源行的高 trHeight（原"计划外任务"行常是 1525），
    #    清空内容后仍撑着空高，会把表挤到第二页。统一取计划区间最小行高。
    heights = []
    for tr in plan:
        h = tr.find(q('trPr') + '/' + q('trHeight'))
        heights.append(int(h.get(q('val'))) if h is not None else 75)
    min_h = min(heights) if heights else 75
    for tr in plan:
        trPr = tr.find(q('trPr'))
        if trPr is None:
            continue
        h = trPr.find(q('trHeight'))
        if h is None:
            continue
        h.set(q('val'), str(min_h))
        h.set(q('hRule'), 'atLeast')

    # 5) 逐行填任务、清完成情况、取消勾选
    for tr, task in zip(plan, tasks):
        cells = tr.findall(q('tc'))
        if len(cells) < 3:
            continue
        set_cell_text(cells[1], task)
        set_cell_text(cells[2], '')
        uncheck(cells[3])

    # 5) 评估要点
    if spec.get('clear_eval', True):
        for tr in rows[end:]:
            cells = tr.findall(q('tc'))
            if len(cells) == 5 and cell_text(cells[1]).strip() in (
                    '执行力', '工作效率', '日常表现', '适岗能力', '团队协作'):
                set_cell_text(cells[2], '')

    # 6) 考核结论块整体不跨页：表头行与内容行分开会很难看
    if spec.get('keep_eval_block', True):
        i = find_row(rows, '考核内容')
        if i >= 0:
            block = rows[i:]
            for k, tr in enumerate(block):
                trPr = tr.find(q('trPr'))
                if trPr is None:
                    trPr = etree.Element(q('trPr'))
                    tr.insert(0, trPr)
                if trPr.find(q('cantSplit')) is None:
                    trPr.append(etree.SubElement(trPr, q('cantSplit')))
                if k < len(block) - 1:
                    # 段落嵌在 w:tc 里，必须用 iter 而不是 findall
                    for p in tr.iter(q('p')):
                        pPr = p.find(q('pPr'))
                        if pPr is None:
                            pPr = etree.Element(q('pPr'))
                            p.insert(0, pPr)
                        if pPr.find(q('keepNext')) is None:
                            pPr.insert(0, etree.Element(q('keepNext')))

    # 7) 签名与日期
    if spec.get('clear_signature', True):
        i = find_row(rows, '领导签字')
        if i >= 0:
            tr = rows[i]
            for tag in ('drawing', 'pict', 'object'):
                for el in tr.iter(q(tag)):
                    el.getparent().remove(el)
            for t in tr.iter(q('t')):
                txt = t.text or ''
                if txt.strip().startswith('20') and '.' in txt:
                    t.text = ' ' + spec.get('date', '') if spec.get('date') else ''
    tree.write(doc, xml_declaration=True, encoding='UTF-8', standalone=True)
    print(f"month={spec['month']} tasks={len(tasks)} rows={len(plan)}")


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    build(sys.argv[1], sys.argv[2])
