# -*- coding: utf-8 -*-
"""按 JSON 内容重写 docx 表格单元格的段落（保留单元格宽度/合并/字体）。

用法:
    python fill_cells.py <解包目录> <content.json> [--table 0]

content.json:
{
  "cells": [
    {"table": 0, "row": 5, "col": 2, "align": "left",
     "paras": ["总述一句，包括：", "(1) 第一条", "(2) 第二条"]},
    {"table": 0, "row": 7, "col": 2,
     "paras": ["部分完成。……"]}
  ]
}

规则:
- 只替换单元格内的 w:p，单元格的 tcPr（宽度、gridSpan、vAlign）一字不动；
- 段落格式从该单元格原有第一段/第一个 run 复制（rPr 原样保留，字体字号不变）；
- 可选 align（left/center/both）：表格样式常是两端对齐，窄栏里混排英文会被拉出
  大空档（"走 通 YAML → 子 进 程"），把这类单元格设为 left 更干净；
- 以 "(" 或 "（" 开头的段落自动加悬挂缩进，使换行与条目文字对齐；
- 清除克隆段落的 w14:paraId / w14:textId，避免 Word 报重复 ID。

配合 pack_docx.py 打包；先解包（见 extract_tables.py 说明中的 zipfile 用法）。
"""
import json
import sys
from copy import deepcopy

from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS = {'w': W}
W14 = 'http://schemas.microsoft.com/office/word/2010/wordml'
HANGING = '170'  # twips，约 0.3cm，对应 9pt 一个字符宽


def q(tag):
    return '{%s}%s' % (W, tag)


def build_para(template_p, run_rPr, text, hanging, align=None):
    p = deepcopy(template_p)
    for k in ('{%s}paraId' % W14, '{%s}textId' % W14):
        if k in p.attrib:
            del p.attrib[k]
    pPr = p.find(q('pPr'))
    if pPr is None:
        pPr = etree.SubElement(p, q('pPr'))
        p.insert(0, pPr)
    # 清空段落内容，只留 pPr
    for child in list(p):
        if child is not pPr:
            p.remove(child)
    # 对齐方式（表格样式常是两端对齐，窄栏里混排英文会被拉出大空档）
    if align:
        for old in pPr.findall(q('jc')):
            pPr.remove(old)
        jc = etree.SubElement(pPr, q('jc'))
        jc.set(q('val'), align)
    # 悬挂缩进
    for old in pPr.findall(q('ind')):
        pPr.remove(old)
    if hanging:
        ind = etree.SubElement(pPr, q('ind'))
        ind.set(q('left'), HANGING)
        ind.set(q('hanging'), HANGING)
        ind.set(q('firstLine'), '0')
        ind.set(q('firstLineChars'), '0')
    r = etree.SubElement(p, q('r'))
    if run_rPr is not None:
        r.append(deepcopy(run_rPr))
    t = etree.SubElement(r, q('t'))
    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    t.text = text
    return p


def fill(unpack_dir, content_path):
    doc_path = f'{unpack_dir.rstrip("/")}/word/document.xml'
    tree = etree.parse(doc_path)
    root = tree.getroot()
    tables = root.xpath('//w:tbl', namespaces=NS)
    content = json.load(open(content_path, encoding='utf-8'))
    for spec in content['cells']:
        tbl = tables[spec.get('table', 0)]
        rows = tbl.findall(q('tr'))
        tr = rows[spec['row']]
        cells = tr.findall(q('tc'))
        tc = cells[spec['col']]
        old_paras = tc.findall(q('p'))
        if not old_paras:
            sys.exit(f"row {spec['row']} col {spec['col']} 没有可作模板的段落")
        template = old_paras[0]
        first_runs = template.findall(q('r'))
        run_rPr = None
        if first_runs:
            rPr = first_runs[0].find(q('rPr'))
            run_rPr = deepcopy(rPr) if rPr is not None else None
        for p in old_paras:
            tc.remove(p)
        new_paras = []
        for text in spec['paras']:
            hanging = text.lstrip().startswith(('(', '（'))
            new_paras.append(build_para(template, run_rPr, text, hanging,
                                        spec.get('align')))
        for p in new_paras:
            tc.append(p)
        print(f"row {spec['row']} col {spec['col']}: {len(new_paras)} 段, "
              f"{sum(len(x) for x in spec['paras'])} 字")
    tree.write(doc_path, xml_declaration=True, encoding='UTF-8', standalone=True)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    fill(sys.argv[1], sys.argv[2])
