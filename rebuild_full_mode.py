import re

# Read the file
with open(r'c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.pyw', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the Full mode section
# First, find the start of Full mode
full_mode_start = content.find('        else:  # full mode')
if full_mode_start == -1:
    print("ERROR: Could not find Full mode section")
    exit(1)

# Find the end (where keyboard shortcuts start)
full_mode_end = content.find('        # Keyboard shortcuts (global)', full_mode_start)
if full_mode_end == -1:
    print("ERROR: Could not find end of Full mode section")
    exit(1)

# Extract the old Full mode section
old_full_mode = content[full_mode_start:full_mode_end]

# New Full mode with tabs
new_full_mode = '''        else:  # full mode
            # Full mode - larger window with tabbed analytics
            self.root.attributes('-transparentcolor', '')
            self.root.geometry(f"650x650+{x_pos}+{y_pos}")
            self.root.update()
            
            # Initialize tab state
            if not hasattr(self, 'active_tab'):
                self.active_tab = 'history'
            
            # Header
            header = tk.Frame(self.root, bg=self.colors['bg3'], height=30)
            header.pack(fill='x')
            header.pack_propagate(False)
            
            title = tk.Label(header, text="📊 Context Monitor", font=('Segoe UI', 10, 'bold'),
                            bg=self.colors['bg3'], fg=self.colors['text'])
            title.pack(side='left', padx=10, pady=5)
            
            # Close button
            close_btn = tk.Label(header, text="✕", font=('Segoe UI', 10),
                                bg=self.colors['bg3'], fg=self.colors['text2'], cursor='hand2')
            close_btn.pack(side='right', padx=8)
            close_action = self.minimize_to_tray if HAS_TRAY else self.cleanup_and_exit
            close_btn.bind('<Button-1>', lambda e: close_action())
            
            # Mode toggle
            mini_btn = tk.Label(header, text="◱", font=('Segoe UI', 12), cursor='hand2',
                               bg=self.colors['bg3'], fg=self.colors['blue'])
            mini_btn.pack(side='right', padx=5)
            mini_btn.bind('<Button-1>', lambda e: self.toggle_mini_mode())
            
            # Transparency controls
            alpha_frame = tk.Frame(header, bg=self.colors['bg3'])
            alpha_frame.pack(side='right', padx=5)
            
            tk.Label(alpha_frame, text="−", font=('Segoe UI', 10), cursor='hand2',
                    bg=self.colors['bg3'], fg=self.colors['text2']).pack(side='left', padx=2)
            alpha_frame.winfo_children()[-1].bind('<Button-1>', lambda e: self.adjust_alpha(-0.05))
            
            tk.Label(alpha_frame, text="+", font=('Segoe UI', 10), cursor='hand2',
                    bg=self.colors['bg3'], fg=self.colors['text2']).pack(side='left', padx=2)
            alpha_frame.winfo_children()[-1].bind('<Button-1>', lambda e: self.adjust_alpha(0.05))
            
            for w in [header, title]:
                w.bind('<Button-1>', self.start_drag)
                w.bind('<B1-Motion>', self.drag)
                w.bind('<Button-3>', self.show_context_menu)
            
            # Top info bar (gauge + tokens)
            top_bar = tk.Frame(self.root, bg=self.colors['bg2'], padx=15, pady=10)
            top_bar.pack(fill='x')
            
            # Gauge (smaller)
            self.gauge_canvas = tk.Canvas(top_bar, width=70, height=70,
                                          bg=self.colors['bg2'], highlightthickness=0)
            self.gauge_canvas.pack(side='left', padx=(0, 12))
            self.gauge_canvas.bind('<Button-3>', self.show_context_menu)
            self.gauge_canvas.bind('<Double-Button-1>', lambda e: self.toggle_mini_mode())
            self.draw_gauge(self.current_percent)
            
            # Info
            info = tk.Frame(top_bar, bg=self.colors['bg2'])
            info.pack(side='left', fill='both', expand=True)
            
            tk.Label(info, text="TOKENS LEFT", font=('Segoe UI', 8),
                    bg=self.colors['bg2'], fg=self.colors['muted']).pack(anchor='w')
            
            self.tokens_label = tk.Label(info, text="Loading...", font=('Segoe UI', 14, 'bold'),
                                        bg=self.colors['bg2'], fg=self.colors['text'])
            self.tokens_label.pack(anchor='w')
            
            self.delta_label = tk.Label(info, text="", font=('Segoe UI', 9),
                                       bg=self.colors['bg2'], fg=self.colors['blue'])
            self.delta_label.pack(anchor='w')
            
            self.project_label = tk.Label(info, text="", font=('Segoe UI', 9),
                                         bg=self.colors['bg2'], fg=self.colors['muted'])
            self.project_label.pack(anchor='w', pady=(2, 0))
            
            # Tab bar
            tab_bar = tk.Frame(self.root, bg=self.colors['bg3'], height=35)
            tab_bar.pack(fill='x')
            tab_bar.pack_propagate(False)
            
            tabs = [
                ('📊 Diagnostics', 'diagnostics'),
                ('📈 Token Stats', 'token_stats'),
                ('📅 History', 'history'),
                ('📊 Analytics', 'analytics')
            ]
            
            for label, tab_id in tabs:
                tab_btn = tk.Label(tab_bar, text=label, font=('Segoe UI', 9),
                                  bg=self.colors['bg3'], fg=self.colors['text'],
                                  cursor='hand2', padx=15, pady=8)
                tab_btn.pack(side='left')
                tab_btn.bind('<Button-1>', lambda e, t=tab_id: self.switch_tab(t))
                
                # Highlight active tab
                if tab_id == self.active_tab:
                    tab_btn.config(bg=self.colors['blue'], fg='white')
            
            # Content area (scrollable)
            self.content_frame = tk.Frame(self.root, bg=self.colors['bg2'])
            self.content_frame.pack(fill='both', expand=True)
            
            # Render active tab content
            self.root.after(100, self.render_tab_content)
            
            # Action buttons at bottom
            actions_bar = tk.Frame(self.root, bg=self.colors['bg3'], padx=10, pady=8)
            actions_bar.pack(fill='x')
            
            self.create_button(actions_bar, "💾 Export CSV", self.export_history_csv).pack(side='left', padx=2)
            self.create_button(actions_bar, "🧹 Clean Old", self.cleanup_old_conversations).pack(side='left', padx=2)
            self.create_button(actions_bar, "📦 Archive", self.archive_old_sessions).pack(side='left', padx=2)
            self.create_button(actions_bar, "🔄 Restart", self.restart_antigravity).pack(side='left', padx=2)
            
            # Status bar
            status = tk.Frame(self.root, bg=self.colors['bg3'], height=24)
            status.pack(fill='x', side='bottom')
            status.pack_propagate(False)
            
            self.status_label = tk.Label(status, text="✓ Ready", font=('Segoe UI', 8),
                                        bg=self.colors['bg3'], fg=self.colors['green'], anchor='w')
            self.status_label.pack(side='left', padx=10, fill='x', expand=True)
        
'''

# Replace the old Full mode section
content = content[:full_mode_start] + new_full_mode + content[full_mode_end:]

# Write back
with open(r'c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.pyw', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Rebuilt Full mode with tabbed interface")
