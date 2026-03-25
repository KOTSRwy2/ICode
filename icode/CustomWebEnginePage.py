from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineSettings, QWebEngineDownloadItem
from PyQt5.QtCore import QUrl, pyqtSignal
from PyQt5.QtWidgets import QFileDialog, QWidget, QVBoxLayout, QMessageBox
import os


class CustomWebEnginePage(QWebEnginePage):
    """自定义 WebEnginePage，处理新窗口跳转"""

    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)

    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        """处理导航请求"""
        return True

    def createWindow(self, window_type):
        """处理新窗口请求（target='_blank' 等）"""
        new_view = CustomWebEngineView(self.parent())
        new_view.setWindowTitle("新窗口")
        new_view.show()

        return new_view.page()


class CustomWebEngineView(QWebEngineView):
    """支持下载和新窗口跳转的 WebEngineView """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_webengine()

    def _setup_webengine(self):
        """配置 WebEngine 支持下载和跳转"""
        # 获取当前 profile
        profile = self.page().profile()

        # PyQt5: 连接下载请求信号 (使用 QWebEngineDownloadItem)
        profile.downloadRequested.connect(self._on_download_requested)

        # 设置自定义 Page 以支持新窗口
        custom_page = CustomWebEnginePage(profile, self)
        self.setPage(custom_page)

        # 启用相关设置
        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)

    def _on_download_requested(self, download: QWebEngineDownloadItem):
        """处理下载请求 - PyQt5 使用 QWebEngineDownloadItem"""
        # 获取建议的文件名
        suggested_filename = download.downloadFileName()

        # 弹出文件保存对话框
        default_path = os.path.join(os.path.expanduser("~"), "Downloads", suggested_filename)
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存文件",
            default_path,
            "所有文件 (*)"
        )

        if save_path:
            # PyQt5: 设置下载路径并接受下载
            download.setDownloadFileName(os.path.basename(save_path))
            download.setDownloadDirectory(os.path.dirname(save_path))
            download.accept()

            # 连接下载完成信号
            download.finished.connect(
                lambda: self._on_download_finished(download, save_path)
            )
        else:
            # 用户取消下载
            download.cancel()

    def _on_download_finished(self, download, save_path):
        """下载完成回调"""
        if download.isFinished():
            self.window().statusBar().showMessage(f"下载完成：{save_path}", 3000) if self.window().statusBar() else None

    def createWindow(self, window_type):
        """重写 createWindow 处理新窗口请求"""
        new_view = CustomWebEngineView(self.parent())
        new_view.setWindowTitle("新窗口")
        new_view.show()
        return new_view.page()