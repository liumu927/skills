# 使用指南

本文档详细说明如何使用 Gradio Skill 组件模板系统快速开发新的 Tab 页面。

## 目录

1. [快速开始](#快速开始)
2. [开发流程详解](#开发流程详解)
3. [组件使用](#组件使用)
4. [模板定制](#模板定制)
5. [最佳实践](#最佳实践)
6. [常见问题](#常见问题)

---

## 快速开始

### 步骤 1：选择模板

根据你的功能类型选择合适的模板：

| 功能类型 | 模板文件 | 特点 |
|----------|----------|------|
| 推理/测试 | `inference_tab_template.py` | 单次执行、结果展示、下载功能 |
| 训练 | `training_tab_template.py` | 长时间运行、Epoch 显示、补丁预览 |

### 步骤 2：复制模板

```bash
# 推理类 Tab
cp .claude/skills/gradio-skill-template/templates/inference_tab_template.py \
   gradio_refactor/tabs/my_algorithm_inference.py

# 训练类 Tab
cp .claude/skills/gradio-skill-template/templates/training_tab_template.py \
   gradio_refactor/tabs/my_algorithm_train.py
```

### 步骤 3：修改模板

按照文件中的 `TODO` 注释进行修改：

1. **类名和函数名**：将 `MyAlgorithm` 替换为你的算法名称
2. **Tab 标签**：修改 `_get_tab_label()` 或 `gr.Tab()` 中的标签
3. **配置组件**：在 `_build_config_section()` 中添加你的配置组件
4. **结果组件**：在 `_build_result_section()` 中添加结果展示组件
5. **任务逻辑**：在 `_start_task()` 中实现算法调用逻辑

### 步骤 4：注册 Tab

在 `gradio_app_refactored.py` 中注册新 Tab：

```python
# 导入
from gradio_refactor.tabs.my_algorithm_inference import create_my_algorithm_inference_tab

# 在 create_demo() 函数中添加
my_tab, my_load_info = create_my_algorithm_inference_tab()

# 注册页面加载回调
demo.load(
    fn=my_load_info['load_fn'],
    outputs=my_load_info['load_outputs']
)
```

---

## 开发流程详解

### 阶段 1：需求分析（必做！）

**1.1 阅读算法文档**

找到算法的运行命令，分析参数：

```bash
# 示例：纯点云攻击训练命令
python test.py --strategy light-PGD-filterOnce --eps 1.0 --fixedEPS 0.4 \
  --attach_rate 0.5 --cfg_file cfgs/kitti_models/pointrcnn.yaml \
  --ckpt ../checkpoints/pointrcnn_7870.pth --batch_size 1
```

**1.2 创建参数分析表**

| 参数名 | 类型 | 默认值 | 是否必需 | 组件类型 | 组件名称 |
|--------|------|--------|----------|----------|----------|
| `--strategy` | 枚举 | light-PGD-filterOnce | 是 | Dropdown | strategy_dropdown |
| `--eps` | 浮点 | 1.0 | 是 | Number | eps_input |
| `--fixedEPS` | 浮点 | 0.4 | 是 | Number | fixedEPS_input |
| `--attach_rate` | 浮点 | 0.5 | 是 | Number | attach_rate_input |
| `--ckpt` | 文件 | - | 否 | Dropdown+File | detector_weights |
| `--batch_size` | 整数 | 1 | 是 | Number | batch_size |

**1.3 参考现有界面**

查看项目中类似功能的 Tab，参考其布局和交互逻辑：

```bash
# 查看现有 Tab 实现
ls gradio_refactor/tabs/

# 参考命令
# - mc_train.py: 两阶段训练、GIF 预览
# - bimodal_train.py: 双模态、多数据集
# - visible_train.py: 基础训练布局
```

### 阶段 2：扫描预设文件

**2.1 添加扫描方法**

```python
def _scan_checkpoints(self):
    """扫描权重文件"""
    checkpoints = []
    if os.path.exists(self.checkpoints_dir):
        for f in os.listdir(self.checkpoints_dir):
            if f.endswith('.pth') or f.endswith('.pt'):
                checkpoints.append((f, os.path.join(self.checkpoints_dir, f)))
    return checkpoints
```

**2.2 在 build_ui 中使用**

```python
def build_ui(self):
    # 扫描预设文件
    checkpoints = self._scan_checkpoints()
    checkpoint_choices = [name for name, path in checkpoints]
    default_checkpoint = checkpoint_choices[0] if checkpoint_choices else None

    # 创建路径映射字典
    checkpoint_dict = {name: path for name, path in checkpoints}
```

### 阶段 3：构建 UI 组件

**3.1 文件选择组件（标准三列布局）**

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
            value=initial_status,
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

**3.2 数据集目录组件（Dropdown + Textbox + Checkbox）**

用于选择预设数据集目录或自定义路径。

```python
# 扫描数据集
datasets = self._scan_datasets()
dataset_mapping = {name: path for name, path in datasets}
dataset_choices = list(dataset_mapping.keys())
default_dataset_name = dataset_choices[0] if dataset_choices else ""
default_dataset_path = dataset_mapping.get(default_dataset_name, "")

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
        value=default_dataset_path,
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

**参考实现**：`sj_inference.py`、`point_cloud_train.py`

**3.3 数值参数组件**

```python
with gr.Row():
    eps_input = gr.Number(
        label="最大扰动量 (eps)",
        value=1.0,
        info="控制对抗扰动的最大幅度 [0.1-1.0]"
    )
    fixedEPS_input = gr.Number(
        label="固定扰动步长 (fixedEPS)",
        value=0.4,
        info="控制每次迭代的扰动步长 [0.1-1.0]"
    )
    attach_rate_input = gr.Number(
        label="注意力比例 (attach_rate)",
        value=0.5,
        info="注意力机制权重 [0.1-1.0]"
    )
```

### 阶段 4：实现任务逻辑

**4.1 参数解包**

```python
def _start_training(self, *args):
    # 解包参数 - 注意顺序要与 inputs 列表一致
    (dataset_val, class_file_dropdown, class_file_upload,
     detector_dropdown, detector_weights_dropdown, detector_weights_upload,
     batch_size_val, strategy_val, eps_val, fixedEPS_val, attach_rate_val,
     board_name_val, save_path_val) = args
```

**4.2 提取短名称（用于带描述的下拉选项）**

```python
# 从 "light-PGD-filterOnce - 轻量 PGD" 提取 "light-PGD-filterOnce"
strategy_short = strategy_val.split(" - ")[0] if " - " in strategy_val else strategy_val
```

**4.3 文件路径处理（上传优先）**

```python
# 权重文件 - 上传的文件优先
model_weights = None
if detector_weights_upload:
    model_weights = detector_weights_upload
elif detector_weights_dropdown:
    checkpoints = self._scan_checkpoints()
    checkpoint_dict = {name: path for name, path in checkpoints}
    model_weights = checkpoint_dict.get(detector_weights_dropdown)
```

---

## 组件使用

### 文件选择组件 (FileSelector)

用于需要选择预设文件或上传自定义文件的场景。

```python
from .components.skill_components import FileSelector, SelectorConfig

# 创建配置
config = SelectorConfig(
    label="检测器模型",
    choices=[
        ("yolov5x.pt", "/path/to/yolov5x.pt"),
        ("yolov5s.pt", "/path/to/yolov5s.pt")
    ],
    default_value="yolov5x.pt",
    file_types=[".pt", ".pth"],
    info="选择检测器权重文件",
    allow_upload=True,      # 允许上传
    upload_height=130       # 上传组件高度
)

# 构建组件
selector = FileSelector(config)
components = selector.build()

# 组件包含：
# - components['dropdown']: 下拉选择框
# - components['upload']: 文件上传组件（如果 allow_upload=True）
# - components['status']: 状态显示文本框

# 获取当前选择的文件路径
current_path = selector.get_current_path(
    dropdown_value=dropdown_value,
    upload_value=upload_value
)
```

### 目录选择组件 (DirectorySelector)

用于需要选择预设目录或自定义路径的场景。

```python
from .components.skill_components import DirectorySelector

selector = DirectorySelector(
    label="数据集目录",
    choices=[
        ("可见光数据集", "/data/visible"),
        ("红外数据集", "/data/infrared")
    ],
    default_value="可见光数据集",
    info="选择训练数据集",
    allow_custom=True  # 允许自定义输入
)

components = selector.build()

# 组件包含：
# - components['dropdown']: 下拉选择框
# - components['path']: 路径显示/输入框
# - components['custom']: 自定义勾选框（如果 allow_custom=True）
```

---

## 模板定制

### 配置区域布局

推荐使用 `gr.Accordion` 进行分组：

```python
def _build_config_section(self):
    components = {}

    with gr.Accordion("📁 数据配置", open=True):
        # 数据相关配置
        components['data_dir'] = gr.Textbox(...)
        components['data_file'] = gr.File(...)

    with gr.Accordion("🔍 检测器配置", open=True):
        # 检测器相关配置
        components['detector'] = gr.Dropdown(...)
        components['weights'] = gr.File(...)

    with gr.Accordion("⚙️ 参数配置", open=True):
        # 其他参数
        components['param1'] = gr.Number(...)
        components['param2'] = gr.Dropdown(...)

    return components
```

### 结果区域布局

根据输出类型选择合适的展示组件：

```python
def _build_result_section(self):
    components = {}

    # 图片结果 - 使用 Gallery
    components['gallery'] = gr.Gallery(
        label="结果图片",
        columns=3,
        rows=2,
        height="auto"
    )

    # 单张图片 - 使用 Image
    components['image'] = gr.Image(
        label="结果图像",
        type="filepath",
        interactive=False
    )

    # 文本结果 - 使用 Textbox
    components['stats'] = gr.Textbox(
        label="统计信息",
        lines=10,
        interactive=False
    )

    # 下载文件 - 使用 File
    components['download'] = gr.File(
        label="下载结果",
        visible=False
    )

    return components
```

### 任务启动逻辑

```python
def _start_inference(self, *args):
    # 1. 解包参数
    (param1, param2, upload_file, ...) = args

    # 2. 清空日志
    self.log_handler.clear_logs()

    # 3. 处理输入参数
    # 优先使用上传文件，否则使用预设
    if upload_file:
        input_file = upload_file.name if hasattr(upload_file, 'name') else upload_file
    else:
        input_file = self._preset_files.get(param1)

    # 4. 验证必要参数
    if not input_file:
        return ("❌ 请选择输入文件", self.log_handler.get_logs(), gr.update(active=False))

    # 5. 创建配置文件（如需要）
    config_data = {
        'input': input_file,
        'param': param2,
        ...
    }
    config_path = os.path.join(self.project_root, "configs", "temp_config.yaml")
    common_utils.save_yaml_config(config_data, config_path)

    # 6. 构建命令
    script_path = os.path.join(self.src_path, "my_algorithm", "run.py")
    cmd = ["python", script_path, "--config", config_path]

    # 7. 启动进程
    task_id = f"{self.task_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    success, msg = self.task_manager.start_process(
        task_id=task_id,
        cmd=cmd,
        log_callback=self.log_handler.add_log,
        cwd=self.project_root,
        task_type=self.task_type
    )

    if not success:
        return (f"❌ {msg}", self.log_handler.get_logs(), gr.update(active=False))

    # 8. 返回结果
    self.log_handler.add_log(f"输入文件: {input_file}")
    return (f"✅ {msg}", self.log_handler.get_logs(), gr.update(active=True))
```

---

## 最佳实践

### 1. 使用通用回调函数

**项目可复用工具函数**（位于 `gradio_refactor/core/common_utils.py`）：

| 工具函数 | 用途 | 使用场景 |
|----------|------|----------|
| `scan_datasets()` | 扫描训练数据集 | 数据集目录选择 |
| `create_yaml_config()` | 创建 YAML 配置 | 训练前生成配置文件 |
| `save_yaml_config()` | 保存 YAML 配置 | 训练前生成配置文件 |
| `safe_relpath()` | 安全相对路径 | 处理跨驱动器问题 |
| `get_detector_weight_path()` | 获取默认权重路径 | 模型权重选择 |
| `on_weights_upload()` | 权重上传回调 | 权重文件上传状态更新 |
| `update_weight_status()` | 权重状态更新 | 检测器改变时更新状态 |
| `create_dataset_dir_callbacks()` | 数据集目录回调工厂 | 创建数据集目录联动回调 |

```python
from gradio_refactor.core import common_utils

# 权重文件上传回调
weight_file.change(
    fn=lambda file_path, det_name: common_utils.on_weights_upload(
        file_path, det_name, tab_name="my_tab"
    ),
    inputs=[weight_file, detector_name],
    outputs=[weight_status]
)

# 检测器改变时更新权重状态
detector_name.change(
    fn=lambda det_name, file_path: common_utils.update_weight_status(
        det_name, file_path, tab_name="my_tab"
    ),
    inputs=[detector_name, weight_file],
    outputs=[weight_status]
)

# 数据集目录回调
callbacks = common_utils.create_dataset_dir_callbacks(dataset_mapping)
dropdown.change(
    fn=callbacks['update_img_dir'],
    inputs=[dropdown, custom_checkbox],
    outputs=[path_textbox]
)
```

### 2. 日志输出规范

```python
# 使用 LogHandler 添加日志
self.log_handler.add_log("✅ 任务启动成功")
self.log_handler.add_log("⚠️ 警告信息")
self.log_handler.add_log("❌ 错误信息")
self.log_handler.add_log(f"参数: {param1}")

# 不要直接使用 print
# ❌ print("错误")  # 错误做法
```

### 3. 文件路径处理

```python
# 始终使用绝对路径
self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# 使用 os.path.join 拼接路径
config_path = os.path.join(self.project_root, "configs", "temp.yaml")

# 处理跨驱动器问题
relative_path = common_utils.safe_relpath(absolute_path, start=self.project_root)
```

### 4. 错误处理

```python
def _start_inference(self, *args):
    # 验证输入
    if not input_file:
        self.log_handler.add_log("❌ 请选择输入文件")
        return ("❌ 请选择输入文件", self.log_handler.get_logs(), gr.update(active=False))

    if not os.path.exists(input_file):
        self.log_handler.add_log(f"❌ 文件不存在: {input_file}")
        return (f"❌ 文件不存在", self.log_handler.get_logs(), gr.update(active=False))

    # 启动失败处理
    success, msg = self.task_manager.start_process(...)
    if not success:
        self.log_handler.add_log(f"❌ {msg}")
        return (f"❌ {msg}", self.log_handler.get_logs(), gr.update(active=False))
```

---

## 常见问题

### Q: 如何处理文件上传和下拉框选择的优先级？

A: 优先使用上传的文件，如果没有上传则使用下拉框选择：

```python
def get_input_file(upload_value, dropdown_value, preset_mapping):
    if upload_value:
        if isinstance(upload_value, list):
            return upload_value[0] if upload_value else None
        return upload_value
    return preset_mapping.get(dropdown_value)
```

### Q: 如何实现两阶段训练？

A: 创建包装脚本，按顺序执行两个阶段：

```python
wrapper_script = os.path.join(config_dir, "run_two_stage.py")
wrapper_content = f'''
import subprocess
import sys

# 阶段1
result1 = subprocess.run([sys.executable, "stage1.py", ...])

# 阶段2
result2 = subprocess.run([sys.executable, "stage2.py", ...])
'''
with open(wrapper_script, 'w') as f:
    f.write(wrapper_content)

cmd = ["python", wrapper_script]
```

### Q: 如何显示实时训练进度（如 Epoch 信息）？

A: 从日志中解析 Epoch 信息：

```python
def _parse_epoch_info(logs):
    for line in reversed(logs.split('\n')):
        if 'Epoch' in line or 'epoch' in line:
            # 解析格式如 "Epoch 10/100"
            import re
            match = re.search(r'Epoch\s+(\d+)/(\d+)', line)
            if match:
                return f"Epoch {match.group(1)}/{match.group(2)}"
    return None
```

### Q: 如何处理浏览器刷新后恢复状态？

A: 实现 `_load_initial_state` 方法：

```python
def _load_initial_state(self):
    logs = self.log_handler.get_logs()
    is_running = self.task_manager.is_running(task_type=self.task_type)

    status = "进行中... (从之前的会话恢复)" if is_running else "等待开始..."

    # 恢复其他状态（如结果显示）
    results, msg, download = self._check_and_display_results(save_dir)

    return (status, logs, gr.update(active=is_running), results, msg, download)
```

---

## 相关资源

- [组件规格说明](./component-spec.md) - 组件接口详细文档
- [项目通用工具](../../../gradio_refactor/core/common_utils.py) - 通用回调函数
- [现有 Tab 实现](../../../gradio_refactor/tabs/) - 参考现有代码
