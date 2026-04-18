# -*- coding: utf-8 -*-
from .BaseFunctionPage import BaseFunctionPage
import os
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import  (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QFileDialog
)

from qfluentwidgets import (
  PushButton, LineEdit
)
from qfluentwidgets import FluentIcon as FIF

from .core import log_manager, FMRIWorkerThread, MODULE_FMRI_CONN
from ..functions.fmri_connectivity import FMRIConnectivityThread
from .InteractiveChartCard import InteractiveChartCard
from ..common.style_sheet import StyleSheet

class FMRIConnectivityPage(BaseFunctionPage):
    def __init__(self, parent=None):
        super().__init__("fMRI 功能连接分析", "读取 NIfTI 文件执行 fMRI 脑功能连接生成 3D 可视化交互式脑网络图，并在主界面展示功能连接矩阵热力图、正负连接比例饼图、滑动窗口时序图等 4 张多维度统计分析图表。", MODULE_FMRI_CONN, parent)
        self.fmri_path = ""
        self.worker = None
        self.cards_container = None
        
        # 指向项目根目录，用于加载资源图片
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        self._init_ui()

    def _init_ui(self):
        # 1. 文件选择区域
        file_layout = QHBoxLayout()
        self.path_edit = LineEdit(self.view)
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("选择一个 .nii / .nii.gz 脑影像文件")

        self.btn_select = PushButton("浏览文件", self.view, FIF.FOLDER)
        self.btn_select.clicked.connect(self._select_file)

        file_layout.addWidget(self.path_edit)
        file_layout.addWidget(self.btn_select)

        # 2. 运行按钮
        self.btn_run = PushButton("一键分析fMRI功能连接", self.view, FIF.PLAY)
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
        if not self.check_file_selected(self.fmri_path, (".nii", ".nii.gz"), "请选择有效的 NIfTI 影像文件"):
            return

        if self.worker is not None and self.worker.isRunning():
            return

        self.set_running_state(True, "初始化 fMRI 连接分析流水线...")
        log_manager.add_log("启动滑动窗口连接计算...", self.module_name)

        # 使用 core.py 提供的线程
        self.worker = FMRIWorkerThread(FMRIConnectivityThread, self.fmri_path, tr=2.0, mode="connectivity")
        
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
            log_manager.add_log(f"连接分析失败: {result_data}", self.module_name)
            self.show_error_dialog("计算错误", str(result_data))
            return

        # ==========================================================
        # 提取本地路径与 OSS 链接
        # ==========================================================
        res_paths = result_data if isinstance(result_data, dict) else {}
        
        # 1. 提取主 3D 视图 HTML 路径
        main_path = res_paths.get('main', '')
        
        # 2. 提取并展示 OSS 分享链接
        share_url = res_paths.get('share_url')
        if share_url:
            self._show_share_link(share_url)
            log_manager.add_log(f"脑网络结果已同步至云端: {share_url}", self.module_name)

        # 打开子窗口展示主 HTML
        viz_win = None
        if main_path and os.path.exists(str(main_path)):
            viz_win = self.show_html_in_subwindow(main_path, "fMRI 功能连接脑网络 3D 可视化")

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

            # 挂载卡片 1：全脑功能连接矩阵
            card1 = InteractiveChartCard(
                title="全脑功能连接矩阵",
                description="AAL 脑区功能连接热力图，颜色代表脑区同步强度，红色为正相关、蓝色为负相关，越红/蓝关联越强。点击查看更多信息。",
                file_path=res_paths.get('path_full_heatmap', ''),
                detail_text="""
本图基于 AAL 标准脑区分割模板，计算全脑两两脑区时间序列之间的皮尔逊相关系数，构建全脑功能连接矩阵。
    
如何理解：
- 横轴/纵轴：脑区索引，对应 AAL 脑区分割模板中的脑区
- 颜色刻度：从蓝色(-1.0)到红色(1.0)，代表皮尔逊相关系数大小
- 颜色越红：脑区间活动同步性越强，正相关越高
- 颜色越蓝：脑区间活动负相关程度越高
- 对角线元素：代表脑区与自身的相关值，恒为 1，无生物学意义
    
核心用途：
1. 直观识别全脑功能网络的模块化结构与高密度连接通路
2. 快速定位核心枢纽脑区与异常连接（如显著负连接区域）
3. 为后续动态连接分析、图论网络属性计算及组间统计比较提供基础数据
""",
                chart_name="全脑功能连接矩阵（AAL 脑区）",
                image_url=os.path.join(self.base_dir, "app/resource/images", "full_heat_map.jpg"),
            )
            card1.web_view.setFixedHeight(650)
            self.cards_layout.addWidget(card1)

            # 挂载卡片 2：正负连接比例饼图
            card2 = InteractiveChartCard(
                title="正负功能连接比例饼图",
                description="正负连接比例饼图，红色代表协同激活，蓝色代表反向调节。点击查看更多信息。",
                file_path=res_paths.get('pie_path', ''),
                detail_text="""
本图基于全脑功能连接矩阵，统计所有脑区连接对中，正相关、负相关及零相关连接的占比分布情况。

如何理解：
- 红色扇区 (Positive)：代表正相关连接占比，反映脑区间协同激活与同步活动
- 蓝色扇区 (Negative)：代表负相关连接占比，反映脑区间功能拮抗与抑制性交互
- 灰色扇区 (Zero)：代表无显著线性关联的连接占比

核心用途：
1. 量化评估大脑功能网络的兴奋-抑制平衡状态
2. 分析任务态或静息态下脑网络整体调控机制的变化
3. 为脑网络整合性、稳定性及病理状态（如精神疾病）的研究提供宏观指标
""",
                chart_name="正负功能连接比例饼图",
                image_url=os.path.join(self.base_dir, "app/resource/images", "pie_chart.jpg"),
            )
            card2.web_view.setFixedHeight(500)
            self.cards_layout.addWidget(card2)

            # 挂载卡片 3：多时间窗口功能连接热力图
            card3 = InteractiveChartCard(
                title="多时间窗口功能连接热力图",
                description="不同时间窗口连接热力图，观察脑网络随时间的动态变化。点击查看更多信息。",
                file_path=res_paths.get('path_heatmap', ''),
                detail_text="""
本图选取全时间序列中具有代表性的关键时间窗口，分别展示各时段内的功能连接矩阵，用于直观呈现脑网络的动态重组过程。

如何理解：
- 每一个子图：对应一个独立的时间窗口
- 时间标注：显示每个窗口对应的时间范围，便于对应分析
- 颜色深浅：代表该时间点脑区间连接强度的高低
- 对比观察：通过多张子图的横向对比，可观察连接模式的时空演变

核心用途：
1. 追踪任务执行过程中，脑网络连接模式的动态演变与状态切换
2. 识别脑网络连接强度发生显著变化的关键时间节点
3. 验证动态功能连接分析的稳定性，观察不同时段网络结构的差异
""",
                chart_name="多时间窗口功能连接热力图",
                image_url=os.path.join(self.base_dir, "app/resource/images", "heat_map_windows.jpg"),
            )
            card3.web_view.setFixedHeight(550)
            self.cards_layout.addWidget(card3)

            # 挂载卡片 4：滑动窗口功能连接动态指标图
            card4 = InteractiveChartCard(
                title="滑动窗口功能连接动态指标图",
                description="滑动窗口动态功能连接，展示脑网络连接强度、平衡度与稳定性随时间的变化. 点击查看更多信息。",
                file_path=res_paths.get('path_metrics', ''),
                detail_text="""
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
            self.cards_layout.addWidget(card4)

            # 将卡片容器添加到当前页面的主内容区底部
            self.content_layout.addWidget(self.cards_container)
            self.view.updateGeometry()
            self.update()

            # 交错延迟触发卡片 HTML 加载
            QTimer.singleShot(100, card1.load_chart)
            QTimer.singleShot(400, card2.load_chart)
            QTimer.singleShot(700, card3.load_chart)
            QTimer.singleShot(1000, card4.load_chart)
            
            # 加载完成后更新状态
            QTimer.singleShot(1200, lambda: self.set_running_state(False, "执行完成"))

        # 加载时机控制：弹窗就绪或关闭后再加载卡片
        if viz_win and hasattr(viz_win, 'ready_sig'):
            viz_win.ready_sig.connect(create_and_load_cards)
        elif viz_win and hasattr(viz_win, 'destroyed'):
            viz_win.destroyed.connect(create_and_load_cards)
        else:
            QTimer.singleShot(1000, create_and_load_cards)

        # 强制刷新UI
        QApplication.processEvents()