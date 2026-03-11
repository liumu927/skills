# 组件规格说明

本文档详细说明 Gradio Skill 组件模板系统中各组件的接口规范。

## 目录

1. [数据类](#数据类)
2. [文件选择组件](#文件选择组件-fileselector)
3. [目录选择组件](#目录选择组件-directoryselector)
4. [Tab 基类](#tab-基类-baseskilltab)
5. [工具函数](#工具函数)

---

## 数据类

### FileChoice

文件选项数据类，用于表示单个文件选项。

```python
@dataclass
class FileChoice:
    name: str          # 显示名称
    path: str          # 实际路径
    size: int = 0      # 文件大小（字节）

    @property
    def size_str(self) -> str:
        """返回格式化的文件大小字符串"""
        ...
```

### SelectorConfig

选择器配置数据类，用于配置文件选择组件。

```python
@dataclass
class SelectorConfig:
    label: str                          # 组件标签
    choices: List[Tuple[str, str]]      # 选项列表 [(显示名称, 路径), ...]
    default_value: Optional[str] = None # 默认选中的值
    file_types: List[str] = None        # 允许的文件类型 [".pt", ".npy", ...]
    info: str = ""                      # 提示信息
    allow_upload: bool = True           # 是否允许上传
    upload_height: int = 130            # 上传组件高度
    status_lines: int = 2               # 状态文本框行数
```

---

## 文件选择组件 (FileSelector)

通用文件选择组件，支持下拉框选择和文件上传两种方式。

### 构造函数

```python
FileSelector(config: SelectorConfig)
```

**参数:**
- `config`: 选择器配置对象

### 方法

#### build()

构建组件并返回组件字典。

```python
def build(self) -> Dict[str, gr.components.Component]
```

**返回:**
- `dict`: 包含以下组件的字典
  - `dropdown`: 下拉选择框 (`gr.Dropdown`)
  - `upload`: 文件上传组件 (`gr.File`)，如果 `allow_upload=True`
  - `status`: 状态显示文本框 (`gr.Textbox`)

#### get_current_path()

获取当前选择的文件路径。

```python
def get_current_path(self, dropdown_value: str, upload_value: Any) -> Optional[str]
```

**参数:**
- `dropdown_value`: 下拉框当前值
- `upload_value`: 上传组件当前值

**返回:**
- 当前选择的文件路径，如果未选择则返回 `None`

### 使用示例

```python
config = SelectorConfig(
    label="检测器模型",
    choices=[("yolov5x.pt", "/path/to/yolov5x.pt")],
    default_value="yolov5x.pt",
    file_types=[".pt", ".pth"]
)

selector = FileSelector(config)
components = selector.build()

# 获取当前路径
current_path = selector.get_current_path(
    dropdown_value=components['dropdown'].value,
    upload_value=components['upload'].value if 'upload' in components else None
)
```

---

## 目录选择组件 (DirectorySelector)

通用目录选择组件，支持下拉框选择和自定义路径输入。

### 构造函数

```python
DirectorySelector(
    label: str,
    choices: List[Tuple[str, str]],
    default_value: Optional[str] = None,
    info: str = "",
    allow_custom: bool = True
)
```

**参数:**
- `label`: 组件标签
- `choices`: 选项列表 `[(显示名称, 路径), ...]`
- `default_value`: 默认选中的值
- `info`: 提示信息
- `allow_custom`: 是否允许自定义路径输入

### 方法

#### build()

构建组件并返回组件字典。

```python
def build(self) -> Dict[str, gr.components.Component]
```

**返回:**
- `dict`: 包含以下组件的字典
  - `dropdown`: 下拉选择框 (`gr.Dropdown`)
  - `path`: 路径显示/输入框 (`gr.Textbox`)
  - `custom`: 自定义勾选框 (`gr.Checkbox`)，如果 `allow_custom=True`

#### get_current_path()

获取当前选择的目录路径。

```python
def get_current_path(self, dropdown_value: str) -> Optional[str]
```

---

## Tab 基类 (BaseSkillTab)

Skill Tab 抽象基类，提供 Tab 的基础结构。

### 构造函数

```python
BaseSkillTab(
    tab_id: str,
    task_type: str,
    project_root: str = None
)
```

**参数:**
- `tab_id`: Tab 标识符（用于日志文件命名）
- `task_type`: 任务类型（用于任务管理器）
- `project_root`: 项目根目录（自动推断）

### 抽象方法（子类必须实现）

#### _get_tab_label()

返回 Tab 标签（带 emoji）。

```python
@abstractmethod
def _get_tab_label(self) -> str
```

**返回:**
- Tab 标签字符串，如 `"🚀 我的技能"`

#### _build_config_section()

构建配置区域（左侧）。

```python
@abstractmethod
def _build_config_section(self) -> Dict[str, gr.components.Component]
```

**返回:**
- 组件字典

#### _build_result_section()

构建结果区域（右侧下方）。

```python
@abstractmethod
def _build_result_section(self) -> Dict[str, gr.components.Component]
```

**返回:**
- 组件字典

#### _start_task()

启动任务。

```python
@abstractmethod
def _start_task(self, *args) -> Tuple
```

**参数:**
- `*args`: 从 `_get_task_inputs()` 获取的输入值

**返回:**
- 输出元组，对应 `_get_task_outputs()`

### 可选重写方法

#### _get_task_inputs()

获取任务输入组件列表。

```python
def _get_task_inputs(self) -> List[gr.components.Component]
```

#### _get_task_outputs()

获取任务输出组件列表。

```python
def _get_task_outputs(self) -> List[gr.components.Component]
```

#### _on_task_stop()

任务停止时的回调。

```python
def _on_task_stop(self) -> Tuple
```

#### _on_logs_refresh()

日志刷新时的回调。

```python
def _on_logs_refresh(self) -> Tuple
```

#### _on_logs_clear()

日志清空时的回调。

```python
def _on_logs_clear(self) -> Tuple
```

#### _on_auto_refresh()

定时器自动刷新回调。

```python
def _on_auto_refresh(self, auto_refresh_enabled: bool) -> Tuple
```

#### _load_initial_state()

页面加载时恢复状态。

```python
def _load_initial_state(self) -> Tuple
```

### 辅助方法

#### _start_process()

启动子进程。

```python
def _start_process(
    self,
    cmd: List[str],
    cwd: str = None,
    extra_logs: List[str] = None
) -> Tuple[bool, str]
```

#### _is_running()

检查是否有任务在运行。

```python
def _is_running(self) -> bool
```

#### _add_log()

添加日志。

```python
def _add_log(self, message: str)
```

#### _get_logs()

获取日志。

```python
def _get_logs(self) -> str
```

#### _clear_logs()

清空日志。

```python
def _clear_logs(self)
```

---

## 工具函数

### scan_files_by_extension()

扫描目录中指定扩展名的文件。

```python
def scan_files_by_extension(
    directory: str,
    extensions: List[str],
    label_prefix: str = ""
) -> List[Tuple[str, str]]
```

**参数:**
- `directory`: 要扫描的目录
- `extensions`: 文件扩展名列表 `[".pt", ".npy", ...]`
- `label_prefix`: 标签前缀

**返回:**
- `[(显示名称, 文件路径), ...]`

### create_file_selector_with_status()

创建带状态显示的文件选择组件（简化工厂函数）。

```python
def create_file_selector_with_status(
    label: str,
    choices: List[Tuple[str, str]],
    default_value: Optional[str] = None,
    file_types: List[str] = None,
    info: str = "",
    allow_upload: bool = True,
    upload_height: int = 130
) -> Tuple[gr.Dropdown, gr.File, gr.Textbox, FileSelector]
```

**返回:**
- `(dropdown, upload, status, selector)`

---

## 状态显示规范

### 文件选择组件状态

| 状态 | 显示格式 | 示例 |
|------|----------|------|
| 未选择 | `未选择文件` | - |
| 下拉框选择 | `当前使用: {文件名} ({大小})` | `当前使用: yolov5x.pt (89.2 MB)` |
| 上传文件 | `已上传: {文件名} ({大小})` | `已上传: custom.pt (45.1 MB)` |

### 目录选择组件状态

| 状态 | 显示格式 | 示例 |
|------|----------|------|
| 未选择 | `未选择目录` | - |
| 下拉框选择 | 显示路径在路径输入框 | `/data/visible` |
| 自定义 | 显示自定义路径 | `/custom/path` |

### 任务状态

| 状态 | 显示格式 |
|------|----------|
| 等待开始 | `等待开始{任务类型}...` |
| 进行中 | `{任务类型}进行中...` |
| 从会话恢复 | `{任务类型}进行中... (从之前的会话恢复)` |
| 已停止 | `{任务类型}已停止` |

---

## 事件绑定规范

### 控制按钮

```python
# 开始按钮
start_btn.click(
    fn=self._start_task,
    inputs=[...],      # 输入组件列表
    outputs=[...]      # 输出组件列表（通常包含 timer）
)

# 停止按钮
stop_btn.click(
    fn=self._on_task_stop,
    outputs=[...]      # 输出组件列表
)

# 刷新按钮
refresh_btn.click(
    fn=self._on_logs_refresh,
    outputs=[...]
)

# 清空按钮
clear_btn.click(
    fn=self._on_logs_clear,
    outputs=[...]      # 通常包含 timer 以停止自动刷新
)

# 定时器
timer.tick(
    fn=self._on_auto_refresh,
    inputs=[auto_refresh_checkbox],
    outputs=[...]
)
```

### 页面加载

```python
load_info = {
    'load_fn': self._load_initial_state,
    'load_outputs': [...]  # 与 _load_initial_state 返回值对应
}

# 在主应用中注册
demo.load(
    fn=load_info['load_fn'],
    outputs=load_info['load_outputs']
)
```

---

## 更新日志

| 日期 | 版本 | 更新内容 |
|------|------|----------|
| 2026-03-03 | 1.0.0 | 初始版本 |
