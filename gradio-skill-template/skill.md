---
name: "gradio-skill-template"
description: "用于快速开发 Gradio Tab 页面的组件模板系统。当用户需要创建新的 Gradio Tab、开发算法推理/训练界面、设计 Tab 布局、实现文件选择器或目录选择器时使用此技能。"
---

# Gradio Skill 组件模板系统

本技能提供**可复用、支持渐进增强**的通用 Skill 组件，用于快速新增对接不同算法的 Tab 页面。

## 核心特性

- **组件复用**：统一的文件选择、目录选择、状态显示组件
- **基类抽象**：提供 Tab 基类，减少重复代码
- **完整模板**：包含推理 Tab 和训练 Tab 的完整示例
- **遵循规范**：严格遵循项目既有代码风格和功能复用原则

## 什么时候使用此技能

- 需要创建新的 Gradio Tab 页面时
- 需要开发算法推理/训练界面时
- 需要设计 Tab 布局时
- 需要实现文件选择器或目录选择器时

---

## 目录结构

```
.claude/skills/gradio-skill-template/
├── skill.md                           # 主入口（本文件）
├── components/                        # 可复用组件
│   ├── skill_components.py            # 通用组件工厂
│   └── base_skill_tab.py              # Tab 抽象基类
├── templates/                         # 完整模板
│   ├── inference_tab_template.py      # 推理 Tab 模板
│   └── training_tab_template.py       # 训练 Tab 模板
└── reference/                         # 参考文档
    ├── usage-guide.md                 # 使用指南（详细）
    ├── component-spec.md              # 组件规格说明
    └── troubleshooting.md             # 常见问题排查
```

---

## 快速开始

### 1. 选择模板类型

| 功能类型 | 模板文件 | 特点 |
|----------|----------|------|
| 推理/测试 | `templates/inference_tab_template.py` | 单次执行、结果展示、下载功能 |
| 训练 | `templates/training_tab_template.py` | 长时间运行、Epoch 显示、补丁预览 |

### 2. 复制模板到目标位置

```bash
cp .claude/skills/gradio-skill-template/templates/inference_tab_template.py \
   gradio_refactor/tabs/my_inference.py
```

### 3. 修改模板

按照模板中的 `TODO` 注释修改：类名、配置组件、结果组件、任务逻辑。

### 4. 注册 Tab

在 `gradio_app_refactored.py` 中导入并注册。

---

## 界面设计原则

### 参数到组件映射

| 参数类型 | 推荐组件 | 示例 |
|----------|----------|------|
| 数值参数 | `gr.Number()` | `eps`, `learning_rate` |
| 整数参数 | `gr.Number(precision=0)` | `batch_size`, `epochs` |
| 枚举参数 | `gr.Dropdown()` | `strategy`, `model_type` |
| 文件路径 | `gr.Dropdown()` + `gr.File()` | 权重文件 |
| 目录路径 | `gr.Textbox()` | 保存路径 |
| 布尔参数 | `gr.Checkbox()` | `enable_xxx` |

### 文件选择标准布局

```python
with gr.Row():
    with gr.Column(scale=2):
        file_dropdown = gr.Dropdown(choices=choices_list, label="文件选择")
        file_status = gr.Textbox(label="文件状态", interactive=False, lines=2)
    file_upload = gr.File(label="上传文件（可选）", file_types=[".pt"], type="filepath", scale=1)
```

**交互逻辑**：上传文件优先于下拉选择。

### 不要使用 Slider

Slider 精度受限，用户无法输入精确值。使用 `gr.Number()` 代替。

### 参考现有界面

```
gradio_refactor/tabs/
├── mc_train.py      # 两阶段训练、GIF 预览
├── bimodal_train.py # 多数据集选择
└── visible_train.py # 基础训练布局
```

---

## 命名规范

1. **类名**：`XxxTab`（如 `McInferenceTab`）
2. **工厂函数**：`create_xxx_tab`（如 `create_mc_inference_tab`）
3. **task_type**：`xxx_inference` 或 `xxx_train`

---

## 代码复用规范

### 必须使用的通用模块

| 模块 | 用途 | 导入路径 |
|------|------|----------|
| LogHandler | 日志管理 | `gradio_refactor.core.log_handler` |
| GlobalTaskManager | 任务管理 | `gradio_refactor.core.task_manager` |
| common_utils | 通用回调函数 | `gradio_refactor.core.common_utils` |

### 禁止重复实现

- 文件上传回调逻辑
- 目录选择回调逻辑
- 权重状态更新逻辑
- 直接 print 日志（使用 LogHandler）

---

## 注意事项

### 文件路径处理

- 始终使用绝对路径
- 使用 `os.path.join()` 拼接路径

### 日志输出

- 使用 `self.log_handler.add_log()` 添加日志
- 重要操作添加 ✅/❌/⚠️ 图标

### 错误处理

- 启动前验证必要参数
- 友好的错误提示

---

## 参考文档

| 文档 | 内容 |
|------|------|
| **[使用指南](./reference/usage-guide.md)** | 详细开发流程、组件使用、最佳实践 |
| **[组件规格说明](./reference/component-spec.md)** | 组件接口文档 |
| **[常见问题排查](./reference/troubleshooting.md)** | Unicode 乱码、Python 环境配置、特殊处理 |
