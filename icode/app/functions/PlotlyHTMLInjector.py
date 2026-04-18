# PlotlyHTMLInjector.py
import os
from typing import Optional, Dict, Any


class PlotlyHTMLInjector:
    """
    Plotly HTML 文件 JavaScript/CSS 注入器
    负责向 Plotly 生成的 HTML 文件中注入自定义脚本和样式
    """

    def __init__(self, output_dir: Optional[str] = None):
        """
        初始化注入器

        Args:
            output_dir: 输出目录路径（可选，用于日志记录）
        """
        self.output_dir = output_dir

    def inject_all(self, html_path: str, options: Optional[Dict[str, bool]] = None) -> bool:
        """
        一次性注入所有需要的脚本

        Args:
            html_path: HTML 文件路径
            options: 注入选项配置

        Returns:
            bool: 注入是否成功
        """
        if options is None:
            options = {
                'fluent_css': True,
                'animation_control': True,
                'debug_info': False,
                'frame_display': False
            }

        if not os.path.exists(html_path):
            print(f"[PlotlyHTMLInjector] 文件不存在：{html_path}")
            return False

        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 按顺序注入各个模块
            if options.get('fluent_css', False):
                content = self._inject_fluent_css_content(content)

            if options.get('animation_control', False):
                content = self._inject_animation_control_content(content)

            if options.get('debug_info', False):
                content = self._inject_debug_info_content(content)

            if options.get('frame_display', False):
                content = self._inject_frame_display_content(content)

            # 写回文件
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"[PlotlyHTMLInjector] 注入完成：{html_path}")
            return True

        except Exception as e:
            print(f"[PlotlyHTMLInjector] 注入失败：{str(e)}")
            return False

    def inject_fluent_css(self, html_path: str) -> bool:
        """仅注入 Fluent CSS"""
        return self._process_single_injection(html_path, self._inject_fluent_css_content)

    def inject_animation_control(self, html_path: str) -> bool:
        """仅注入动画控制脚本"""
        return self._process_single_injection(html_path, self._inject_animation_control_content)

    def inject_debug_info(self, html_path: str) -> bool:
        """仅注入调试信息"""
        return self._process_single_injection(html_path, self._inject_debug_info_content)

    def inject_frame_display(self, html_path: str) -> bool:
        """仅注入帧显示组件"""
        return self._process_single_injection(html_path, self._inject_frame_display_content)

    # 内部处理方法

    def _process_single_injection(self, html_path: str, inject_func) -> bool:
        """处理单个注入操作"""
        if not os.path.exists(html_path):
            return False

        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                content = f.read()

            content = inject_func(content)

            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(content)

            return True
        except Exception as e:
            print(f"[PlotlyHTMLInjector] 注入失败：{str(e)}")
            return False

    # 注入内容生成方法

    def _inject_fluent_css_content(self, content: str) -> str:
        """生成 Fluent CSS 注入内容"""
        css_script = """
            <script>
                const originalInsertRule = CSSStyleSheet.prototype.insertRule;
                CSSStyleSheet.prototype.insertRule = function(rule, index) {
                    try {
                        return originalInsertRule.call(this, rule, index);
                    } catch (e) {
                       // console.warn("屏蔽了不兼容的 CSS 规则：", rule);
                        return 0;
                    }
                };
            </script>
            """
        return self._inject_to_head(content, css_script)

    def _inject_animation_control_content(self, content: str) -> str:
        """生成动画控制脚本内容"""
        # 添加隐藏按钮的 CSS
        hide_css = """
        <style>
            /* 隐藏 Plotly 内置的播放/暂停按钮 */
            g.updatemenu-button {
                display: none !important;
            }
            /* 或者隐藏整个 updatemenu 容器 */
            .updatemenu-container {
                display: none !important;
            }
             .plotly-graph-div .updatemenu {
                display: none !important;
            }
        </style>
        """

        js_code = """
        <script>
        console.log('[PlotlyAnimationControl] 脚本已加载');

        window.PlotlyAnimationControl = {
            isPlaying: false,
            graphDiv: null,
            playButton: null,
            pauseButton: null,

            // 获取 Plotly updatemenu 按钮（SVG 元素）
            getButtons: function() {
                var buttonGroups = document.querySelectorAll('g.updatemenu-button');
                console.log('[PlotlyAnimationControl] 找到 updatemenu-button 数量:', buttonGroups.length);

                var playBtn = null;
                var pauseBtn = null;

                buttonGroups.forEach(function(group) {
                    var textElem = group.querySelector('text.updatemenu-item-text');
                    if (textElem) {
                        var labelText = textElem.getAttribute('data-unformatted') || textElem.textContent;
                        console.log('[PlotlyAnimationControl] 按钮标签:', labelText);

                        if (labelText === 'Play') {
                            playBtn = group;
                        }
                        if (labelText === 'Pause') {
                            pauseBtn = group;
                        }
                    }
                });

                this.playButton = playBtn;
                this.pauseButton = pauseBtn;

                console.log('[PlotlyAnimationControl] 播放按钮:', playBtn);
                console.log('[PlotlyAnimationControl] 暂停按钮:', pauseBtn);

                return { play: playBtn, pause: pauseBtn };
            },

            // 播放动画 - 触发 SVG 元素的 click 事件
            play: function() {
                console.log('[PlotlyAnimationControl] 播放请求');

                var buttons = this.getButtons();
                if (buttons.play) {
                    var event = new MouseEvent('click', {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    });
                    buttons.play.dispatchEvent(event);
                    this.isPlaying = true;
                    console.log('[PlotlyAnimationControl] 播放已触发');
                } else {
                    console.error('[PlotlyAnimationControl] 未找到播放按钮');
                }
            },

            // 暂停动画
            pause: function() {
                console.log('[PlotlyAnimationControl] 暂停请求');

                var buttons = this.getButtons();
                if (buttons.pause) {
                    var event = new MouseEvent('click', {
                        bubbles: true,
                        cancelable: true,
                        view: window
                    });
                    buttons.pause.dispatchEvent(event);
                    this.isPlaying = false;
                    console.log('[PlotlyAnimationControl] 暂停已触发');
                } else {
                    console.error('[PlotlyAnimationControl] 未找到暂停按钮');
                }
            },

            // 重播
            replay: function() {
                location.reload();
            }
        };

        // 页面加载后自动播放
        window.addEventListener('load', function() {
            setTimeout(function() {
                if (window.PlotlyAnimationControl) {
                    window.PlotlyAnimationControl.play();
                }
            }, 1500);
        });
        </script>
        """
        return self._inject_to_body(content, js_code + hide_css)

    def _inject_debug_info_content(self, content: str) -> str:
        """生成调试信息脚本内容"""
        debug_js = """
        <script>
        window.addEventListener('load', function() {
            setTimeout(function() {
                console.log('=== SVG 按钮调试信息 ===');

                var buttonGroups = document.querySelectorAll('g.updatemenu-button');
                console.log('updatemenu-button 数量:', buttonGroups.length);
                buttonGroups.forEach(function(group, i) {
                    var text = group.querySelector('text.updatemenu-item-text');
                    console.log('按钮组', i, ':', {
                        'transform': group.getAttribute('transform'),
                        'text': text ? text.getAttribute('data-unformatted') : 'none',
                        'textContent': text ? text.textContent : 'none'
                    });
                });

                var texts = document.querySelectorAll('text.updatemenu-item-text');
                console.log('updatemenu-item-text 数量:', texts.length);
                texts.forEach(function(text, i) {
                    console.log('text', i, ':', {
                        'data-unformatted': text.getAttribute('data-unformatted'),
                        'textContent': text.textContent
                    });
                });

                var modebarBtns = document.querySelectorAll('button.modebar-btn');
                console.log('modebar-btn 数量:', modebarBtns.length);

                console.log('=== 调试结束 ===');
            }, 2000);
        });
        </script>
        """
        return self._inject_to_body(content, debug_js)

    def _inject_frame_display_content(self, content: str) -> str:
        """生成帧显示组件内容"""
        display_html = """
        <style>
            #frame-display {
                position: fixed;
                top: 10px;
                right: 10px;
                padding: 8px 16px;
                background: rgba(0, 0, 0, 0.8);
                color: #1677ff;
                border-radius: 4px;
                font-family: 'Segoe UI', sans-serif;
                font-size: 12px;
                z-index: 9999;
            }
        </style>
        <div id="frame-display">帧：0/0</div>
        <script>
        setInterval(function() {
            if (window.PlotlyAnimationControl && window.PlotlyAnimationControl.graphDiv) {
                var display = document.getElementById('frame-display');
                if (display) {
                    var current = window.PlotlyAnimationControl.currentFrameIndex || 0;
                    var total = window.PlotlyAnimationControl.totalFrames || 0;
                    display.textContent = '帧：' + (current + 1) + '/' + total;
                }
            }
        }, 100);
        </script>
        """
        return self._inject_to_body(content, display_html)

    # HTML 操作工具方法

    def _inject_to_head(self, content: str, script: str) -> str:
        """注入内容到 <head> 标签"""
        if '<head>' in content:
            return content.replace('<head>', f'<head>{script}')
        return content

    def _inject_to_body(self, content: str, script: str) -> str:
        """注入内容到 </body> 标签"""
        if '</body>' in content:
            return content.replace('</body>', f'{script}</body>')
        return content

    # 批量处理方法

    def inject_multiple(self, html_paths: list, options: Optional[Dict[str, bool]] = None) -> Dict[str, bool]:
        """
        批量注入多个 HTML 文件

        Args:
            html_paths: HTML 文件路径列表
            options: 注入选项

        Returns:
            Dict[str, bool]: 每个文件的注入结果
        """
        results = {}
        for path in html_paths:
            results[path] = self.inject_all(path, options)
        return results