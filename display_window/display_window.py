"""
Enhanced display window with markdown support.
"""

import markdown
from typing import Optional
import sys
from loguru import logger
from PyQt6.QtWidgets import QApplication, QMainWindow, QTextBrowser
from PyQt6.QtCore import Qt, QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QClipboard

class ContentWindow(QMainWindow):
    def __init__(self, content: str):
        super().__init__()
        self.setWindowTitle("Content Display")
        
        # Initialize browser first
        self.browser = QTextBrowser(self)
        self.browser.setOpenExternalLinks(True)
        
        # Set font and style before content
        font = QFont('Segoe UI', 12)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        self.browser.setFont(font)
        
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
        
        # Store original content and set text
        self.original_content = content
        self.browser.setPlainText(content)
        
        # Calculate and set window size based on content
        self.adjustSize()
        document_size = self.browser.document().size()
        width = min(1600, max(800, document_size.width() + 60))  # Add padding
        height = min(900, max(200, document_size.height() + 60))  # Add padding
        
        # Center the window on screen
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - width) // 2
        y = (screen.height() - height) // 2
        self.setGeometry(x, y, width, height)
        
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
        
        # Emit signal to show window with content asynchronously
        QTimer.singleShot(0, lambda: _window_manager.show_window.emit(content))
            
    except Exception as e:
        logger.error(f"Error displaying content: {str(e)}")
        raise
