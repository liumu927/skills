# weread-skills-cli

微信读书 CLI 助手 — 内置 weread-skills API 文档，可搜索书籍、查看书架/笔记/阅读数据，并将微信读书划线、想法/点评导出为适配 Obsidian 的 Markdown。

## 功能

- 搜索微信读书书籍
- 查看书架、笔记划线、阅读统计
- 导出划线和想法/点评为 Obsidian 兼容的 Markdown
- 内置完整的 weread-skills API 文档

## 安装

### 方式一：安装到当前项目（推荐）

```bash
git clone https://github.com/你的用户名/weread-skills-cli.git
cp -r weread-skills-cli .claude/skills/weread-skills-cli
rm -rf weread-skills-cli
```

### 方式二：安装到全局（所有项目可用）

```bash
git clone https://github.com/你的用户名/weread-skills-cli.git
cp -r weread-skills-cli ~/.claude/skills/weread-skills-cli
rm -rf weread-skills-cli
```

## 配置

### 1. API Token

微信读书 API 需要 Bearer Token 鉴权。

1. 访问微信读书网页版（weread.qq.com）
2. 打开浏览器开发者工具（F12）
3. 在 Network 标签中找到任意请求，复制 `wrk-` 开头的 token
4. 设置环境变量：
   ```bash
   # 临时设置
   export WEREAD_API_KEY=wrk-xxxxxxxx
   
   # 永久设置（推荐）- 写入 shell 配置文件
   echo 'export WEREAD_API_KEY=wrk-xxxxxxxx' >> ~/.bashrc
   source ~/.bashrc
   ```

   Windows PowerShell 永久设置：
   ```powershell
   [Environment]::SetEnvironmentVariable("WEREAD_API_KEY", "wrk-xxxxxxxx", "User")
   ```

### 2. 导出模板（可选）

导出笔记时默认使用内置模板。如需使用自定义 Obsidian 模板，设置 `WEREAD_TEMPLATE_PATH` 环境变量指向模板文件：

```bash
# Linux/macOS
export WEREAD_TEMPLATE_PATH="/path/to/your-template.md"

# Windows PowerShell 永久设置
[Environment]::SetEnvironmentVariable("WEREAD_TEMPLATE_PATH", "D:\文档\Obsidian\个人库\模板库\【模板】微信读书导出.md", "User")
```

未设置时，导出脚本会使用内置备用模板并输出警告提醒。

或者在项目的 `.claude/settings.local.json` 中配置（不要提交到 git）：
```json
{
  "permissions": {
    "allow": [
      "Bash(curl -s -X POST https://i.weread.qq.com/api/agent/gateway*)"
    ]
  }
}
```

## 使用

在 Claude Code 中：

```
/weread-skills-cli
```

### 导出笔记

```
/export 书名
```

或者不指定书名，会展示书架供你选择：

```
/export
```

## 文件结构

```
├── SKILL.md                    # Skill 定义
├── assets/
│   └── template.md             # 导出模板
├── references/
│   └── weread-api/             # API 文档
│       ├── book.md
│       ├── discover.md
│       ├── notes.md
│       ├── official-skill.md
│       ├── profile.md
│       ├── readdata.md
│       ├── review.md
│       ├── search.md
│       └── shelf.md
└── scripts/
    └── weread_export.py        # 导出脚本
```

## 依赖

- Python 3.6+（导出功能需要）
- Claude Code

## License

MIT
