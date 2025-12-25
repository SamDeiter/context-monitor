import re

# Read the file
with open(r'c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.pyw', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the graph drawing section to add buttons
old_section = '''            # Draw mini graph (will implement draw_mini_graph next)
            try:
                self.draw_mini_graph()
            except:
                # Fallback if draw_mini_graph not implemented yet
                self.graph_canvas.create_text(280, 75, text="Graph loading...",
                                             fill=self.colors['muted'], font=('Segoe UI', 10))
            
            # Status bar'''

new_section = '''            # Draw mini graph after widget is ready
            self.root.after(100, lambda: self.draw_mini_graph() if hasattr(self, 'graph_canvas') else None)
            
            # Action buttons panel
            buttons_frame = tk.Frame(main_content, bg=self.colors['bg2'], padx=15, pady=10)
            buttons_frame.pack(fill='x')
            
            # Row 1: Diagnostics
            row1 = tk.Frame(buttons_frame, bg=self.colors['bg2'])
            row1.pack(fill='x', pady=(0, 5))
            
            self.create_button(row1, "📊 Diagnostics", self.show_diagnostics).pack(side='left', padx=2)
            self.create_button(row1, "📈 Token Stats", self.show_advanced_stats).pack(side='left', padx=2)
            self.create_button(row1, "📅 History", self.show_history).pack(side='left', padx=2)
            self.create_button(row1, "📊 Analytics", self.show_analytics_dashboard).pack(side='left', padx=2)
            
            # Row 2: Actions
            row2 = tk.Frame(buttons_frame, bg=self.colors['bg2'])
            row2.pack(fill='x')
            
            self.create_button(row2, "💾 Export CSV", self.export_history_csv).pack(side='left', padx=2)
            self.create_button(row2, "🧹 Clean Old", self.cleanup_old_conversations).pack(side='left', padx=2)
            self.create_button(row2, "📦 Archive", self.archive_old_sessions).pack(side='left', padx=2)
            self.create_button(row2, "🔄 Restart", self.restart_antigravity).pack(side='left', padx=2)
            
            # Status bar'''

content = content.replace(old_section, new_section)

# Write back
with open(r'c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.pyw', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Added action buttons to Full mode")
