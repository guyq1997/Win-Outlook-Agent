import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QPushButton, QTextEdit, QProgressBar, QLabel,
                            QSystemTrayIcon, QMenu, QStyle)
from PyQt6.QtCore import Qt, QTimer, QMetaObject, Q_ARG, pyqtSlot
from PyQt6.QtGui import QIcon, QPixmap
import asyncio
from qasync import QEventLoop, asyncSlot
from voice_email_workflow import VoiceEmailWorkflow
from loguru import logger
import keyboard  # 新增导入
import random


class VoiceEmailUI(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.debug("Initializing VoiceEmailUI")
        self.workflow = VoiceEmailWorkflow()
        self.recording = False
        self.dragging = False
        self.offset = None
        self.initUI()
        self.setupTrayIcon()
        # Set window flags to remove from taskbar and make it tool window
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.update_button_style()  # Initialize button style
        self.setup_logger()
        logger.debug("VoiceEmailUI initialization completed")

    def initUI(self):
        self.setWindowTitle('语音邮件助手')
        self.setGeometry(100, 100, 120, 200)  # 缩小主窗口尺寸
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(10, 10, 10, 10)  # 减小边距
        
        # Record button - using custom style
        self.record_button = QPushButton()
        self.record_button.setFixedSize(80, 80)
        self.record_button.clicked.connect(self.toggle_recording)
        layout.addWidget(self.record_button, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Create horizontal layout for bottom buttons
        bottom_layout = QVBoxLayout()
        
        # Add toggle button for log display (right aligned)
        self.toggle_log_button = QPushButton("▶")  # 使用箭头符号替代文字
        self.toggle_log_button.setFixedSize(20, 20)  # 设置更小的固定尺寸
        self.toggle_log_button.setStyleSheet("""
            QPushButton {
                background-color: #E0E0E0;
                border: none;
                border-radius: 10px;
                padding: 0px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #D0D0D0;
            }
        """)
        self.toggle_log_button.clicked.connect(self.toggle_log_display)
        bottom_layout.addWidget(self.toggle_log_button, alignment=Qt.AlignmentFlag.AlignRight)
        
        # Close button
        self.close_button = QPushButton("×")
        self.close_button.setFixedSize(20, 20)
        self.close_button.clicked.connect(self.closeEvent)
        self.close_button.setStyleSheet("""
            QPushButton {
                background-color: #FF4444;
                color: white;
                border-radius: 10px;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #FF6666;
            }
        """)
        bottom_layout.addWidget(self.close_button, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addLayout(bottom_layout)
        
        # Create separate log window
        self.log_window = QWidget(None)
        self.log_window.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        log_layout = QVBoxLayout(self.log_window)
        
        # Log display area - increased size and font
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMinimumHeight(600)  # 增加高度
        self.log_display.setMinimumWidth(800)   # 增加宽度
        self.log_display.setStyleSheet("""
            QTextEdit {
                background-color: #F0F0F0;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 8px;
                font-family: Consolas, Monaco, monospace;
                font-size: 20pt;  /* 增大字体 */
                line-height: 1.8;
            }
        """)
        log_layout.addWidget(self.log_display)
        self.log_window.hide()  # Initially hidden
        
        # Initialize timer for UI updates
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(100)

    def update_button_style(self):
        """更新按钮样式"""
        if self.recording:
            # 停止按钮样式 - 方形
            self.record_button.setStyleSheet("""
                QPushButton {
                    background-color: #FF4444;
                    border-radius: 10px;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #FF6666;
                }
                QPushButton:pressed {
                    background-color: #CC3333;
                }
            """)
        else:
            # 开始录音按钮样式 - 圆形
            self.record_button.setStyleSheet("""
                QPushButton {
                    background-color: #FF4444;
                    border-radius: 40px;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #FF6666;
                }
                QPushButton:pressed {
                    background-color: #CC3333;
                }
            """)

    def update_ui(self):
        """Update UI display"""
        if random.random() < 0.001:  # Only log 0.1% of the updates
            loop = asyncio.get_event_loop()
            status_msg = f"Event loop status: running={loop.is_running()}, closed={loop.is_closed()}"
            logger.debug(status_msg)
            self.add_log_message(status_msg)

    def setup_logger(self):
        """设置 loguru 日志处理器"""
        def ui_sink(message):
            # 确保在主线程中更新 UI
            record = message.record
            log_message = f"[{record['level'].name}] {record['message']}"
            QMetaObject.invokeMethod(self, "add_log_message",
                                   Qt.ConnectionType.QueuedConnection,
                                   Q_ARG(str, log_message))
        
        # 添加自定义 sink 到 loguru
        logger.add(ui_sink, format="{message}", level="DEBUG")

    @pyqtSlot(str)
    def add_log_message(self, message: str):
        """添加日志消息到显示区域"""
        self.log_display.append(message)
        # 滚动到底部
        self.log_display.verticalScrollBar().setValue(
            self.log_display.verticalScrollBar().maximum()
        )

    def volume_callback(self, level: float):
        """音量回调，更新进度条"""
        # 将音量级别转换为0-100的范围
        volume_level = min(100, int(level * 100))
        self.volume_bar.setValue(volume_level)
    
    def closeEvent(self, event=None):
        """Override close event to stop recording and cleanup"""
        try:
            if event:  # If called from window close
                event.ignore()
            
            # Hide log window if visible
            if self.log_window.isVisible():
                self.log_window.hide()
                self.toggle_log_button.setText("▶")
            
            # Create cleanup task
            cleanup_task = asyncio.create_task(self._cleanup_and_hide())
            
            def cleanup_done(task):
                try:
                    task.result()
                except Exception as e:
                    logger.error(f"Cleanup failed: {str(e)}")
                finally:
                    self.hide()
            
            cleanup_task.add_done_callback(cleanup_done)
                
        except Exception as e:
            logger.error(f"Error during close event: {str(e)}")
            self.hide()

    async def _cleanup_and_hide(self):
        """Helper method to handle cleanup when closing"""
        try:
            if self.recording:
                self.recording = False
                self.update_button_style()
                # Cancel any ongoing recording tasks
                if hasattr(self.workflow, '_stream_task'):
                    self.workflow._stream_task.cancel()
                # Stop the audio service
                self.workflow.audio_service.stop_recording()
                # Cleanup all services
                await self.workflow.cleanup()
            logger.debug("Cleanup completed successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
            raise

    @asyncSlot()
    async def toggle_recording(self):
        """Toggle recording state"""
        try:
            if not self.recording:
                logger.debug("Starting recording process...")
                self.add_log_message("开始录音...")
                # Ensure clean state before starting
                await self.workflow.initialize_services()
                
                self.recording = True
                self.update_button_style()
                await self.workflow.start_recording(volume_callback=self.volume_callback)
                self.add_log_message("录音已开始")
                logger.debug("Recording started successfully")
            else:
                logger.debug("Stopping recording process...")
                self.add_log_message("停止录音...")
                self.recording = False
                self.update_button_style()
                try:
                    await asyncio.wait_for(
                        self.workflow.stop_and_process(),
                        timeout=35.0
                    )
                    self.add_log_message("录音处理完成")
                    logger.debug("stop_and_process completed successfully")
                except (asyncio.CancelledError, TimeoutError, ValueError, Exception) as e:
                    error_msg = f"处理失败: {str(e)}"
                    self.add_log_message(error_msg)
                    logger.error(error_msg, exc_info=True)
                finally:
                    logger.debug("cleaning up...")
                    await self.workflow.cleanup()
                    self.add_log_message("清理完成")
        except Exception as e:
            error_msg = f"录音操作失败: {str(e)}"
            self.add_log_message(error_msg)
            logger.error(error_msg, exc_info=True)
            self.recording = False
            self.update_button_style()

    def handle_transcript(self, text: str):
        """处理转录文本，创建Outlook草稿"""
        try:
            # 这里添加调用Outlook API创建草稿的代码
            # 示例：
            # outlook = win32.Dispatch('Outlook.Application')
            # mail = outlook.CreateItem(0)  # 0 表示邮件项
            # mail.Body = text
            # mail.Display()  # 显示邮件草稿
            pass
        except Exception as e:
            logger.error(f"创建邮件草稿失败: {str(e)}")

    def show_window(self):
        """确保窗口正确显示的方法"""
        logger.debug("Showing window...")
        self.update_button_style()
        QTimer.singleShot(100, self._do_show)
        # If log window was visible, show it again
        if self.toggle_log_button.text() == "隐藏日志 ▲":
            self.log_window.show()
            self.log_window.raise_()
    
    def _do_show(self):
        """实际执行显示窗口的操作"""
        # Set window to stay on top
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.show()
        logger.debug("Window shown, forcing repaint...")
        self.repaint()
        logger.debug("Window repainted")
        # 确保所有子部件都更新
        for widget in self.findChildren(QWidget):
            widget.repaint()
        self.raise_()  # Brings window to front
        self.activateWindow()  # Activates the window
        self.setFocus()  # Gives focus to the window
        logger.debug("Window activated and brought to front")

    async def initialize(self):
        """异步初始化所有服务"""
        try:
            await self.workflow.initialize_services()
            logger.info("All services initialized successfully")
        except Exception as e:
            logger.error(f"初始化失败: {str(e)}")

    async def stop_recording(self):
        """Stop recording and cleanup"""
        try:
            self.recording = False
            self.update_button_style()
            await self.workflow.stop_and_process()
        except Exception as e:
            logger.error(f"Error stopping recording: {str(e)}")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.offset = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.dragging and self.offset:
            new_pos = event.globalPosition().toPoint() - self.offset
            self.move(new_pos)
            # Move log window with main window if it's visible
            if self.log_window.isVisible():
                self.log_window.move(self.x() + self.width(), self.y())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.dragging = False
        self.offset = None
        super().mouseReleaseEvent(event)

    def setupTrayIcon(self):
        """设置系统托盘图标"""
        self.tray_icon = QSystemTrayIcon(self)
        # 使用系统标准图标
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
        self.tray_icon.setIcon(icon)
        
        # 创建右键菜单
        tray_menu = QMenu()
        show_action = tray_menu.addAction("显示")
        show_action.triggered.connect(self.show_window)
        quit_action = tray_menu.addAction("退出")
        quit_action.triggered.connect(self.closeEvent)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.trayIconActivated)
        self.tray_icon.show()
        
    def trayIconActivated(self, reason):
        """处理托盘图标的激活事件"""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # 单击
            self.show_window()

    def toggle_log_display(self):
        """Toggle the visibility of the log display"""
        if self.log_window.isVisible():
            self.log_window.hide()
            self.toggle_log_button.setText("▶")
        else:
            self.log_window.move(self.x() + self.width(), self.y())
            self.log_window.show()
            self.toggle_log_button.setText("◀")

def main():
    app = QApplication(sys.argv)
    # 确保应用程序不会在最后一个窗口关闭时退出
    app.setQuitOnLastWindowClosed(False)
    
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    window = VoiceEmailUI()
    window.hide()  # 初始隐藏窗口
    
    # 在事件循环中初始化
    async def init():
        try:
            await window.initialize()
            logger.info("Application initialized successfully")
        except Exception as e:
            logger.error(f"Initialization failed: {str(e)}")
            sys.exit(1)
    
    # 注册全局热键
    keyboard.add_hotkey('ctrl+alt+m', window.show_window)
    
    # 退出处理
    async def shutdown():
        try:
            logger.info("Starting application shutdown...")
            if window.recording:
                await window.stop_recording()
            await window.workflow.cleanup()
            await window.cleanup()
            app.quit()
            logger.info("Application shutdown completed")
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}")
            app.quit()
    
    # 注册退出热键
    keyboard.add_hotkey('ctrl+alt+q', lambda: asyncio.create_task(shutdown()))
    
    # 运行初始化和事件循环
    try:
        with loop:
            loop.run_until_complete(init())
            # 设置应用程序退出时的清理
            app.aboutToQuit.connect(lambda: asyncio.create_task(shutdown()))
            loop.run_forever()
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        raise
    finally:
        loop.close()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.error(f"Failed to start application: {str(e)}")
        input("Press Enter to exit...")  # 让用户看到错误信息