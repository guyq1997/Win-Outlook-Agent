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

class VoiceEmailUI(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.debug("Initializing VoiceEmailUI")
        self.workflow = VoiceEmailWorkflow(
            whisper_model="base",
            transcript_callback=self.handle_transcript
        )
        self.recording = False
        self.initUI()
        # Set window flags to remove from taskbar and make it tool window
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        logger.debug("VoiceEmailUI initialization completed")

    def initUI(self):
        self.setWindowTitle('语音邮件助手')
        self.setGeometry(100, 100, 200, 200)  # 缩小窗口尺寸
        
        # 创建中心部件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # 录音按钮 - 使用自定义样式
        self.record_button = QPushButton()
        self.record_button.setFixedSize(100, 100)  # 设置固定大小
        self.record_button.setStyleSheet("""
            QPushButton {
                background-color: #FF4444;
                border-radius: 50px;
                border: none;
            }
            QPushButton:hover {
                background-color: #FF6666;
            }
            QPushButton:pressed {
                background-color: #CC3333;
            }
        """)
        self.record_button.clicked.connect(self.toggle_recording)
        layout.addWidget(self.record_button, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # 状态标签
        self.status_label = QLabel('准备就绪')
        layout.addWidget(self.status_label)
        
        # 音量进度条
        self.volume_bar = QProgressBar()
        self.volume_bar.setRange(0, 100)
        layout.addWidget(self.volume_bar)
        
        # 文本显示区域
        self.text_display = QTextEdit()
        self.text_display.setReadOnly(True)
        layout.addWidget(self.text_display)
        
        # 初始化定时器用于更新UI
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_ui)
        self.timer.start(100)  # 每100ms更新一次
        
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
                    border-radius: 50px;
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
        """更新UI显示"""
        if self.recording:
            # 更新录音状态显示
            dots = '.' * (int(self.timer.interval() / 500) % 4)
            self.status_label.setText(f'正在录音{dots}')
    
    def volume_callback(self, level: float):
        """音量回调，更新进度条"""
        # 将音量级别转换为0-100的范围
        volume_level = min(100, int(level * 100))
        self.volume_bar.setValue(volume_level)
    
    def closeEvent(self, event):
        """Override close event to minimize instead of close"""
        event.ignore()
        self.hide()

    @asyncSlot()
    async def toggle_recording(self):
        """切换录音状态"""
        if not self.recording:
            # 开始录音
            self.recording = True
            self.update_button_style()
            self.text_display.clear()
            self.status_label.setText('正在录音...')
            try:
                await self.workflow.start_recording()
            except Exception as e:
                logger.error(f'录音启动失败: {str(e)}')
                self.recording = False
                self.update_button_style()
                self.status_label.setText('准备就绪')
                return
        else:
            # 停止录音并处理
            self.recording = False
            self.update_button_style()
            self.status_label.setText('正在处理...')
            try:
                await self.workflow.stop_and_process()
            except Exception as e:
                logger.error(f"处理失败: {str(e)}")
            finally:
                self.status_label.setText('准备就绪')
                self.hide()  # Hide the window after stopping recording
    
    async def cleanup(self):
        """清理资源"""
        await self.workflow.full_cleanup()

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
        # 使用 QTimer 延迟显示窗口
        QTimer.singleShot(100, self._do_show)
    
    def _do_show(self):
        """实际执行显示窗口的操作"""
        self.show()
        logger.debug("Window shown, forcing repaint...")
        self.repaint()
        logger.debug("Window repainted")
        # 确保所有子部件都更新
        for widget in self.findChildren(QWidget):
            widget.repaint()
        self.raise_()
        self.activateWindow()
        logger.debug("Window activated")

    async def initialize(self):
        """异步初始化所有服务"""
        try:
            await self.workflow.initialize_services()
            logger.info("All services initialized successfully")
        except Exception as e:
            logger.error(f"初始化失败: {str(e)}")

def main():
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    window = VoiceEmailUI()
    window.hide()  # 初始隐藏窗口
    
    # 在事件循环中初始化
    async def init():
        await window.initialize()
    
    # 注册全局热键
    keyboard.add_hotkey('ctrl+alt+m', window.show_window)
    
    # 退出处理
    async def shutdown():
        await window.cleanup()
        app.quit()
    
    # 注册退出热键
    keyboard.add_hotkey('ctrl+alt+q', lambda: asyncio.create_task(shutdown()))
    
    # 运行初始化和事件循环
    with loop:
        loop.run_until_complete(init())
        loop.run_forever()

if __name__ == '__main__':
    main() 