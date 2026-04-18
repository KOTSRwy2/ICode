# -*- coding: utf-8 -*-
from .BaseFunctionPage import BaseFunctionPage
import os
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog
)

from qfluentwidgets import (
 PushButton, LineEdit
)
from qfluentwidgets import FluentIcon as FIF

from .core import log_manager, FMRIWorkerThread, MODULE_FMRI_ACT
from ..functions.fmri_activation import FMRIActivationThread
from .InteractiveChartCard import InteractiveChartCard
from ..common.style_sheet import StyleSheet

class FMRIActivationPage(BaseFunctionPage):
    def __init__(self, parent=None):
        super().__init__("fMRI 脑区激活定位", "读取 NIfTI 文件执行脑激活定位可视化，生成交互式主激活图，并在主界面展示阈值-体素数动画曲线、激活强度直方图共 2 种激活统计分析图表。", MODULE_FMRI_ACT, parent)
        self.fmri_path = ""
        self.worker = None
        self.cards_container = None
        
        # 定义基础目录，解决图片加载路径问题
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        self._init_ui()

    def _init_ui(self):
        # 1. 文件选择
        file_layout = QHBoxLayout()
        self.path_edit = LineEdit(self.view)
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("选择一个 .nii / .nii.gz 脑影像文件")

        self.btn_select = PushButton("浏览文件", self.view, FIF.FOLDER)
        self.btn_select.clicked.connect(self._select_file)

        file_layout.addWidget(self.path_edit)
        file_layout.addWidget(self.btn_select)

        # 2. 运行按钮
        self.btn_run = PushButton("一键分析fMRI激活定位", self.view, FIF.PLAY)
        self.btn_run.clicked.connect(self._run_task)

        self.content_layout.addLayout(file_layout)
        self.content_layout.addWidget(self.btn_run)

        # 3. 分享链接区域
        share_layout = QHBoxLayout()
        self.share_link_edit = LineEdit(self.view)
        self.share_link_edit.setReadOnly(True)
        self.share_link_edit.setPlaceholderText("分析完成后，分享链接将在此显示")
        self.share_link_edit.setVisible(False)

        self.copy_link_btn = PushButton("复制链接", self.view, FIF.COPY)
        self.copy_link_btn.setVisible(False)
        self.copy_link_btn.clicked.connect(self._copy_share_link)

        share_layout.addWidget(self.share_link_edit)
        share_layout.addWidget(self.copy_link_btn)
        self.content_layout.addLayout(share_layout)
        
        StyleSheet.MAIN.apply(self)

    def _select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 fMRI 文件", "", "NIfTI Files (*.nii *.nii.gz)")
        if file_path:
            self.fmri_path = file_path
            self.path_edit.setText(file_path)
            log_manager.add_log(f"选择文件: {file_path}", self.module_name)

    def _copy_share_link(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.share_link_edit.text())
        self.show_success_dialog("已复制", "分享链接已复制到剪贴板。")

    def _show_share_link(self, share_url: str):
        if not share_url:
            return
        self.share_link_edit.setText(share_url)
        self.share_link_edit.setVisible(True)
        self.copy_link_btn.setVisible(True)

    def _run_task(self):
        if not self.check_file_selected(self.fmri_path, (".nii", ".nii.gz"), "请选择支持的 fmri 格式文件"):
            return

        if self.worker is not None and self.worker.isRunning():
            return

        self.set_running_state(True, "初始化 fMRI 激活定位流水线...")
        log_manager.add_log("开始处理 NIfTI 数据流...", self.module_name)

        # 使用 core.py 提供的线程
        self.worker = FMRIWorkerThread(FMRIActivationThread, self.fmri_path, tr=2.0, mode="activation")
        
        def update_log(msg):
            self.status_label.setText(f"处理中: {msg}")
            log_manager.add_log(msg, self.module_name)

        self.worker.log_sig.connect(update_log)
        self.worker.finished_sig.connect(self._on_task_finished)
        self.worker.start()

    def _on_task_finished(self, success, result_data):
        """处理子线程返回的结果"""
        self.set_running_state(False, "分析完成" if success else "分析失败")
        
        if not success:
            log_manager.add_log(f"计算失败: {result_data}", self.module_name)
            self.show_error_dialog("分析异常", str(result_data))
            return

        # ==========================================================
        # 提取本地路径与 OSS 链接
        # ==========================================================
        res_paths = result_data if isinstance(result_data, dict) else {}
        
        # 1. 提取主 3D 视图
        main_path = res_paths.get('main', '')
        
        # 2. 提取并展示分享链接
        share_url = res_paths.get('share_url')
        if share_url:
            self._show_share_link(share_url)
            log_manager.add_log(f"激活图云端同步成功: {share_url}", self.module_name)

        # 展示 HTML 结果窗口
        viz_win = None
        if main_path and os.path.exists(str(main_path)):
            viz_win = self.show_html_in_subwindow(main_path, "fMRI 脑激活定位 3D 可视化")

        # ==========================================================
        # 卡片加载逻辑：恢复详细的临床释义
        # ==========================================================
        def create_and_load_cards():
            """创建卡片并恢复详细的临床释义"""
            self._clear_previous_cards()
            self.cards_container = QWidget()
            self.cards_container.setObjectName("CardsContainer")
            self.cards_layout = QVBoxLayout(self.cards_container)
            self.cards_layout.setContentsMargins(0, 16, 0, 0)
            self.cards_layout.setSpacing(16)

            # 挂载卡片 1：曲线图
            curve_path = res_paths.get('curve', '') 
            card1 = InteractiveChartCard(
                title="阈值-激活体素数曲线",
                description="查看不同阈值下，显著激活体素的数量变化，帮助选择合适的分析阈值。点击查看更多信息。",
                file_path=curve_path,
                detail_text="""
本曲线展示了不同统计阈值下，被判定为“显著激活”的脑体素数量变化趋势。
在 fMRI 分析中，每个体素会被赋予一个统计值（如 z-score），通过设置不同阈值，可筛选出不同显著性水平产生脑区。

如何理解：
- 横轴：统计阈值（数值越大，筛选标准越严格）
- 纵轴：被判定为“显著激活”的体素总数

曲线特点：
- 阈值较低：激活体素数量多，但包含噪声
- 阈值较高：激活体素数量少，但结果的统计可靠性更高

核心用途：
1. 辅助选择合理的统计阈值，平衡噪声与结果的敏感性
2. 评估激活结果对阈值变化的稳定性，判断数据质量
3. 结合 FDR/Bonferroni 等校正方法，确定最终分析阈值
""",
                chart_name="阈值-激活体素数曲线",
                image_url=os.path.join(self.base_dir, "app/resource/images", "fmri_activation_crue.jpg"),
                enable_animation=True,
            )
            card1.web_view.setFixedHeight(500)
            self.cards_layout.addWidget(card1)

            # 挂载卡片 2：直方图
            hist_path = res_paths.get('histogram', '')
            card2 = InteractiveChartCard(
                title="激活强度分布直方图",
                description="全脑激活强度分布，红色虚线为 90% 高激活阈值，可快速定位显著脑区。点击查看更多信息。",
                file_path=hist_path,
                detail_text="""
本图展示了全脑体素的激活强度频数分布，可直观反映数据整体特征。
图中红色虚线为系统计算的 90% 分位数阈值线，用于快速定位高显著性激活区域。

如何理解：
- 横轴：激活强度（数值越大，体素的任务响应越强）
- 纵轴：对应激活强度的体素数量
- 红色虚线右侧：代表全脑内统计上最显著的高响应体素

核心用途：
1. 快速评估数据分布形态与整体质量
2. 量化不同激活强度区间的体素占比
3. 为阈值选择提供数据分布依据
""",
                chart_name="激活强度直方图",
                image_url=os.path.join(self.base_dir, "app/resource/images", "fmri_hist.png"),
                enable_animation=False,
            )
            card2.web_view.setFixedHeight(500)
            self.cards_layout.addWidget(card2)

            self.content_layout.addWidget(self.cards_container)
            self.view.updateGeometry()
            self.update()

            # 交错延迟触发卡片 HTML 加载
            QTimer.singleShot(100, card1.load_chart)
            QTimer.singleShot(400, card2.load_chart)
            
            QTimer.singleShot(600, lambda: self.set_running_state(False, "执行完成"))

        # 加载时机控制：弹窗就绪或关闭后再加载卡片
        if viz_win and hasattr(viz_win, 'ready_sig'):
            viz_win.ready_sig.connect(create_and_load_cards)
        elif viz_win and hasattr(viz_win, 'destroyed'):
            viz_win.destroyed.connect(create_and_load_cards)
        else:
            QTimer.singleShot(1000, create_and_load_cards)

        # 强制刷新UI
        QApplication.processEvents()