# templates/training_tab_template.py
"""
训练 Tab 模板

使用说明：
1. 复制此文件到 gradio_refactor/tabs/ 目录
2. 重命名为你的功能名称（如 my_algorithm_train.py）
3. 按照注释中的 TODO 标记修改代码
4. 在 gradio_app_refactored.py 中注册新 Tab

训练 Tab 特有功能：
- 长时间运行的任务管理
- Epoch 信息显示
- 补丁/结果图像实时预览
- 两阶段训练支持

替换说明：
- MyAlgorithm: 你的算法名称（驼峰命名）
- my_algorithm: 你的算法名称（下划线命名）
"""

import os
import time
import gradio as gr
from datetime import datetime
from typing import Dict, Tuple, Optional

# TODO: 修改导入路径为项目实际路径
from ..core.task_manager import GlobalTaskManager
from ..core.log_handler import LogHandler
from ..core import common_utils
from ..core.patch_handler import PatchImageCache
from ..core import patch_handler


class MyAlgorithmTrainingTab:
    """
    TODO: 修改类名为你的算法名称（如 McTrainTab）

    算法训练Tab - [算法功能描述]
    """

    def __init__(self):
        # 获取项目根目录
        self.project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

        # TODO: 修改 tab_id 和 task_type
        self.tab_id = "my_algorithm_train"
        self.task_type = "my_algorithm_train"

        # 初始化核心组件
        self.task_manager = GlobalTaskManager()
        self.log_handler = LogHandler(
            self.tab_id,
            results_dir=os.path.join(self.project_root, "results")
        )

        # 补丁缓存（用于实时预览）
        self.patch_cache = PatchImageCache(cache_interval=2)
        self.training_start_time = None  # 记录训练开始时间

        # TODO: 设置默认路径
        self.default_data_path = os.path.join(self.project_root, "data", "train-data")
        self.default_save_path = os.path.join(self.project_root, "results", "my_algorithm")

    # ==================== 辅助方法 ====================

    def _scan_datasets(self) -> Tuple[Dict, str, str, str]:
        """
        扫描训练数据集

        Returns:
            (dataset_mapping, default_name, default_img_dir, default_lab_dir)
        """
        return common_utils.scan_datasets(
            base_path=self.default_data_path,
            preferred_dataset="default"
        )

    def _extract_paths_from_logs(self) -> Tuple[Optional[str], str]:
        """
        从日志中提取保存路径和名称

        Returns:
            (save_path, board_name)
        """
        save_path = None
        board_name = "demo"

        try:
            logs = self.log_handler.all_logs
            for log_line in reversed(logs):
                # TODO: 根据实际命令格式解析
                if "命令:" in log_line and "-s" in log_line:
                    parts = log_line.split()
                    if "-s" in parts:
                        save_idx = parts.index("-s")
                        if save_idx + 1 < len(parts):
                            save_path = parts[save_idx + 1]

                if "-n" in log_line:
                    parts = log_line.split()
                    if "-n" in parts:
                        name_idx = parts.index("-n")
                        if name_idx + 1 < len(parts):
                            board_name = parts[name_idx + 1]

                if save_path:
                    break
        except:
            pass

        if not save_path:
            save_path = self.default_save_path

        return save_path, board_name

    def _get_patch_image(self, save_path, board_name=None, log_start_time=None):
        """
        获取补丁图像及epoch信息

        Args:
            save_path: 保存路径
            board_name: 补丁名称
            log_start_time: 日志开始时间戳，用于过滤旧补丁

        Returns:
            (补丁文件路径, epoch信息) 或 (None, None)
        """
        try:
            return patch_handler.get_single_patch_filtered(
                save_path,
                board_name=board_name,
                log_start_time=log_start_time
            )
        except Exception as e:
            print(f"获取补丁图像失败: {e}")
            return None, None

    def _get_patch_image_with_cache(self, save_path, board_name=None, log_start_time=None):
        """获取补丁图像（带缓存）"""
        return self.patch_cache.get_with_cache(
            self._get_patch_image,
            save_path,
            board_name=board_name,
            log_start_time=log_start_time
        )

    # ==================== 控制方法 ====================

    def _start_training(self, *args) -> Tuple:
        """
        TODO: 实现启动训练的逻辑
        """
        # 解包参数 - TODO: 根据实际输入组件修改
        # (param1, param2, ...) = args

        # 清空日志和缓存
        self.log_handler.clear_logs()
        self.patch_cache.clear()
        self.training_start_time = time.time()

        # TODO: 处理输入参数
        # - 验证必要参数
        # - 处理文件路径
        # - 提取攻击类别索引等

        # TODO: 创建配置文件
        # config_data = common_utils.create_yaml_config(...)
        # config_path = os.path.join(...)
        # common_utils.save_yaml_config(config_data, config_path)

        # TODO: 构建命令
        # script_path = os.path.join(self.project_root, "src", "train_xxx_run.py")
        # cmd = ["python", script_path, "-cfg", config_path, ...]

        # TODO: 创建保存目录
        # os.makedirs(save_path, exist_ok=True)

        # TODO: 启动进程
        # task_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.task_type}"
        # success, msg = self.task_manager.start_process(
        #     task_id=task_id,
        #     cmd=cmd,
        #     log_callback=self.log_handler.add_log,
        #     cwd=self.project_root,
        #     task_type=self.task_type
        # )

        # TODO: 返回结果（包括补丁显示更新）

        # 临时返回
        return ("✅ 训练已启动", self.log_handler.get_logs(), None, "等待补丁生成...", "等待训练开始...", gr.update(active=True))

    def _stop_training(self) -> Tuple:
        """停止训练"""
        success, msg = self.task_manager.stop_current_task(task_type=self.task_type)
        if success:
            self.log_handler.add_log(f"⏹️ {msg}")
        else:
            self.log_handler.add_log(f"⚠️ {msg}")

        # 清除缓存
        self.patch_cache.clear()
        self.training_start_time = None

        return (msg, self.log_handler.get_logs(), None, "训练已停止", "训练已停止", gr.update(active=False))

    def _refresh_logs(self) -> Tuple:
        """刷新日志"""
        is_running = self.task_manager.is_running(task_type=self.task_type)
        status = "训练中..." if is_running else "训练已停止"
        logs = self.log_handler.get_logs()

        # 更新补丁显示
        patch_img, patch_info, epoch_text = None, "等待补丁生成", "等待..."
        if logs.strip():
            save_path, board_name = self._extract_paths_from_logs()
            if save_path:
                log_start_time = self.training_start_time if is_running else None
                patch_img, epoch_info = self._get_patch_image(save_path, board_name, log_start_time)
                if patch_img:
                    patch_info = f"补丁路径: {patch_img}"
                    epoch_text = epoch_info if epoch_info else "最新补丁"

        return status, logs, patch_img, patch_info, epoch_text

    def _clear_logs(self) -> Tuple:
        """清空日志"""
        self.log_handler.clear_logs()
        self.patch_cache.clear()
        self.training_start_time = None

        return "日志已清空", "", None, "等待补丁生成", "等待训练开始...", gr.update(active=False)

    def _auto_refresh_logs(self, auto_refresh_enabled: bool) -> Tuple:
        """定时器自动刷新"""
        is_running = self.task_manager.is_running(task_type=self.task_type)

        if auto_refresh_enabled and is_running:
            status = "训练中..."
            logs = self.log_handler.get_logs()

            # 更新补丁显示
            patch_img, patch_info, epoch_text = None, "训练中...", "训练中..."
            if logs.strip():
                save_path, board_name = self._extract_paths_from_logs()
                if save_path:
                    patch_img, epoch_info = self._get_patch_image_with_cache(
                        save_path, board_name,
                        log_start_time=self.training_start_time
                    )
                    if patch_img:
                        patch_info = f"最新补丁: {os.path.basename(patch_img)}"
                        epoch_text = epoch_info if epoch_info else "训练中..."

            return status, logs, patch_img, patch_info, epoch_text, gr.update(active=True)
        else:
            status = "训练已停止" if not is_running else "等待开始训练..."
            logs = self.log_handler.get_logs()

            # 训练停止后显示所有补丁
            patch_img, patch_info, epoch_text = None, "等待补丁生成", "等待..."
            if logs.strip() and not is_running:
                save_path, board_name = self._extract_paths_from_logs()
                if save_path:
                    patch_img, epoch_info = self._get_patch_image(save_path, board_name)
                    if patch_img:
                        patch_info = f"补丁路径: {patch_img}"
                        epoch_text = epoch_info if epoch_info else "训练完成"

            return status, logs, patch_img, patch_info, epoch_text, gr.update(active=False)

    def _load_initial_state(self) -> Tuple:
        """页面加载时恢复状态"""
        logs = self.log_handler.get_logs()
        is_running = self.task_manager.is_running(task_type=self.task_type)
        status = "训练进行中... (从之前的会话恢复)" if is_running else "等待开始训练..."
        timer_active = is_running

        # 恢复补丁显示
        patch_img, patch_info, epoch_text = None, "等待补丁生成", "等待训练开始..."
        if is_running or logs.strip():
            try:
                save_path, board_name = self._extract_paths_from_logs()
                if save_path and os.path.exists(save_path):
                    log_start_time = self.training_start_time if is_running else None
                    patch_img, epoch_info = self._get_patch_image(save_path, board_name, log_start_time)
                    if patch_img:
                        patch_info = f"补丁路径: {patch_img}"
                        epoch_text = epoch_info if epoch_info else "最新补丁"
            except:
                pass

        return status, logs, patch_img, patch_info, epoch_text, gr.update(active=timer_active)

    # ==================== UI 构建 ====================

    def build_ui(self):
        """构建UI"""
        # 扫描数据集
        all_datasets, default_name, default_img_dir, default_lab_dir = self._scan_datasets()
        dataset_choices = list(all_datasets.keys())

        with gr.Tab("🚀 我的算法训练") as tab:  # TODO: 修改 Tab 标签
            with gr.Row():
                # 左侧配置区域
                with gr.Column(scale=1):
                    gr.Markdown("## 📋 训练配置")

                    # TODO: 添加配置组件
                    # 训练 Tab 常见配置组：
                    # 1. 数据配置（图像目录、标签目录、类别文件）
                    # 2. 检测器配置（检测器类型、权重、批次大小）
                    # 3. 攻击器配置（攻击方法、迭代次数、学习率）
                    # 4. 补丁配置（补丁尺寸、初始化方式）
                    # 5. 运行参数（保存名称、保存路径）

                    with gr.Accordion("📁 数据配置", open=True):
                        # 数据集选择
                        with gr.Row():
                            dataset_dropdown = gr.Dropdown(
                                choices=dataset_choices,
                                label="训练数据集",
                                value=default_name,
                                info="选择训练数据集"
                            )
                            img_dir = gr.Textbox(
                                label="图像目录",
                                value=default_img_dir,
                                interactive=False
                            )
                            img_dir_custom = gr.Checkbox(label="自定义路径", value=False)

                        with gr.Row():
                            lab_dir = gr.Textbox(
                                label="标签目录",
                                value=default_lab_dir,
                                interactive=False
                            )
                            lab_dir_custom = gr.Checkbox(label="自定义路径", value=False)

                    with gr.Accordion("🔍 检测器配置", open=True):
                        with gr.Row():
                            detector_name = gr.Dropdown(
                                choices=["YOLOV5", "YOLOV3", "Faster_RCNN"],
                                label="检测器名称",
                                value="YOLOV5"
                            )
                            batch_size = gr.Number(label="批量大小", value=2, precision=0)

                        # 权重文件上传
                        detector_weights = gr.File(
                            label="模型权重（可选）",
                            file_types=[".pt", ".pth"],
                            file_count="single",
                            type="filepath"
                        )
                        detector_weights_status = gr.Textbox(
                            label="权重状态",
                            value="未自定义上传，将使用默认权重",
                            interactive=False,
                            lines=2
                        )

                    with gr.Accordion("⚔️ 攻击器配置", open=True):
                        # TODO: 添加攻击器配置组件
                        # max_epoch = gr.Number(label="最大训练轮数", value=200)
                        # method = gr.Dropdown(label="攻击方法", choices=["optim", "pgd"], value="optim")
                        pass

                    with gr.Accordion("⚙️ 运行参数", open=True):
                        with gr.Row():
                            board_name = gr.Textbox(
                                label="保存名称",
                                value="demo"
                            )
                            save_path = gr.Textbox(
                                label="保存路径",
                                value=self.default_save_path,
                                scale=2
                            )

                # 右侧执行区域
                with gr.Column(scale=1):
                    gr.Markdown("## ▶️ 训练执行")

                    # 控制按钮
                    with gr.Row():
                        start_btn = gr.Button("🚀 开始训练", variant="primary", size="lg")
                        stop_btn = gr.Button("⏹️ 停止训练", variant="secondary", size="lg")
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
                        label="训练状态",
                        lines=2,
                        max_lines=3,
                        interactive=False,
                        value="等待开始训练..."
                    )

                    # 日志显示
                    output = gr.Textbox(
                        label="实时训练日志",
                        lines=15,
                        max_lines=15,
                        interactive=False,
                        value="",
                        autoscroll=True,
                        show_copy_button=True
                    )

                    # Epoch 信息
                    epoch_label = gr.Textbox(
                        label="当前迭代",
                        value="等待训练开始...",
                        interactive=False
                    )

                    # 补丁显示
                    with gr.Accordion("📊 补丁结果", open=True):
                        with gr.Row():
                            with gr.Column(scale=3):
                                patch_image = gr.Image(
                                    label="生成的补丁",
                                    height=300,
                                    show_download_button=True
                                )
                            with gr.Column(scale=2):
                                patch_info = gr.Textbox(
                                    label="补丁信息",
                                    lines=8,
                                    interactive=False,
                                    value="等待补丁生成"
                                )

            # 定时器
            timer = gr.Timer(value=3, active=False)

            # ==================== 事件绑定 ====================

            # 数据集目录回调
            dataset_callbacks = common_utils.create_dataset_dir_callbacks(all_datasets, path_index=0)

            dataset_dropdown.change(
                fn=dataset_callbacks['update_img_dir'],
                inputs=[dataset_dropdown, img_dir_custom],
                outputs=[img_dir]
            )
            img_dir_custom.change(
                fn=dataset_callbacks['toggle_img_dir'],
                inputs=[img_dir_custom, dataset_dropdown],
                outputs=[img_dir]
            )
            # 标签目录回调...

            # 权重文件回调
            detector_weights.change(
                fn=lambda file_path, det_name: common_utils.on_weights_upload(
                    file_path, det_name, tab_name=self.tab_id
                ),
                inputs=[detector_weights, detector_name],
                outputs=[detector_weights_status]
            )

            detector_name.change(
                fn=lambda det_name, file_path: common_utils.update_weight_status(
                    det_name, file_path, tab_name=self.tab_id
                ),
                inputs=[detector_name, detector_weights],
                outputs=[detector_weights_status]
            )

            # 绑定控制按钮
            start_btn.click(
                fn=self._start_training,
                inputs=[...],  # TODO: 添加输入组件
                outputs=[status_text, output, patch_image, patch_info, epoch_label, timer]
            )

            stop_btn.click(
                fn=self._stop_training,
                outputs=[status_text, output, patch_image, patch_info, epoch_label, timer]
            )

            refresh_btn.click(
                fn=self._refresh_logs,
                outputs=[status_text, output, patch_image, patch_info, epoch_label]
            )

            clear_btn.click(
                fn=self._clear_logs,
                outputs=[status_text, output, patch_image, patch_info, epoch_label, timer]
            )

            timer.tick(
                fn=self._auto_refresh_logs,
                inputs=[auto_refresh_checkbox],
                outputs=[status_text, output, patch_image, patch_info, epoch_label, timer]
            )

        # 返回 tab 和状态恢复信息
        load_info = {
            'load_fn': self._load_initial_state,
            'load_outputs': [status_text, output, patch_image, patch_info, epoch_label, timer]
        }

        return tab, load_info


# 导出工厂函数
def create_my_algorithm_train_tab():
    """
    TODO: 修改函数名

    创建我的算法训练Tab

    Returns:
        tuple: (tab, load_info)
    """
    tab_instance = MyAlgorithmTrainingTab()
    return tab_instance.build_ui()
