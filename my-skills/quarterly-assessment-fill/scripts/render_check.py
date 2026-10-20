# -*- coding: utf-8 -*-
"""用本机 Word (COM) 渲染 docx 为 PDF 并逐页导出 PNG，供视觉验收。

用法:
    python render_check.py <输入.docx> <输出前缀>

依赖: pywin32（Word 已安装）、pymupdf。
输出: <前缀>.pdf 和 <前缀>_page1.png、<前缀>_page2.png …
"""
import glob
import os
import sys

import fitz  # pymupdf
import win32com.client

PDF_MARK = 17  # wdExportFormatPDF


def render(docx_path, prefix):
    docx_path = os.path.abspath(docx_path)
    if not os.path.exists(docx_path):
        sys.exit(f'文件不存在: {docx_path}')
    pdf_path = os.path.abspath(prefix + '.pdf')
    ap = win32com.client.Dispatch('Word.Application')
    ap.Visible = False
    ap.DisplayAlerts = 0
    try:
        d = ap.Documents.Open(docx_path, ReadOnly=True)
        d.Fields.Update()  # 刷新编号/字段后再导出
        d.ExportAsFixedFormat(pdf_path, PDF_MARK)
        pages = d.ComputeStatistics(2)  # wdStatisticPages
        d.Close(False)
        print('Word pages:', pages)
    finally:
        ap.Quit()

    for f in glob.glob(prefix + '_page*.png'):
        os.remove(f)
    doc = fitz.open(pdf_path)
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=110)
        pix.save(f'{prefix}_page{i + 1}.png')
    print(f'rendered {len(doc)} pages -> {prefix}_pageN.png')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    render(sys.argv[1], sys.argv[2])
