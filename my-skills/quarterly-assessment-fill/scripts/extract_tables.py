# -*- coding: utf-8 -*-
"""提取 docx 表格与顶层段落文本。

用法:
    python extract_tables.py 文件1.docx [文件2.docx ...]

不依赖 pandoc/python-docx，仅用标准库 zipfile + minidom，
按单元格/段落打印文本，便于建立月度计划与季度考核表的对应关系。
"""
import sys
import zipfile
from xml.dom import minidom


def cell_text(tc):
    paras = []
    for p in tc.getElementsByTagName('w:p'):
        texts = [t.firstChild.nodeValue if t.firstChild else '' for t in p.getElementsByTagName('w:t')]
        paras.append(''.join(texts))
    return paras


def extract(path):
    print(f"========== {path} ==========")
    with zipfile.ZipFile(path) as z:
        xml = z.read('word/document.xml').decode('utf-8')
    doc = minidom.parseString(xml)
    tables = doc.getElementsByTagName('w:tbl')
    print(f"[tables: {len(tables)}]")
    for ti, tbl in enumerate(tables):
        rows = [r for r in tbl.childNodes if r.nodeName == 'w:tr']
        print(f"--- Table {ti}: {len(rows)} rows ---")
        for ri, tr in enumerate(rows):
            cells = [c for c in tr.childNodes if c.nodeName == 'w:tc']
            cell_strs = [' / '.join(cell_text(tc)) for tc in cells]
            print(f"R{ri}: " + ' || '.join(cell_strs))
    body = doc.getElementsByTagName('w:body')[0]
    print("--- top-level paragraphs ---")
    for node in body.childNodes:
        if node.nodeName == 'w:p':
            texts = [t.firstChild.nodeValue if t.firstChild else '' for t in node.getElementsByTagName('w:t')]
            txt = ''.join(texts)
            if txt.strip():
                print("P:", txt)
    print()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    for path in sys.argv[1:]:
        extract(path)
