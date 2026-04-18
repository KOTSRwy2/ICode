# -*- coding: utf-8 -*-
from .BaseFunctionPage import BaseFunctionPage
import os
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog
)

from qfluentwidgets import (
    PushButton, InfoBar, InfoBarPosition, ComboBox, LineEdit, BodyLabel
)
from qfluentwidgets import FluentIcon as FIF

from .core import log_manager, WorkerThread, MODULE_EEG_CONN, _oss_internal_put, UPLOAD_CONFIG
from ..functions.eeg_connectivity_visualization import compute_connectivity_data, render_connectivity_html

from .InteractiveChartCard import InteractiveChartCard
from ..common.style_sheet import StyleSheet

class _SimpleUploadThread(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, result_data):
        super().__init__()
        self.result_data = result_data

    def run(self):
        try:
            path_map = UPLOAD_CONFIG.get("EEG_CONN", {})
            oss_urls = {}
            key_map = {
                "main": self.result_data.get("main"),
                "fc_matrix_path": self.result_data.get("fc_matrix_path"),
                "fc_hub_path": self.result_data.get("fc_hub_path"),
                "fc_distance_path": self.result_data.get("fc_distance_path"),
                "fc_distribution_path": self.result_data.get("fc_distribution_path")
            }

            for key, folder in path_map.items():
                local_file = key_map.get(key)
                if local_file and os.path.exists(local_file):
                    url = _oss_internal_put(local_file, folder)
                    if url:
                        oss_urls[key] = url

            self.result_data["share_url"] = oss_urls.get("main")
            self.result_data["oss_urls"] = oss_urls
            self.finished.emit(True, "OSS上传成功")
        except Exception as e:
            self.finished.emit(False, f"OSS上传失败: {str(e)}")

class EEGConnectivityPage(BaseFunctionPage):
    def __init__(self, parent=None):
        super().__init__("EEG 功能连接分析", "读取 BDF 文件执行 EEG 脑功能连接 3D 可视化，并在主界面展示功能连接强度矩阵、网络核心枢纽、连接强度分布及物理距离相关性等 4 张量化动态图表。", MODULE_EEG_CONN, parent)
        self.bdf_path = ""
        self.cards_container = None
        self.worker = None
        self.oss_worker = None
        
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

        self.btn_run = PushButton("执行EEG功能连接分析", self.view, FIF.PLAY)
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

    def get_selected_duration(self):
        text = self.duration_box.currentText()
        mapping = {"5 秒": 5, "10 秒": 10, "30 秒": 30, "60 秒": 60, "全部": None}
        return mapping[text]

    def get_selected_band(self):
        text = self.band_box.currentText()
        mapping = {"全频道": "full", "α 频段": "alpha", "β 频段": "beta", "γ 频段": "gamma"}
        return mapping[text]

    def _copy_share_link(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.share_link_edit.text())
        self.show_success_dialog("已复制", "分享链接已复制到剪贴板。")

    def _show_share_link(self, share_url: str):
        if not share_url: return
        self.share_link_edit.setText(share_url)
        self.share_link_edit.setVisible(True)
        self.copy_link_btn.setVisible(True)

    def _update_connectivity_log(self, msg):
        msg_text = str(msg)
        self.status_label.setText(f"处理中: {msg_text}")
        log_manager.add_log(msg_text, self.module_name)

    def _select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 BDF 文件", "", "BDF Files (*.bdf)")
        if file_path:
            self.bdf_path = file_path
            self.path_edit.setText(file_path)
            log_manager.add_log(f"已选择 BDF 文件: {file_path}", self.module_name)

    def _run_task(self):
        if not self.check_file_selected(self.bdf_path, (".bdf",), "请选择合法的 .bdf 格式文件。"): return
        if self.worker is not None and self.worker.isRunning(): return

        duration_sec = self.get_selected_duration()
        analysis_band = self.get_selected_band()
        self.share_link_edit.setVisible(False)
        self.copy_link_btn.setVisible(False)
        self.share_link_edit.clear()

        self.set_running_state(True, "初始化连接分析网络...")
        log_manager.add_log("开始运行 EEG 功能连接...", self.module_name)

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
            self.status_label.setText("处理中: 正在渲染 3D 场景并导出结果...")
            result_data = render_connectivity_html(result, logger=self._update_connectivity_log)
            main_path = result_data.get("main", "")
            self.status_label.setText("处理中: 3D 渲染完成，请关闭弹窗后展示链接与卡片...")
            sync_state = {
                "popup_closed": False,
                "upload_done": False,
                "cards_loaded": False,
            }

            def show_cards_and_link_together():
                if sync_state["cards_loaded"]:
                    return
                if not (sync_state["popup_closed"] and sync_state["upload_done"]):
                    return
                sync_state["cards_loaded"] = True
                self.status_label.setText("处理中: 正在加载分享链接与分析卡片...")
                share_url = result_data.get("share_url")
                if share_url:
                    self._show_share_link(share_url)
                create_and_load_cards()

            def start_oss_upload():
                self.oss_worker = _SimpleUploadThread(result_data)

                def on_upload_done(upload_success, _msg):
                    if upload_success:
                        share_url = result_data.get("share_url")
                        if share_url:
                            log_manager.add_log(f"脑网络结果已同步至云端: {share_url}", self.module_name)
                    sync_state["upload_done"] = True
                    if not sync_state["popup_closed"]:
                        self.status_label.setText("处理中: 云端同步完成，请关闭3D弹窗查看链接与卡片...")
                    show_cards_and_link_together()
                    if self.oss_worker:
                        self.oss_worker.deleteLater()
                        self.oss_worker = None

                self.oss_worker.finished.connect(on_upload_done)
                self.oss_worker.start()

            # 渲染完成后立即启动上传，避免等卡片加载后才出现分享链接
            QTimer.singleShot(0, start_oss_upload)

            viz_win = self.show_html_in_subwindow(main_path, "EEG 功能连接可视化")

            def create_and_load_cards():
                self._clear_previous_cards()
                self.cards_container = QWidget()
                self.cards_container.setObjectName("CardsContainer")
                self.cards_layout = QVBoxLayout(self.cards_container)
                self.cards_layout.setContentsMargins(0, 16, 0, 0)
                self.cards_layout.setSpacing(16)
                
                card1 = InteractiveChartCard(
                    title="功能连接强度矩阵",
                    description="展示全脑 68 个脑区间的同步强度，红色代表强耦合，蓝色代表低同步。点击查看更多信息。",
                    file_path=result_data.get('fc_matrix_path', ''),
                    detail_text="""
本图基于皮尔逊相关系数计算全脑各解剖分区信号序列的瞬时协同程度，构建出 68*68 的功能交互网络，量化了不同脑区间连接的紧密程度。

如何理解:
- 横纵轴：对应 68 个解剖脑区。颜色越深红，代表两个脑区间的电活动同步性越高，功能耦合越强。
- 块状结构：矩阵中出现的深红色“小方块”通常代表了特定功能模块（如视觉网络、注意力网络）内部的高度集成。

核心用途:
1. 网络拓扑扫描：识别大脑在处理认知任务时，各功能模块之间是处于高度集成状态还是相对分工状态。
2. 质量控制：排查是否存在由于公共参考电极或全局噪声导致的伪影性高相关，确保连接结果的生理学效度。
""",
                    chart_name="功能连接强度矩阵",
                    image_url=os.path.join(self.base_dir, "app/resource/images", "eeg_heat_map.jpg"),
                )
                card1.web_view.setFixedHeight(650)
                self.cards_layout.addWidget(card1)

                card2 = InteractiveChartCard(
                    title="网络核心枢纽排名图",
                    description="找出大脑网络中的“CEO”脑区，展示影响力最强的核心节点。点击查看更多信息。",
                    file_path=result_data.get('fc_hub_path', ''),
                    detail_text="""
本图引入图论（Graph Theory）中的“加权节点度”指标，量化了每个脑区在全脑神经网络信息交换中的枢纽地位和全局影响力。

如何理解:
- 纵轴：排名靠前的核心枢纽脑区名称。
- 横轴：节点度数值，即该脑区与网络中所有其他脑区连接强度的总和。
- 逻辑：数值越高，代表该区在全脑信息流中起到“调度中心”的作用越强。

核心用途:
1. 关键靶点识别：定位在特定过程中起到关键作用的核心节点，为脑机接口（BCI）选点或神经调控提供参考。
2. 网络稳定性分析：观察在不同任务负荷下，大脑核心枢纽的迁移规律，评估神经网络的稳健性。
""",
                    chart_name="网络核心枢纽排名图",
                    image_url=os.path.join(self.base_dir, "app/resource/images", "network_hub.jpg"),
                )
                card2.web_view.setFixedHeight(500)
                self.cards_layout.addWidget(card2)

                card3 = InteractiveChartCard(
                    title="连接强度分布直方图",
                    description="统计全脑数千条连接的整体分布，用于评估网络健康度与设定筛选阈值。点击查看更多信息。",
                    file_path=result_data.get('fc_distribution_path', ''),
                    detail_text="""
本图统计了连接矩阵中数千条连接对的相关系数频率分布。在大脑网络中，连接的强度分布直接反映了信息传递的经济性和有效性。

如何理解:
- 横轴：相关系数值（-1 到 1）。
- 分布形态：健康的 EEG 网络通常呈现“小世界”特征，即大部分连接为中低强度（0.2-0.4），仅少数关键连接表现为极高强度。

核心用途:
1. 筛选阈值科学化：为“连接边剪枝”提供统计学依据。通过观察分布，选择能够保留最强 10% 关键连接的阈值。
2. 全局属性评估：若分布过度偏右（高相关），可能存在全局干扰；若过度偏左，则可能信号质量过低。
""",
                    chart_name="连接强度分布直方图",
                    image_url=os.path.join(self.base_dir, "app/resource/images", "Weight Distribution.png"),
                )
                card3.web_view.setFixedHeight(500)
                self.cards_layout.addWidget(card3)

                card4 = InteractiveChartCard(
                    title="距离-强度相关性散点图",
                    description="探索物理距离对功能连接的影响，验证大脑的空间组织逻辑。点击查看更多信息。",
                    file_path=result_data.get('fc_distance_path', ''),
                    detail_text="""
本图研究两脑区间的 3D 几何距离与功能同步强度之间的关系，揭示了大脑在处理信息时，物理成本与功能整合之间的平衡。

如何理解:
- 横轴：两脑区中心的空间直线距离 (mm)。
- 趋势线：通常向下倾斜，代表“近邻连接强、远端连接弱”的生理规律。
- 离群点：右上角的点代表虽然物理距离远、但功能高度同步，反映了大脑的长距离功能整合（如额顶网络）。

核心用途:
1. 空间约束分析：验证是否存在跨越半球或长距离的功能协作，排除“体积传导”引起的伪相关。
2. 生理逻辑验证：如果趋势线斜率异常平坦，可能提示数据存在全局系统性误差。
""",
                    chart_name="距离-强度相关性散点图",
                    image_url=os.path.join(self.base_dir, "app/resource/images", "diatance-connectivity.png"),
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

            def on_popup_closed():
                sync_state["popup_closed"] = True
                if not sync_state["upload_done"]:
                    self.status_label.setText("处理中: 弹窗已关闭，正在等待云端同步完成...")
                show_cards_and_link_together()

            if viz_win and hasattr(viz_win, 'closed_sig'):
                viz_win.closed_sig.connect(on_popup_closed)
            elif viz_win and hasattr(viz_win, 'destroyed'):
                viz_win.destroyed.connect(on_popup_closed)
            else:
                QTimer.singleShot(1000, on_popup_closed)

            self.view.updateGeometry()
            self.update()

        except Exception as e:
            self.set_running_state(False, "执行失败")
            log_manager.add_log(f"功能连接渲染失败: {str(e)}", self.module_name)
            self.show_error_dialog("渲染失败", f"导出 HTML 时出错：\n{str(e)}")