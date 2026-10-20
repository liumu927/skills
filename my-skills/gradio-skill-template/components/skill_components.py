# components/skill_components.py
"""
通用 Skill 组件工厂模块
提供可复用的 Gradio 组件，支持渐进增强

核心交互逻辑：
- 未上传文件时：界面显示「当前使用：下拉框选中的文件名」
- 已上传文件时：界面显示「已上传：文件名（文件大小）」
- 所有场景下保证界面样式统一

使用方式：
  将此文件复制到 gradio_refactor/core/ 目录下使用
"""

import os
import gradio as gr
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass


@dataclass
class FileChoice:
    """文件选项数据类"""
    name: str          # 显示名称
    path: str          # 实际路径
    size: int = 0      # 文件大小（字节）

    @property
    def size_str(self) -> str:
        """返回格式化的文件大小字符串"""
        if self.size < 1024:
            return f"{self.size} B"
        elif self.size < 1024 * 1024:
            return f"{self.size / 1024:.1f} KB"
        else:
            return f"{self.size / (1024 * 1024):.1f} MB"


@dataclass
class SelectorConfig:
    """选择器配置数据类"""
    label: str                          # 组件标签
    choices: List[Tuple[str, str]]      # 选项列表 [(显示名称, 路径), ...]
    default_value: Optional[str] = None # 默认选中的值
    file_types: List[str] = None        # 允许的文件类型 [".pt", ".npy", ...]
    info: str = ""                      # 提示信息
    allow_upload: bool = True           # 是否允许上传
    upload_height: int = 130            # 上传组件高度
    status_lines: int = 2               # 状态文本框行数


class FileSelector:
    """
    通用文件选择组件

    支持两种选择方式：
    1. 下拉框选择预设文件
    2. 上传自定义文件

    自动处理状态显示：
    - 未上传：显示「当前使用：下拉框选中的文件名」
    - 已上传：显示「已上传：文件名（文件大小）」

    使用示例：
    ```python
    selector = FileSelector(
        config=SelectorConfig(
            label="检测器模型",
            choices=[("yolov5x.pt", "/path/to/yolov5x.pt")],
            default_value="yolov5x.pt",
            file_types=[".pt", ".pth"]
        )
    )
    components = selector.build()
    # 获取当前选择的文件路径
    current_path = selector.get_current_path(dropdown_value, upload_value)
    ```
    """

    def __init__(self, config: SelectorConfig):
        self.config = config
        self._choice_map: Dict[str, str] = {}
        self._build_choice_map()

    def _build_choice_map(self):
        """构建选项名称到路径的映射"""
        self._choice_map = {name: path for name, path in self.config.choices}

    def _get_file_size_str(self, path: str) -> str:
        """获取文件大小的格式化字符串"""
        try:
            size = os.path.getsize(path)
            if size < 1024:
                return f"{size} B"
            elif size < 1024 * 1024:
                return f"{size / 1024:.1f} KB"
            else:
                return f"{size / (1024 * 1024):.1f} MB"
        except:
            return "未知大小"

    def _get_initial_status(self) -> str:
        """获取初始状态文本"""
        if self.config.default_value and self.config.default_value in self._choice_map:
            path = self._choice_map[self.config.default_value]
            size_str = self._get_file_size_str(path)
            return f"当前使用: {self.config.default_value} ({size_str})"
        return "未选择文件"

    def _on_dropdown_change(self, dropdown_value: str, upload_value: Any) -> str:
        """下拉框值改变时的回调"""
        # 如果有上传文件，优先显示上传文件信息
        if upload_value:
            return self._format_upload_status(upload_value)

        # 显示下拉框选择的预设文件
        if dropdown_value and dropdown_value in self._choice_map:
            path = self._choice_map[dropdown_value]
            size_str = self._get_file_size_str(path)
            return f"当前使用: {dropdown_value} ({size_str})"

        return "未选择文件"

    def _on_upload_change(self, upload_value: Any, dropdown_value: str) -> str:
        """上传文件改变时的回调"""
        if upload_value:
            return self._format_upload_status(upload_value)

        # 没有上传文件，回退到下拉框选择
        return self._on_dropdown_change(dropdown_value, None)

    def _format_upload_status(self, upload_value: Any) -> str:
        """格式化上传文件状态"""
        if upload_value is None:
            return "未选择文件"

        # 处理不同的上传值类型
        if isinstance(upload_value, list):
            if not upload_value:
                return "未选择文件"
            upload_value = upload_value[0]

        # 获取文件路径
        if hasattr(upload_value, 'name'):
            file_path = upload_value.name
        else:
            file_path = str(upload_value)

        # 获取文件名和大小
        file_name = os.path.basename(file_path)
        size_str = self._get_file_size_str(file_path)

        return f"已上传: {file_name} ({size_str})"

    def build(self) -> Dict[str, gr.components.Component]:
        """
        构建组件

        Returns:
            dict: 包含以下组件的字典
                - dropdown: 下拉选择框
                - upload: 文件上传组件（可选）
                - status: 状态显示文本框
        """
        components = {}

        with gr.Row():
            # 下拉框
            choices = [name for name, path in self.config.choices]
            components['dropdown'] = gr.Dropdown(
                choices=choices,
                label=self.config.label,
                value=self.config.default_value,
                info=self.config.info,
                scale=2
            )

            # 状态显示
            components['status'] = gr.Textbox(
                label=f"{self.config.label}状态",
                value=self._get_initial_status(),
                interactive=False,
                lines=self.config.status_lines,
                info="显示当前使用的文件" + ("，上传后将覆盖预设" if self.config.allow_upload else ""),
                scale=2
            )

            # 上传组件（可选）
            if self.config.allow_upload:
                components['upload'] = gr.File(
                    label=f"上传{self.config.label}（可选）",
                    file_types=self.config.file_types,
                    file_count="single",
                    type="filepath",
                    height=self.config.upload_height,
                    scale=1
                )

        # 绑定事件
        if self.config.allow_upload:
            components['dropdown'].change(
                fn=self._on_dropdown_change,
                inputs=[components['dropdown'], components['upload']],
                outputs=[components['status']]
            )
            components['upload'].change(
                fn=self._on_upload_change,
                inputs=[components['upload'], components['dropdown']],
                outputs=[components['status']]
            )

        return components

    def get_current_path(self, dropdown_value: str, upload_value: Any) -> Optional[str]:
        """
        获取当前选择的文件路径

        Args:
            dropdown_value: 下拉框当前值
            upload_value: 上传组件当前值

        Returns:
            当前选择的文件路径，如果未选择则返回 None
        """
        # 优先使用上传的文件
        if upload_value:
            if isinstance(upload_value, list):
                if upload_value:
                    upload_value = upload_value[0]
                else:
                    upload_value = None

            if upload_value:
                if hasattr(upload_value, 'name'):
                    return upload_value.name
                return str(upload_value)

        # 使用下拉框选择的预设文件
        if dropdown_value and dropdown_value in self._choice_map:
            return self._choice_map[dropdown_value]

        return None


class DirectorySelector:
    """
    通用目录选择组件

    支持两种选择方式：
    1. 下拉框选择预设目录
    2. 自定义路径输入

    使用示例：
    ```python
    selector = DirectorySelector(
        label="数据集目录",
        choices=[("可见光数据集", "/path/to/visible"), ("红外数据集", "/path/to/infrared")],
        default_value="可见光数据集"
    )
    components = selector.build()
    ```
    """

    def __init__(
        self,
        label: str,
        choices: List[Tuple[str, str]],
        default_value: Optional[str] = None,
        info: str = "",
        allow_custom: bool = True
    ):
        self.label = label
        self.choices = choices
        self.default_value = default_value or (choices[0][0] if choices else None)
        self.info = info
        self.allow_custom = allow_custom
        self._choice_map: Dict[str, str] = {name: path for name, path in choices}

    def build(self) -> Dict[str, gr.components.Component]:
        """
        构建组件

        Returns:
            dict: 包含以下组件的字典
                - dropdown: 下拉选择框
                - path: 路径显示/输入框
                - custom: 自定义勾选框（可选）
        """
        components = {}

        choice_names = [name for name, path in self.choices]
        default_path = self._choice_map.get(self.default_value, "")

        with gr.Row():
            components['dropdown'] = gr.Dropdown(
                choices=choice_names,
                label=self.label,
                value=self.default_value,
                info=self.info,
                scale=2
            )

            components['path'] = gr.Textbox(
                label=f"自定义{self.label}",
                value=default_path,
                info=f"{self.label}的绝对路径" + ("（勾选自定义后可手动输入）" if self.allow_custom else ""),
                interactive=False,
                scale=3
            )

            if self.allow_custom:
                components['custom'] = gr.Checkbox(
                    label="自定义路径",
                    value=False,
                    info="勾选后可手动输入路径",
                    scale=1
                )

        # 绑定事件
        def on_dropdown_change(dropdown_value: str, custom_enabled: bool):
            if not custom_enabled:
                if dropdown_value in self._choice_map:
                    return gr.update(value=self._choice_map[dropdown_value], interactive=False)
                return gr.update(value=dropdown_value, interactive=False)
            return gr.update()

        def on_custom_toggle(custom_enabled: bool, dropdown_value: str):
            if custom_enabled:
                return gr.update(interactive=True)
            else:
                if dropdown_value in self._choice_map:
                    return gr.update(value=self._choice_map[dropdown_value], interactive=False)
                return gr.update(value=dropdown_value, interactive=False)

        components['dropdown'].change(
            fn=on_dropdown_change,
            inputs=[components['dropdown'], components.get('custom', gr.State(False))],
            outputs=[components['path']]
        )

        if self.allow_custom:
            components['custom'].change(
                fn=on_custom_toggle,
                inputs=[components['custom'], components['dropdown']],
                outputs=[components['path']]
            )

        return components

    def get_current_path(self, dropdown_value: str) -> Optional[str]:
        """获取当前选择的目录路径"""
        if dropdown_value and dropdown_value in self._choice_map:
            return self._choice_map[dropdown_value]
        return dropdown_value


class SkillTabBuilder:
    """
    Skill Tab 构建器

    提供构建 Skill Tab 的通用方法和布局

    使用示例：
    ```python
    builder = SkillTabBuilder(
        tab_name="my_skill",
        task_type="my_skill_inference"
    )

    # 构建左侧配置区域
    with builder.config_column():
        # 添加配置组件
        pass

    # 构建右侧执行区域
    with builder.execution_column():
        # 添加执行组件
        pass
    ```
    """

    def __init__(
        self,
        tab_name: str,
        task_type: str,
        project_root: str,
        log_handler,
        task_manager
    ):
        self.tab_name = tab_name
        self.task_type = task_type
        self.project_root = project_root
        self.log_handler = log_handler
        self.task_manager = task_manager

    def create_standard_buttons(self) -> Dict[str, gr.Button]:
        """创建标准控制按钮"""
        with gr.Row():
            buttons = {
                'start': gr.Button("🚀 开始", variant="primary", size="lg"),
                'stop': gr.Button("⏹️ 停止", variant="secondary", size="lg"),
                'refresh': gr.Button("🔄 刷新日志", variant="secondary"),
                'clear': gr.Button("🗑️ 清空日志", variant="secondary")
            }
        return buttons

    def create_standard_status(self, initial_value: str = "等待开始...") -> gr.Textbox:
        """创建标准状态显示"""
        return gr.Textbox(
            label=f"{self.tab_name}状态",
            lines=2,
            max_lines=3,
            interactive=False,
            value=initial_value
        )

    def create_standard_log_output(self) -> gr.Textbox:
        """创建标准日志输出"""
        return gr.Textbox(
            label=f"实时{self.tab_name}日志",
            lines=20,
            max_lines=20,
            interactive=False,
            value="",
            autoscroll=True,
            show_copy_button=True
        )

    def create_auto_refresh_checkbox(self) -> gr.Checkbox:
        """创建自动刷新勾选框"""
        return gr.Checkbox(
            label="自动刷新",
            value=True,
            info="每3秒自动更新日志"
        )

    def create_timer(self, interval: float = 3.0) -> gr.Timer:
        """创建定时器"""
        return gr.Timer(value=interval, active=False)


# ==================== 工具函数 ====================

def scan_files_by_extension(
    directory: str,
    extensions: List[str],
    label_prefix: str = ""
) -> List[Tuple[str, str]]:
    """
    扫描目录中指定扩展名的文件

    Args:
        directory: 要扫描的目录
        extensions: 文件扩展名列表 [".pt", ".npy", ...]
        label_prefix: 标签前缀

    Returns:
        [(显示名称, 文件路径), ...]
    """
    files = []

    if not os.path.exists(directory):
        return files

    extensions_lower = [ext.lower() for ext in extensions]

    for item in os.listdir(directory):
        item_path = os.path.join(directory, item)

        if os.path.isfile(item_path):
            _, ext = os.path.splitext(item)
            if ext.lower() in extensions_lower:
                display_name = f"{label_prefix}{item}" if label_prefix else item
                files.append((display_name, item_path))

    # 按文件名排序
    files.sort(key=lambda x: x[0])

    return files


def create_file_selector_with_status(
    label: str,
    choices: List[Tuple[str, str]],
    default_value: Optional[str] = None,
    file_types: List[str] = None,
    info: str = "",
    allow_upload: bool = True,
    upload_height: int = 130
) -> Tuple[gr.Dropdown, gr.File, gr.Textbox, FileSelector]:
    """
    创建带状态显示的文件选择组件（简化工厂函数）

    Returns:
        (dropdown, upload, status, selector)
    """
    config = SelectorConfig(
        label=label,
        choices=choices,
        default_value=default_value,
        file_types=file_types,
        info=info,
        allow_upload=allow_upload,
        upload_height=upload_height
    )

    selector = FileSelector(config)
    components = selector.build()

    return (
        components['dropdown'],
        components.get('upload'),
        components['status'],
        selector
    )
