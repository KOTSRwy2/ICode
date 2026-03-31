from .BaseFunctionPage import BaseFunctionPage
import os
import ast

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog
)

from qfluentwidgets import (
 PushButton,LineEdit
)
from qfluentwidgets import FluentIcon as FIF

from .core import log_manager,  FMRIWorkerThread, MODULE_FMRI_ACT
from ..functions.fmri_activation import FMRIActivationThread
from .InteractiveChartCard import InteractiveChartCard
from ..common.style_sheet import StyleSheet

class FMRIActivationPage(BaseFunctionPage):
    def __init__(self, parent=None):
        super().__init__("fMRI 脑区激活定位", "读取 NIfTI 文件执行脑激活定位可视化，生成交互式主激活图，并在主界面展示阈值-体素数动画曲线、激活强度直方图共 2 种激活统计分析图表。", MODULE_FMRI_ACT, parent)
        self.fmri_path = ""
        self._init_ui()

    def _init_ui(self):
        file_layout = QHBoxLayout()
        self.path_edit = LineEdit(self.view)
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("选择一个 .nii / .nii.gz 脑影像文件")

        self.btn_select = PushButton("浏览文件", self.view, FIF.FOLDER)
        self.btn_select.clicked.connect(self._select_file)

        file_layout.addWidget(self.path_edit)
        file_layout.addWidget(self.btn_select)

        self.btn_run = PushButton("一键分析激活脑区", self.view, FIF.PLAY)
        self.btn_run.clicked.connect(self._run_task)

        self.content_layout.addLayout(file_layout)
        self.content_layout.addWidget(self.btn_run)

        StyleSheet.MAIN.apply(self)

    def _select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 fMRI 文件", "", "NIfTI Files (*.nii *.nii.gz)")
        if file_path:
            self.fmri_path = file_path
            self.path_edit.setText(file_path)
            log_manager.add_log(f"选择文件: {file_path}", self.module_name)

    def _run_task(self):
        if not self.check_file_selected(self.fmri_path, (".nii", ".nii.gz"), "请选择支持的 fmri 格式文件"):
            return

        self.set_running_state(True, "初始化 fMRI 处理管道...")
        log_manager.add_log("开始 fMRI 脑区激活分析...", self.module_name)

        self.worker = FMRIWorkerThread(FMRIActivationThread, self.fmri_path, tr=2.0, mode="activation")
        def update_log(msg):
            self.status_label.setText(f"处理中: {msg}")
            log_manager.add_log(msg, self.module_name)

        self.worker.log_sig.connect(update_log)
        self.worker.finished_sig.connect(self._on_task_finished)
        self.worker.start()


    def _on_task_finished(self, success, result_data):
        """处理子线程返回的结果"""
        self.set_running_state(False, "执行完成" if success else "执行失败")

        if success and result_data is not None:
            result_data = ast.literal_eval(result_data)

            main = result_data["main"]
            log_manager.add_log(f"fMRI 脑区激活定位图生成完成: {main}", self.module_name)
            self.show_success_dialog("计算完毕", f"多图交互HTML分析报告已投递:\n{main}")
            self.show_html_in_subwindow(main, "fMRI 脑区激活定位可视化")

            log_manager.add_log(f"fMRI 图表渲染完成，准备挂载UI", self.module_name)
            self.show_success_dialog("计算完毕", "激活分析已完成，请在下方查看交互图表。")

            # 清理卡片
            self._clear_previous_cards()

            # 创建一个用于容纳卡片的布局
            self.cards_container = QWidget()
            self.cards_container.setObjectName("CardsContainer")
            self.cards_layout = QVBoxLayout(self.cards_container)
            self.cards_layout.setContentsMargins(0, 16, 0, 0)
            self.cards_layout.setSpacing(16)

            # 挂载卡片 1：曲线图
            card1 = InteractiveChartCard(
                title="阈值-激活体素数曲线",
                description="查看不同阈值下，显著激活体素的数量变化，帮你选择合适的分析阈值。点击查看更多信息。",
                file_path=result_data.get('curve', ''),
                detail_text=
"""
本曲线展示了不同统计阈值下，被判定为“显著激活”的脑体素数量变化趋势。
在fMRI分析中，每个体素会被赋予一个统计值（如z-score），通过设置不同阈值，可筛选出不同显著性水平的脑区。

如何理解：
- 横轴：统计阈值（数值越大，筛选标准越严格）
- 纵轴：被判定为“显著激活”的体素总数

曲线特点：
- 阈值较低：激活体素数量多，但可能包含噪声
- 阈值较高：激活体素数量少，但结果的统计可靠性更高

核心用途：
1. 辅助选择合理的统计阈值，平衡噪声与结果的敏感性
2. 评估激活结果对阈值变化的稳定性，判断数据质量
3. 结合FDR/ Bonferroni等校正方法，确定最终分析阈值                
"""                ,
                chart_name = "阈值-激活体素数曲线",
                image_url = os.path.join(self.base_dir, "app/resource/images","fmri_activation_crue.jpg"),
                enable_animation=True,
            )
            card1.web_view.setFixedHeight(500)
            card1.web_view.setObjectName(f"web_view_{id(card1)}")
            # 挂载卡片 2：直方图
            card2 = InteractiveChartCard(
                title="激活强度分布直方图",
                description="全脑激活强度分布，红色虚线为90%高激活阈值，可快速定位显著脑区。点击查看更多信息。",
                file_path=result_data.get('histogram', ''),
                detail_text=
"""
本图展示了全脑体素的激活强度频数分布，可直观反映数据整体特征。
图中红色虚线为系统计算的90%分位数阈值线，用于快速定位高显著性激活区域。

如何理解：
- 横轴：激活强度（数值越大，体素的任务响应越强）
- 纵轴：对应激活强度的体素数量
- 红色虚线右侧：代表全脑内统计上最显著的高响应体素

核心用途：
1. 快速评估数据分布形态与整体质量
2. 量化不同激活强度区间的体素占比
3. 为阈值选择提供数据分布依据
""",
                chart_name = "阈值-激活体素数曲线",
                image_url = os.path.join(self.base_dir, "app/resource/images", "fmri_hist.png"),
                enable_animation=False,
            )
            card2.web_view.setFixedHeight(500)
            card2.web_view.setObjectName(f"web_view_{id(card2)}")
            # 添加到垂直布局
            self.cards_layout.addWidget(card1)
            self.cards_layout.addWidget(card2)

            # 将卡片容器添加到当前页面的主内容区底部
            self.content_layout.addWidget(self.cards_container)

            self.view.updateGeometry()
            self.update()
            QApplication.processEvents()

        else:
            log_manager.add_log(f"fMRI 处理失败: {result_data}", self.module_name)
            self.show_error_dialog("发生异常", f"预处理或生成时报错:\n{result_data}")