# components/base_skill_tab.py
"""
通用 Skill Tab 基类
提供所有 Skill Tab 的基础结构和通用功能

遵循 SOLID 原则：
- S (单一职责): 每个方法只负责一个功能
- O (开放封闭): 通过继承和重写扩展功能
- L (里氏替换): 子类可以替换父类
- I (接口隔离): 提供细粒度的可选接口
- D (依赖倒置): 依赖抽象而非具体实现

使用方式：
  将此文件复制到 gradio_refactor/core/ 目录下使用
"""

import os
import gradio as gr
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

# 注意：使用时需要从实际位置导入
# from gradio_refactor.core.log_handler import LogHandler
# from gradio_refactor.core.task_manager import GlobalTaskManager
# from gradio_refactor.core import common_utils


class BaseSkillTab(ABC):
    """
    Skill Tab 抽象基类

    提供 Tab 的基础结构，子类只需实现特定方法：
    - _get_tab_label(): 返回 Tab 标签
    - _build_config_section(): 构建配置区域
    - _build_result_section(): 构建结果区域
    - _start_task(): 启动任务
    - _get_task_inputs(): 获取任务输入组件列表
    - _get_task_outputs(): 获取任务输出组件列表
    """

    def __init__(
        self,
        tab_id: str,
        task_type: str,
        project_root: str = None
    ):
        """
        初始化基类

        Args:
            tab_id: Tab 标识符（用于日志文件命名等）
            task_type: 任务类型（用于任务管理器）
            project_root: 项目根目录（自动推断）
        """
        # 自动推断项目根目录
        if project_root is None:
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

        self.project_root = project_root
        self.tab_id = tab_id
        self.task_type = task_type

        # 初始化核心组件（子类需要在实际使用时正确导入）
        # 这里使用延迟导入或占位符
        self._init_core_components()

        # 状态标志
        self._logs_cleared = True
        self._current_save_dir = None

    def _init_core_components(self):
        """
        初始化核心组件

        注意：子类应该重写此方法，使用正确的导入路径
        """
        # 占位符，子类需要实现实际导入
        # from gradio_refactor.core.log_handler import LogHandler
        # from gradio_refactor.core.task_manager import GlobalTaskManager
        #
        # self.task_manager = GlobalTaskManager()
        # self.log_handler = LogHandler(
        #     self.tab_id,
        #     results_dir=os.path.join(self.project_root, "results")
        # )
        pass

    # ==================== 抽象方法（子类必须实现） ====================

    @abstractmethod
    def _get_tab_label(self) -> str:
        """
        返回 Tab 标签（带 emoji）

        Returns:
            如 "🚀 我的技能"
        """
        pass

    @abstractmethod
    def _build_config_section(self) -> Dict[str, gr.components.Component]:
        """
        构建配置区域（左侧）

        Returns:
            组件字典，用于后续事件绑定
        """
        pass

    @abstractmethod
    def _build_result_section(self) -> Dict[str, gr.components.Component]:
        """
        构建结果区域（右侧下方）

        Returns:
            组件字典，用于后续事件绑定
        """
        pass

    @abstractmethod
    def _start_task(self, *args) -> Tuple:
        """
        启动任务

        Args:
            *args: 从 _get_task_inputs() 获取的输入值

        Returns:
            输出元组，对应 _get_task_outputs()
        """
        pass

    # ==================== 可选重写方法 ====================

    def _get_task_inputs(self) -> List[gr.components.Component]:
        """
        获取任务输入组件列表

        Returns:
            输入组件列表，用于 start_btn.click 的 inputs
        """
        return []

    def _get_task_outputs(self) -> List[gr.components.Component]:
        """
        获取任务输出组件列表

        Returns:
            输出组件列表，用于 start_btn.click 的 outputs
        """
        return []

    def _get_timer_outputs(self) -> List[gr.components.Component]:
        """
        获取定时器输出组件列表

        Returns:
            输出组件列表，用于 timer.tick 的 outputs
        """
        return self._get_task_outputs()

    def _get_load_outputs(self) -> List[gr.components.Component]:
        """
        获取页面加载输出组件列表

        Returns:
            输出组件列表，用于 demo.load 的 outputs
        """
        return self._get_task_outputs()

    def _on_task_stop(self) -> Tuple:
        """
        任务停止时的回调

        Returns:
            输出元组
        """
        success, msg = self.task_manager.stop_current_task(task_type=self.task_type)
        if success:
            self.log_handler.add_log(f"⏹️ {msg}")
        else:
            self.log_handler.add_log(f"⚠️ {msg}")

        return self._build_stop_outputs(msg)

    def _on_logs_refresh(self) -> Tuple:
        """
        日志刷新时的回调

        Returns:
            输出元组
        """
        is_running = self.task_manager.is_running(task_type=self.task_type)
        status = self._get_running_status_text(is_running)
        logs = self.log_handler.get_logs()

        return self._build_refresh_outputs(status, logs, is_running)

    def _on_logs_clear(self) -> Tuple:
        """
        日志清空时的回调

        Returns:
            输出元组
        """
        self.log_handler.clear_logs()
        self._logs_cleared = True

        return self._build_clear_outputs()

    def _on_auto_refresh(self, auto_refresh_enabled: bool) -> Tuple:
        """
        定时器自动刷新回调

        Args:
            auto_refresh_enabled: 是否启用自动刷新

        Returns:
            输出元组
        """
        is_running = self.task_manager.is_running(task_type=self.task_type)

        if auto_refresh_enabled and is_running:
            return self._build_auto_refresh_outputs(is_running=True)

        return self._build_auto_refresh_outputs(is_running=False)

    def _load_initial_state(self) -> Tuple:
        """
        页面加载时恢复状态

        Returns:
            输出元组
        """
        logs = self.log_handler.get_logs()
        is_running = self.task_manager.is_running(task_type=self.task_type)
        status = self._get_running_status_text(is_running, recovery=True)

        return self._build_load_outputs(status, logs, is_running)

    # ==================== 辅助方法 ====================

    def _get_running_status_text(self, is_running: bool, recovery: bool = False) -> str:
        """
        获取运行状态文本

        Args:
            is_running: 是否正在运行
            recovery: 是否是恢复状态

        Returns:
            状态文本
        """
        if is_running:
            suffix = " (从之前的会话恢复)" if recovery else ""
            return f"{self.task_type}进行中...{suffix}"
        return f"等待开始{self.task_type}..."

    def _start_process(
        self,
        cmd: List[str],
        cwd: str = None,
        extra_logs: List[str] = None
    ) -> Tuple[bool, str]:
        """
        启动子进程

        Args:
            cmd: 命令列表
            cwd: 工作目录
            extra_logs: 额外的日志信息

        Returns:
            (成功?, 消息)
        """
        task_id = f"{self.task_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        success, msg = self.task_manager.start_process(
            task_id=task_id,
            cmd=cmd,
            log_callback=self.log_handler.add_log,
            cwd=cwd or self.project_root,
            task_type=self.task_type
        )

        if success:
            self.log_handler.add_log(f"✅ {msg}")
            if extra_logs:
                for log in extra_logs:
                    self.log_handler.add_log(log)
        else:
            self.log_handler.add_log(f"❌ {msg}")

        return success, msg

    def _stop_current_task(self) -> Tuple[bool, str]:
        """停止当前任务"""
        return self.task_manager.stop_current_task(task_type=self.task_type)

    def _is_running(self) -> bool:
        """检查是否有任务在运行"""
        return self.task_manager.is_running(task_type=self.task_type)

    def _clear_logs(self):
        """清空日志"""
        self.log_handler.clear_logs()
        self._logs_cleared = True

    def _add_log(self, message: str):
        """添加日志"""
        self.log_handler.add_log(message)
        self._logs_cleared = False

    def _get_logs(self) -> str:
        """获取日志"""
        return self.log_handler.get_logs()

    # ==================== 输出构建方法（子类可重写） ====================

    def _build_stop_outputs(self, msg: str) -> Tuple:
        """构建停止输出"""
        return (msg, self._get_logs(), gr.update(active=False))

    def _build_refresh_outputs(self, status: str, logs: str, is_running: bool) -> Tuple:
        """构建刷新输出"""
        return (status, logs)

    def _build_clear_outputs(self) -> Tuple:
        """构建清空输出"""
        return ("日志已清空", "", gr.update(active=False))

    def _build_auto_refresh_outputs(self, is_running: bool) -> Tuple:
        """构建自动刷新输出"""
        status = self._get_running_status_text(is_running)
        logs = self._get_logs()
        timer_update = gr.update(active=is_running)

        return (status, logs, timer_update)

    def _build_load_outputs(self, status: str, logs: str, is_running: bool) -> Tuple:
        """构建加载输出"""
        timer_update = gr.update(active=is_running)
        return (status, logs, timer_update)

    # ==================== UI 构建方法 ====================

    def build_ui(self) -> Tuple[gr.Tab, Dict]:
        """
        构建 UI

        Returns:
            (tab, load_info)
        """
        with gr.Tab(self._get_tab_label()) as tab:
            with gr.Row():
                # 左侧：配置区域
                with gr.Column(scale=1):
                    gr.Markdown("## 📋 配置")
                    config_components = self._build_config_section()

                # 右侧：执行区域
                with gr.Column(scale=1):
                    gr.Markdown("## ▶️ 执行")

                    # 控制按钮
                    with gr.Row():
                        start_btn = gr.Button("🚀 开始", variant="primary", size="lg")
                        stop_btn = gr.Button("⏹️ 停止", variant="secondary", size="lg")
                        refresh_btn = gr.Button("🔄 刷新日志", variant="secondary")
                        clear_btn = gr.Button("🗑️ 清空日志", variant="secondary")

                    # 自动刷新
                    with gr.Row():
                        auto_refresh = gr.Checkbox(
                            label="自动刷新",
                            value=True,
                            info="每3秒自动更新日志"
                        )

                    # 状态显示
                    status_text = gr.Textbox(
                        label="状态",
                        lines=2,
                        max_lines=3,
                        interactive=False,
                        value=f"等待开始{self.task_type}..."
                    )

                    # 日志显示
                    log_output = gr.Textbox(
                        label=f"实时{self.task_type}日志",
                        lines=20,
                        max_lines=20,
                        interactive=False,
                        value="",
                        autoscroll=True,
                        show_copy_button=True
                    )

                    # 结果区域
                    with gr.Accordion("📊 结果", open=True):
                        result_components = self._build_result_section()

            # 定时器
            timer = gr.Timer(value=3, active=False)

            # 存储基础组件引用
            self._base_components = {
                'start_btn': start_btn,
                'stop_btn': stop_btn,
                'refresh_btn': refresh_btn,
                'clear_btn': clear_btn,
                'auto_refresh': auto_refresh,
                'status_text': status_text,
                'log_output': log_output,
                'timer': timer,
                **config_components,
                **result_components
            }

            # 绑定事件
            self._bind_events()

        # 返回 load_info
        load_info = {
            'load_fn': self._load_initial_state,
            'load_outputs': self._get_load_outputs()
        }

        return tab, load_info

    def _bind_events(self):
        """绑定事件（子类可重写以添加自定义事件）"""
        components = self._base_components

        # 开始按钮
        components['start_btn'].click(
            fn=self._start_task,
            inputs=self._get_task_inputs(),
            outputs=self._get_task_outputs()
        )

        # 停止按钮
        components['stop_btn'].click(
            fn=self._on_task_stop,
            outputs=self._get_task_outputs()
        )

        # 刷新按钮
        components['refresh_btn'].click(
            fn=self._on_logs_refresh,
            outputs=self._get_task_outputs()
        )

        # 清空按钮
        components['clear_btn'].click(
            fn=self._on_logs_clear,
            outputs=self._get_task_outputs()
        )

        # 定时器
        components['timer'].tick(
            fn=self._on_auto_refresh,
            inputs=[components['auto_refresh']],
            outputs=self._get_timer_outputs()
        )


class InferenceTabMixin:
    """
    推理 Tab 混入类

    提供推理 Tab 的通用功能：
    - 结果检查和显示
    - ZIP 打包下载
    """

    def _check_and_display_results(self, save_dir: str) -> Tuple:
        """
        检查并显示推理结果

        Args:
            save_dir: 结果保存目录

        Returns:
            (results, status_msg, download_file)
        """
        # 子类实现具体逻辑
        return ([], "等待推理结果...", None)

    def _create_result_zip(self, save_dir: str, prefix: str = "result") -> Optional[str]:
        """
        创建结果 ZIP 文件

        Args:
            save_dir: 要打包的目录
            prefix: ZIP 文件名前缀

        Returns:
            ZIP 文件路径，失败返回 None
        """
        if not save_dir or not os.path.exists(save_dir):
            return None

        try:
            # 需要导入 common_utils
            # zip_path = common_utils.create_temp_zip_file(prefix=prefix, suffix=".zip")
            import tempfile
            temp_file = tempfile.NamedTemporaryFile(prefix=prefix, suffix=".zip", delete=False)
            zip_path = temp_file.name
            temp_file.close()

            import zipfile
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(save_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.join("result", os.path.relpath(file_path, save_dir))
                        zipf.write(file_path, arcname)

            self.log_handler.add_log(f"✅ 结果已打包到临时目录")
            return zip_path

        except Exception as e:
            self.log_handler.add_log(f"❌ 创建 ZIP 失败: {e}")
            return None


class TrainingTabMixin:
    """
    训练 Tab 混入类

    提供训练 Tab 的通用功能：
    - 补丁图像显示
    - Epoch 信息解析
    """

    def _extract_paths_from_logs(self) -> Tuple[Optional[str], str]:
        """
        从日志中提取保存路径和名称

        Returns:
            (save_path, board_name)
        """
        # 子类实现具体逻辑
        return (None, "demo")
