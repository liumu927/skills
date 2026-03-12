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

---

## 标准组件布局

### 1. 文件选择组件（Dropdown + Status + File）

用于选择预设文件或上传自定义文件（如权重文件、配置文件）。

```python
with gr.Row():
    with gr.Column(scale=2):
        file_dropdown = gr.Dropdown(
            choices=choices_list,
            label="文件选择",
            value=default_value
        )
        file_status = gr.Textbox(
            label="文件状态",
            value=f"已选择: {default_path}",
            interactive=False,
            lines=2
        )
    file_upload = gr.File(
        label="上传文件（可选）",
        file_types=[".pt", ".pth"],
        type="filepath",
        scale=1
    )
```

**交互逻辑**：上传文件优先于下拉选择。

**参考实现**：`sj_inference.py` - 权重文件选择

---

### 2. 目录组件（Dropdown + Textbox + Checkbox）

用于选择预设数据集目录或自定义路径。

```python
# 扫描数据集
datasets = self._scan_datasets()
dataset_mapping = {name: path for name, path in datasets}
dataset_choices = list(dataset_mapping.keys())
default_dataset_name = dataset_choices[0] if dataset_choices else ""

# 构建组件
with gr.Row():
    dataset_dropdown = gr.Dropdown(
        choices=dataset_choices,
        label="数据集",
        value=default_dataset_name,
        info="选择预设数据集",
        scale=2
    )
    dataset_path = gr.Textbox(
        label="数据集路径",
        value=dataset_mapping.get(default_dataset_name, ""),
        info="勾选自定义后可手动输入路径",
        interactive=False,
        scale=3
    )
    dataset_custom = gr.Checkbox(
        label="自定义路径",
        value=False,
        info="勾选后可手动输入",
        scale=1
    )

# 事件绑定（使用 common_utils）
dataset_callbacks = common_utils.create_dataset_dir_callbacks(dataset_mapping, path_index=0)

dataset_dropdown.change(
    fn=dataset_callbacks['update_img_dir'],
    inputs=[dataset_dropdown, dataset_custom],
    outputs=[dataset_path]
)

dataset_custom.change(
    fn=dataset_callbacks['toggle_img_dir'],
    inputs=[dataset_custom, dataset_dropdown],
    outputs=[dataset_path]
)
```

**交互逻辑**：
- 未勾选"自定义路径"：下拉选择更新 Textbox，Textbox 只读
- 勾选"自定义路径"：Textbox 可编辑，用户可手动输入路径

**参考实现**：`sj_inference.py`、`point_cloud_train.py` - 数据集目录选择

---

### 不要使用 Slider

Slider 精度受限，用户无法输入精确值。使用 `gr.Number()` 代替。

---

### 3. 对比展示组件（统一 Gallery）

用于展示标准评估 vs 对抗评估的对比结果，使用**单一 Gallery 组件**实现两列对比布局。

```python
# ❌ 错误：使用两个独立的 Gallery
with gr.Row():
    with gr.Column():
        standard_gallery = gr.Gallery(label="标准评估")
    with gr.Column():
        adv_gallery = gr.Gallery(label="对抗评估")

# ✅ 正确：使用单一 Gallery，两列多行
gr.Markdown("**预测结果对比**（左列: 标准 | 右列: 对抗）")
pred_gallery = gr.Gallery(
    label="预测结果对比",
    columns=2,
    rows=5,
    height="auto",
    object_fit="contain"
)
```

**数据合并逻辑**：将两组图片交替排列，确保左列显示标准、右列显示对抗。**每张图片必须带标签**，格式为 `(路径, "标准|文件名")` 或 `(路径, "对抗|文件名")`。

```python
# 收集图片时添加标签：(路径, "类型|文件名")
standard_images = [(os.path.join(dir_path, f), f"标准|{f}") for f in standard_png_files]
adv_images = [(os.path.join(dir_path, f), f"对抗|{f}") for f in adv_png_files]

# 合并图片为对比列表：[(std1, "标准|xxx"), (adv1, "对抗|xxx"), ...]
max_images = 10
merged_images = []
for i in range(max_images):
    if i < len(standard_images):
        merged_images.append(standard_images[i])
    if i < len(adv_images):
        merged_images.append(adv_images[i])

return merged_images  # 返回给单一 Gallery，每张图片下方显示标签
```

**参考实现**：`point_cloud_inference.py` - 预测结果对比展示

---

## 常见错误与注意事项

### 1. 必须使用中文

所有界面文本、日志消息、错误提示、回调函数返回值都必须使用中文。

```python
# ❌ 错误
return "No config file selected"
self.log_handler.add_log("Task started")

# ✅ 正确
return "未选择配置文件"
self.log_handler.add_log("任务已启动")
```

### 2. 事件绑定 outputs 数量必须匹配

回调函数的返回值数量必须与 `outputs` 列表长度一致，否则会报 `ValueError`。

```python
# ❌ 错误：返回 8 个值但 outputs 有 9 个
outputs=[status, logs, timer, standard_status, gallery1, gallery2, img1, img2, stats]
return (status, logs, gr.update(active=True), standard_status, images1, images2, img1, img2)  # 少了 stats

# ✅ 正确：数量一致
outputs=[status, logs, timer, standard_status, gallery, img1, img2, stats]
return (status, logs, gr.update(active=True), standard_status, images, img1, img2, stats)
```

### 3. Accordion 不能作为 output 组件

Accordion 是布局组件，不能作为回调函数的输出。

```python
# ❌ 错误：Accordion 不能作为 output
outputs=[status, logs, download_accordion]

# ✅ 正确：使用 File 组件作为下载输出
outputs=[status, logs, download_file]
```

### 4. 清空日志必须同时清空评估结果

`_clear_logs` 方法应该清空所有结果显示组件（Gallery、Image、Textbox、File），并设置标志防止刷新时重新加载。

```python
def __init__(self):
    # ...
    self._results_cleared = False  # 标记结果是否被清空

def _clear_logs(self):
    """清空日志和评估结果"""
    self.log_handler.clear_logs()
    self._task_completed = False
    self._results_cleared = True  # 标记已清空，防止刷新时重新加载
    return (
        "日志已清空",           # status_text
        "",                     # output (日志)
        "等待开始...",          # status
        [],                     # gallery (清空图片)
        None,                   # image (清空)
        "",                     # stats (清空统计)
        gr.update(value=None, visible=False)  # file (隐藏下载)
    )

def _start_task(self, *args):
    """启动任务时重置清空标志"""
    self._results_cleared = False  # 允许显示结果
    # ...

def _refresh_logs(self):
    """刷新时检查清空标志"""
    if self._results_cleared:
        return (  # 返回空结果
            "评估已停止", self.log_handler.get_logs(),
            "等待开始评估...",
            [], None, None, "",
            gr.update(value=None, visible=False)
        )
    # 正常刷新逻辑...
```

### 5. 下载组件使用 File 而非按钮

下载功能直接使用 `gr.File()` 组件，不需要单独的"创建下载包"按钮。评估完成后自动生成并显示。

```python
# ❌ 错误：使用 Accordion + 按钮
with gr.Accordion("下载结果", visible=False) as download_accordion:
    download_btn = gr.Button("创建下载包")
    download_file = gr.File()

# ✅ 正确：直接使用 File 组件
download_file = gr.File(
    label="📦 下载完整结果",
    visible=False  # 初始隐藏，完成后自动显示
)

# 更新下载组件
return gr.update(value=zip_path, visible=True)
```

### 6. 路径拼接避免多层嵌套

使用 `os.path.join()` 时注意不要多套一层目录。

```python
# ❌ 错误：多套了 tools 层
self.output_base_dir = os.path.join(self.radar_tools_dir, "output")

# ✅ 正确：直接使用目标目录
self.output_base_dir = os.path.join(self.project_root, "src", "radar", "OpenPCDet-202309-adv", "output")
```

### 参考现有界面

```
gradio_refactor/tabs/
├── mc_train.py        # 两阶段训练、GIF 预览
├── bimodal_train.py   # 多数据集选择
├── sj_inference.py    # 文件选择、数据集目录组件参考
├── point_cloud_train.py # 数据集目录组件参考
└── visible_train.py   # 基础训练布局
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

### 启动前清理旧数据

**重要**：在每次评估/训练/推理任务启动前，必须清理旧的结果数据，避免界面一开始时展示旧数据。

使用 `common_utils.clear_old_inference_data()` 函数：

```python
def _start_task(self, *args):
    """启动任务"""
    # ...参数处理...

    # 清理旧的结果数据（在启动任务前）
    self.log_handler.add_log("🗑️ 清理旧数据: 结果目录")
    common_utils.clear_old_inference_data(self.result_dir, self.log_handler.add_log)

    # 创建必要的目录
    os.makedirs(self.result_dir, exist_ok=True)

    # 启动任务...
```

**典型使用场景**：

| Tab | 清理目录 | 参考代码 |
|-----|----------|----------|
| 推理 Tab | 推理结果保存目录 | `sj_inference.py:411` |
| 训练 Tab | 补丁保存目录 | `sj_train.py:254` |
| 迷彩训练 | textures/gif 目录 | `mc_train.py:192-193` |
| 迷彩推理 | 生成/评估输出目录 | `mc_inference.py:283-285` |
| 点云评估 | 对抗评估结果目录 | `point_cloud_inference.py` |

**函数签名**：

```python
def clear_old_inference_data(save_dir, log_callback=None):
    """清理旧的推理数据

    Args:
        save_dir: 要清理的结果目录路径
        log_callback: 日志回调函数（可选），用于记录清理操作

    Returns:
        bool: 是否成功清理（True表示成功或目录不存在，False表示清理失败）
    """
```

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
