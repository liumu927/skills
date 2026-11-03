---
name: skills-manager
description: 管理 E:\project\skills 统一技能仓库：新增/修改/删除 skill、区分自建与三方、运行 setup.cmd 建立联接、git 提交推送。当用户要求新增技能、安装三方技能、整理/同步/管理 skills，或询问技能仓库在哪、setup.cmd 是什么时使用。
---

# Skills 统一技能仓库管理

本技能的实体就存放在统一技能仓库内，各 agent 都通过 junction 看到它。

## 仓库位置（写死，勿凭记忆猜路径）

- 仓库根：`E:\project\skills`（git 仓库，remote: `git@github.com:liumu927/skills.git`）
- 自建技能：`E:\project\skills\my-skills\<skill>\`
- 三方（下载）技能：`E:\project\skills\download\<skill>\`
- 部署脚本：`E:\project\skills\setup.cmd`（用绝对路径执行，从任何工作目录都可以）

若 E 盘路径将来变化，可由本技能自身位置反推：本 SKILL.md 的物理路径的仓库根就是它。setup.cmd 挪了位置同理——它永远在仓库根。

## 机制速览

各 agent 的 skills 目录（`~\.claude\skills`、`~\.agents\skills`、`~\.zcode\skills`）里是逐 skill 的 NTFS junction，指向本仓库对应目录：

- **改内容**：实时生效，无需任何同步动作（已开的 agent 会话需开新会话刷新清单）。
- **结构变化**（新增/删除/挪动 skill 目录）：跑一次 `setup.cmd` 补建/清理联接；脚本幂等，可反复跑，会自动修复断链。
- git 管仓库内容；agent 端联接是 `setup.cmd` 在本机生成的状态，新机器 clone 后跑一次即恢复。

## 标准流程

**新增自建技能**：
1. 在 `E:\project\skills\my-skills\` 下建 `<skill-name>\` 目录，必须含 `SKILL.md`（frontmatter 带 `name` 和 `description`，description 决定各 agent 的触发时机）。
2. 执行 `cmd /c E:\project\skills\setup.cmd`。
3. `git -C E:\project\skills add -A && git -C E:\project\skills commit && git -C E:\project\skills push`。

**新增三方技能**：
1. 下载后把 skill 目录放入 `E:\project\skills\download\`，必须含 `SKILL.md`。
2. 若目录自带 `.git`：先询问用户——默认删除内嵌 `.git` 作为普通目录纳入管理（上游仓库历史不丢），或改用 git submodule。
3. 执行 `cmd /c E:\project\skills\setup.cmd`，然后提交推送（同上）。

**修改/删除技能**：直接在仓库内改/删；删除或挪动后跑一次 `setup.cmd` 自动清理断链，再提交推送。

## 禁止事项

- 不要在 agent 端联接目录（`~\.claude\skills` 等）里直接创建文件——一律写到 `E:\project\skills` 仓库里，否则 git 管不到。
- 两个来源目录不可混放：自建放 `my-skills\`，三方放 `download\`。
- 非技能的散文件（如笔记）不放 skill 目录里，避免被当成技能联接出去。
