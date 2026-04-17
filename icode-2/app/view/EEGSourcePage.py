# -*- coding: utf-8 -*-
from .BaseFunctionPage import BaseFunctionPage
import os
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog
)
from qfluentwidgets import (
    PushButton, LineEdit, BodyLabel, ComboBox, InfoBar, InfoBarPosition
)
from qfluentwidgets import FluentIcon as FIF

from .core import log_manager, EEGWorkerThread, MODULE_EEG_SOURCE, _oss_internal_put, UPLOAD_CONFIG
from ..functions.eeg_scource_localization import compute_source_localization, show_source_localization_window
from .InteractiveChartCard import InteractiveChartCard
from ..common.style_sheet import StyleSheet

class _SourceMissingUploadThread(QThread):
    finished = pyqtSignal(dict)

    def __init__(self, result_data):
        super().__init__()
        self.result_data = result_data

    def run(self):
        oss_urls = dict(self.result_data.get("oss_urls") or {})
        path_map = UPLOAD_CONFIG.get("EEG_SOURCE", {})

        # 只补传缺失项：重点覆盖 main / hist_path，且不影响已成功上传项
        for key in ("main", "hist_path"):
            if oss_urls.get(key):
                continue
            local_file = self.result_data.get(key)
            folder = path_map.get(key)
            if local_file and folder and os.path.exists(local_file):
                url = _oss_internal_put(local_file, folder)
                if url:
                    oss_urls[key] = url

        self.result_data["oss_urls"] = oss_urls
        self.result_data["share_url"] = oss_urls.get("main")
        self.finished.emit(oss_urls)

class EEGSourcePage(BaseFunctionPage):
    def __init__(self, parent=None):
        super().__init__("EEG 源定位可视化", "读取 BDF 文件执行 3D 大脑源定位可视化，并在主界面展示全球功率时间曲线图、源活动功率谱密度图、激活强度分布直方图和脑区激活 Top15 柱状图共 4 张源活动统计分析图表。", MODULE_EEG_SOURCE, parent)
        self.bdf_path = ""
        self.worker = None
        self.upload_worker = None
        self.cards_container = None
        
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
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

    def _update_source_log(self, msg):
        msg_text = str(msg)
        self.status_label.setText(f"处理中: {msg_text}")
        log_manager.add_log(msg_text, self.module_name)

    def _run_task(self):
        if not self.check_file_selected(self.bdf_path, (".bdf",), "请选择合法的 .bdf 格式文件。"):
            return

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
        self.share_link_edit.setVisible(False)
        self.copy_link_btn.setVisible(False)
        self.share_link_edit.clear()

        self.set_running_state(True, "初始化读取EEG数据...")
        log_manager.add_log("开始运行 EEG 源定位...", self.module_name)

        self.worker = EEGWorkerThread(
            compute_source_localization,
            lambda data, logger=None: data,
            self.bdf_path,
            band=analysis_band,
            duration=duration_sec,
            mode="SOURCE"
        )

        self.worker.log_sig.connect(self._update_source_log)
        self.worker.finished_sig.connect(self._on_task_finished)
        self.worker.start()

    def _on_task_finished(self, success, result_data):
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None

        if success:
            try:
                share_url = result_data.get("share_url")
                if share_url:
                    self._show_share_link(share_url)
                    log_manager.add_log(f"源定位结果已同步至云端: {share_url}", self.module_name)

                self.status_label.setText("目前步骤: 正在打开 3D 窗口...")
                log_manager.add_log("EEG 源定位后台计算完成，正在打开 3D 窗口...", self.module_name)

                def ui_log(msg):
                    self.status_label.setText(f"目前步骤: {msg}")
                    log_manager.add_log(msg, self.module_name)

                brain = show_source_localization_window(result_data, logger=ui_log)

                # 3D 图导出在主线程完成后，再补传缺失的主图/直方图
                def start_missing_upload():
                    if self.upload_worker is not None and self.upload_worker.isRunning():
                        return
                    self.upload_worker = _SourceMissingUploadThread(result_data)

                    def on_missing_upload_done(_oss_urls):
                        added_count = len(_oss_urls or {})
                        log_manager.add_log(
                            f"云端补传完成：当前已同步 {added_count} 个结果文件。",
                            self.module_name
                        )
                        share_url_after = result_data.get("share_url")
                        if share_url_after:
                            self._show_share_link(share_url_after)
                            log_manager.add_log(f"源定位结果已同步至云端: {share_url_after}", self.module_name)
                        if self.upload_worker is not None:
                            self.upload_worker.deleteLater()
                            self.upload_worker = None

                    self.upload_worker.finished.connect(on_missing_upload_done)
                    self.upload_worker.start()

                QTimer.singleShot(0, start_missing_upload)

                self.set_running_state(True, "3D 视界已开启。请进行交互，关闭或最小化窗口后将加载分析报告。")
                log_manager.add_log("EEG 源定位运行成功完成", self.module_name)
                InfoBar.success(
                    title="操作成功",
                    content="EEG源定位已完成。关闭或最小化 3D 窗口后将加载统计报告。",
                    orient=Qt.Horizontal,
                    isClosable=True,
                    position=InfoBarPosition.TOP_RIGHT,
                    duration=3000,
                    parent=self.window()
                )

                def create_and_load_cards():
                    self._clear_previous_cards()
                    self.cards_container = QWidget()
                    self.cards_container.setObjectName("CardsContainer")
                    self.cards_layout = QVBoxLayout(self.cards_container)
                    self.cards_layout.setContentsMargins(0, 16, 0, 0)
                    self.cards_layout.setSpacing(16)

                    card1 = InteractiveChartCard(
                        title="全球功率时间曲线图",
                        description="本图实时记录了全脑所有源点电流强度的平均方根（RMS）随时间轴波动的轨迹，反映了全脑神经元放电的总能量水平随任务进程的起伏。",
                        file_path=result_data.get('gfp_path', ''),
                        detail_text="""
本图实时记录了全脑所有源点电流强度的平均方根（RMS）随时间轴波动的轨迹，反映了全脑神经元放电的总能量水平随任务进程的起伏。

如何理解:
- 横轴：时间（ms），从刺激呈现时刻（0ms）开始计时。
- 纵轴：平均感应强度（无量纲强度值）。
- 峰值点：曲线最高点对应 P300 成分最显著的时刻，代表大脑对刺激进行特征提取和模板匹配的加工顶峰。

核心用途:
1. 潜伏期判定：通过寻找峰值所在的时间点，分析受试者对刺激反应的信息加工速度及大脑传导效率。
2. 算法自动联动：作为分析流水线的基准，确保后续的所有空间排名和网络分析均锁定在“信息处理最活跃”的黄金时间窗口。
""",
                        chart_name="全球功率时间曲线图",
                        image_url=os.path.join(self.base_dir, "app/resource/images", "time_course.jpg"),
                        enable_animation=True,
                    )
                    card1.web_view.setFixedHeight(500)
                    self.cards_layout.addWidget(card1)

                    card2 = InteractiveChartCard(
                        title="源活动功率谱密度图",
                        description="展示脑源信号在不同频率上的能量分布，用于检查信号成分与滤波效果。点击查看更多信息。",
                        file_path=result_data.get('psd_path', ''),
                        detail_text="""
本图利用 Welch 法对重构出的源空间时间序列进行频域变换，量化了 1-45Hz 范围内各生理频段对信号总能量的贡献，揭示了大脑在执行任务时的振荡特征。

如何理解:
- 横轴：频率 (Hz)，涵盖了从慢波 Delta 到快波 Gamma 的主要生理频段。
- 纵轴：相对功率 (dB)。采用对数分贝单位，能更灵敏地反映微弱的高频成分及背景噪声。
- 特征形态：正常脑电呈现 1/f 分布；以任务态 P300 为例，低频（1-6Hz）的能量突起通常代表诱发成分的贡献。

核心用途:
1. 信号纯净度评估：检查是否存在 50Hz 工频尖峰或由于眼动、肌电引起的高频干扰，验证带通滤波的有效性。
2. 脑态识别：通过分析 Alpha (8-13Hz) 或 Beta (13-30Hz) 频段的能量占比，评估受试者的觉醒水平、疲劳状态或认知负荷。
""",
                        chart_name="源活动功率谱密度图",
                        image_url=os.path.join(self.base_dir, "app/resource/images", "psd.jpg"),
                        enable_animation=True,
                    )
                    card2.web_view.setFixedHeight(500)
                    self.cards_layout.addWidget(card2)

                    card3 = InteractiveChartCard(
                        title="激活强度分布直方图",
                        description="全脑激活强度分布统计，展示皮层各点电活动的频数特征。点击查看更多信息。",
                        file_path=result_data.get('hist_path', ''),
                        detail_text="""
本图基于源定位逆解计算得到的全脑皮层所有偶极子（Dipoles）电流强度，展示其在某一特定时间点或时间窗内的频数分布状况。该分布图反映了大脑在执行认知任务时，神经元活动的整体离散程度与激活水平，是判断源成像结果是否具有统计学显著性的重要直观指标。

如何理解:
- 横轴：激活强度（数值越大，代表皮层该位置的神经电活动响应越强烈，通常为归一化的电流密度值）。
- 纵轴：对应激活强度的偶极子/源点数量（展示了全脑范围内不同活跃程度脑区的占比情况）。
- 红色虚线：代表系统自动计算的 95% 分位数阈值线。虚线右侧的部分代表了当前大脑中统计上最显著的高响应脑区。

核心用途:
1. 评估数据分布特征：快速观察全脑激活是呈现弥漫性特征还是局部显著特征，帮助评估源定位算法的收敛性与数据质量。
2. 量化激活范围：通过统计不同强度区间的脑源点占比，量化任务态下皮层资源的投入规模。
3. 科学设定分析阈值：为 3D 绘图及后续脑区排名提供客观的数据分布依据，确保选取的“显著激活脑区”具有严谨的统计学基础。
""",
                        chart_name="激活强度分布直方图",
                        image_url=os.path.join(self.base_dir, "app/resource/images", "eeg_hist.png"),
                        is_html=False
                    )
                    card3.web_view.setFixedHeight(500)
                    self.cards_layout.addWidget(card3)

                    card4 = InteractiveChartCard(
                        title="脑区激活 Top 15 柱状图",
                        description="展示特定时刻电流密度最高的前 15 个脑区，精准锁定任务触发的核心位置。点击查看更多信息。",
                        file_path=result_data.get('top15_path', ''),
                        detail_text="""
本图基于 dSPM（动态统计参数映射）算法，展示了在诱发电位峰值瞬间，全脑皮层电流偶极子强度（Current Amplitude）经归一化处理后的前 15 位解剖分区。该分析消除了不同被试间头皮厚度和电极阻抗的差异，实现了从头皮电信号到皮层神经活动的解剖定位。

如何理解:
- 横轴：相对激活强度（0-1 归一化）。数值越接近 1，代表该区域神经元集群在特定时间点的突触后电位同步性越高，能量释放越集中。
- 纵轴：采用标准 Desikan-Killiany (aparc) 图谱命名的脑区。后缀 -lh 代表左脑，-rh 代表右脑。

核心用途:
1. 解剖功能定位：识别如顶叶（Parietal）、前楔叶（Precuneus）等核心区域的参与度，验证 P300 的空间分布特性。
2. 生理机制验证：通过激活排名判断实验是否成功诱发了与注意力分配、刺激评价相关的脑部响应。
3. 科研量化对比：作为核心指标，用于对比不同组别在任务态下皮层资源的投入差异。
""",
                        chart_name="脑区激活排行榜",
                        image_url=os.path.join(self.base_dir, "app/resource/images", "top-K.jpg"),
                    )
                    card4.web_view.setFixedHeight(500)
                    self.cards_layout.addWidget(card4)

                    self.content_layout.addWidget(self.cards_container)
                    self.view.updateGeometry()
                    self.update()

                    QTimer.singleShot(100, card1.load_chart)
                    QTimer.singleShot(400, card2.load_chart)
                    QTimer.singleShot(700, card3.load_chart)
                    QTimer.singleShot(1000, card4.load_chart)
                    
                    QTimer.singleShot(1200, lambda: self.set_running_state(False, "执行完成"))

                if brain and hasattr(brain, 'plotter') and brain.plotter.app_window:
                    app_win = brain.plotter.app_window
                    
                    def check_window_state():
                        if app_win.isMinimized() or not app_win.isVisible():
                            monitor_timer.stop()
                            create_and_load_cards()
                    
                    monitor_timer = QTimer(self)
                    monitor_timer.timeout.connect(check_window_state)
                    monitor_timer.start(500)
                    
                    app_win.destroyed.connect(lambda: (monitor_timer.stop(), create_and_load_cards()))
                else:
                    create_and_load_cards()

            except Exception as e:
                self.set_running_state(False, "执行失败")
                log_manager.add_log(f"EEG 源定位窗口显示失败: {str(e)}", self.module_name)
                self.show_error_dialog("显示失败", f"源定位结果已计算完成，但显示3D窗口时发生错误：\n{str(e)}")
        else:
            self.set_running_state(False, "执行失败")
            log_manager.add_log(f"EEG 源定位运行失败: {result_data}", self.module_name)
            self.show_error_dialog("运行失败", f"源定位过程中发生错误：\n{result_data}")