# My Claude Code Skills

Claude Code 技能集合，用于增强 AI 辅助开发能力。

## 技能列表

| 技能 | 描述 |
|------|------|
| [gradio-skill-template](./gradio-skill-template/skill.md) | Gradio Tab 页面组件模板系统，用于快速开发算法推理/训练界面 |

## 使用方法

将技能目录复制到项目的 `.claude/skills/` 目录下：

```bash
# 复制单个技能
cp -r gradio-skill-template /path/to/your/project/.claude/skills/

# 或复制所有技能
cp -r * /path/to/your/project/.claude/skills/
```

## 技能开发

每个技能遵循以下结构：

```
skill-name/
├── skill.md          # 技能入口（必需）
├── components/       # 可复用组件（可选）
├── templates/        # 模板文件（可选）
└── reference/        # 参考文档（可选）
```
