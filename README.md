# My Skills

个人 Agent Skills 统一仓库。整个 `E:\project\skills\` 目录为一个 git 仓库，自建与第三方 skill 分开存放，通过 NTFS 目录联接（junction）映射到各 agent 的 skills 目录，实现跨 agent 共享 + 版本管理。

## 结构

```
E:\project\skills\            ← git 仓库根
├── my-skills\                ← 自建 skills（放这里）
│   ├── code-dojo\
│   ├── dingtalk-integration\
│   └── ...
├── officecli\                ← 三方 skills（平铺在仓库根）
├── frontend-design\
├── source-command-zcf-git-worktree\
├── setup.cmd                 ← 一键在各 agent 端建立联接
└── README.md
```

判定规则：自建 skill 放 `my-skills\`，下载的三方 skill 放仓库根（两者都必须是含 `SKILL.md` 的目录，setup.cmd 靠这个自动识别）。

## 当前技能清单

| 技能 | 来源 | 描述 |
|------|------|------|
| code-dojo | 自建 | 交互式代码业务逻辑"带练教练" |
| dingtalk-integration | 自建 | 钉钉低代码集成（审批、连接器、连接流、AI 表格）配置陪跑与排错 |
| dingtalk-login | 自建 | 网页系统接入钉钉扫码登录 / 工作台免登 |
| gradio-skill-template | 自建 | Gradio Tab 页面组件模板系统 |
| quarterly-assessment-fill | 自建 | 根据月度计划表汇总填写季度考核表 |
| weread-skills-cli | 自建 | 微信读书 CLI 助手与笔记导出 |
| export-conversation.md | 自建 | 会话导出笔记（非 skill，仅存档） |
| frontend-design | 三方 | 高质量前端界面设计与实现 |
| officecli | 三方 | 用 officecli CLI 创建/检查/修改 Office 文档 |
| source-command-zcf-git-worktree | 三方 | Git worktree 管理 |

## 新机器部署

1. 克隆本仓库到本地磁盘（如 `E:\project\skills`）：

   ```bash
   git clone git@github.com:liumu927/skills.git E:\project\skills
   ```

2. 运行一次（双击或在命令行执行）：

   ```cmd
   setup.cmd
   ```

   脚本会扫描 `my-skills\` 和仓库根下所有含 `SKILL.md` 的目录，在每个 agent 的 `skills\` 目录里逐个建立 junction。新增 agent 工具时，在 `setup.cmd` 的 `for %%D in (...)` 列表里加一项即可。

3. 重启各 agent 工具加载 skills。

## 日常使用

- **新增自建 skill**：在 `my-skills\` 下建目录（含 `SKILL.md`），跑一次 `setup.cmd`，然后 `git commit` + `push`。
- **新增三方 skill**：下载后把 skill 目录放到仓库根（含 `SKILL.md`），跑一次 `setup.cmd`，提交推送。
- **修改 / 删除 skill**：直接改仓库内内容，所有 agent 立即生效；删除后跑一次 `setup.cmd` 清理残留联接（目前需手动删 agent 端对应 junction）。
- 各 agent 的 `skills\` 目录里全是 junction，不要在里面直接创建文件——改到仓库里来。

## 技能开发约定

每个技能遵循以下结构：

```
<skill-name>/
├── SKILL.md          # 技能入口（必需）
├── components/       # 可复用组件（可选）
├── templates/        # 模板文件（可选）
├── scripts/          # 脚本（可选）
└── reference/        # 参考文档（可选）
```
