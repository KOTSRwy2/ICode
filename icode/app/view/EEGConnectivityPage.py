from .BaseFunctionPage import BaseFunctionPage
import os
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog
)

from qfluentwidgets import (
    PushButton,InfoBar, InfoBarPosition, ComboBox, LineEdit, BodyLabel
)
from qfluentwidgets import FluentIcon as FIF

from .core import log_manager, WorkerThread, MODULE_EEG_CONN
from ..functions.eeg_connectivity_visualization import compute_connectivity_data, render_connectivity_html

from .InteractiveChartCard import InteractiveChartCard
from ..common.style_sheet import StyleSheet


class EEGConnectivityPage(BaseFunctionPage):
    def __init__(self, parent=None):
        super().__init__("EEG 功能连接分析", "读取 BDF 文件执行 EEG 脑功能连接 3D 可视化，并在主界面展示功能连接强度矩阵、网络核心枢纽排名图、连接强度分布直方图和距离-强度相关性散点图共 4 张多维度统计分析图表", MODULE_EEG_CONN, parent)
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

        self.btn_run = PushButton("执行EEG功能连接分析", self.view, FIF.PLAY)
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
1.网络拓扑扫描：识别大脑在处理认知任务时，各功能模块之间是处于高度集成状态还是相对分工状态。
2.质量控制：排查是否存在由于公共参考电极或全局噪声导致的伪影性高相关，确保连接结果的生理学效度。               
""",
                chart_name="功能连接强度矩阵",
                image_url=os.path.join(self.base_dir, "app/resource/images", "eeg_heat_map.jpg"),
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
1.关键靶点识别：定位在特定认知过程中起到协调全局作用的核心节点，为脑机接口（BCI）选点或经颅磁刺激（TMS）提供参考。
2.网络稳定性分析：观察在不同任务负荷下，大脑核心枢纽的迁移规律，评估神经网络的抗干扰能力。             
""",
                chart_name="网络核心枢纽排名图",
                image_url=os.path.join(self.base_dir, "app/resource/images", "network_hub.jpg"),
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
1.筛选阈值科学化：为“连接边剪枝”提供统计学依据。通过观察分布，选择能够保留最强 10% 关键连接的阈值。
2.全局属性评估：若分布过度偏右（高相关），可能存在全局干扰；若过度偏左（低相关），则可能信号质量过低。             
""",
                chart_name="连接强度分布直方图",
                image_url=os.path.join(self.base_dir, "app/resource/images", "Weight Distribution.png"),
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
1.空间约束分析：验证是否存在跨越半球或长距离的功能协作，排除“体积传导”引起的伪相关。
2.生理逻辑验证：如果趋势线斜率异常平坦，可能提示数据存在全局系统性误差。              
""",
                chart_name="距离-强度相关性散点图",
                image_url=os.path.join(self.base_dir, "app/resource/images", "diatance-connectivity.png"),
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

