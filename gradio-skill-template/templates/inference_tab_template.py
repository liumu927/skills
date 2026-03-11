# templates/inference_tab_template.py
"""
推理 Tab 模板

使用说明：
1. 复制此文件到 gradio_refactor/tabs/ 目录
2. 重命名为你的功能名称（如 my_algorithm_inference.py）
3. 按照注释中的 TODO 标记修改代码
4. 在 gradio_app_refactored.py 中注册新 Tab

替换说明：
- MyAlgorithm: 你的算法名称（驼峰命名）
- my_algorithm: 你的算法名称（下划线命名）
- MY_ALGORITHM: 你的算法名称（大写下划线命名）
"""

import os
import gradio as gr
from datetime import datetime
from typing import Dict, Tuple, Optional

# TODO: 修改导入路径为项目实际路径
from ..core.task_manager import GlobalTaskManager
from ..core.log_handler import LogHandler
from ..core import common_utils


class MyAlgorithmInferenceTab:
    """
    TODO: 修改类名为你的算法名称（如 McInferenceTab）

    算法推理Tab - [算法功能描述]
    """

    def __init__(self):
        # 获取项目根目录
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.src_path = os.path.abspath(os.path.join(self.project_root, "src"))

        # TODO: 修改 tab_id 和 task_type
        self.tab_id = "my_algorithm_inference"  # 用于日志文件命名
        self.task_type = "my_algorithm_inference"  # 用于任务管理器

        # 初始化核心组件
        self.task_manager = GlobalTaskManager()
        self.log_handler = LogHandler(
            self.tab_id,
            results_dir=os.path.join(self.project_root, "results")
        )

        # TODO: 设置默认路径
        self.default_input_dir = os.path.join(self.project_root, "data", "my_algorithm")
        self.default_output_dir = os.path.join(self.project_root, "results", "my_algorithm")

        # 状态变量
        self._logs_cleared = True
        self._current_save_dir = None

    # ==================== 辅助方法 ====================

    def _scan_available_files(self, file_type: str) -> list:
        """
        TODO: 实现扫描可用文件的逻辑

        Args:
            file_type: 文件类型标识

        Returns:
            [(显示名称, 文件路径), ...]
        """
        # 示例：扫描特定目录下的文件
        files = []
        # ... 扫描逻辑
        return files

    def _check_and_display_results(self, save_dir: str) -> Tuple:
        """
        TODO: 实现检查并显示推理结果的逻辑

        Args:
            save_dir: 结果保存目录

        Returns:
            (结果列表, 状态消息, 下载文件)
        """
        if not save_dir or not os.path.exists(save_dir):
            return [], "等待推理结果...", None

        # TODO: 实现结果收集逻辑
        results = []
        status_msg = "推理完成"
        download_file = None

        return results, status_msg, download_file

    def _create_result_zip(self, save_dir: str) -> Optional[str]:
        """创建结果 ZIP 文件"""
        if not save_dir or not os.path.exists(save_dir):
            return None

        try:
            zip_path = common_utils.create_temp_zip_file(
                prefix=f"{self.tab_id}_",
                suffix=".zip"
            )

            import zipfile
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(save_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.join("result", os.path.relpath(file_path, save_dir))
                        zipf.write(file_path, arcname)

            self.log_handler.add_log(f"✅ 结果已打包")
            return zip_path
        except Exception as e:
            self.log_handler.add_log(f"❌ 创建 ZIP 失败: {e}")
            return None

    # ==================== 控制方法 ====================

    def _start_inference(self, *args) -> Tuple:
        """
        TODO: 实现启动推理的逻辑

        这里的 args 应该与 _get_task_inputs() 返回的组件对应
        """
        # 解包参数 - TODO: 根据实际输入组件修改
        # (param1, param2, param3, ...) = args

        # 清空日志
        self.log_handler.clear_logs()
        self._logs_cleared = True

        # TODO: 处理输入参数
        # - 验证必要参数
        # - 处理文件路径（优先使用上传文件，否则使用下拉框选择）
        # - 设置默认值

        # TODO: 创建配置文件（如需要）
        # config_data = {...}
        # config_path = os.path.join(...)
        # common_utils.save_yaml_config(config_data, config_path)

        # TODO: 构建命令
        # script_path = os.path.join(self.src_path, "my_algorithm", "run.py")
        # cmd = ["python", script_path, "--config", config_path]

        # TODO: 启动进程
        # task_id = f"{self.task_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        # success, msg = self.task_manager.start_process(
        #     task_id=task_id,
        #     cmd=cmd,
        #     log_callback=self.log_handler.add_log,
        #     cwd=self.project_root,
        #     task_type=self.task_type
        # )

        # TODO: 返回结果
        # return (status, logs, timer_update, ...)

        # 临时返回
        return ("✅ 推理已启动", self.log_handler.get_logs(), gr.update(active=True))

    def _stop_inference(self) -> Tuple:
        """停止推理"""
        success, msg = self.task_manager.stop_current_task(task_type=self.task_type)
        if success:
            self.log_handler.add_log(f"⏹️ {msg}")
        else:
            self.log_handler.add_log(f"⚠️ {msg}")

        # 检查并显示结果
        results, status_msg, download_file = self._check_and_display_results(self._current_save_dir)

        return (
            msg,
            self.log_handler.get_logs(),
            gr.update(active=False),
            results,
            status_msg,
            download_file
        )

    def _refresh_logs(self) -> Tuple:
        """刷新日志"""
        is_running = self.task_manager.is_running(task_type=self.task_type)
        status = "推理中..." if is_running else "推理已停止"
        logs = self.log_handler.get_logs()

        return status, logs

    def _clear_logs(self) -> Tuple:
        """清空日志"""
        self.log_handler.clear_logs()
        self._logs_cleared = True

        return "日志已清空", "", gr.update(active=False)

    def _auto_refresh_logs(self, auto_refresh_enabled: bool) -> Tuple:
        """定时器自动刷新"""
        is_running = self.task_manager.is_running(task_type=self.task_type)

        if auto_refresh_enabled and is_running:
            status = "推理中..."
            logs = self.log_handler.get_logs()
            return status, logs, gr.update(active=True)
        else:
            status = "推理已停止" if not is_running else "等待开始推理..."
            logs = self.log_handler.get_logs()
            return status, logs, gr.update(active=False)

    def _load_initial_state(self) -> Tuple:
        """页面加载时恢复状态"""
        logs = self.log_handler.get_logs()
        is_running = self.task_manager.is_running(task_type=self.task_type)
        status = "推理进行中... (从之前的会话恢复)" if is_running else "等待开始推理..."
        timer_active = is_running

        return status, logs, gr.update(active=timer_active)

    # ==================== UI 构建 ====================

    def build_ui(self):
        """构建UI"""
        # TODO: 扫描可用文件
        # file_choices = self._scan_available_files('model')
        # file_choices = [(name, path) for name, path in file_choices]

        with gr.Tab("🎯 我的算法推理") as tab:  # TODO: 修改 Tab 标签
            with gr.Row():
                # 左侧配置区域
                with gr.Column(scale=1):
                    gr.Markdown("## 📋 推理配置")

                    # TODO: 添加配置组件
                    # 参考：
                    # - 使用 gr.Accordion 分组
                    # - 使用 common_utils 中的通用回调函数
                    # - 使用下拉框 + 上传组件 + 状态文本框 的组合模式

                    with gr.Accordion("📁 输入配置", open=True):
                        # TODO: 添加输入组件
                        # 示例：数据集目录选择
                        # with gr.Row():
                        #     input_dir_dropdown = gr.Dropdown(...)
                        #     input_dir = gr.Textbox(...)
                        #     input_dir_custom = gr.Checkbox(...)
                        pass

                    with gr.Accordion("🔧 参数配置", open=True):
                        # TODO: 添加参数组件
                        # param1 = gr.Number(label="参数1", value=100)
                        # param2 = gr.Dropdown(label="参数2", choices=["A", "B"], value="A")
                        pass

                    with gr.Accordion("📂 输出配置", open=True):
                        # TODO: 添加输出配置
                        # output_dir = gr.Textbox(label="输出目录", value=self.default_output_dir)
                        pass

                # 右侧执行区域
                with gr.Column(scale=1):
                    gr.Markdown("## ▶️ 推理执行")

                    # 控制按钮
                    with gr.Row():
                        start_btn = gr.Button("🚀 开始推理", variant="primary", size="lg")
                        stop_btn = gr.Button("⏹️ 停止推理", variant="secondary", size="lg")
                        refresh_btn = gr.Button("🔄 刷新日志", variant="secondary")
                        clear_btn = gr.Button("🗑️ 清空日志", variant="secondary")

                    with gr.Row():
                        auto_refresh_checkbox = gr.Checkbox(
                            label="自动刷新",
                            value=True,
                            info="每3秒自动更新日志"
                        )

                    # 状态显示
                    status_text = gr.Textbox(
                        label="推理状态",
                        lines=2,
                        max_lines=3,
                        interactive=False,
                        value="等待开始推理..."
                    )

                    # 日志显示
                    output = gr.Textbox(
                        label="实时推理日志",
                        lines=20,
                        max_lines=20,
                        interactive=False,
                        value="",
                        autoscroll=True,
                        show_copy_button=True
                    )

                    # 结果区域
                    with gr.Accordion("📊 推理结果", open=True):
                        # TODO: 添加结果展示组件
                        # result_gallery = gr.Gallery(...)
                        # result_download = gr.File(...)
                        pass

            # 定时器
            timer = gr.Timer(value=3, active=False)

            # ==================== 事件绑定 ====================

            # TODO: 绑定配置组件的交互事件
            # - 下拉框变化更新路径
            # - 文件上传更新状态
            # - 使用 common_utils 中的通用回调函数

            # 示例：权重文件上传回调
            # weight_file_upload.change(
            #     fn=lambda file_path, detector_name: common_utils.on_weights_upload(
            #         file_path, detector_name, tab_name=self.tab_id
            #     ),
            #     inputs=[weight_file_upload, detector_name],
            #     outputs=[weight_status]
            # )

            # 绑定控制按钮
            start_btn.click(
                fn=self._start_inference,
                inputs=[...],  # TODO: 添加输入组件
                outputs=[status_text, output, timer]  # TODO: 添加输出组件
            )

            stop_btn.click(
                fn=self._stop_inference,
                outputs=[status_text, output, timer]  # TODO: 添加输出组件
            )

            refresh_btn.click(
                fn=self._refresh_logs,
                outputs=[status_text, output]
            )

            clear_btn.click(
                fn=self._clear_logs,
                outputs=[status_text, output, timer]
            )

            timer.tick(
                fn=self._auto_refresh_logs,
                inputs=[auto_refresh_checkbox],
                outputs=[status_text, output, timer]  # TODO: 添加输出组件
            )

        # 返回 tab 和状态恢复信息
        load_info = {
            'load_fn': self._load_initial_state,
            'load_outputs': [status_text, output, timer]  # TODO: 添加输出组件
        }

        return tab, load_info


# 导出工厂函数
def create_my_algorithm_inference_tab():
    """
    TODO: 修改函数名

    创建我的算法推理Tab

    Returns:
        tuple: (tab, load_info)
            - tab: gr.Tab 对象
            - load_info: 字典，包含 'load_fn' 和 'load_outputs'
    """
    tab_instance = MyAlgorithmInferenceTab()
    return tab_instance.build_ui()
