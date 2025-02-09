import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QPushButton, QTextEdit, QProgressBar, QLabel)
from PyQt6.QtCore import Qt, QTimer
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
        # Set window flags to remove from taskbar and make it tool window
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.update_button_style()  # Initialize button style
        logger.debug("VoiceEmailUI initialization completed")

    def initUI(self):
        self.setWindowTitle('语音邮件助手')
        self.setGeometry(100, 100, 120, 150)  # Even smaller window size
        
        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Record button - using custom style
        self.record_button = QPushButton()
        self.record_button.setFixedSize(80, 80)  # Smaller button
        self.record_button.clicked.connect(self.toggle_recording)
        layout.addWidget(self.record_button, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Close button
        self.close_button = QPushButton("×")  # Using × symbol for close
        self.close_button.setFixedSize(20, 20)
        self.close_button.clicked.connect(self.closeEvent)  # Changed from hide() to trigger_close()
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
        layout.addWidget(self.close_button, alignment=Qt.AlignmentFlag.AlignCenter)
        
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
            logger.debug(f"Event loop status: running={loop.is_running()}, closed={loop.is_closed()}")

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
                # Ensure clean state before starting
                await self.workflow.initialize_services()
                

                self.recording = True
                self.update_button_style()
                await self.workflow.start_recording(volume_callback=self.volume_callback)
                logger.debug("Recording started successfully")
            else:
                logger.debug("Stopping recording process...")
                self.recording = False
                self.update_button_style()
                self.hide()
                try:
                    await asyncio.wait_for(
                        self.workflow.stop_and_process(),
                        timeout=35.0
                    )
                    logger.debug("stop_and_process completed successfully")
                    
                    logger.debug("UI hidden")
                except (asyncio.CancelledError, TimeoutError, ValueError, Exception) as e:
                    logger.error(f"Processing failed: {str(e)}", exc_info=True)
                finally:
                    logger.debug("cleaning up...")
                    await self.workflow.cleanup()  # Ensure cleanup after processing
        except Exception as e:

            logger.error(f"Recording operation failed: {str(e)}", exc_info=True)

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
        self.update_button_style()  # Ensure correct button style when showing window
        QTimer.singleShot(100, self._do_show)
    
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
            self.move(event.globalPosition().toPoint() - self.offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.dragging = False
        self.offset = None
        super().mouseReleaseEvent(event)

def main():
    app = QApplication(sys.argv)
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