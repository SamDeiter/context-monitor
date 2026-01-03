"""
Custom UI Widgets for Context Monitor
"""
import tkinter as tk

class ToolTip:
    def __init__(self, widget, text, colors):
        self.widget = widget
        self.text = text
        self.colors = colors
        self.tooltip = None
        self.id = None
        self.widget.bind("<Enter>", self.schedule)
        self.widget.bind("<Leave>", self.hide)
        self.widget.bind("<ButtonPress>", self.hide)

    def schedule(self, event=None):
        self.unschedule()
        self.id = self.widget.after(500, self.show)

    def unschedule(self):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None

    def show(self, event=None):
        if self.tooltip:
            return
            
        x, y, _, _ = self.widget.bbox("insert") if self.widget.bbox("insert") else (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        
        try:
            self.tooltip = tk.Toplevel(self.widget)
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.wm_geometry(f"+{x}+{y}")
            self.tooltip.attributes('-topmost', True)
            
            label = tk.Label(self.tooltip, text=self.text, justify='left',
                           bg=self.colors['bg3'], fg=self.colors['text'],
                           relief='solid', borderwidth=1,
                           font=("Segoe UI", 8))
            label.pack()
        except:
            self.hide()

    def hide(self, event=None):
        self.unschedule()
        if self.tooltip:
            try:
                self.tooltip.destroy()
            except:
                pass
            self.tooltip = None
