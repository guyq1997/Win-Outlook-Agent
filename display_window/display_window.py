"""
Enhanced display window with modern UI and taskbar integration using PyQt6.
"""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QPushButton, QLabel, 
                           QTextEdit, QApplication)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QIcon
import os
from typing import Optional

class DisplayWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._setup_ui()
        
    def _setup_ui(self):
        self.setWindowTitle("Message Display")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        
        # Set window icon
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(script_dir, '..', 'assets', 'icon.ico')
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(1, 1, 1, 1)  # 减小边框间距
        layout.setSpacing(0)  # 移除组件之间的间距
        
        # Title bar - 减小高度，调整背景色
        title_bar = QWidget()
        title_bar.setStyleSheet("background-color: #2c3e50;")
        title_bar.setFixedHeight(24)  # 减小标题栏高度
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(8, 0, 0, 0)
        
        # Title label - 调整字体大小
        title_label = QLabel("Message Content")
        title_label.setStyleSheet("color: white; font-family: 'Segoe UI'; font-size: 9pt;")
        
        # 调整按钮样式
        minimize_button = QPushButton("−")
        minimize_button.setFixedWidth(24)  # 减小按钮宽度
        minimize_button.clicked.connect(self.showMinimized)
        minimize_button.setStyleSheet("""
            QPushButton {
                color: white;
                border: none;
                font-family: 'Segoe UI';
                font-size: 11pt;
                font-weight: bold;
                background-color: #2c3e50;
            }
            QPushButton:hover {
                background-color: #34495e;
            }
        """)
        
        close_button = QPushButton("×")
        close_button.setFixedWidth(24)  # 减小按钮宽度
        close_button.clicked.connect(self.hide)
        close_button.setStyleSheet("""
            QPushButton {
                color: white;
                border: none;
                font-family: 'Segoe UI';
                font-size: 11pt;
                font-weight: bold;
                background-color: #2c3e50;
            }
            QPushButton:hover {
                background-color: #e74c3c;
            }
        """)
        
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        title_layout.addWidget(minimize_button)
        title_layout.addWidget(close_button)
        
        # Text widget - 更新样式
        self.text_widget = QTextEdit()
        self.text_widget.setReadOnly(True)
        self.text_widget.setStyleSheet("""
            QTextEdit {
                background-color: #f5f6f7;
                color: #2c3e50;
                border: none;
                font-family: 'Segoe UI', 'Microsoft YaHei';
                font-size: 10.5pt;
                line-height: 1.6;
                padding: 12px;
            }
        """)
        
        layout.addWidget(title_bar)
        layout.addWidget(self.text_widget)
        
        # Make window draggable
        self._drag_pos = None
        title_bar.mousePressEvent = self._start_move
        title_bar.mouseMoveEvent = self._do_move
        
        # 为窗口添加边框样式
        self.setStyleSheet("""
            QMainWindow {
                border: 1px solid #2c3e50;
                background-color: #f5f6f7;
            }
        """)
        
    def _start_move(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()
            
    def _do_move(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self._drag_pos:
            new_pos = event.globalPosition().toPoint()
            self.move(self.pos() + new_pos - self._drag_pos)
            self._drag_pos = new_pos
            
    def show_content(self, content: str):
        """Display content in the window"""
        # Set window size
        width = min(max(len(content) * 7, 400), 800)
        height = min((content.count('\n') + 1) * 20 + 100, 600)
        self.resize(width, height)
        
        # Center window
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - width) // 2,
            (screen.height() - height) // 2
        )
        
        # Set content
        self.text_widget.setText(content)
        
        # Copy to clipboard
        QApplication.clipboard().setText(content)
        
        self.show()
        self.raise_()
        self.activateWindow()

def display_content(content: str):
    """Display content in a popup window."""
    global _current_window
    
    if '_current_window' in globals() and _current_window is not None:
        _current_window.close()
        _current_window = None
    
    _current_window = DisplayWindow()
    _current_window.show_content(content)
    return _current_window 