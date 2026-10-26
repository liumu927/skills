# -*- coding: utf-8 -*-
"""解析 Obsidian「待办导出」Markdown，输出按日期分组的任务树 JSON。

用法:
    python parse_todo_log.py <待办导出.md> [out.json]

支持的结构（本机 Obsidian 待办看板的导出格式）：

    - 无日期的待办树（按 Tab 缩进）
    > [!multi-column]
    > 
    >> [!2026-10-26-周一]+
    >> - [ ] 钉钉数据摆渡方案调研
    >> - [x] K4平台优化
    >> 	- [x] 联调链路自动化测试体系落地
    >>
    >> [!2026-10-25-周日]+
    >> - [ ] ...

输出 JSON:
{
  "dates": {"2026-10-26": [{"depth": 0, "checked": true, "text": "K4平台优化"}, ...]},
  "backlog": [{"depth": 0, "checked": false, "text": "钉钉数据摆渡"}, ...]
}

勾选状态 checked 只作参考：写考核表时以「考核截止日之前」为准，
未勾选但业主会补完的条目同样要写进完成情况（见 SKILL.md 模式 B）。
"""
import json
import re
import sys

_DATE_RE = re.compile(r'\[!(\d{4}-\d{2}-\d{2})[^\]]*\]')
_ITEM_RE = re.compile(r'^(\t*)- \[([ xX])\]\s*(.*)$')


def parse(path):
    dates = {}
    backlog = []
    cur = 'BACKLOG'
    for raw in open(path, encoding='utf-8'):
        line = raw.rstrip('\n')
        # 去掉引用块前缀 > / >> / >>>（每级 > 后最多跟一个空格）。
        # 不能用 \s*，否则会把子项的 Tab 缩进一起吃掉，层级全变 0。
        body = re.sub(r'^(?:> ?)+', '', line)
        m = _DATE_RE.search(body)
        if m:
            cur = m.group(1)
            dates.setdefault(cur, [])
            continue
        m = _ITEM_RE.match(body)
        if not m:
            continue
        depth = len(m.group(1))
        checked = m.group(2).lower() == 'x'
        text = m.group(3).strip()
        item = {'depth': depth, 'checked': checked, 'text': text}
        (backlog if cur == 'BACKLOG' else dates[cur]).append(item)
    return {'dates': dict(sorted(dates.items())), 'backlog': backlog}


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    data = parse(sys.argv[1])
    if len(sys.argv) > 2:
        json.dump(data, open(sys.argv[2], 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=2)
        print(f'wrote {sys.argv[2]}')
    for d, items in data['dates'].items():
        done = sum(1 for i in items if i['checked'])
        print(f'== {d}  ({done}/{len(items)} 勾选)')
        for i in items:
            print('   ' * i['depth'] + ('[x] ' if i['checked'] else '[ ] ') + i['text'])
    if data['backlog']:
        print(f'== 无日期待办 ({len(data["backlog"])} 条)')
        for i in data['backlog']:
            print('   ' * i['depth'] + ('[x] ' if i['checked'] else '[ ] ') + i['text'])


if __name__ == '__main__':
    main()
