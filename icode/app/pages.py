# -*- coding: utf-8 -*-
import os
from PyQt5.QtCore import Qt, QSize, QUrl, QPoint, QRect
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFileDialog, QMainWindow, QAction, QSizePolicy, QFrame
)
from PyQt5.QtWebEngineWidgets import QWebEngineView

from qfluentwidgets import (
    ScrollArea, ExpandLayout, SettingCardGroup, PushButton,
    ComboBoxSettingCard, OptionsConfigItem, OptionsValidator,
    qconfig, Theme, setTheme, setThemeColor, InfoBar, InfoBarPosition,
    TextEdit, ComboBox, LineEdit, IndeterminateProgressBar,
    SubtitleLabel, BodyLabel, FluentStyleSheet, isDarkTheme, ToolButton, HeaderCardWidget
)
from qfluentwidgets import FluentIcon as FIF

from .core import log_manager, WorkerThread, FMRIWorkerThread, MODULE_EEG_SOURCE, MODULE_EEG_CONN, MODULE_FMRI_ACT, MODULE_FMRI_CONN, MODULE_SYSTEM
from source_localization import run_source_localization
from connectivity_visualization import run_connectivity_visualization
from fmri_activation import FMRIActivationThread
from fmri_connectivity import FMRIConnectivityThread
from CustomWebEnginePage import CustomWebEngineView


class FlowLayout(QHBoxLayout):
    def __init__(self, parent=None, spacing=-1):
        super().__init__(parent)
        self._item_list = []
        self.setSpacing(spacing)

    def __del__(self):
        while self._item_list:
            self._item_list.pop()

    def addItem(self, item):
        self._item_list.append(item)

    def count(self):
        return len(self._item_list)

    def itemAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations(Qt.Orientation(0))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(width, apply_geometry=False)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect.width(), apply_geometry=True)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        size += QSize(2 * self.contentsMargins().top(), 2 * self.contentsMargins().top())
        return size

    def _do_layout(self, width, apply_geometry=True):
        x = self.contentsMargins().left()
        y = self.contentsMargins().top()
        line_height = 0

        for item in self._item_list:
            wid = item.widget()
            space_x = self.spacing()
            space_y = self.spacing()
            if wid is not None:
                space_x = wid.style().layoutSpacing(QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Horizontal)
                space_y = wid.style().layoutSpacing(QSizePolicy.PushButton, QSizePolicy.PushButton, Qt.Vertical)

            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > width and line_height > 0:
                x = self.contentsMargins().left()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if apply_geometry:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height + self.contentsMargins().bottom()



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

        # self.setCentralWidget(self.web)
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
        self.viewport().setStyleSheet("background: transparent; border: none;")

        self.view = QWidget(self)
        self.view.setObjectName("FunctionPageView")
        self.view.setStyleSheet("background: transparent;")

        # 允许通过父窗口（FluentWindow）传递主题背景
        self.setStyleSheet("ScrollArea { background: transparent; border: none; }")

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

    def _run_task(self):
        if not self.check_file_selected(self.bdf_path, (".bdf",), "请选择合法的 .bdf 格式文件。"):
            return

        duration_sec = self.get_selected_duration()
        analysis_band = self.get_selected_band()

        self.set_running_state(True, "初始化读取EEG数据...")
        log_manager.add_log("开始运行 EEG 源定位...", self.module_name)
        log_manager.add_log(f"当前选择的分析频道：{self.band_box.currentText()}")

        def update_log(msg):
            self.status_label.setText(f"目前步骤: {msg}")
            log_manager.add_log(msg, self.module_name)
            QApplication.processEvents()

        QApplication.processEvents()
        try:
            plot_theme = "auto"
            run_source_localization(
                self.bdf_path,
                logger=update_log,
                duration_sec=duration_sec,
                analysis_band=analysis_band,
                plot_theme=plot_theme
            )
            self._on_task_finished(True, "ok")
        except Exception as e:
            self._on_task_finished(False, str(e))

    def _on_task_finished(self, success, msg):
        self.set_running_state(False, "执行完成" if success else "执行失败")
        if success:
            log_manager.add_log("EEG 源定位运行成功完成", self.module_name)
            self.show_success_dialog("操作成功", "EEG源定位已完成，弹出并渲染3D窗口。")
        else:
            log_manager.add_log(f"EEG 源定位运行失败: {msg}", self.module_name)
            self.show_error_dialog("运行失败", f"源定位过程中发生错误:\n{msg}")


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

    def _select_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 BDF 文件", "", "BDF Files (*.bdf)")
        if file_path:
            self.bdf_path = file_path
            self.path_edit.setText(file_path)
            log_manager.add_log(f"已选择 BDF 文件: {file_path}", self.module_name)

    def _run_task(self):
        if not self.check_file_selected(self.bdf_path, (".bdf",), "请选择合法的 .bdf 格式文件。"):
            return

        duration_sec = self.get_selected_duration()
        analysis_band = self.get_selected_band()

        self.set_running_state(True, "初始化连接分析网络...")
        log_manager.add_log("开始运行 EEG 功能连接...", self.module_name)

        # EEG 功能连接内部会构建 MNE/PyVista 的 3D 场景对象，放在子线程可能导致异常或卡死。
        # 这里与旧版行为保持一致：在主线程执行，同时通过 processEvents 保持进度条刷新。
        def update_log(msg):
            self.status_label.setText(f"目前步骤: {msg}")
            log_manager.add_log(msg, self.module_name)
            QApplication.processEvents()

        QApplication.processEvents()
        try:
            out_path = run_connectivity_visualization(
                self.bdf_path,
                logger=update_log,
                analysis_band=analysis_band,
                duration_sec=duration_sec
            )
            self._on_task_finished(True, out_path)
        except Exception as e:
            self._on_task_finished(False, str(e))

    def _on_task_finished(self, success, out_path):
        self.set_running_state(False, "执行完成" if success else "执行失败")
        if success:
            log_manager.add_log(f"功能连接导出成功: {out_path}", self.module_name)
            self.show_success_dialog("任务完成", f"结果已保存并尝试打开:\n{out_path}")
            self.show_html_in_subwindow(out_path, "EEG 功能连接可视化")
        else:
            log_manager.add_log(f"分析失败: {out_path}", self.module_name)
            self.show_error_dialog("分析失败", f"发生了未知错误:\n{out_path}")


# ==========================================
# fMRI 结果展示卡片
# ==========================================
class PlotlyCard(QFrame):
    """一个专门用于显示 Plotly 图表的卡片式控件。"""
    def __init__(self, title, subtitle, parent=None):
        super().__init__(parent=parent)
        self.fig = None
        self.title = title
        self.setObjectName('PlotlyCard')
        FluentStyleSheet.CARD.apply(self) # 应用卡片样式

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(16, 12, 16, 16)
        self.main_layout.setSpacing(10)

        # --- 标题和按钮 --- #
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0,0,0,0)
        title_layout = QVBoxLayout()
        title_layout.setSpacing(0)
        self.title_label = SubtitleLabel(title, self)
        self.subtitle_label = BodyLabel(subtitle, self)
        self.subtitle_label.setStyleSheet("color: gray;")
        title_layout.addWidget(self.title_label)
        title_layout.addWidget(self.subtitle_label)
        header_layout.addLayout(title_layout)
        header_layout.addStretch(1)
        self.save_btn = ToolButton(FIF.SAVE, self)
        self.save_btn.setToolTip("保存图表为PNG文件")
        self.save_btn.clicked.connect(self._save_figure)
        header_layout.addWidget(self.save_btn)
        self.main_layout.addLayout(header_layout)

        # --- 可折叠的图表和描述 --- #
        self.plot_view = CustomWebEngineView(self)
        self.plot_view.setMinimumHeight(400)
        self.desc_label = BodyLabel("详细描述...")
        self.desc_label.setWordWrap(True)
        self.desc_label.setVisible(False) # 默认隐藏

        self.main_layout.addWidget(self.plot_view)
        self.main_layout.addWidget(self.desc_label)
        
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        # 点击卡片时，切换详细描述的可见性
        # We check if the click was on the save button
        if self.save_btn.geometry().contains(event.pos()):
             super().mousePressEvent(event)
             return
        self.desc_label.setVisible(not self.desc_label.isVisible())
        super().mousePressEvent(event)

    def set_figure(self, fig, description: str):
        self.fig = fig
        self.desc_label.setText(description)

        # --- 配色和主题 --- #
        # 根据PyQt Fluent Widgets的深/浅色主题，调整Plotly的模板
        template = 'plotly_dark' if isDarkTheme() else 'plotly_white'
        self.fig.update_layout(
            template=template,
            paper_bgcolor='rgba(0,0,0,0)', # 使图表背景透明以融入卡片
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#e0e0e0' if isDarkTheme() else '#202020') # 适配字体颜色
        )

        # 将图表转为HTML并加载
        html = self.fig.to_html(include_plotlyjs='cdn')
        self.plot_view.setHtml(html)

    def _save_figure(self):
        if not self.fig:
            InfoBar.warning("提示", "图表尚未生成。", parent=self, position=InfoBarPosition.TOP_RIGHT)
            return

        # 弹出文件保存对话框
        default_name = f"{self.title.replace(' ', '_')}.png"
        path, _ = QFileDialog.getSaveFileName(
            self, "保存图表", default_name, "PNG Image (*.png)"
        )

        if path:
            try:
                # 使用 kaleido 保存为静态图片
                self.fig.write_image(path, width=1200, height=800, scale=2)
                InfoBar.success("保存成功", f"图表已保存至: {path}", parent=self, position=InfoBarPosition.TOP_RIGHT)
            except Exception as e:
                InfoBar.error("保存失败", f"无法保存图表: {e}", parent=self, position=InfoBarPosition.TOP_RIGHT)


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

        # --- 结果展示区 --- #
        self.results_container = QWidget(self.view)
        self.results_layout = FlowLayout(self.results_container, spacing=16)
        self.results_container.setLayout(self.results_layout)
        self.content_layout.addWidget(self.results_container)
        self.results_container.hide()

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

    def _on_task_finished(self, success, out_path):
        self.set_running_state(False, "执行完成" if success else "执行失败")

        # 清空旧的结果
        while self.results_layout.count():
            child = self.results_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not success:
            log_manager.add_log(f"fMRI 处理失败: {out_path}", self.module_name)
            self.show_error_dialog("发生异常", f"预处理或生成时报错:\n{out_path}")
            self.results_container.hide()
            return

        log_manager.add_log(f"fMRI 激活图生成完成", self.module_name)
        InfoBar.success("分析完成", "fMRI 脑区激活图表已生成在下方。", parent=self)

        figures = self.worker.processor.plotly_figures
        if not figures:
            self.show_error_dialog("没有结果", "后台任务未生成任何图表。")
            self.results_container.hide()
            return

        # 定义图表的标题、副标题和详细描述
        plot_info = {
            "ortho_activation": {
                "title": "三正交切片激活图",
                "subtitle": "在标准脑模板上显示最强激活点",
                "description": "此图从矢状面、冠状面和轴状面三个互相垂直的视角，展示了fMRI信号显著激活的区域。背景是MNI152标准脑模板，彩色部分是激活信号强度图。程序会自动定位到信号最强的激活峰值点进行切片，帮助快速定位核心激活区。"
            },
            "activation_intensity_hist": {
                "title": "激活强度分布直方图",
                "subtitle": "显示所有激活体素的信号强度分布",
                "description": "此直方图统计了所有被识别为‘激活’的脑区体素（voxel）的信号强度值，并展示了它们的分布情况。这有助于了解激活信号的整体强度和离散程度。图中的红色虚线标示了95%分位点，通常被用作一个较高的激活阈值参考。"
            },
            "threshold_voxel_curve": {
                "title": "阈值-激活体素数曲线",
                "subtitle": "不同阈值下，激活区域的体素数量",
                "description": "此曲线图展示了当统计阈值从宽松到严格变化时，被判定为‘激活’的体素数量是如何减少的。这对于选择一个合适的统计阈值至关重要：过于宽松的阈值可能导致假阳性，而过于严格的阈值可能遗漏真实的激活。曲线的拐点通常是选择阈值的参考区域。"
            }
        }

        for key, fig in figures.items():
            if key in plot_info:
                info = plot_info[key]
                card = PlotlyCard(info["title"], info["subtitle"], self.results_container)
                card.set_figure(fig, info["description"])
                self.results_layout.addWidget(card)

        self.results_container.show()


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

    def _on_task_finished(self, success, out_path):
        self.set_running_state(False, "执行完成" if success else "执行失败")
        if success:
            log_manager.add_log(f"fMRI 连接图生成完成: {out_path}", self.module_name)
            self.show_success_dialog("计算完毕", f"多图交互HTML分析报告已投递:\n{out_path}")
            self.show_html_in_subwindow(out_path, "fMRI 功能连接可视化")
        else:
            log_manager.add_log(f"连接计算失败: {out_path}", self.module_name)
            self.show_error_dialog("发生异常", f"提取或矩阵计算报错:\n{out_path}")


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
        self.viewport().setStyleSheet("background: transparent; border: none;")
        self.setStyleSheet("ScrollArea { background: transparent; border: none; }")

        self.view = QWidget(self)
        self.view.setObjectName("LogReportPageView")
        self.view.setStyleSheet("background: transparent;")
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
        self.viewport().setStyleSheet("background: transparent; border: none;")
        self.setStyleSheet("ScrollArea { background: transparent; border: none; }")

        self.view = QWidget(self)
        self.view.setObjectName("SettingsPageView")
        self.view.setStyleSheet("background: transparent;")
        self.expand_layout = ExpandLayout(self.view)
        self.expand_layout.setContentsMargins(36, 36, 36, 36)

        self._init_ui()

    def _init_ui(self):
        title = SubtitleLabel("系统设置", self.view)
        self.expand_layout.addWidget(title)

        # 使用分组归类管理项
        self.personal_group = SettingCardGroup("界面与主题", self.view)

        # 主题模式：必须调用 setTheme 才会刷新 Fluent 背景与控件样式
        self.theme_card = ComboBoxSettingCard(
            configItem=qconfig.themeMode,
            icon=FIF.BRUSH,
            title="应用主题",
            content="更改应用的外观并重新映射内部颜色",
            texts=["浅色", "深色", "跟随系统"],
            parent=self.personal_group
        )
        self.theme_card.comboBox.currentIndexChanged.connect(
            lambda i: self._on_theme_changed(i)
        )

        from qfluentwidgets import ColorSettingCard
        self.color_card = ColorSettingCard(
            qconfig.themeColor,
            icon=FIF.PALETTE,
            title="主题色",
            content="自定义状态与高亮的指向色",
            parent=self.personal_group
        )

        self.personal_group.addSettingCard(self.theme_card)
        self.personal_group.addSettingCard(self.color_card)

        self.expand_layout.addWidget(self.personal_group)
        self.setWidget(self.view)

    def _on_theme_changed(self, index: int):
        theme = [Theme.LIGHT, Theme.DARK, Theme.AUTO][index]
        setTheme(theme, save=True, lazy=False)
        # qconfig.themeChanged 信号会触发 main.py 中的刷新，但我们这里也可以手动更新样式
        # FluentStyleSheet.apply(self.window())
