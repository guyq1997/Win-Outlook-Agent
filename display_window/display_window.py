"""
Enhanced display window with markdown support.
"""

import markdown
from typing import Optional
import sys
from loguru import logger
from PyQt6.QtWidgets import QApplication, QMainWindow, QTextBrowser
from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtGui import QFont, QClipboard

class ContentWindow(QMainWindow):
    def __init__(self, content: str):
        super().__init__()
        self.setWindowTitle("Content Display")
        
        # Calculate window size based on content
        content_length = len(content)
        width = min(1600, max(1200, content_length * 2))  # Between 1200 and 1600 pixels
        height = min(900, max(600, content_length))       # Between 600 and 900 pixels
        
        # Center the window on screen
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - width) // 2
        y = (screen.height() - height) // 2
        self.setGeometry(x, y, width, height)
        
        self.browser = QTextBrowser(self)
        self.browser.setOpenExternalLinks(True)
        
        # 设置更好看的字体
        font = QFont('Segoe UI', 12)  # Windows 默认的现代字体
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)  # 启用抗锯齿
        self.browser.setFont(font)
        
        # 设置文本浏览器的样式
        self.browser.setStyleSheet("""
            QTextBrowser {
                background-color: #FFFFFF;
                color: #2C3E50;
                border: none;
                padding: 20px;
                line-height: 1.6;
            }
        """)
        
        self.setCentralWidget(self.browser)
        
        # Store original content for clipboard
        self.original_content = content
        
        # Set plain text instead of HTML
        self.browser.setPlainText(content)
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint)
        
        # Copy to clipboard
        self._copy_to_clipboard()
    
    def _copy_to_clipboard(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.original_content)
        # Also copy to selection clipboard (for Linux middle-click paste)
        clipboard.setText(self.original_content, QClipboard.Mode.Selection)
    
    def closeEvent(self, event):
        # Hide the window instead of closing it
        self.hide()
        event.ignore()

class WindowManager(QObject):
    show_window = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.window = None
        self.show_window.connect(self._create_window)
    
    def _create_window(self, content: str):
        if self.window is None:
            self.window = ContentWindow(content)
        else:
            # Update content if window already exists
            self.window.original_content = content
            self.window.browser.setPlainText(content)
            self.window._copy_to_clipboard()
        self.window.show()

_window_manager: Optional[WindowManager] = None
_app: Optional[QApplication] = None

def display_content(content: str):
    """Display content in a popup window and copy to clipboard."""
    try:
        global _window_manager, _app
        
        # Create or get QApplication instance
        if QApplication.instance() is None:
            _app = QApplication(sys.argv)
            # Prevent Qt from exiting when last window is closed
            _app.setQuitOnLastWindowClosed(False)
        
        # Create window manager if it doesn't exist
        if _window_manager is None:
            _window_manager = WindowManager()
        
        # Show window with content
        _window_manager.show_window.emit(content)
            
    except Exception as e:
        logger.error(f"Error displaying content: {str(e)}")
        raise
