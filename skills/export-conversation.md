---
name: export-conversation
description: 将当前 Claude Code 会话导出为 Markdown 格式，无需外部依赖
---

# 导出会话为 Markdown

将当前 Claude Code 会话完整导出为可读的 Markdown 文件。

## 执行步骤

当用户请求导出对话时，按以下步骤操作：

### 1. 定位会话文件
会话文件位于 `~/.claude/projects/*/` 目录下，格式为 `*.jsonl`

### 2. 读取会话文件
使用 Read 工具读取 JSONL 文件内容

### 3. 解析并转换
将每行 JSON 解析为消息对象，然后转换为 Markdown：

```markdown
# Claude Code 会话导出

**导出时间**: YYYY-MM-DD HH:MM:SS
**会话文件**: [文件名]

---

## 对话历史

### 用户 (HH:MM:SS)
> 用户消息内容

### Claude (HH:MM:SS)
Claude 回复内容

<details>
<summary>🔧 工具调用</summary>

```
工具名称
参数: {...}
```

</details>

<details>
<summary>📤 工具结果</summary>

```
工具返回内容（截断至500字符）
```

</details>

---
```

### 4. 保存文件
将 Markdown 内容写入用户指定的位置，默认为：
- `~/claude_conversation_export.md`
- 或用户指定的路径

## 特殊处理

- **图片**: 显示为 `[图片: filename]`
- **长文本**: 工具结果超过 500 字符时截断
- **敏感信息**: API 密钥、token 等脱敏显示
- **代码块**: 保留原始格式，添加语言标识
- **思考块**: 折叠显示

## 使用方法

用户可以这样说：
- "导出对话" → 导出到默认位置
- "导出对话到 /path/to/file.md" → 导出到指定位置
- "保存当前会话"
