# -*- coding: utf-8 -*-
import weakref
import os
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineSettings, QWebEngineDownloadItem, QWebEngineProfile
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtCore import Qt

from qfluentwidgets import InfoBarPosition, InfoBar


class CustomWebEnginePage(QWebEnginePage):
    """自定义 WebEnginePage，处理新窗口跳转"""

    def __init__(self, profile, parent=None):
        super().__init__(profile, parent)

    def createWindow(self, window_type):
        """处理 target='_blank' 等新窗口请求"""
        new_view = CustomWebEngineView(self.parent())
        new_view.setWindowTitle("新窗口")
        new_view.show()
        return new_view.page()


class CustomWebEngineView(QWebEngineView):
    """支持下载、多窗口及自动资源清理的 WebEngineView"""
    _profile_cache = {}
    _view_instances = weakref.WeakSet()

    def __init__(self, parent=None, is_isolated=False, compatibility_mode=False):
        super().__init__(parent)
        self.is_isolated = is_isolated
        self.compatibility_mode = compatibility_mode
        self._download_items = []
        self._profile = None
        CustomWebEngineView._view_instances.add(self)
        self._setup_webengine()

    def _setup_webengine(self):
        """配置 WebEngine，硬件加速"""
        top_window = self.window()
        parent_id = id(top_window) if top_window else id(self)

        if self.is_isolated:
            # 独立进程模式：使用随机 ID 确保完全隔离
            import uuid
            unique_id = f"isolated_{uuid.uuid4().hex[:8]}"
            self._profile = QWebEngineProfile(unique_id, self)
            storage_path = os.path.join(os.path.expanduser("~"), ".cache", f"webengine_{unique_id}")
            self._profile.setPersistentStoragePath(storage_path)
            # 隔离模式不放入全局缓存
        elif parent_id not in self._profile_cache:
            new_profile = QWebEngineProfile(f"storage_{parent_id}", None)
            self._profile = new_profile
            storage_path = os.path.join(os.path.expanduser("~"), ".cache", f"webengine_{parent_id}")
            self._profile.setPersistentStoragePath(storage_path)
            self._profile_cache[parent_id] = self._profile
        else:
            self._profile = self._profile_cache[parent_id]

        custom_page = CustomWebEnginePage(self._profile, self)
        self.setPage(custom_page)

        if not hasattr(self._profile, '_download_handler_connected'):
            self._profile.downloadRequested.connect(self._on_download_requested)
            self._profile._download_handler_connected = True

        s = self.settings()
        s.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)
        s.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        # 与驱动相关的加速路径：兼容模式下仅关闭 2D 硬件加速，降低黑屏概率。
        s.setAttribute(QWebEngineSettings.WebGLEnabled, True)
        s.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, not self.compatibility_mode)

    def _on_download_requested(self, download: QWebEngineDownloadItem):
        """处理文件下载"""
        suggested_filename = download.downloadFileName()
        default_path = os.path.join(os.path.expanduser("~"), "Downloads", suggested_filename)

        save_path, _ = QFileDialog.getSaveFileName(self, "保存文件", default_path, "所有文件 (*)")

        if save_path:
            download.setDownloadFileName(os.path.basename(save_path))
            download.setDownloadDirectory(os.path.dirname(save_path))
            download.accept()
            self._download_items.append(download)
            download.finished.connect(lambda: self._on_download_finished(download, save_path))
        else:
            download.cancel()

    def _on_download_finished(self, download, save_path):
        """下载完成提示"""
        if download.isFinished():
            self._show_info_bar(f"下载完成", f"文件已保存至：{os.path.basename(save_path)}")

    def _show_info_bar(self, title, content):
        """显示通知"""
        InfoBar.success(
            title=title, content=content, orient=Qt.Horizontal,
            isClosable=True, position=InfoBarPosition.TOP_RIGHT,
            duration=3000, parent=self
        )

    def cleanup(self):
        """显式释放资源"""
        try:
            old_page = self.page()
            self.setPage(QWebEnginePage(None))
            if old_page:
                old_page.deleteLater()

            for item in self._download_items:
                item.cancel()
            self._download_items.clear()
        except:
            pass

    def closeEvent(self, event):
        """窗口关闭事件"""
        self.cleanup()
        CustomWebEngineView._view_instances.discard(self)
        super().closeEvent(event)


def cleanup_all_profiles():
    """全局清理逻辑"""
    for view in list(CustomWebEngineView._view_instances):
        if view:
            view.cleanup()

    for key in list(CustomWebEngineView._profile_cache.keys()):
        p = CustomWebEngineView._profile_cache.pop(key)
        p.deleteLater()