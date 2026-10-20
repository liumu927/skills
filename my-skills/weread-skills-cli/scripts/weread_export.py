#!/usr/bin/env python3
"""微信读书笔记导出脚本

从 WeRead API 获取划线和想法数据，渲染为 Obsidian 兼容的 Markdown 笔记。

用法:
    python weread_export.py --book-id <bookId> --api-key <token> --output <path> [--date <YYYY-MM-DD>]

环境变量:
    WEREAD_API_KEY  - 微信读书 API Bearer Token（wrk-xxxx 格式）
"""

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime
from collections import defaultdict

# ========== 常量 ==========

GATEWAY_URL = "https://i.weread.qq.com/api/agent/gateway"
SKILL_VERSION = "1.0.3"

COLOR_MAP = {
    1: ("红色", "#FF909C"),
    2: ("紫色", "#B89FFF"),
    3: ("蓝色", "#74B4FF"),
    4: ("绿色", "#70D382"),
    5: ("黄色", "#FFCB7E"),
}


def load_template(custom_path=None):
    """加载模板文件。以 Obsidian 模板为准，内置模板仅作备用。"""
    # 1. 命令行 --template 参数
    if custom_path and os.path.isfile(custom_path):
        print(f"[信息] 使用模板（命令行参数）：{custom_path}")
        with open(custom_path, "r", encoding="utf-8") as f:
            return f.read()

    # 2. 环境变量 WEREAD_TEMPLATE_PATH
    env_path = os.environ.get("WEREAD_TEMPLATE_PATH")
    if env_path and os.path.isfile(env_path):
        print(f"[信息] 使用 Obsidian 模板：{env_path}")
        with open(env_path, "r", encoding="utf-8") as f:
            return f.read()

    # 3. 兜底：内置备用模板（提醒用户）
    builtin = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "template.md")
    if os.path.isfile(builtin):
        print("[警告] 未找到 Obsidian 模板文件，正在使用内置备用模板！", file=sys.stderr)
        print("[警告] 建议设置环境变量 WEREAD_TEMPLATE_PATH 指向你的模板文件，以获得完整版式。", file=sys.stderr)
        with open(builtin, "r", encoding="utf-8") as f:
            return f.read()

    print("[错误] 未找到任何可用的模板文件", file=sys.stderr)
    sys.exit(1)


def ts_to_date(ts):
    """Unix 时间戳 → YYYY-MM-DD"""
    if not ts:
        return ""
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def seconds_to_hours(secs):
    """秒 → X小时Y分钟"""
    if not secs:
        return "0小时"
    h = int(secs // 3600)
    m = int((secs % 3600) // 60)
    if h == 0:
        return f"{m}分钟"
    if m == 0:
        return f"{h}小时"
    return f"{h}小时{m}分钟"


def api_call(api_name, api_key, extra_params=None):
    """调用 WeRead API Gateway"""
    body = {"api_name": api_name, "skill_version": SKILL_VERSION}
    if extra_params:
        body.update(extra_params)

    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        GATEWAY_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if "upgrade_info" in result:
                message = result["upgrade_info"].get("message", "检测到 skill 需要升级")
                print(f"[升级] {message}", file=sys.stderr)
                sys.exit(2)
            return result
    except urllib.error.HTTPError as e:
        print(f"[错误] API 调用失败 {api_name}: HTTP {e.code}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[错误] API 调用异常 {api_name}: {e}", file=sys.stderr)
        sys.exit(1)


def fetch_book_data(book_id, api_key):
    """获取书籍的全部数据"""
    print(f"[信息] 正在获取书籍数据 (bookId={book_id})...")

    # 1. 书籍信息
    print("[信息] 获取书籍基本信息...")
    book_info = api_call("/book/info", api_key, {"bookId": book_id})

    # 2. 章节目录
    print("[信息] 获取章节目录...")
    chapter_info = api_call("/book/chapterinfo", api_key, {"bookId": book_id})

    # 3. 划线列表
    print("[信息] 获取划线列表...")
    bookmark_list = api_call("/book/bookmarklist", api_key, {"bookId": book_id})

    # 4. 想法列表（需分页）
    print("[信息] 获取想法/点评...")
    all_reviews = []
    synckey = 0
    page = 0
    while True:
        page += 1
        review_data = api_call(
            "/review/list/mine",
            api_key,
            {"bookid": book_id, "synckey": synckey, "count": 20},
        )
        reviews = review_data.get("reviews", [])
        all_reviews.extend(reviews)
        print(f"[信息]   第{page}页获取 {len(reviews)} 条想法")
        has_more = review_data.get("hasMore", 0)
        if not has_more or has_more == 0:
            break
        new_synckey = review_data.get("synckey", 0)
        if new_synckey == synckey:
            break
        synckey = new_synckey

    # 5. 阅读进度
    print("[信息] 获取阅读进度...")
    progress_data = api_call("/book/getprogress", api_key, {"bookId": book_id})

    return {
        "book_info": book_info,
        "chapter_info": chapter_info,
        "bookmark_list": bookmark_list,
        "reviews": all_reviews,
        "progress_data": progress_data,
    }


def build_chapter_map(chapter_info):
    """构建 chapterUid → 章节标题 的映射"""
    chapters = chapter_info.get("chapters", [])
    return {c["chapterUid"]: c["title"] for c in chapters}


def build_highlights(bookmark_list, chapter_map):
    """按章节分组划线"""
    highlights = bookmark_list.get("updated", [])
    chapters_in_bookmark = {c["chapterUid"]: c["title"] for c in bookmark_list.get("chapters", [])}

    # 合并两个章节映射（bookmarklist 的 chapters 可能更完整）
    merged_map = {**chapter_map, **chapters_in_bookmark}

    grouped = defaultdict(list)
    for h in highlights:
        uid = h.get("chapterUid", 0)
        title = merged_map.get(uid, f"未知章节({uid})")
        grouped[title].append(h)

    return dict(grouped)


def build_thoughts(reviews, chapter_map):
    """按章节分组想法/点评"""
    grouped = defaultdict(list)
    for r in reviews:
        review = r.get("review", {})
        uid = review.get("chapterUid", 0)
        title = review.get("chapterName") or chapter_map.get(uid, f"未知章节({uid})")
        grouped[title].append(review)

    return dict(grouped)


def render_highlight(h):
    """渲染单条划线"""
    color_style = h.get("colorStyle", 1)
    hex_color = COLOR_MAP.get(color_style, ("未知", "#999999"))[1]
    text = h.get("markText", "")
    date = ts_to_date(h.get("createTime"))
    return f"> {date}\n>\n> <span style=\"color:{hex_color}\">{text}</span>"


def render_thought(thought):
    """渲染单条想法/点评"""
    abstract = thought.get("abstract", "")
    content = thought.get("content", "")
    date = ts_to_date(thought.get("createTime"))

    # 尝试获取点赞数（API 可能不返回）
    likes = thought.get("likesCount", thought.get("likeCount", 0))

    if abstract:
        source_line = f'> "{abstract}" | {date} | 点赞 {likes}'
    else:
        source_line = f"> 章节讨论 | {date} | 点赞 {likes}"

    return f"{source_line}\n\n**想法：** {content}"


def render_highlights_section(highlights_by_chapter):
    """渲染划线列表章节"""
    lines = []
    for chapter_title, chapter_highlights in highlights_by_chapter.items():
        lines.append(f"### {chapter_title}\n")
        for h in chapter_highlights:
            lines.append(render_highlight(h))
            lines.append("")  # 空行分隔
    return "\n".join(lines)


def render_thoughts_section(thoughts_by_chapter):
    """渲染想法与点评章节"""
    lines = []
    for chapter_title, chapter_thoughts in thoughts_by_chapter.items():
        lines.append(f"### {chapter_title}\n")
        for t in chapter_thoughts:
            lines.append(render_thought(t))
            lines.append("")  # 空行分隔
    return "\n".join(lines)


def determine_export_date(progress_data):
    """确定导出日期：优先使用 finishTime，否则使用当前日期"""
    book = progress_data.get("book", {})
    finish_time = book.get("finishTime")
    if finish_time:
        return ts_to_date(finish_time)
    return datetime.now().strftime("%Y-%m-%d")


def determine_filename(title, export_date):
    """生成文件名：阅读结束日期《书名》.md"""
    return f"{export_date}《{title}》.md"


def replace_section(markdown, start_pattern, end_pattern, replacement):
    """替换模板中一段示例内容，保留标题和分隔线结构。"""
    pattern = f"({start_pattern})(.*?)(?={end_pattern})"
    return re.sub(pattern, lambda m: f"{m.group(1)}\n\n{replacement.rstrip()}\n", markdown, flags=re.S)


def generate_markdown(data, export_date=None, template_path=None):
    """生成完整的 Markdown 笔记"""
    book_info = data["book_info"]
    chapter_info = data["chapter_info"]
    bookmark_list = data["bookmark_list"]
    reviews = data["reviews"]
    progress_data = data["progress_data"]

    title = book_info.get("title", "未知书名")
    author = book_info.get("author", "未知作者")
    cover = book_info.get("cover", "")
    category = book_info.get("category", "")
    book_id = book_info.get("bookId", "")

    # 阅读进度
    progress_book = progress_data.get("book", {})
    progress_pct = progress_book.get("progress", 0)
    # API 返回 readingTime（秒），recordReadingTime 可能为 0
    reading_time = progress_book.get("readingTime") or progress_book.get("recordReadingTime") or 0
    start_reading_time = progress_book.get("startReadingTime", 0)
    finish_time = progress_book.get("finishTime")

    # 计算阅读天数
    if start_reading_time and finish_time:
        reading_days = (finish_time - start_reading_time) // 86400
    elif start_reading_time:
        reading_days = (datetime.now().timestamp() - start_reading_time) // 86400
    else:
        reading_days = 0

    # 章节映射
    chapter_map = build_chapter_map(chapter_info)

    # 按章节分组
    highlights_by_chapter = build_highlights(bookmark_list, chapter_map)
    thoughts_by_chapter = build_thoughts(reviews, chapter_map)

    # 统计
    highlight_count = len(bookmark_list.get("updated", []))
    thought_count = len(reviews)
    bookmark_count = 0  # 当前 API 不支持导出书签内容

    filename_date = export_date or determine_export_date(progress_data)
    current_export_date = datetime.now().strftime("%Y-%m-%d")

    # 渲染
    highlights_section = render_highlights_section(highlights_by_chapter)
    thoughts_section = render_thoughts_section(thoughts_by_chapter)
    reading_link = f"weread://reading?bId={book_id}" if book_id else ""

    # 加载模板
    template = load_template(template_path)

    replacements = {
        "{{封面}}": cover,
        "{{作者}}": author,
        "{{分类}}": category,
        "{{书名}}": title,
        "{{当日导出时间}}": current_export_date,
        "{{导出时间}}": current_export_date,
        "{{bookId}}": book_id,
        "{{划线数}}": str(highlight_count),
        "{{想法数}}": str(thought_count),
        "{{书签数}}": str(bookmark_count),
        "{{累计阅读时长}}": seconds_to_hours(reading_time),
        "{{阅读天数}}": f"{int(reading_days)}天",
        "{{阅读进度}}": f"{progress_pct}%",
        "{{书签内容或\"无书签\"}}": "无书签",
        "{{阅读链接}}": reading_link,
    }

    result = template
    for placeholder, value in replacements.items():
        result = result.replace(placeholder, value)

    result = replace_section(
        result,
        r"## 一、划线列表（\d+条）",
        r"\n---\n\n## 二、想法与点评",
        highlights_section or "无划线",
    )
    result = replace_section(
        result,
        r"## 二、想法与点评（\d+条）",
        r"\n---\n\n## ",
        thoughts_section or "无想法/点评",
    )

    return result, determine_filename(title, filename_date)


def main():
    parser = argparse.ArgumentParser(description="微信读书笔记导出")
    parser.add_argument("--book-id", required=True, help="书籍 ID")
    parser.add_argument("--api-key", default=None, help="API Key (默认从环境变量 WEREAD_API_KEY 读取)")
    parser.add_argument("--output", default=".", help="输出目录路径")
    parser.add_argument("--date", default=None, help="导出日期 (YYYY-MM-DD)，默认自动检测")
    parser.add_argument("--json-data", default=None, help="直接传入 JSON 数据文件路径（跳过 API 调用）")
    parser.add_argument("--template", default=None, help="自定义模板文件路径（默认使用 WEREAD_TEMPLATE_PATH 环境变量或内置模板）")
    args = parser.parse_args()

    # 获取 API Key
    api_key = args.api_key or os.environ.get("WEREAD_API_KEY")
    if not api_key and not args.json_data:
        print("[错误] 未设置 API Key。请设置环境变量 WEREAD_API_KEY 或使用 --api-key 参数。", file=sys.stderr)
        sys.exit(1)

    # 获取数据
    if args.json_data:
        with open(args.json_data, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = fetch_book_data(args.book_id, api_key)

    # 生成 Markdown
    markdown, filename = generate_markdown(data, args.date, args.template)

    # 输出文件
    output_path = os.path.join(args.output, filename)
    os.makedirs(args.output, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"[完成] 笔记已导出到：{output_path}")
    print(f"[信息] 文件名：{filename}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
