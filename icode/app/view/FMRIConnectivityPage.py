from .BaseFunctionPage import BaseFunctionPage
import ast
import os
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog
)

from qfluentwidgets import (
  PushButton, LineEdit
)
from qfluentwidgets import FluentIcon as FIF

from .core import log_manager,  FMRIWorkerThread, MODULE_FMRI_CONN
from ..functions.fmri_connectivity import FMRIConnectivityThread
from .InteractiveChartCard import InteractiveChartCard
from ..common.style_sheet import StyleSheet

class FMRIConnectivityPage(BaseFunctionPage):
    def __init__(self, parent=None):
        super().__init__("fMRI 功能连接分析", "读取 NIfTI 文件执行 fMRI 脑功能连接 3D 可视化生成交互式脑网络图，在主界面展示功能连接矩阵热力图、正负连接比例饼图、四项指标合一的滑动窗口时序图、关键窗口连接矩阵图集共 4 张多维度统计分析图表，并输出时序指标 CSV 文件与全窗口连接矩阵 npy 文件。", MODULE_FMRI_CONN, parent)
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

        self.btn_run = PushButton("一键分析fMRI功能连接", self.view, FIF.PLAY)
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

        self.set_running_state(True, "初始化 fMRI 连接分析流水线...")
        log_manager.add_log("开始计算 ROI 网络...", self.module_name)

        self.worker = FMRIWorkerThread(FMRIConnectivityThread, self.fmri_path, tr=2.0, mode="connectivity")
        def update_log(msg):
            self.status_label.setText(f"处理中: {msg}")
            log_manager.add_log(msg, self.module_name)

        self.worker.log_sig.connect(update_log)
        self.worker.finished_sig.connect(self._on_task_finished)
        self.worker.start()

    def _on_task_finished(self, success, result_data):
        self.set_running_state(False, "执行完成" if success else "执行失败")
        if success and result_data is not None:
            result_data = ast.literal_eval(result_data)

            main = result_data["main"]
            log_manager.add_log(f"fMRI 连接图生成完成: {main}", self.module_name)
            self.show_success_dialog("计算完毕", f"多图交互HTML分析报告已投递:\n{main}")
            self.show_html_in_subwindow(main, "fMRI 功能连接可视化")

            # 清理之前可能残留的卡片
            self._clear_previous_cards()

            # 创建一个用于容纳卡片的布局
            self.cards_container = QWidget()
            self.cards_container.setObjectName("CardsContainer")
            self.cards_layout = QVBoxLayout(self.cards_container)
            self.cards_layout.setContentsMargins(0, 16, 0, 0)
            self.cards_layout.setSpacing(16)

            card1 = InteractiveChartCard(
                title="全脑功能连接矩阵",
                description="AAL 脑区功能连接热力图，颜色代表脑区同步强度，红色为正相关、蓝色为负相关，越红 / 蓝关联越强。点击查看更多信息。",
                file_path=result_data.get('path_full_heatmap', ''),
                detail_text=
                """
本图基于AAL标准脑区分割模板，计算全脑两两脑区时间序列之间的皮尔逊相关系数，构建全脑功能连接矩阵。
    
如何理解：
- 横轴/纵轴：脑区索引，对应AAL脑区分割模板中的83个脑区
- 颜色刻度：从蓝色(-1.0)到红色(1.0)，代表皮尔逊相关系数大小
- 颜色越红：脑区间活动同步性越强，正相关越高
- 颜色越蓝：脑区间活动负相关程度越高
- 对角线元素：代表脑区与自身的相关值，恒为1，无生物学意义
    
核心用途：
1. 直观识别全脑功能网络的模块化结构与高密度连接通路
2. 快速定位核心枢纽脑区与异常连接（如显著负连接区域）
3. 为后续动态连接分析、图论网络属性计算及组间统计比较提供基础数据
                """,
                chart_name="全脑功能连接矩阵（AAL 脑区）",
                image_url=os.path.join(self.base_dir, "app/resource/images", "full_heat_map.jpg"),
            )
            card1.web_view.setFixedHeight(650)

            # 挂载卡片 2：正负连接饼图
            card2 = InteractiveChartCard(
                title="正负功能连接比例饼图",
                description="正负连接比例饼图，红色代表协同激活，蓝色代表反向调节。点击查看更多信息。",
                file_path=result_data.get('pie_path', ''),
                detail_text=
"""
本图基于全脑功能连接矩阵，统计所有脑区连接对中，正相关、负相关及零相关连接的占比分布情况。

如何理解：
- 红色扇区（Positive）：代表正相关连接占比，反映脑区间协同激活与同步活动
- 蓝色扇区（Negative）：代表负相关连接占比，反映脑区间功能拮抗与抑制性交互
- 灰色扇区（Zero）：代表无显著线性关联的连接占比

核心用途：
1. 量化评估大脑功能网络的兴奋-抑制平衡状态
2. 分析任务态或静息态下脑网络整体调控机制的变化
3. 为脑网络整合性、稳定性及病理状态（如精神疾病）的研究提供宏观指标
""",
                chart_name="正负功能连接比例饼图",
                image_url=os.path.join(self.base_dir, "app/resource/images", "pie_chart.jpg"),
            )
            card2.web_view.setFixedHeight(500)
            # 挂载卡片 3：多时间窗口功能连接热力图
            card3 = InteractiveChartCard(
                title="多时间窗口功能连接热力图",
                description="不同时间窗口连接热力图，观察脑网络随时间的动态变化。点击查看更多信息。",
                file_path=result_data.get('path_heatmap', ''),
                detail_text=
"""
本图选取全时间序列中具有代表性的关键时间窗口，分别展示各时段内的功能连接矩阵，用于直观呈现脑网络的动态重组过程。

如何理解：
- 每一个子图：对应一个独立的时间窗口（如窗口0对应0-60s, 窗口10 对应196-256s）
- 时间标注：显示每个窗口对应的时间范围，便于对应分析
- 颜色深浅：代表该时间点脑区间连接强度的高低
- 对比观察：通过多张子图的横向对比，可观察连接模式的时空演变

核心用途：
1. 追踪任务执行过程中，脑网络连接模式的动态演变与状态切换
2. 识别脑网络连接强度发生显著变化的关键时间节点
3. 验证动态功能连接分析的稳定性，观察不同时段网络结构的差异
""",
                chart_name="多时间窗口功能连接热力图",
                image_url=r"app\resource\images\heat_map_windows.jpg",
            )

            card3.web_view.setFixedHeight(550)

            # 挂载卡片 4：滑动窗口功能连接动态指标图
            card4 = InteractiveChartCard(
                title="滑动窗口功能连接动态指标图",
                description="滑动窗口动态功能连接，展示脑网络连接强度、平衡度与稳定性随时间的变化。点击查看更多信息。",
                file_path=result_data.get('path_metrics', ''),
                detail_text=
                """
本图通过在时间轴上滑动分析窗口，动态计算全脑功能连接的多维度统计指标，全面揭示脑网络随时间变化的时序特征与动态规律。

如何理解：
- 平均连接强度（左上）：横轴为时间，纵轴为平均绝对相关系数，反映整体连接水平
- 正负连接比例（右上）：红线为正连接比例，青线为负连接比例，反映网络兴奋-抑制平衡
- 连接异质性（左下）：横轴为时间，纵轴为连接值标准差，反映脑网络连接模式的多样性
- 滑动窗口覆盖示意（右下）：彩色条块展示每个分析窗口在时间轴上的位置与重叠关系

核心用途：
1. 评估脑网络连接强度的时间稳定性与动态波动趋势
2. 分析任务相关的脑网络兴奋/抑制平衡的动态转换机制
3. 量化脑网络状态的复杂性，为动态功能连接研究提供多维量化依据
                """,
                chart_name="滑动窗口功能连接动态指标图",
                image_url=os.path.join(self.base_dir, "app/resource/images", "fmri_sliding_window.png"),
                enable_animation=True,
            )
            card4.web_view.setFixedHeight(500)

            self.cards_layout.addWidget(card1)
            self.cards_layout.addWidget(card2)
            self.cards_layout.addWidget(card3)
            self.cards_layout.addWidget(card4)

            # 将卡片容器添加到当前页面的主内容区底部
            self.content_layout.addWidget(self.cards_container)

            self.view.updateGeometry()
            self.update()
            QApplication.processEvents()
        else:
            log_manager.add_log(f"连接计算失败: {result_data}", self.module_name)
            self.show_error_dialog("发生异常", f"提取或矩阵计算报错:\n{result_data}")