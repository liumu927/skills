# -*- coding: utf-8 -*-
"""把解包目录重新打包为 docx（Windows 下无 zip 命令时的替代）。

用法:
    python pack_docx.py <解包目录> <输出.docx>

[Content_Types].xml 会最先写入，其余文件按目录递归打包，
自动跳过脚本等杂物。
"""
import os
import sys
import zipfile


def pack(src_dir, out_path):
    if os.path.exists(out_path):
        os.remove(out_path)
    zf = zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED)
    ct = os.path.join(src_dir, '[Content_Types].xml')
    if not os.path.exists(ct):
        sys.exit(f'缺少 [Content_Types].xml: {src_dir} 不是有效的 docx 解包目录')
    zf.write(ct, '[Content_Types].xml')
    for root, _dirs, files in os.walk(src_dir):
        for fn in files:
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, src_dir).replace(os.sep, '/')
            if rel == '[Content_Types].xml' or rel.endswith(('.py', '.md')):
                continue
            zf.write(full, rel)
    zf.close()
    with zipfile.ZipFile(out_path) as z:
        bad = z.testzip()
        if bad:
            sys.exit(f'打包校验失败: {bad}')
    print(f'packed: {out_path} ({os.path.getsize(out_path)} bytes)')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    pack(sys.argv[1], sys.argv[2])
