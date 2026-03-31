import weakref

from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage, QWebEngineSettings, QWebEngineDownloadItem, \
    QWebEngineProfile
from PyQt5.QtWidgets import QFileDialog, QWidget
import os
from PyQt5.QtCore import Qt
from qfluentwidgets import InfoBarPosition, InfoBar


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
    _download_signal_connected = False
    _profile_cache = {}
    _view_instances = weakref.WeakSet()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._download_items = []  # 跟踪下载项
        self._profile = None  # 持有 profile 引用
        CustomWebEngineView._view_instances.add(self)
        self._setup_webengine()

    def _setup_webengine(self):
        """配置 WebEngine 支持下载和跳转"""
        # 获取当前 profile
        parent_id = id(self.parent()) if self.parent() else id(self)

        if len(self._profile_cache) > 10:
            oldest_key = next(iter(self._profile_cache))
            old_profile = self._profile_cache.pop(oldest_key)
            try:
                old_profile.deleteLater()
            except:
                pass

        if parent_id not in self._profile_cache:
            # 创建新的独立 profile
            self._profile = QWebEngineProfile(self)
            self._profile.setPersistentStoragePath(
                os.path.join(os.path.expanduser("~"), ".cache", f"webengine_{parent_id}")
            )
            self._profile_cache[parent_id] = self._profile
        else:
            profile = self._profile_cache[parent_id]

        # 设置自定义 Page
        custom_page = CustomWebEnginePage(self._profile, self)
        self.setPage(custom_page)


        if not hasattr(self._profile, '_download_handler_connected'):
            weak_self = weakref.ref(self)

            def _download_handler(download):
                view = weak_self()
                if view:
                    view._on_download_requested(download)

            self._profile.downloadRequested.connect(_download_handler)
            self._profile._download_handler_connected = True
            self._profile._download_handler = _download_handler
            # profile.downloadRequested.connect(self._on_download_requested)
            # profile._download_handler_connected = True

        # 启用相关设置
        settings = self.settings()
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.JavascriptCanOpenWindows, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)

    def _on_download_requested(self, download: QWebEngineDownloadItem):
        """处理下载请求 - PyQt5 使用 QWebEngineDownloadItem"""
        if hasattr(download, '_processed') and download._processed:
            return
        download._processed = True
        self._download_items.append(download)
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

            weak_self = weakref.ref(self)
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
            # self.window().statusTip().showMessage(f"下载完成：{save_path}", 3000) if self.window().statusBar() else None
            self._show_info_bar(f"下载完成：{os.path.basename(save_path)}", save_path)

    def _show_info_bar(self, title, content=None):
        """显示 InfoBar 通知"""
        # 获取主窗口（FluentWindow）
        main_window = self.window()

        # 查找合适的父 widget 用于显示 InfoBar
        parent_widget = None

        # 尝试获取当前显示的子页面
        if hasattr(main_window, 'stackWidget'):
            parent_widget = main_window.stackWidget.currentWidget()
        elif hasattr(main_window, 'centralWidget'):
            parent_widget = main_window.centralWidget()
        else:
            #  fallback：使用 view 本身
            parent_widget = self

        if parent_widget and isinstance(parent_widget, QWidget):
            InfoBar.success(
                title=title,
                content=content,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP_RIGHT,
                duration=3000,
                parent=parent_widget
            )
        else:
            print(f"✅ {title}")
            if content:
                print(f"   路径：{content}")


    def createWindow(self, window_type):
        """重写 createWindow 处理新窗口请求"""
        new_view = CustomWebEngineView(self.parent())
        new_view.setWindowTitle("新窗口")
        new_view.show()
        return new_view.page()

    # ========== 修复 8：添加清理方法 ==========
    def cleanup(self):
        """手动清理资源"""
        try:
            # 断开所有下载信号
            if self._profile and hasattr(self._profile, '_download_handler'):
                try:
                    self._profile.downloadRequested.disconnect(self._profile._download_handler)
                except:
                    pass

            # 清理下载项
            for item in self._download_items[:]:
                try:
                    item.deleteLater()
                except:
                    pass
            self._download_items.clear()

            # 清理页面
            page = self.page()
            if page:
                page.deleteLater()

        except Exception as e:
            print(f"Cleanup error: {e}")

    def closeEvent(self, event):
        """视图关闭时清理资源"""
        self.cleanup()
        # 从实例跟踪中移除
        CustomWebEngineView._view_instances.discard(self)
        super().closeEvent(event)

    def __del__(self):
        """析构时确保清理"""
        try:
            self.cleanup()
        except:
            pass


# ========== 修复 9：添加全局清理函数（在应用退出时调用） ==========
def cleanup_all_profiles():
    """清理所有缓存的 profile"""
    for key, profile in list(CustomWebEngineView._profile_cache.items()):
        try:
            profile.deleteLater()
        except:
            pass
    CustomWebEngineView._profile_cache.clear()