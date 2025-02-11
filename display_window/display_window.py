"""
Enhanced display window with markdown support using Tkinter and tkhtmlview.
"""

import tkinter as tk
from tkinter import ttk
from tkhtmlview import HTMLLabel
import markdown
from typing import Optional
import os

class DisplayWindow(tk.Toplevel):
    def __init__(self):
        super().__init__()
        self._setup_ui()
        
    def _setup_ui(self):
        # Configure window
        self.title("Message Display")
        self.overrideredirect(True)  # Frameless window
        
        # Create title bar
        title_bar = ttk.Frame(self, style='Title.TFrame')
        title_bar.pack(fill='x', side='top')
        
        # Title label
        title_label = ttk.Label(title_bar, text="Message Content", style='Title.TLabel')
        title_label.pack(side='left', padx=10)
        
        # Close button
        close_btn = ttk.Button(title_bar, text="×", style='Close.TButton', 
                              command=self.destroy, width=3)
        close_btn.pack(side='right')
        
        # Minimize button
        min_btn = ttk.Button(title_bar, text="−", style='Min.TButton',
                            command=self.iconify, width=3)
        min_btn.pack(side='right')
        
        # Content area
        self.content = HTMLLabel(self, background='#ffffff', 
                               html='<body style="font-size: 12pt;"></body>')
        self.content.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Configure styles
        style = ttk.Style()
        style.configure('Title.TFrame', background='#2c3e50')
        style.configure('Title.TLabel', 
                       background='#2c3e50',
                       foreground='white',
                       font=('Segoe UI', 11))
        style.configure('Close.TButton', 
                       font=('Segoe UI', 11, 'bold'))
        style.configure('Min.TButton', 
                       font=('Segoe UI', 11, 'bold'))
        
        # Make window draggable
        title_bar.bind('<Button-1>', self._start_move)
        title_bar.bind('<B1-Motion>', self._do_move)
        
        # Add border
        self.configure(background='#2c3e50')
        
    def _start_move(self, event):
        self._drag_x = event.x
        self._drag_y = event.y
        
    def _do_move(self, event):
        x = self.winfo_x() + (event.x - self._drag_x)
        y = self.winfo_y() + (event.y - self._drag_y)
        self.geometry(f"+{x}+{y}")
        
    def show_content(self, content: str):
        """Display markdown content in the window"""
        # Convert markdown to HTML
        html = markdown.markdown(content)
        html = f'''
        <body style="
            font-family: 'SF Pro Display', 'Segoe UI', 'Microsoft YaHei UI', Arial, sans-serif;
            font-size: 8pt;
            line-height: 1.5;
            color: #333333;
            padding: 15px;
            letter-spacing: 0.2px;
        ">
        {html}
        </body>
        '''
        
        # Update the window first to calculate required size
        self.content.set_html(html)
        self.update_idletasks()
        
        # Get the required height for all content
        required_height = self.content.winfo_reqheight() + 50  # Add padding for title bar
        
        # Calculate width based on content
        max_line_length = max(len(line) for line in content.split('\n'))
        width = min(max(max_line_length * 7, 400), 1000)
        
        # Calculate height ensuring all content is visible
        height = min(required_height, self.winfo_screenheight() - 100)  # Leave some screen margin
        
        # Center window
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        
        # Set window geometry
        self.geometry(f"{width}x{height}+{x}+{y}")
        
        # Copy to clipboard
        self.clipboard_clear()
        self.clipboard_append(content)
        
        self.deiconify()
        self.lift()
        self.focus_force()

_current_window: Optional[DisplayWindow] = None

def display_content(content: str):
    """Display content in a popup window."""
    global _current_window
    
    if _current_window is not None:
        _current_window.destroy()
    
    root = tk.Tk()  # Create root window
    root.withdraw()  # Hide the root window
    
    _current_window = DisplayWindow()
    _current_window.show_content(content)
    
    # Start the Tkinter event loop if not already running
    try:
        _current_window.mainloop()
    except:
        pass  # Window was closed
    
    return _current_window 