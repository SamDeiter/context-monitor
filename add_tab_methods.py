import re

# Read the file
with open(r'c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.pyw', 'r', encoding='utf-8') as f:
    content = f.read()

# Find where to add the new methods (before show_history)
insert_marker = '    def show_history(self):'
insert_pos = content.find(insert_marker)

if insert_pos == -1:
    print("ERROR: Could not find insertion point")
    exit(1)

# New methods to insert
new_methods = '''    def switch_tab(self, tab_id):
        """Switch active tab in Full mode"""
        self.active_tab = tab_id
        self.setup_ui()  # Rebuild UI with new active tab
    
    def render_tab_content(self):
        """Render content for the active tab"""
        if not hasattr(self, 'content_frame'):
            return
        
        # Clear existing content
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        # Render based on active tab
        if self.active_tab == 'diagnostics':
            self.render_diagnostics_inline()
        elif self.active_tab == 'token_stats':
            self.render_token_stats_inline()
        elif self.active_tab == 'history':
            self.render_history_inline()
        elif self.active_tab == 'analytics':
            self.render_analytics_inline()
    
    def render_history_inline(self):
        """Render usage history graph inline"""
        canvas = tk.Canvas(self.content_frame, width=620, height=400,
                          bg=self.colors['bg2'], highlightthickness=1,
                          highlightbackground=self.colors['bg3'])
        canvas.pack(padx=15, pady=15, fill='both', expand=True)
        
        # Reuse draw_mini_graph logic but with larger canvas
        self.graph_canvas = canvas
        self.root.after(100, self.draw_mini_graph)
    
    def render_diagnostics_inline(self):
        """Render system diagnostics inline"""
        container = tk.Frame(self.content_frame, bg=self.colors['bg2'], padx=15, pady=15)
        container.pack(fill='both', expand=True)
        
        tk.Label(container, text="System Diagnostics", font=('Segoe UI', 12, 'bold'),
                bg=self.colors['bg2'], fg=self.colors['text']).pack(anchor='w', pady=(0, 10))
        
        # Placeholder - will add actual diagnostics
        tk.Label(container, text="System health information will appear here",
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['muted']).pack()
    
    def render_token_stats_inline(self):
        """Render token statistics inline"""
        container = tk.Frame(self.content_frame, bg=self.colors['bg2'], padx=15, pady=15)
        container.pack(fill='both', expand=True)
        
        tk.Label(container, text="Token Statistics", font=('Segoe UI', 12, 'bold'),
                bg=self.colors['bg2'], fg=self.colors['text']).pack(anchor='w', pady=(0, 10))
        
        # Placeholder - will add actual stats
        tk.Label(container, text="Detailed token breakdown will appear here",
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['muted']).pack()
    
    def render_analytics_inline(self):
        """Render analytics dashboard inline"""
        container = tk.Frame(self.content_frame, bg=self.colors['bg2'], padx=15, pady=15)
        container.pack(fill='both', expand=True)
        
        tk.Label(container, text="Analytics Dashboard", font=('Segoe UI', 12, 'bold'),
                bg=self.colors['bg2'], fg=self.colors['text']).pack(anchor='w', pady=(0, 10))
        
        # Placeholder - will add actual analytics
        tk.Label(container, text="Analytics data will appear here",
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['muted']).pack()
    
'''

# Insert the new methods
content = content[:insert_pos] + new_methods + content[insert_pos:]

# Write back
with open(r'c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.pyw', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Added tab switching and rendering methods")
