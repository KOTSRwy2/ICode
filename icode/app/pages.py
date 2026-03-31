# -*- coding: utf-8 -*-
import os
import ast
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog, QMainWindow,QGridLayout
)

from qfluentwidgets import (
    ScrollArea, ExpandLayout, SettingCardGroup, PushButton,
    ComboBoxSettingCard, qconfig, Theme, setTheme, setThemeColor, InfoBar, InfoBarPosition,
    TextEdit, ComboBox, LineEdit, IndeterminateProgressBar,
    SubtitleLabel, BodyLabel, OptionsSettingCard
)
from qfluentwidgets import FluentIcon as FIF

from .core import log_manager, WorkerThread, FMRIWorkerThread, MODULE_EEG_SOURCE, MODULE_EEG_CONN, MODULE_FMRI_ACT, MODULE_FMRI_CONN, MODULE_SYSTEM
from source_localization import compute_source_localization,show_source_localization_window
from connectivity_visualization import compute_connectivity_data, render_connectivity_html
from fmri_activation import FMRIActivationThread
from fmri_connectivity import FMRIConnectivityThread
from CustomWebEnginePage import CustomWebEngineView
from InteractiveChartCard import InteractiveChartCard
from app.common.config import cfg
from app.common.style_sheet import StyleSheet

class VisualizationWebWindow(QMainWindow):
    """仅负责显示 HTML 可视化结果的子窗口（可全屏/可交互）"""

    def __init__(self, html_path: str, title: str = "可视化结果", parent=None):
        super().__init__(parent)
        self._html_path = html_path
        self.setWindowTitle(title)
        self.resize(1280, 860)

        self.web = CustomWebEngineView(self)

        self.setCentralWidget(self.web)
        self.web.load(QUrl.fromLocalFile(os.path.abspath(html_path)))

        self.web.load(QUrl.fromLocalFile(os.path.abspath(html_path)))


# ==========================================
# 基础功能页面模板 (包含固定底部的进度状态栏)
# ==========================================
class BaseFunctionPage(ScrollArea):
    """提取四大功能页的共用逻辑：标题、文件选择、运行按钮、以及置底的进度条"""
    def __init__(self, title: str, description: str, module_name: str, parent=None):
        super().__init__(parent=parent)
        self.module_name = module_name
        self.setObjectName(title.replace(" ", "_"))
        # 保留圆角与无边框，不覆盖 Fluent 的主题背景绘制
        self.setWidgetResizable(True)
        self.setFrameShape(self.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # 移除强制样式覆盖，改用 FluentWidgets 推荐的透明化配置
        self.viewport().setObjectName("FunctionPageViewport")

        self.view = QWidget(self)
        self.view.setObjectName("FunctionPageView")

        # 主布局
        self.main_layout = QVBoxLayout(self.view)
        self.main_layout.setContentsMargins(36, 36, 36, 36)
        self.main_layout.setSpacing(24)

        # 建立标题区
        self.title_label = SubtitleLabel(title, self.view)
        self.desc_label = BodyLabel(description, self.view)
        # 使用 QFluentWidgets 默认配色，确保在深浅主题下均有良好的可读性

        self.main_layout.addWidget(self.title_label)
        self.main_layout.addWidget(self.desc_label)

        # 内容填充区 (子类在这里添加自己的输入和设置控件)
        self.content_layout = QVBoxLayout()
        self.content_layout.setSpacing(16)
        self.main_layout.addLayout(self.content_layout)

        self.main_layout.addStretch(1)

        # 底部状态展示区 (固定在页面下方)
        self._build_status_bar()
        self.main_layout.addWidget(self.status_container)

        self.setWidget(self.view)
        self.worker = None # 后台工作线程引用，防止被回收
        self.view.setObjectName('view')
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        print(self.base_dir)

    def _build_status_bar(self):
        # 进度状态外层布局
        self.status_container = QWidget(self.view)
        self.status_layout = QVBoxLayout(self.status_container)
        self.status_layout.setContentsMargins(0, 0, 0, 0)
        self.status_layout.setSpacing(6)

        # 状态小字，靠右对齐
        self.status_label = BodyLabel("当前状态...", self.status_container)
        self.status_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.status_label.setStyleSheet("font-size: 13px;")

        # 左右循环播放的进度条
        self.progress_bar = IndeterminateProgressBar(self.status_container,0.4)
        self.status_layout.addWidget(self.status_label)
        self.status_layout.addWidget(self.progress_bar)

        # 默认隐藏整个组件，运行时才展现
        self.status_container.setVisible(False)

    def set_running_state(self, is_running: bool, msg: str = "运行中..."):
        """统一切换底部状态：运行时显示并开启控件锁，否则关闭条幅"""
        self.status_container.setVisible(is_running)
        self.status_label.setText(msg)
        self.view.setEnabled(not is_running) # 运行期间锁定页面除状态栏外的操作

    def check_file_selected(self, file_path: str, ext_tuple: tuple, err_msg: str):
        if not file_path:
            InfoBar.warning("提示", "请选择需要处理的文件。", parent=self, position=InfoBarPosition.TOP_RIGHT)
            return False
        if not os.path.exists(file_path):
            InfoBar.error("错误", "所选文件不存在。", parent=self, position=InfoBarPosition.TOP_RIGHT)
            return False
        if not file_path.endswith(ext_tuple):
            InfoBar.error("错误", err_msg, parent=self, position=InfoBarPosition.TOP_RIGHT)
            return False
        return True

    def show_success_dialog(self, title: str, content: str):
        # 优化原有的弹窗，使用 InfoBar 组件在页面内进行不打断的通知
        InfoBar.success(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=3000,
            parent=self.window()
        )

    def show_error_dialog(self, title: str, content: str):
        InfoBar.error(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            position=InfoBarPosition.BOTTOM_RIGHT,
            duration=-1,
            parent=self.window()
        )

    def show_html_in_subwindow(self, html_path: str, title: str):
        """仅显示逻辑：将 HTML 在 QWebEngineView 子窗口中打开"""
        if not html_path or not os.path.exists(html_path):
            return
        self._viz_window = VisualizationWebWindow(html_path, title=title, parent=self.window())
        self._viz_window.show()

    def _on_theme_changed(self, theme: Theme):
        StyleSheet.MAIN.apply(self)

        # 刷新窗口
        self.update()
        self.repaint()
        QApplication.processEvents()

    def _clear_previous_cards(self):
        """清空之前生成的卡片容器（防止多次运行后无限往下叠加）"""
        if hasattr(self, 'cards_container') and self.cards_container is not None:
            self.content_layout.removeWidget(self.cards_container)
            self.cards_container.deleteLater()
            self.cards_container = None

# ==========================================
# EEG 源定位页面
# ==========================================
class EEGSourcePage(BaseFunctionPage):
    def __init__(self, parent=None):
        super().__init__("EEG 源定位可视化", "读取 BDF 文件并执行 3D 大脑源定位", MODULE_EEG_SOURCE, parent)
        self.bdf_path = ""
        self._init_ui()

    def _init_ui(self):
        file_layout = QHBoxLayout()
        self.path_edit = LineEdit(self.view)
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("选择一个 .bdf 脑电文件")

        self.btn_select = PushButton("浏览文件", self.view, FIF.FOLDER)
        self.btn_select.clicked.connect(self._select_file)

        file_layout.addWidget(self.path_edit)
        file_layout.addWidget(self.btn_select)

        parameters_layout = QHBoxLayout()

        dur_layout = QHBoxLayout()
        band_layout = QHBoxLayout()
        dur_label = BodyLabel("截取时长：", self.view)
        self.duration_box = ComboBox(self.view)
        self.duration_box.addItems(["5 秒", "10 秒", "30 秒", "60 秒", "全部"])

        dur_layout.addWidget(dur_label)
        dur_layout.addWidget(self.duration_box)
        dur_layout.addStretch(1)
        parameters_layout.addLayout(dur_layout)

        band_label = BodyLabel("分析频道：", self.view)
        self.band_box = ComboBox(self.view)
        self.band_box.addItems(["全频道", "α 频段", "β 频段", "γ 频段"])

        band_layout.addWidget(band_label)
        band_layout.addWidget(self.band_box)
        band_layout.addStretch(1)
        parameters_layout.addLayout(band_layout)

        self.btn_run = PushButton("执行 EEG 源定位", self.view, FIF.PLAY)
        self.btn_run.clicked.connect(self._run_task)

        self.content_layout.addLayout(file_layout)
        self.content_layout.addLayout(parameters_layout)
        self.content_layout.addWidget(self.btn_run)
        StyleSheet.MAIN.apply(self)

    def _select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 BDF 文件", "", "BDF Files (*.bdf)")
        if file_path:
            self.bdf_path = file_path
            self.path_edit.setText(file_path)
            log_manager.add_log(f"已选择 BDF 文件: {file_path}", self.module_name)

    def get_selected_duration(self):
        text = self.duration_box.currentText()
        mapping = {"5 秒": 5, "10 秒": 10, "30 秒": 30, "60 秒": 60, "全部": None}
        return mapping[text]

    def get_selected_band(self):
        text = self.band_box.currentText()
        mapping = {
            "全频道": "full",
            "α 频段": "alpha",
            "β 频段": "beta",
            "γ 频段": "gamma",
        }
        return mapping[text]

    def _update_source_log(self, msg):
        self.status_label.setText(f"目前步骤: {msg}")
        log_manager.add_log(msg, self.module_name)

    def _run_task(self):
        if not self.check_file_selected(self.bdf_path, (".bdf",), "请选择合法的 .bdf 格式文件。"):
            return

        # 防止重复点击
        if self.worker is not None and self.worker.isRunning():
            InfoBar.warning(
                title="提示",
                content="EEG源定位任务正在运行中，请稍候。",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=2500,
                parent=self.window()
            )
            return

        duration_sec = self.get_selected_duration()
        analysis_band = self.get_selected_band()
        plot_theme = "auto"

        self.set_running_state(True, "初始化读取EEG数据...")
        log_manager.add_log("开始运行 EEG 源定位...", self.module_name)
        log_manager.add_log(f"当前选择的分析频道：{self.band_box.currentText()}", self.module_name)

        # 用你们 core.py 里现成的 WorkerThread，把重计算放到后台
        self.worker = WorkerThread(
            compute_source_localization,
            self.bdf_path,
            duration_sec=duration_sec,
            analysis_band=analysis_band,
            plot_theme=plot_theme
        )

        self.worker.log_sig.connect(self._update_source_log)
        self.worker.finished_sig.connect(self._on_task_finished)
        self.worker.start()

    def _on_task_finished(self, success, result_data):
        # 先把线程对象释放掉
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None

        if success:
            try:
                # 这里已经回到主线程了，可以安全弹 MNE 3D 窗口
                self.status_label.setText("目前步骤: 正在打开 3D 窗口...")
                log_manager.add_log("EEG 源定位后台计算完成，正在打开 3D 窗口...", self.module_name)

                def ui_log(msg):
                    self.status_label.setText(f"目前步骤: {msg}")
                    log_manager.add_log(msg, self.module_name)

                show_source_localization_window(result_data, logger=ui_log)

                self.set_running_state(False, "执行完成")
                log_manager.add_log("EEG 源定位运行成功完成", self.module_name)
                self.show_success_dialog("操作成功", "EEG源定位已完成，已弹出并渲染3D窗口。")

                self._clear_previous_cards()

                # 创建一个用于容纳卡片的布局
                self.cards_container = QWidget()
                self.cards_container.setObjectName("CardsContainer")
                self.cards_layout = QVBoxLayout(self.cards_container)
                self.cards_layout.setContentsMargins(0, 16, 0, 0)
                self.cards_layout.setSpacing(16)

                # 挂载卡片 1：源活动时间序列图
                card1 = InteractiveChartCard(
                    title="全球功率时间曲线图",
                    description="本图实时记录了全脑所有源点电流强度的平均方根（RMS）随时间轴波动的轨迹，反映了全脑神经元放电的总能量水平随任务进程的起伏。",
                    file_path=result_data.get('time_course_path', ''),
                    detail_text=
                    """           
本图实时记录了全脑所有源点电流强度的平均方根（RMS）随时间轴波动的轨迹，反映了全脑神经元放电的总能量水平随任务进程的起伏。
如何理解:
-横轴：时间（ms），从刺激呈现时刻（0ms）开始计时。
-纵轴：平均感应强度（无量纲强度值）。
-峰值点：曲线最高点对应 P300 成分最显著的时刻，代表大脑对刺激进行特征提取和模板匹配的加工顶峰。

核心用途:
-潜伏期判定：通过寻找峰值所在的时间点，分析受试者对刺激反应的信息加工速度及大脑传导效率。
-算法自动联动：作为分析流水线的基准，确保后续的所有空间排名和网络分析均锁定在“信息处理最活跃”的黄金时间窗口。   
                    """,
                    chart_name="全球功率时间曲线图",
                    image_url=os.path.join(self.base_dir, "resource/images", "time_course.jpg"),
                    # tutorial_url = "https://blog.csdn.net/sky77/article/details/149389952",
                    enable_animation=True,
                )
                card1.web_view.setFixedHeight(500)

                # 挂载卡片 2：功率谱图
                card2 = InteractiveChartCard(
                    title="源活动功率谱密度图",
                    description="展示脑源信号在不同频率上的能量分布，用于检查信号成分与滤波效果。点击查看更多信息。",
                    file_path=result_data.get('psd_path', ''),
                    detail_text=
                    """
本图利用 Welch 法对重构出的源空间时间序列进行频域变换，量化了 1-45Hz 范围内各生理频段对信号总能量的贡献，揭示了大脑在执行任务时的振荡特征。

如何理解:
-横轴：频率 (Hz)，涵盖了从慢波 Delta 到快波 Gamma 的主要生理频段。
-纵轴：相对功率 (dB)。采用对数分贝单位，能更灵敏地反映微弱的高频成分及背景噪声。
-特征形态：正常脑电呈现 1/f 分布；以任务态P300为例，低频（1-6Hz）的能量突起通常代表诱发成分的贡献。

核心用途:
-信号纯净度评估：检查是否存在 50Hz 工频尖峰或由于眼动、肌电引起的高频干扰，验证带通滤波的有效性。
-脑态识别：通过分析 Alpha (8-13Hz) 或 Beta (13-30Hz) 频段的能量占比，评估受试者的觉醒水平、疲劳状态或认知负荷。               
                    """,
                    chart_name="源活动功率谱密度图",
                    image_url=os.path.join(self.base_dir, "resource/images", "psd.jpg"),
                    # tutorial_url = "https://blog.csdn.net/sky77/article/details/149389952",
                    enable_animation=True,
                )
                card2.web_view.setFixedHeight(500)

                # 挂载卡片 3：激活强度直方图
                card3 = InteractiveChartCard(
                    title="激活强度分布直方图",
                    description="全脑激活强度分布统计，展示皮层各点电活动的频数特征。点击查看更多信息。",
                    file_path=result_data.get('hist_path', ''),
                    detail_text=
                    """
本图基于源定位逆解计算得到的全脑皮层所有偶极子（Dipoles）电流强度，展示其在某一特定时间点或时间窗内的频数分布状况。该分布图反映了大脑在执行认知任务时，神经元活动的整体离散程度与激活水平，是判断源成像结果是否具有统计学显著性的重要直观指标。

如何理解
-横轴：激活强度（数值越大，代表皮层该位置的神经电活动响应越强烈，通常为归一化的电流密度值）。
-纵轴：对应激活强度的偶极子/源点数量（展示了全脑范围内不同活跃程度脑区的占比情况）。
-红色虚线：代表系统自动计算的 90% 分位数阈值线。虚线右侧的部分代表了当前大脑中统计上最显著的高响应脑区。

核心用途
-评估数据分布特征：快速观察全脑激活是呈现弥漫性特征还是局部显著特征，帮助评估源定位算法的收敛性与数据质量。
-量化激活范围：通过统计不同强度区间的脑源点占比，量化任务态下皮层资源的投入规模。
-科学设定分析阈值：为 3D 绘图及后续脑区排名提供客观的数据分布依据，确保选取的“显著激活脑区”具有严谨的统计学基础。              
                    """,
                    chart_name="激活强度分布直方图",
                    image_url=os.path.join(self.base_dir, "resource/images", "eeg_hist.png"),
                    # tutorial_url = "https://blog.csdn.net/sky77/article/details/149389952",
                    is_html = False
                )
                card3.web_view.setFixedHeight(500)

                # 挂载卡片 4：脑区激活排名
                card4 = InteractiveChartCard(
                    title="脑区激活 Top 15 柱状图",
                    description="以任务态P300为例，展示 P300 峰值时刻电流密度最高的前 15 个脑区，精准锁定任务触发的核心位置。点击查看更多信息。",
                    file_path=result_data.get('region_path', ''),
                    detail_text=
                    """
本图基于 dSPM（动态统计参数映射）算法，展示了在诱发电位（如 P300）峰值瞬间，全脑皮层电流偶极子强度（Current Amplitude）经归一化处理后的前 15 位解剖分区。该分析消除了不同被试间头皮厚度和电极阻抗的差异，实现了从头皮电信号到皮层神经活动的解剖定位。
如何理解
-横轴：相对激活强度（0-1 归一化）。数值越接近 1，代表该区域神经元集群在特定时间点的突触后电位同步性越高，能量释放越集中。
-纵轴：采用标准 Desikan-Killiany (aparc) 图谱命名的脑区。后缀 -lh 代表左脑，-rh 代表右脑。

核心用途
-解剖功能定位：识别如顶叶（Parietal）、前楔叶（Precuneus）等核心区域的参与度，验证 P300 的空间分布特性。
-生理机制验证：通过激活排名判断实验是否成功诱发了与注意力分配、刺激评价相关的脑部响应。
-科研量化对比：作为核心指标，用于对比不同组别（如健康组 vs 临床组）在任务态下皮层资源的投入差异。               
                    """,
                    chart_name="脑区激活 Top 15 柱状图",
                    image_url=os.path.join(self.base_dir, "resource/images", "top-K.jpg"),
                    # tutorial_url = "https://blog.csdn.net/sky77/article/details/149389952",
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

            except Exception as e:
                self.set_running_state(False, "执行失败")
                log_manager.add_log(f"EEG 源定位窗口显示失败: {str(e)}", self.module_name)
                self.show_error_dialog("显示失败", f"源定位结果已计算完成，但显示3D窗口时发生错误：\n{str(e)}")
        else:
            self.set_running_state(False, "执行失败")
            log_manager.add_log(f"EEG 源定位运行失败: {result_data}", self.module_name)
            self.show_error_dialog("运行失败", f"源定位过程中发生错误：\n{result_data}")


# ==========================================
# EEG 功能连接页面
# ==========================================
class EEGConnectivityPage(BaseFunctionPage):
    def __init__(self, parent=None):
        super().__init__("EEG 功能连接分析", "计算频带连接强度并导出交互式图表", MODULE_EEG_CONN, parent)
        self.bdf_path = ""
        self._init_ui()

    def _init_ui(self):
        file_layout = QHBoxLayout()
        self.path_edit = LineEdit(self.view)
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("选择一个 .bdf 脑电文件")

        self.btn_select = PushButton("浏览文件", self.view, FIF.FOLDER)
        self.btn_select.clicked.connect(self._select_file)

        file_layout.addWidget(self.path_edit)
        file_layout.addWidget(self.btn_select)

        parameters_layout = QHBoxLayout()

        dur_layout = QHBoxLayout()
        dur_label = BodyLabel("截取时长：", self.view)
        self.duration_box = ComboBox(self.view)
        self.duration_box.addItems(["5 秒", "10 秒", "30 秒", "60 秒", "全部"])

        dur_layout.addWidget(dur_label)
        dur_layout.addWidget(self.duration_box)
        dur_layout.addStretch(1)
        parameters_layout.addLayout(dur_layout)

        band_layout = QHBoxLayout()
        band_label = BodyLabel("分析频道：", self.view)
        self.band_box = ComboBox(self.view)
        self.band_box.addItems(["全频道", "α 频段", "β 频段", "γ 频段"])

        band_layout.addWidget(band_label)
        band_layout.addWidget(self.band_box)
        band_layout.addStretch(1)
        parameters_layout.addLayout(band_layout)

        self.btn_run = PushButton("执行功能连接分析", self.view, FIF.PLAY)
        self.btn_run.clicked.connect(self._run_task)

        self.content_layout.addLayout(file_layout)
        self.content_layout.addLayout(parameters_layout)
        self.content_layout.addWidget(self.btn_run)
        StyleSheet.MAIN.apply(self)

    def get_selected_duration(self):
        text = self.duration_box.currentText()
        mapping = {"5 秒": 5, "10 秒": 10, "30 秒": 30, "60 秒": 60, "全部": None}
        return mapping[text]

    def get_selected_band(self):
        text = self.band_box.currentText()
        mapping = {
            "全频道": "full",
            "α 频段": "alpha",
            "β 频段": "beta",
            "γ 频段": "gamma",
        }
        return mapping[text]

    def _update_connectivity_log(self, msg):
        self.status_label.setText(f"目前步骤: {msg}")
        log_manager.add_log(msg, self.module_name)

    def _select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 BDF 文件", "", "BDF Files (*.bdf)")
        if file_path:
            self.bdf_path = file_path
            self.path_edit.setText(file_path)
            log_manager.add_log(f"已选择 BDF 文件: {file_path}", self.module_name)

    def _run_task(self):
        if not self.check_file_selected(self.bdf_path, (".bdf",), "请选择合法的 .bdf 格式文件。"):
            return

        if self.worker is not None and self.worker.isRunning():
            InfoBar.warning(
                title="提示",
                content="EEG功能连接任务正在运行中，请稍候。",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=2500,
                parent=self.window()
            )
            return

        duration_sec = self.get_selected_duration()
        analysis_band = self.get_selected_band()

        self.set_running_state(True, "初始化连接分析网络...")
        log_manager.add_log("开始运行 EEG 功能连接...", self.module_name)
        log_manager.add_log(f"当前选择的分析频道：{self.band_box.currentText()}", self.module_name)

        # 这里只做后台计算，不在线程里创建 Brain
        self.worker = WorkerThread(
            compute_connectivity_data,
            self.bdf_path,
            analysis_band=analysis_band,
            duration_sec=duration_sec
        )

        self.worker.log_sig.connect(self._update_connectivity_log)
        self.worker.finished_sig.connect(self._on_task_finished)
        self.worker.start()

    def _on_task_finished(self, success, result):
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None

        if not success:
            self.set_running_state(False, "执行失败")
            log_manager.add_log(f"分析失败: {result}", self.module_name)
            self.show_error_dialog("分析失败", f"功能连接分析过程中发生错误：\n{result}")
            return

        try:
            self.status_label.setText("目前步骤: 后台计算完成，正在主线程生成 3D 场景并导出 HTML...")
            log_manager.add_log("后台计算完成，开始在主线程生成 3D 场景并导出 HTML...", self.module_name)

            result_data = render_connectivity_html(result, logger=self._update_connectivity_log)
            main_path = result_data["main"]

            self.set_running_state(False, "执行完成")
            log_manager.add_log(f"功能连接导出成功: {main_path}", self.module_name)
            self.show_success_dialog("任务完成", f"结果已保存并生成 HTML：\n{main_path}")
            self.show_html_in_subwindow(main_path, "EEG 功能连接可视化")

            self._clear_previous_cards()

            # 创建一个用于容纳卡片的布局
            self.cards_container = QWidget()
            self.cards_container.setObjectName("CardsContainer")
            self.cards_layout = QVBoxLayout(self.cards_container)
            self.cards_layout.setContentsMargins(0, 16, 0, 0)
            self.cards_layout.setSpacing(16)

            # 挂载卡片 1：曲线图
            card1 = InteractiveChartCard(
                title="功能连接强度矩阵",
                description="展示全脑 68 个脑区间的同步强度，红色代表强耦合，蓝色代表低同步。点击查看更多信息。",
                file_path=result_data.get('fc_matrix_path', ''),
                detail_text=
"""
本图基于皮尔逊相关系数计算全脑各解剖分区信号序列的瞬时协同程度，构建出 68*68 的功能交互网络，量化了不同脑区间连接的紧密程度。
如何理解
横纵轴：对应 68 个解剖脑区。颜色越深红，代表两个脑区间的电活动同步性越高，功能耦合越强。
块状结构：矩阵中出现的深红色“小方块”通常代表了特定功能模块（如视觉网络、注意力网络）内部的高度集成。

核心用途
-网络拓扑扫描：识别大脑在处理认知任务时，各功能模块之间是处于高度集成状态还是相对分工状态。
-质量控制：排查是否存在由于公共参考电极或全局噪声导致的伪影性高相关，确保连接结果的生理学效度。               
""",
                chart_name="功能连接强度矩阵",
                image_url=os.path.join(self.base_dir, "resource/images", "eeg_heat_map.jpg"),
                # tutorial_url = "https://blog.csdn.net/sky77/article/details/149389952",
            )
            card1.web_view.setFixedHeight(650)

            # 挂载卡片 2：曲线图
            card2 = InteractiveChartCard(
                title="网络核心枢纽排名图",
                description="找出大脑网络中的“CEO”脑区，展示影响力最强的核心节点。点击查看更多信息。",
                file_path=result_data.get('fc_hubs_path', ''),
                detail_text=
"""  
本图引入图论（Graph Theory）中的“加权节点度”指标，量化了每个脑区在全脑神经网络信息交换中的枢纽地位和全局影响力。
如何理解
-纵轴：排名靠前的核心枢纽脑区名称。
-横轴：节点度数值，即该脑区与网络中所有其他脑区连接强度的总和。
-逻辑：数值越高，代表该区在全脑信息流中起到“调度中心”的作用越强。

核心用途
-关键靶点识别：定位在特定认知过程中起到协调全局作用的核心节点，为脑机接口（BCI）选点或经颅磁刺激（TMS）提供参考。
-网络稳定性分析：观察在不同任务负荷下，大脑核心枢纽的迁移规律，评估神经网络的抗干扰能力。             
""",
                chart_name="网络核心枢纽排名图",
                image_url=os.path.join(self.base_dir, "resource/images", "network_hub.jpg"),
                # tutorial_url = "https://blog.csdn.net/sky77/article/details/149389952",
            )
            card2.web_view.setFixedHeight(500)

            # 挂载卡片 3：曲线图
            card3 = InteractiveChartCard(
                title="连接强度分布直方图",
                description="统计全脑数千条连接的整体分布，用于评估网络健康度与设定筛选阈值。点击查看更多信息。",
                file_path=result_data.get('fc_distribution_path', ''),
                detail_text=
"""  
本图统计了连接矩阵中数千条连接对的相关系数频率分布。在大脑网络中，连接的强度分布直接反映了信息传递的经济性和有效性。
如何理解
-横轴：相关系数值（-1 到 1）。
-分布形态：健康的 EEG 网络通常呈现“小世界”特征，即大部分连接为中低强度（0.2-0.4），仅少数关键连接表现为极高强度。

核心用途
-筛选阈值科学化：为“连接边剪枝”提供统计学依据。通过观察分布，选择能够保留最强 10% 关键连接的阈值。
-全局属性评估：若分布过度偏右（高相关），可能存在全局干扰；若过度偏左（低相关），则可能信号质量过低。             
""",
                chart_name="连接强度分布直方图",
                image_url=os.path.join(self.base_dir, "resource/images", "Weight Distribution.png"),
                # tutorial_url = "https://blog.csdn.net/sky77/article/details/149389952",
            )
            card3.web_view.setFixedHeight(500)

            # 挂载卡片 4：曲线图
            card4 = InteractiveChartCard(
                title="距离-强度相关性散点图",
                description="探索物理距离对功能连接的影响，验证大脑的空间组织逻辑。点击查看更多信息。",
                file_path=result_data.get('fc_distance_path', ''),
                detail_text=
""" 
本图研究两脑区间的 3D 几何距离与功能同步强度之间的关系，揭示了大脑在处理信息时，物理成本与功能整合之间的平衡。
如何理解
-横轴：两脑区中心的空间直线距离 (mm)。
-趋势线：通常向下倾斜，代表“近邻连接强、远端连接弱”的生理规律。
-离群点：右上角的点代表虽然物理距离远、但功能高度同步，反映了大脑的长距离功能整合（如额顶网络）。

核心用途
-空间约束分析：验证是否存在跨越半球或长距离的功能协作，排除“体积传导”引起的伪相关。
-生理逻辑验证：如果趋势线斜率异常平坦，可能提示数据存在全局系统性误差。              
""",
                chart_name="距离-强度相关性散点图",
                image_url=os.path.join(self.base_dir, "resource/images", "diatance-connectivity.png"),
                # tutorial_url = "https://blog.csdn.net/sky77/article/details/149389952",
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

        except Exception as e:
            self.set_running_state(False, "执行失败")
            log_manager.add_log(f"功能连接渲染失败: {str(e)}", self.module_name)
            self.show_error_dialog("渲染失败", f"后台计算已完成，但生成 3D/导出 HTML 时出错：\n{str(e)}")


# ==========================================
# fMRI 激活定位页面
# ==========================================
class FMRIActivationPage(BaseFunctionPage):
    def __init__(self, parent=None):
        super().__init__("fMRI 脑区激活定位", "生成并展示皮层 fMRI 激活热力图", MODULE_FMRI_ACT, parent)
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

            # 清理之前可能残留的卡片
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
                image_url = os.path.join(self.base_dir, "resource/images","fmri_activation_crue.jpg"),
                # tutorial_url = "https://blog.csdn.net/sky77/article/details/149389952",
                enable_animation=True,
            )
            card1.web_view.setFixedHeight(500)
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
                image_url = os.path.join(self.base_dir, "resource/images", "fmri_hist.png"),
                # tutorial_url = "https://chat.qwen.ai/c/143eeb40-1792-4113-9bc3-43a1af669976",
                enable_animation=False,
            )
            card2.web_view.setFixedHeight(500)

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

# ==========================================
# fMRI 连接分析页面
# ==========================================
class FMRIConnectivityPage(BaseFunctionPage):
    def __init__(self, parent=None):
        super().__init__("fMRI 功能连接分析", "基于 AAL 标准模板提取并计算网络连通性", MODULE_FMRI_CONN, parent)
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

        self.btn_run = PushButton("计算独立功能网络", self.view, FIF.PLAY)
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

            # 挂载卡片 1：正负连接饼图
            card1 = InteractiveChartCard(
                title="正负功能连接比例饼图",
                description="正负连接比例饼图，红色代表协同激活，青色代表反向调节。点击查看更多信息。",
                file_path=result_data.get('pie_path', ''),
                detail_text=
"""
本图基于全脑功能连接矩阵，统计所有脑区连接对中，正相关、负相关及零相关连接的占比分布情况。

如何理解：
- 红色扇区（Positive）：代表正相关连接占比，反映脑区间协同激活与同步活动
- 青色扇区（Negative）：代表负相关连接占比，反映脑区间功能拮抗与抑制性交互
- 灰色扇区（Zero）：代表无显著线性关联的连接占比

核心用途：
1. 量化评估大脑功能网络的兴奋-抑制平衡状态
2. 分析任务态或静息态下脑网络整体调控机制的变化
3. 为脑网络整合性、稳定性及病理状态（如精神疾病）的研究提供宏观指标
""",
                chart_name="正负功能连接比例饼图",
                image_url=os.path.join(self.base_dir, "resource/images", "pie_chart.jpg"),
                # tutorial_url="https://blog.csdn.net/sky77/article/details/149389952",
            )
            card1.web_view.setFixedHeight(500)
            # 挂载卡片 2：滑动窗口功能连接动态指标图
            card2 = InteractiveChartCard(
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
                image_url=os.path.join(self.base_dir, "resource/images", "indicators.png"),
                # tutorial_url="https://chat.qwen.ai/c/143eeb40-1792-4113-9bc3-43a1af669976",
                enable_animation=True,
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
                # tutorial_url="https://chat.qwen.ai/c/143eeb40-1792-4113-9bc3-43a1af669976",
            )

            card3.web_view.setFixedHeight(550)

            card4 = InteractiveChartCard(
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
                image_url=os.path.join(self.base_dir, "resource/images", "full_heat_map.jpg"),
                # tutorial_url="https://chat.qwen.ai/c/143eeb40-1792-4113-9bc3-43a1af669976",
            )
            card4.web_view.setFixedHeight(650)
            # 添加到垂直布局
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


# ==========================================
# 集中化日志报告页面
# ==========================================
class LogReportPage(ScrollArea):
    """独立的系统中心日志监控面板"""
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("Log_Report")
        self.setWidgetResizable(True)
        self.setFrameShape(self.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)


        self.view = QWidget(self)
        self.view.setObjectName("LogReportPageView")

        self.main_layout = QVBoxLayout(self.view)
        self.main_layout.setContentsMargins(36, 36, 36, 36)

        self.title_label = SubtitleLabel("系统运行日志", self.view)
        self.main_layout.addWidget(self.title_label)
        self.main_layout.addSpacing(16)

        # 过滤器与操作区
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(BodyLabel("日志模块源:", self.view))

        self.combo_filter = ComboBox(self.view)
        self.combo_filter.addItems(["全部", MODULE_EEG_SOURCE, MODULE_EEG_CONN, MODULE_FMRI_ACT, MODULE_FMRI_CONN, MODULE_SYSTEM])
        self.combo_filter.currentIndexChanged.connect(self._update_log_display)
        filter_layout.addWidget(self.combo_filter)

        self.btn_export = PushButton("导出日志报表", self.view, FIF.DOWNLOAD)
        self.btn_export.clicked.connect(self._export_log)
        filter_layout.addWidget(self.btn_export)

        self.btn_clear = PushButton("清理屏幕", self.view, FIF.DELETE)
        self.btn_clear.clicked.connect(self._clear_log)
        filter_layout.addWidget(self.btn_clear)

        filter_layout.addStretch(1)
        self.main_layout.addLayout(filter_layout)

        # 多行只读本文显示区
        self.text_editor = TextEdit(self.view)
        self.text_editor.setReadOnly(True)
        self.text_editor.setPlaceholderText("暂无日志报告...")
        self.main_layout.addWidget(self.text_editor, stretch=1)

        self.setWidget(self.view)

        # 绑定核心派发器刷新UI
        log_manager.log_updated.connect(self._update_log_display)
        StyleSheet.MAIN.apply(self)

    def _update_log_display(self):
        mod = self.combo_filter.currentText()
        lines = log_manager.get_logs(mod)
        self.text_editor.setPlainText("\n".join(lines))
        self.text_editor.verticalScrollBar().setValue(self.text_editor.verticalScrollBar().maximum())

    def _clear_log(self):
        log_manager.clear()

    def _export_log(self):
        mod = self.combo_filter.currentText()
        lines = log_manager.get_logs(mod)
        if not lines:
            InfoBar.warning("导出提示", "当前过滤器下没有可导出的日志。", parent=self.window(), position=InfoBarPosition.BOTTOM_RIGHT)
            return

        path, _ = QFileDialog.getSaveFileName(self, "导出运行记录", f"system_logs_{mod}.txt", "Text Files (*.txt)")
        if path:
            with open(path, "w", encoding='utf-8') as f:
                f.write("\n".join(lines))
            InfoBar.success("导出完成", f"日志报告已落地到指定记录:\n{path}", parent=self.window(), position=InfoBarPosition.BOTTOM_RIGHT)


# ==========================================
# 通用设置中心页面
# ==========================================
class SettingsPage(ScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setObjectName("Global_Settings")
        self.setWidgetResizable(True)
        self.setFrameShape(self.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.view = QWidget(self)
        self.view.setObjectName("SettingsPageView")

        self.expand_layout = ExpandLayout(self.view)
        self.expand_layout.setContentsMargins(36, 36, 36, 36)

        self._init_ui()

    def _init_ui(self):
        title = SubtitleLabel("系统设置", self.view)
        self.expand_layout.addWidget(title)

        # 使用分组归类管理项
        self.personal_group = SettingCardGroup("界面与主题", self.view)

        # 主题模式：必须调用 setTheme 才会刷新 Fluent 背景与控件样式
        self.theme_card = OptionsSettingCard(
            cfg.themeMode,
            FIF.BRUSH,
            self.tr("应用主题"),
            self.tr("更改应用的外观并重新映射内部颜色"),
            texts=[
                self.tr("浅色"), self.tr("深色"),
                self.tr("跟随系统")
            ],
            parent=self.personal_group
        )

        from qfluentwidgets import ColorSettingCard
        self.color_card = ColorSettingCard(
            cfg.themeColor,
            icon=FIF.PALETTE,
            title="主题色",
            content="自定义状态与高亮的指向色",
            parent=self.personal_group
        )

        self.personal_group.addSettingCard(self.theme_card)
        self.personal_group.addSettingCard(self.color_card)

        # ensure theme changes actually update qfluentwidgets styles
        cfg.themeChanged.connect(setTheme)
        # propagate color selection to fluent theme color
        self.color_card.colorChanged.connect(lambda c: setThemeColor(c))

        self.expand_layout.addWidget(self.personal_group)
        self.setWidget(self.view)
        StyleSheet.MAIN.apply(self)

    def _on_theme_changed(self, theme):
        # theme = [Theme.LIGHT, Theme.DARK, Theme.AUTO][index]
        # setTheme(theme, save=True, lazy=False)
        # # qconfig.themeChanged 信号会触发 main.py 中的刷新，但我们这里也可以手动更新样式
        # # FluentStyleSheet.apply(self.window())
        StyleSheet.MAIN.apply(self)

        # 刷新窗口
        self.update()
        self.repaint()
        QApplication.processEvents()