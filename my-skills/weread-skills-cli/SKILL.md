---
name: weread-skills-cli
description: 微信读书 CLI 助手，内置 weread-skills API 文档，可搜索书籍、查看书架/笔记/阅读数据，并将微信读书划线、想法/点评导出为适配 Obsidian 的 Markdown。
version: 1.1.0
---

# 微信读书 CLI 助手

提供两类能力：

1. 查询微信读书数据：搜索、书籍信息、书架、阅读统计、笔记划线、书评、推荐。
2. 导出单本书笔记：把划线和想法/点评渲染为 Obsidian Markdown。

本 skill 已内置官方 `weread-skills` Markdown 文档，不再要求用户额外安装官方 skill。

## 内置 API 文档

调用接口或解释字段前，先按用户意图读取对应文档：

| 能力 | 文档 |
|------|------|
| 总览、鉴权、通用规则、深度链接 | `references/weread-api/official-skill.md` |
| 搜索书籍 | `references/weread-api/search.md` |
| 书籍信息、章节、阅读进度 | `references/weread-api/book.md` |
| 书架管理 | `references/weread-api/shelf.md` |
| 阅读统计 | `references/weread-api/readdata.md` |
| 笔记、划线、想法/点评 | `references/weread-api/notes.md` |
| 书籍点评 | `references/weread-api/review.md` |
| 推荐发现 | `references/weread-api/discover.md` |
| 用户资料 | `references/weread-api/profile.md` |

## 鉴权

微信读书 API 使用 Agent Gateway：

```text
POST https://i.weread.qq.com/api/agent/gateway
Authorization: Bearer $WEREAD_API_KEY
Content-Type: application/json
```

`WEREAD_API_KEY` 从环境变量读取，格式为 `wrk-xxxxxxxx`。如果未设置，提示用户先配置该环境变量。

请求体必须平铺参数，并带 `skill_version`：

```json
{"api_name":"/store/search","keyword":"三体","count":10,"skill_version":"1.0.3"}
```

## 快捷命令

使用 `/weread-skills-cli <命令> [参数]` 调用。也可以用自然语言描述需求，效果相同。

所有命令必须先检查 `WEREAD_API_KEY`。需要书名参数的命令，若用户未提供，展示书架列表供选择。书名参数通过书架匹配或 `/store/search` 搜索解析为 `bookId`。

### `help`

展示所有可用命令及简要说明。

- 无参数
- 触发条件：`/weread-skills-cli`（无参数）、`/weread-skills-cli help`、`/weread-skills-cli ?`
- 输出格式：

```
📖 微信读书 CLI 助手 - 命令列表

查询
  shelf [排序]       查看书架（排序: 默认/进度/最近/书名/分类/字数/评分/私密/已读完/在读）
  search <关键词>    搜索书城（可选 scope:0-16）
  info <书名>        书籍详情与章节目录
  progress <书名>    阅读进度
  notes <书名>       个人划线与想法
  notebooks          笔记总览（所有有笔记的书）
  popular <书名>     热门划线
  stats [周期]       阅读统计（周期: 周/月/年/总计）
  reviews <书名>     公开点评（可选 type:0-4）
  profile            阅读画像

发现
  recommend          个性化推荐
  similar <书名>     相似书籍推荐

导出
  export [书名]      导出笔记为 Obsidian Markdown

帮助
  help               显示此列表
```

### `shelf [排序方式]`

查看书架列表，支持多种排序/展示方式。

- 调用 `/shelf/sync`，然后按指定方式排列。
- 排序方式（默认为 `默认`）：

| 排序方式 | 说明 | 数据来源 |
|----------|------|----------|
| `默认` | 按书架默认分类（archive）分组列出 | `archive[]` 分组 |
| `进度` | 按阅读进度排序（未读→部分→读完） | 需逐本调 `/book/getprogress` 获取 `progress`（0-100），升序排列 |
| `最近` | 按最近阅读时间排序（最新在前） | `readUpdateTime` 降序 |
| `书名` | 按书名排序 | `title` 字典序 |
| `分类` | 按 `books[].category` 分组 | `category` 字段 |
| `字数` | 按字数排序 | 需逐本调 `/book/info` 获取 `wordCount`，降序 |
| `评分` | 按微信读书评分排序 | 需逐本调 `/book/info` 获取 `newRating`，降序 |
| `私密` | 只列出私密阅读的书 | `secret == 1` |
| `已读完` | 只列出已读完的书 | `finishReading == 1` |
| `在读` | 只列出在读（有进度未读完）的书 | `finishReading != 1 && readUpdateTime > 0` |

- 用法示例：
  - `/weread-skills-cli shelf` → 默认分类
  - `/weread-skills-cli shelf 最近` → 最近阅读排序
  - `/weread-skills-cli shelf 进度` → 按进度排序
  - `/weread-skills-cli shelf 书名` → 按书名排序
- 输出：总条目数 + 排序后的书籍列表（书名/作者/对应排序字段值/状态标记）
- 需要逐本查询的排序（`进度`、`字数`、`评分`）性能较慢，需在结果中标注"数据来源：逐本查询"。

### `search <关键词>`

搜索书城书籍。

- 调用 `/store/search`
- 参数：关键词（必填）
- 可选：`scope:值`，如 `/weread-skills-cli search 三体 scope:10`
  - scope 值：`0`=全部, `10`=电子书, `16`=网文, `14`=有声书, `6`=作者, `12`=全文搜索, `13`=书单
- 默认 scope=10（电子书）
- 输出：编号列表，书名/作者/评分/阅读人数
- 翻页：用最后一条的 `searchIdx` 作为 `maxIdx`

### `info <书名>`

查看书籍详情。

- 调用 `/book/info` + `/book/chapterinfo`
- 参数：书名（必填）
- 输出：书名、作者、译者、出版社、出版时间、字数、评分、评分人数、简介、章节目录

### `progress <书名>`

查看阅读进度。

- 调用 `/book/getprogress`
- 参数：书名（必填）
- 输出：阅读进度百分比、当前章节、累计阅读时长、最近阅读时间、是否读完

### `notes <书名>`

查看单本书的笔记划线和想法。

- 并行调用 `/book/bookmarklist` + `/review/list/mine`
- 参数：书名（必填）
- 输出：划线列表（内容/颜色/章节）、想法/点评列表（内容/评分/时间）

### `notebooks`

笔记总览，列出所有有笔记的书。

- 调用 `/user/notebooks`
- 无参数
- 输出：总书籍数、总笔记数，每本书的书名/划线数/想法数/阅读进度
- 翻页：用最后一条的 `sort` 作为 `lastSort`

### `popular <书名>`

查看书籍热门划线。

- 调用 `/book/bestbookmarks`
- 参数：书名（必填）
- 输出：热门划线内容、划线人数、所在章节
- 可选：章节限定，如 `/weread-skills-cli popular 三体 chapterUid:123`

### `stats [周期]`

查看阅读统计。

- 调用 `/readdata/detail`
- 周期（默认为 `monthly`）：`weekly`=本周, `monthly`=本月, `annually`=本年, `overall`=总计
- 用法示例：
  - `/weread-skills-cli stats` → 本月统计
  - `/weread-skills-cli stats 周` → 本周
  - `/weread-skills-cli stats 年` → 本年
  - `/weread-skills-cli stats 总计` → 总计
- 输出：总时长、阅读天数、日均时长、与上期对比、读得最多的书 Top 10、偏好分类/作者/时段

### `reviews <书名>`

查看书籍公开点评。

- 调用 `/review/list`
- 参数：书名（必填）
- 可选：`type:值`，如 `/weread-skills-cli reviews 三体 type:1`
  - type 值：`0`=全部, `1`=推荐, `2`=差评, `3`=最新, `4`=一般
- 默认 type=0（全部）
- 输出：点评总数、推荐率、评分分布，每条点评的作者/评分/内容/时间

### `recommend`

查看个性化推荐。

- 调用 `/book/recommend`
- 无参数
- 输出：推荐书籍列表（书名/作者/评分/推荐理由）
- 翻页：用最后一条的 `searchIdx` 作为 `maxIdx`

### `similar <书名>`

查看相似书籍推荐。

- 调用 `/book/similar`
- 参数：书名（必填）
- 输出：相似书籍列表（书名/作者/评分）

### `profile`

用户阅读画像。

- 组合调用：`/shelf/sync` + `/readdata/detail`
- 无参数
- 输出：书架概况、阅读统计摘要、偏好分类、偏好作者、阅读时段

### `export [书名]`

导出指定书籍的笔记为 Markdown 文件。

- 工作流详见下方「导出命令」章节。

## 导出命令

### `/export [书名]`

导出指定书籍的笔记为 Markdown 文件。

工作流：

1. 检查 `WEREAD_API_KEY`。
2. 若用户提供书名，先通过书架或搜索解析 `bookId`；若未提供，展示书架列表供用户选择。
3. 获取导出所需数据：
   - `/book/info`：书名、作者、分类等基本信息。
   - `/book/chapterinfo`：章节目录，用于分组。
   - `/book/bookmarklist`：划线内容。
   - `/review/list/mine`：个人想法/点评。
   - `/book/getprogress`：阅读进度、阅读时长、开始/完成时间。
4. 运行 `scripts/weread_export.py` 渲染模板。模板加载优先级：`--template` 参数 > `WEREAD_TEMPLATE_PATH` 环境变量 > 内置 `assets/template.md`。
5. 输出文件名使用 `阅读结束日期《书名》.md`；未读完时使用导出日期。

## 导出模板

以用户 Obsidian 模板为准，内置模板仅作备用。加载优先级：

1. `--template` 命令行参数指定的路径
2. `WEREAD_TEMPLATE_PATH` 环境变量指向的 Obsidian 模板文件
3. 内置 `assets/template.md`（**仅兜底，使用时会输出警告提醒用户**）

必须将 `WEREAD_TEMPLATE_PATH` 设置为用户的 Obsidian 模板路径（如 `D:\文档\Obsidian\个人库\模板库\【模板】微信读书导出.md`）。若未配置且使用内置模板时，脚本会打印警告提示用户设置。

模板中的示例划线颜色只作为版式约束，脚本会按章节替换为真实划线和想法内容。

## 数据处理规则

- 时间戳统一展示为 `YYYY-MM-DD`。
- 阅读时长由秒转换为 `X小时Y分钟`。
- 划线使用 `<span style="color:#HEX">文本</span>`，不额外添加下划线。
- `colorStyle` 映射：

| 值 | 颜色 | Hex |
|----|------|-----|
| 1 | 红色 | `#FF909C` |
| 2 | 紫色 | `#B89FFF` |
| 3 | 蓝色 | `#74B4FF` |
| 4 | 绿色 | `#70D382` |
| 5 | 黄色 | `#FFCB7E` |

- 当前 `/book/bookmarklist` 只导出划线内容，不导出书签正文；书签区域无可用内容时输出 `无书签`。
- 深度链接只在「深度链接」章节输出总阅读入口，按官方 URL Schema 构造为 `weread://reading?bId={bookId}`；不要默认给每条划线或想法添加定位链接，除非用户明确要求。
- 若接口返回 `upgrade_info`，立即暂停当前操作并按提示升级，不能忽略。
