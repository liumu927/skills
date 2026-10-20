# My Skills

个人 Agent Skills 统一仓库。所有 skill 只在此仓库维护一份，通过 NTFS 目录联接（junction）映射到各 agent 的 skills 目录，实现跨 agent 共享 + git 版本管理。

## 结构

```
my-skills/
├── skills/       ← 所有 skill 平铺于此（junction 指向这里）
├── setup.cmd     ← 新机器一键建立联接
└── README.md
```

## 技能列表

| 技能 | 描述 |
|------|------|
| code-dojo | 交互式代码业务逻辑"带练教练" |
| dingtalk-integration | 钉钉低代码集成（审批、连接器、连接流、AI 表格）配置陪跑与排错 |
| dingtalk-login | 网页系统接入钉钉扫码登录 / 工作台免登 |
| export-conversation.md | 会话导出（散文件笔记） |
| frontend-design | 高质量前端界面设计与实现 |
| gradio-skill-template | Gradio Tab 页面组件模板系统 |
| officecli | 用 officecli 创建/检查/修改 Office 文档 |
| quarterly-assessment-fill | 根据月度计划表汇总填写季度考核表 |
| source-command-zcf-git-worktree | Git worktree 管理 |
| weread-skills-cli | 微信读书 CLI 助手与笔记导出 |

## 新机器部署

1. 克隆本仓库（保持本地磁盘，如 `E:\project\skills\my-skills`）：

   ```bash
   git clone git@github.com:liumu927/skills.git E:\project\skills\my-skills
   ```

2. 运行一次（双击或在命令行执行）：

   ```cmd
   setup.cmd
   ```

   脚本会把 `~\.claude\skills`、`~\.agents\skills`、`~\.zcode\skills` 建为指向本仓库 `skills\` 的 junction；已存在的目录会先备份为 `skills.bak`，已是 junction 则跳过。新增 agent 工具时，在 `setup.cmd` 的 `for %%D in (...)` 列表里加一项即可。

3. 重启各 agent 工具加载 skills。

## 日常使用

- **修改 / 新增 skill**：只改本仓库 `skills/` 下的内容，所有 agent 立即生效；记得 `git commit` + `push`。
- **删除 skill**：在 `skills/` 下删除目录并提交。
- 不要直接编辑 `~\.claude\skills` 等联接目录里的文件——编辑的就是本仓库，效果相同，但路径绕一层容易混淆，建议直接在仓库里改。

## 技能开发约定

每个技能遵循以下结构：

```
skills/skill-name/
├── SKILL.md          # 技能入口（必需）
├── components/       # 可复用组件（可选）
├── templates/        # 模板文件（可选）
├── scripts/          # 脚本（可选）
└── reference/        # 参考文档（可选）
```
