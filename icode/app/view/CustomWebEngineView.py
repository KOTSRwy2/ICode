# -*- coding: utf-8 -*-
import weakref
import os
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineSettings, QWebEngineDownloadItem, \
    QWebEngineProfile
from PyQt5.QtWidgets import QFileDialog, QWidget
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._download_items = []
        self._profile = None  # 预声明属性
        CustomWebEngineView._view_instances.add(self)
        self._setup_webengine()

    def _setup_webengine(self):
        """配置 WebEngine，确保 Profile 赋值顺序正确"""
        # 1. 确定当前上下文的 ID（用于 Profile 复用）
        # 优先使用顶级窗口的 ID，确保同一个功能模块下的子窗口共享一个 Profile
        top_window = self.window()
        parent_id = id(top_window) if top_window else id(self)

        # 2. 获取或创建 Profile
        if parent_id not in self._profile_cache:
            # 创建独立 Profile，Parent 设为 None 由全局清理函数管理
            new_profile = QWebEngineProfile(f"storage_{parent_id}", None)

            # 关键修复点：先赋值给 self._profile，再调用其方法
            self._profile = new_profile

            storage_path = os.path.join(os.path.expanduser("~"), ".cache", f"webengine_{parent_id}")
            self._profile.setPersistentStoragePath(storage_path)

            # 存入缓存
            self._profile_cache[parent_id] = self._profile
        else:
            self._profile = self._profile_cache[parent_id]

        # 3. 设置自定义 Page
        custom_page = CustomWebEnginePage(self._profile, self)
        self.setPage(custom_page)

        # 4. 连接下载信号（仅在 Profile 首次创建时连接一次，或确保不重复连接）
        if not hasattr(self._profile, '_download_handler_connected'):
            self._profile.downloadRequested.connect(self._on_download_requested)
            self._profile._download_handler_connected = True

        # 5. 启用相关设置
        s = self.settings()
        s.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        s.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)
        s.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        s.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

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
        if download.isFinished():
            self._show_info_bar(f"下载完成", f"文件已保存至：{os.path.basename(save_path)}")

    def _show_info_bar(self, title, content):
        """在当前页面显示成功通知"""
        InfoBar.success(
            title=title, content=content, orient=Qt.Horizontal,
            isClosable=True, position=InfoBarPosition.TOP_RIGHT,
            duration=3000, parent=self
        )

    def cleanup(self):
        """显式释放资源，防止 Profile 报错"""
        try:
            old_page = self.page()
            # 切断 Page 与 Profile 的联系
            self.setPage(QWebEnginePage(None))
            if old_page:
                old_page.deleteLater()

            for item in self._download_items:
                item.cancel()
            self._download_items.clear()
        except:
            pass

    def closeEvent(self, event):
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