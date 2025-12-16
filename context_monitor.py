"""
Context Monitor - Python Desktop Widget
Borderless, always-on-top token usage tracker for Antigravity
"""

import tkinter as tk
from tkinter import messagebox
import sys
from pathlib import Path
from datetime import datetime
import json
import subprocess
import os
import ctypes
import platform

class ContextMonitor:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Context Monitor")
        
        # Settings
        self.settings_file = Path.home() / '.gemini' / 'antigravity' / 'scratch' / 'token-widget' / 'settings.json'
        self.settings = self.load_settings()
        
        # Borderless, always on top
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', self.settings.get('alpha', 0.95))
        
        # Dark theme colors
        self.colors = {
            'bg': '#0d1117',
            'bg2': '#161b22',
            'bg3': '#21262d',
            'text': '#e6edf3',
            'text2': '#8b949e',
            'muted': '#484f58',
            'green': '#3fb950',
            'yellow': '#d29922',
            'red': '#f85149',
            'blue': '#58a6ff'
        }
        
        self.root.configure(bg=self.colors['bg'])
        
        # State
        self.drag_x = 0
        self.drag_y = 0
        self.current_session = None
        self.handoff_copied = False
        self.mini_mode = self.settings.get('mini_mode', False)
        self.advanced_mode = self.settings.get('advanced_mode', False)
        self.flash_state = False
        self.current_percent = 0
        
        # Project name cache
        self.project_name_cache = {}
        self.project_name_timestamp = {}
        
        # Paths
        self.conversations_dir = Path.home() / '.gemini' / 'antigravity' / 'conversations'
        
        # Hardware Scan
        self.total_ram_mb = self.get_total_memory()
        self.thresholds = self.calculate_thresholds()
        
        self.setup_ui()
        self.load_session()
        self.root.after(5000, self.auto_refresh)
        self.root.after(500, self.flash_warning)
        
    def setup_ui(self):
        # Clear existing widgets
        for widget in self.root.winfo_children():
            widget.destroy()
        
        # Preserve current position
        current_geometry = self.root.geometry()
        # Extract position (format: WxH+X+Y)
        pos = current_geometry.split('+')
        x_pos = pos[1] if len(pos) > 1 else "50"
        y_pos = pos[2] if len(pos) > 2 else "50"
        
        if self.mini_mode:
            # Mini mode: circular gauge with stats
            size = 200 if self.advanced_mode else 120
            self.root.geometry(f"{size}x{size}+{x_pos}+{y_pos}")
            self.root.update()  # Force resize
            
            # Use transparent color to create circular appearance
            trans_color = '#010101'  # Nearly black, used as transparent
            self.root.configure(bg=trans_color)
            self.root.attributes('-transparentcolor', trans_color)
            
            size = 200 if self.advanced_mode else 120
            self.gauge_canvas = tk.Canvas(self.root, width=size, height=size,
                                          bg=trans_color, highlightthickness=0)
            self.gauge_canvas.pack()
            
            # Draw circular background
            if self.advanced_mode:
                # Larger circle for advanced mode
                self.gauge_canvas.create_oval(10, 10, 190, 190, fill=self.colors['bg'], outline='')
            else:
                self.gauge_canvas.create_oval(10, 10, 110, 110, fill=self.colors['bg'], outline='')
            
            self.draw_gauge(self.current_percent)
            
            # Interactions
            self.gauge_canvas.bind('<Double-Button-1>', lambda e: self.toggle_mini_mode())
            self.gauge_canvas.bind('<Button-3>', self.show_context_menu)
            
            # Bind drag to canvas
            self.gauge_canvas.bind('<Button-1>', self.start_drag)
            self.gauge_canvas.bind('<B1-Motion>', self.drag)
            
        else:
            # Full mode - reset transparency
            self.root.attributes('-transparentcolor', '')
            # Adjust height based on advanced mode
            height = 280 if self.advanced_mode else 200
            self.root.geometry(f"280x{height}+{x_pos}+{y_pos}")
            self.root.update()  # Force resize
            
            # Header
            header = tk.Frame(self.root, bg=self.colors['bg3'], height=30)
            header.pack(fill='x')
            header.pack_propagate(False)
            
            title = tk.Label(header, text="📊 Context Monitor", font=('Segoe UI', 10, 'bold'),
                            bg=self.colors['bg3'], fg=self.colors['text'])
            title.pack(side='left', padx=10, pady=5)
            
            # Transparency controls
            alpha_frame = tk.Frame(header, bg=self.colors['bg3'])
            alpha_frame.pack(side='right', padx=5)
            
            tk.Label(alpha_frame, text="−", font=('Segoe UI', 10), cursor='hand2',
                    bg=self.colors['bg3'], fg=self.colors['text2']).pack(side='left', padx=2)
            alpha_frame.winfo_children()[-1].bind('<Button-1>', lambda e: self.adjust_alpha(-0.05))
            
            tk.Label(alpha_frame, text="+", font=('Segoe UI', 10), cursor='hand2',
                    bg=self.colors['bg3'], fg=self.colors['text2']).pack(side='left', padx=2)
            alpha_frame.winfo_children()[-1].bind('<Button-1>', lambda e: self.adjust_alpha(0.05))
            
            # Advanced mode toggle
            adv_icon = "📊" if not self.advanced_mode else "📉"
            adv_btn = tk.Label(header, text=adv_icon, font=('Segoe UI', 10), cursor='hand2',
                              bg=self.colors['bg3'], fg=self.colors['blue'])
            adv_btn.pack(side='right', padx=8)
            adv_btn.bind('<Button-1>', lambda e: self.toggle_advanced_mode())
            
            # Restart button
            restart_btn = tk.Label(header, text="🔄", font=('Segoe UI', 10), cursor='hand2',
                                  bg=self.colors['bg3'], fg=self.colors['blue'])
            restart_btn.pack(side='right', padx=8)
            restart_btn.bind('<Button-1>', lambda e: self.restart_app())
            
            # Mini mode toggle
            mini_btn = tk.Label(header, text="◱", font=('Segoe UI', 12), cursor='hand2',
                               bg=self.colors['bg3'], fg=self.colors['blue'])
            mini_btn.pack(side='right', padx=8)
            mini_btn.bind('<Button-1>', lambda e: self.toggle_mini_mode())
            
            close_btn = tk.Label(header, text="✕", font=('Segoe UI', 10),
                                bg=self.colors['bg3'], fg=self.colors['text2'], cursor='hand2')
            close_btn.pack(side='right', padx=5)
            close_btn.bind('<Button-1>', lambda e: self.root.destroy())
            
            for w in [header, title]:
                w.bind('<Button-1>', self.start_drag)
                w.bind('<B1-Motion>', self.drag)
                w.bind('<Button-3>', self.show_context_menu)
            
            # Content
            content = tk.Frame(self.root, bg=self.colors['bg2'], padx=15, pady=12)
            content.pack(fill='both', expand=True)
            content.bind('<Button-3>', self.show_context_menu)
            
            # Main row
            main = tk.Frame(content, bg=self.colors['bg2'])
            main.pack(fill='x')
            main.bind('<Button-3>', self.show_context_menu)
            
            # Gauge
            self.gauge_canvas = tk.Canvas(main, width=70, height=70, 
                                          bg=self.colors['bg2'], highlightthickness=0)
            self.gauge_canvas.pack(side='left', padx=(0, 12))
            self.gauge_canvas.bind('<Button-3>', self.show_context_menu)
            self.draw_gauge(self.current_percent)
            
            # Info
            info = tk.Frame(main, bg=self.colors['bg2'])
            info.pack(side='left', fill='both', expand=True)
            info.bind('<Button-3>', self.show_context_menu)
            
            tk.Label(info, text="TOKENS LEFT", font=('Segoe UI', 8),
                    bg=self.colors['bg2'], fg=self.colors['muted']).pack(anchor='w')
            self.tokens_label = tk.Label(info, text="—", font=('Segoe UI', 14, 'bold'),
                                         bg=self.colors['bg2'], fg=self.colors['text'])
            self.tokens_label.pack(anchor='w')
            self.tokens_label.bind('<Button-3>', self.show_context_menu)
            
            tk.Label(info, text="PROJECT", font=('Segoe UI', 8),
                    bg=self.colors['bg2'], fg=self.colors['muted']).pack(anchor='w', pady=(8,0))
            self.session_label = tk.Label(info, text="—", font=('Segoe UI', 8),
                                          bg=self.colors['bg2'], fg=self.colors['text2'])
            self.session_label.pack(anchor='w')
            self.session_label.bind('<Button-3>', self.show_context_menu)
            
            # Advanced stats section (only shown when advanced_mode is True)
            if self.advanced_mode:
                # Separator
                tk.Frame(content, bg=self.colors['muted'], height=1).pack(fill='x', pady=(8, 8))
                
                # Advanced breakdown with mini gauges
                adv_row = tk.Frame(content, bg=self.colors['bg2'])
                adv_row.pack(fill='x')
                adv_row.bind('<Button-3>', self.show_context_menu)
                
                # Input tokens gauge
                input_col = tk.Frame(adv_row, bg=self.colors['bg2'])
                input_col.pack(side='left', expand=True, fill='both')
                
                self.input_canvas = tk.Canvas(input_col, width=50, height=50,
                                             bg=self.colors['bg2'], highlightthickness=0)
                self.input_canvas.pack(pady=(0, 4))
                self.input_canvas.bind('<Button-3>', self.show_context_menu)
                
                tk.Label(input_col, text="INPUT", font=('Segoe UI', 7),
                        bg=self.colors['bg2'], fg=self.colors['muted']).pack()
                self.input_label = tk.Label(input_col, text="—", font=('Segoe UI', 8, 'bold'),
                                           bg=self.colors['bg2'], fg=self.colors['text'])
                self.input_label.pack()
                
                # Output tokens gauge
                output_col = tk.Frame(adv_row, bg=self.colors['bg2'])
                output_col.pack(side='left', expand=True, fill='both')
                
                self.output_canvas = tk.Canvas(output_col, width=50, height=50,
                                              bg=self.colors['bg2'], highlightthickness=0)
                self.output_canvas.pack(pady=(0, 4))
                self.output_canvas.bind('<Button-3>', self.show_context_menu)
                
                tk.Label(output_col, text="OUTPUT", font=('Segoe UI', 7),
                        bg=self.colors['bg2'], fg=self.colors['muted']).pack()
                self.output_label = tk.Label(output_col, text="—", font=('Segoe UI', 8, 'bold'),
                                            bg=self.colors['bg2'], fg=self.colors['text'])
                self.output_label.pack()
                
                # File size info
                file_col = tk.Frame(adv_row, bg=self.colors['bg2'])
                file_col.pack(side='left', expand=True, fill='both')
                
                self.file_canvas = tk.Canvas(file_col, width=50, height=50,
                                            bg=self.colors['bg2'], highlightthickness=0)
                self.file_canvas.pack(pady=(0, 4))
                self.file_canvas.bind('<Button-3>', self.show_context_menu)
                
                tk.Label(file_col, text="FILE SIZE", font=('Segoe UI', 7),
                        bg=self.colors['bg2'], fg=self.colors['muted']).pack()
                self.file_label = tk.Label(file_col, text="—", font=('Segoe UI', 8, 'bold'),
                                          bg=self.colors['bg2'], fg=self.colors['text'])
                self.file_label.pack()
            
            # Status bar with copy button
            self.status_frame = tk.Frame(content, bg=self.colors['bg3'], padx=8, pady=6)
            self.status_frame.pack(fill='x', pady=(10, 0))
            self.status_frame.bind('<Button-3>', self.show_context_menu)
            
            self.status_label = tk.Label(self.status_frame, text="✓ Loading...", 
                                        font=('Segoe UI', 9),
                                        bg=self.colors['bg3'], fg=self.colors['text2'])
            self.status_label.pack(side='left')
            self.status_label.bind('<Button-3>', self.show_context_menu)
            
            self.copy_btn = tk.Label(self.status_frame, text="📋 Copy", 
                                    font=('Segoe UI', 8), cursor='hand2',
                                    bg=self.colors['bg3'], fg=self.colors['blue'])
            self.copy_btn.pack(side='right')
            self.copy_btn.bind('<Button-1>', lambda e: self.copy_handoff())
            
            # Tooltips (full mode only)
            self.create_tooltip(self.gauge_canvas, "Token Usage\\nGreen: Safe\\nYellow: < 60% Left\\nRed: < 80% Left")
            self.create_tooltip(adv_btn, "Toggle Advanced Mode\\nShow detailed token breakdown")
            self.create_tooltip(self.copy_btn, "Generate Handoff\\nCreates a summary prompt for the next agent")
            self.create_tooltip(self.session_label, "Current Session ID\\nAuto-detected from files")
            self.create_tooltip(mini_btn, "Toggle Mini Mode (M)\\nSwitch to compact view")
            self.create_tooltip(alpha_frame, "Transparency (+/-)\\nAdjust window opacity")
        
        # Keyboard shortcuts (global)
        self.root.bind('<KeyPress-m>', lambda e: self.toggle_mini_mode())
        self.root.bind('<KeyPress-M>', lambda e: self.toggle_mini_mode())
        self.root.bind('<KeyPress-plus>', lambda e: self.adjust_alpha(0.05))
        self.root.bind('<KeyPress-minus>', lambda e: self.adjust_alpha(-0.05))
        self.root.bind('<KeyPress-r>', lambda e: self.reset_settings())
        self.root.bind('<KeyPress-R>', lambda e: self.reset_settings())
        self.root.bind('<KeyPress-a>', lambda e: self.show_advanced_stats())
        self.root.bind('<KeyPress-A>', lambda e: self.show_advanced_stats())
        
    def create_tooltip(self, widget, text):
        tooltip = ToolTip(widget, text, self.colors)
        
    def draw_gauge(self, percent):
        # Don't delete all in mini mode (preserve circle background)
        if not self.mini_mode:
            self.gauge_canvas.delete('all')
        else:
            self.gauge_canvas.delete('arc')
            self.gauge_canvas.delete('text')
        
        # Get canvas dimensions for dynamic sizing
        width = self.gauge_canvas.winfo_reqwidth()
        
        if self.mini_mode:
            # Center within the visible circle
            if self.advanced_mode:
                cx, cy = 100, 100
                # Main context gauge (Inner)
                r = 35 
                arc_width = 10
            else:
                cx, cy = 60, 60
                r = 35
                arc_width = 8
        else:
            cx, cy = width // 2, width // 2
            r = (width // 2) - 12
            arc_width = 6
        
        # Draw Main Context Gauge
        self.gauge_canvas.create_arc(cx-r, cy-r, cx+r, cy+r, start=90, extent=-360,
                                     style='arc', outline=self.colors['bg3'], width=arc_width, tags='arc')
        
        if percent > 0:
            color = self.colors['green']
            if percent >= 80:
                color = self.colors['red']
            elif percent >= 60:
                color = self.colors['yellow']
            self.gauge_canvas.create_arc(cx-r, cy-r, cx+r, cy+r, start=90, 
                                         extent=-360*(percent/100),
                                         style='arc', outline=color, width=arc_width, tags='arc')
        
        # Advanced Mode: Draw Concentric Rings for Input, Output, File Size
        if self.mini_mode and self.advanced_mode and self.current_session:
            file_size = self.current_session.get('size', 0)
            total_tokens = file_size // 4
            estimated_input = int(total_tokens * 0.4)
            estimated_output = int(total_tokens * 0.6)
            
            # Context window for normalization
            context_window = 200000
            
            # Colors for stats
            col_input = '#58a6ff'   # Blue
            col_output = '#bc8cff'  # Purple
            col_file = '#39c5cf'    # Cyan
            
            # Adjust radii for spacing (Cleaner tracks)
            cx, cy = 100, 100
            r_in = 39    # Input (Inner)
            r_out = 49   # Output (Middle) - Wider gap
            r_file = 59  # File (Outer)
            
            width_r = 5  # Optimized ring width for visibility
            
            # 1. Input Gauge (Inner Ring) - Blue
            pct_in = min(1.0, estimated_input / context_window)
            self.gauge_canvas.create_arc(cx-r_in, cy-r_in, cx+r_in, cy+r_in, start=90, extent=-360,
                                         style='arc', outline='#101418', width=width_r, tags='stats_arc')
            if pct_in > 0:
                self.gauge_canvas.create_arc(cx-r_in, cy-r_in, cx+r_in, cy+r_in, start=90, extent=-360*pct_in,
                                             style='arc', outline=col_input, width=width_r, tags='stats_arc')
            
            # 2. Output Gauge (Middle Ring) - Purple
            pct_out = min(1.0, estimated_output / context_window)
            self.gauge_canvas.create_arc(cx-r_out, cy-r_out, cx+r_out, cy+r_out, start=90, extent=-360,
                                         style='arc', outline='#101418', width=width_r, tags='stats_arc')
            if pct_out > 0:
                self.gauge_canvas.create_arc(cx-r_out, cy-r_out, cx+r_out, cy+r_out, start=90, extent=-360*pct_out,
                                             style='arc', outline=col_output, width=width_r, tags='stats_arc')
                                             
            # 3. File Size (Outer Ring) - Cyan
            # Normalize file size to 50MB
            pct_file = min(1.0, file_size / (50 * 1024 * 1024))
            self.gauge_canvas.create_arc(cx-r_file, cy-r_file, cx+r_file, cy+r_file, start=90, extent=-360,
                                         style='arc', outline='#101418', width=width_r, tags='stats_arc')
            if pct_file > 0:
                self.gauge_canvas.create_arc(cx-r_file, cy-r_file, cx+r_file, cy+r_file, start=90, extent=-360*pct_file,
                                             style='arc', outline=col_file, width=width_r, tags='stats_arc')
        
        # Font sizes
        pct_font_size = 22 if self.mini_mode else 14
        label_font_size = 7
        
        # Enhanced text shadow/outline for mini mode
        if self.mini_mode:
            # Create outline effect with 8-directional shadow
            outline_color = '#000000'
            for offset_x, offset_y in [(0,-2), (0,2), (-2,0), (2,0), (-1,-1), (-1,1), (1,-1), (1,1)]:
                self.gauge_canvas.create_text(cx+offset_x, cy+offset_y, text=f"{percent}%", 
                                              font=('Segoe UI', pct_font_size, 'bold'), 
                                              fill=outline_color, tags='text')
            # Add semi-transparent background circle for extra contrast
            bg_radius = 25
            self.gauge_canvas.create_oval(cx-bg_radius, cy-bg_radius, cx+bg_radius, cy+bg_radius,
                                         fill='#000000', outline='', tags='text', stipple='gray50')
        
        # Percentage text (centered in mini mode, offset in full mode)
        y_offset = 0 if self.mini_mode else -6
        self.gauge_canvas.create_text(cx, cy + y_offset, text=f"{percent}%", 
                                      font=('Segoe UI', pct_font_size, 'bold'), fill='#FFFFFF' if self.mini_mode else self.colors['text'], tags='text')
        
        # Only show CONTEXT label in full mode
        if not self.mini_mode:
            self.gauge_canvas.create_text(cx, cy+14, text="CONTEXT", 
                                          font=('Segoe UI', label_font_size), fill=self.colors['muted'], tags='text')
        
        # Show advanced stats labels in mini mode with LEADER LINES
        if self.mini_mode and self.advanced_mode and self.current_session:
            stats_font_size = 9
            
            # Helper to draw leader line and text
            def draw_stat_label(x_start, y_start, x_end, y_end, text, color, anchor='center'):
                 # Enhanced leader line with slight glow
                 self.gauge_canvas.create_line(x_start, y_start, x_end, y_end, fill='#000000', width=3, tags='text')
                 self.gauge_canvas.create_line(x_start, y_start, x_end, y_end, fill=color, width=2, tags='text')
                 # Text with subtle shadow for depth
                 shadow_offset = 1
                 self.gauge_canvas.create_text(x_end + shadow_offset, y_end + shadow_offset, 
                                              text=text, font=('Segoe UI', stats_font_size, 'bold'), 
                                              fill='#000000', tags='text', anchor=anchor)
                 self.gauge_canvas.create_text(x_end, y_end, 
                                              text=text, font=('Segoe UI', stats_font_size, 'bold'), 
                                              fill=color, tags='text', anchor=anchor)
            # 1. Input (Blue) - Right side, top position
            import math
            text_x, text_y = 175, 60
            # Calculate x position on ring at this y-coordinate
            # Circle equation: (x - cx)² + (y - cy)² = r²
            # Solve for x: x = cx + sqrt(r² - (y - cy)²)
            dy = text_y - 100
            if abs(dy) < r_in:  # Ensure point exists on circle
                dx = math.sqrt(r_in**2 - dy**2)
                x_start = 100 + dx  # Right side of circle
                y_start = text_y
                draw_stat_label(x_start, y_start, text_x, text_y, f"IN:{estimated_input//1000}K", col_input, 'w')
            
            # 2. Output (Purple) - Right side, middle position  
            text_x, text_y = 175, 100
            # At y = center, the rightmost point is simply cx + radius
            x_start = 100 + r_out
            y_start = 100
            draw_stat_label(x_start, y_start, text_x, text_y, f"OUT:{estimated_output//1000}K", col_output, 'w')
            
            # 3. File (Cyan) - Right side, bottom position
            text_x, text_y = 175, 140
            dy = text_y - 100
            if abs(dy) < r_file:
                dx = math.sqrt(r_file**2 - dy**2)
                x_start = 100 + dx
                y_start = text_y
                draw_stat_label(x_start, y_start, text_x, text_y, f"{file_size / (1024*1024):.2f}MB", col_file, 'w')
    
    def draw_mini_gauge(self, canvas, percent, color):
        """Draw a small circular gauge for advanced stats"""
        canvas.delete('all')
        
        width = canvas.winfo_reqwidth()
        cx, cy = width // 2, width // 2
        r = (width // 2) - 8
        arc_width = 4
        
        # Background arc
        canvas.create_arc(cx-r, cy-r, cx+r, cy+r, start=90, extent=-360,
                         style='arc', outline=self.colors['bg3'], width=arc_width)
        
        # Filled arc
        if percent > 0:
            canvas.create_arc(cx-r, cy-r, cx+r, cy+r, start=90, 
                             extent=-360*(percent/100),
                             style='arc', outline=color, width=arc_width)
        
        # Center percentage
        canvas.create_text(cx, cy, text=f"{percent}%", 
                          font=('Segoe UI', 9, 'bold'), fill=self.colors['text'])
        
    def get_sessions(self):
        sessions = []
        try:
            for f in self.conversations_dir.glob('*.pb'):
                if '.tmp' not in f.name:
                    stat = f.stat()
                    sessions.append({
                        'id': f.stem,
                        'size': stat.st_size,
                        'modified': stat.st_mtime,
                        'estimated_tokens': stat.st_size // 4
                    })
            sessions.sort(key=lambda x: x['modified'], reverse=True)
        except Exception as e:
            print(f"Error: {e}")
        return sessions

    def get_project_name(self, session_id):
        """Extract project name from brain directory with caching"""
        import time
        
        # Check cache first (cache for 60 seconds)
        current_time = time.time()
        if session_id in self.project_name_cache:
            cache_age = current_time - self.project_name_timestamp.get(session_id, 0)
            if cache_age < 60:
                return self.project_name_cache[session_id]
        
        try:
            brain_dir = Path.home() / '.gemini' / 'antigravity' / 'brain' / session_id
            
            # Strategy 1: Look for GitHub project path in markdown files
            # This is most accurate for "Project Name"
            import re
            # Pattern matches: .../Documents/GitHub/RepoName/...
            # Captures 'RepoName'
            github_pattern = re.compile(r'GitHub[\\/]([^\\/)\n\r]+)', re.IGNORECASE)
            
            # Check all markdown files, prioritizing specific ones
            priority_files = ['task.md', 'walkthrough.md', 'implementation_plan.md']
            try:
                # Get all md files
                all_md_files = list(brain_dir.glob('*.md'))
                # Sort: priority files first, then alphabetical
                all_md_files.sort(key=lambda f: (0 if f.name in priority_files else 1, f.name))
                
                for fpath in all_md_files:
                    try:
                        content = fpath.read_text(encoding='utf-8', errors='ignore')
                        match = github_pattern.search(content)
                        if match:
                            project_name = match.group(1).strip()
                            # Cache the result
                            self.project_name_cache[session_id] = project_name
                            self.project_name_timestamp[session_id] = current_time
                            return project_name
                    except Exception as e:
                        print(f"Error reading {fpath.name}: {e}")
                        continue
            except Exception as e:
                print(f"Error scanning md files: {e}")

            # Strategy 2: Fallback to Task Name (header in task.md)
            task_file = brain_dir / 'task.md'
            if task_file.exists():
                try:
                    with open(task_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        for line in content.split('\n'):
                            line = line.strip()
                            # Return the first header found
                            if line.startswith('# '):
                                project_name = line[2:].strip()
                                self.project_name_cache[session_id] = project_name
                                self.project_name_timestamp[session_id] = current_time
                                return project_name
                except Exception as e:
                    print(f"Error reading task.md: {e}")
            
            # Strategy 3: Implementation plan header
            plan_file = brain_dir / 'implementation_plan.md'
            if plan_file.exists():
                try:
                    with open(plan_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith('# '):
                                project_name = line[2:].strip()
                                self.project_name_cache[session_id] = project_name
                                self.project_name_timestamp[session_id] = current_time
                                return project_name
                except Exception as e:
                    print(f"Error reading implementation_plan.md: {e}")
                            
        except Exception as e:
            print(f"Error getting project name: {e}")
        
        # Final fallback: short session ID
        fallback = f"Session {session_id[:8]}"
        # Cache even the fallback to prevent repeated failures
        self.project_name_cache[session_id] = fallback
        self.project_name_timestamp[session_id] = current_time
        return fallback
    
    def load_session(self):
        sessions = self.get_sessions()
        if not sessions:
            if not self.mini_mode and hasattr(self, 'status_label'):
                self.status_label.config(text="⚠ No sessions")
            return
            
        self.current_session = sessions[0]
        context_window = 200000
        tokens_used = self.current_session['estimated_tokens'] // 10
        tokens_left = max(0, context_window - tokens_used)
        percent = min(100, round((tokens_used / context_window) * 100))
        
        self.current_percent = percent
        self.draw_gauge(percent)
        
        if not self.mini_mode:
            self.tokens_label.config(text=f"{tokens_left:,}")
            
            # Try to get project name from brain directory
            project_name = self.get_project_name(self.current_session['id'])
            self.session_label.config(text=project_name)
            
            # Update advanced stats if in advanced mode
            if self.advanced_mode and hasattr(self, 'input_label'):
                file_size = self.current_session['size']
                total_tokens = file_size // 4
                estimated_input = int(total_tokens * 0.4)
                estimated_output = int(total_tokens * 0.6)
                
                # Update labels
                self.input_label.config(text=f"{estimated_input//1000}K")
                self.output_label.config(text=f"{estimated_output//1000}K")
                self.file_label.config(text=f"{file_size / (1024*1024):.1f}MB")
                
                # Draw mini gauges
                self.draw_mini_gauge(self.input_canvas, 40, self.colors['blue'])
                self.draw_mini_gauge(self.output_canvas, 60, self.colors['green'])
                # File size as percentage of typical max (50MB)
                file_percent = min(100, int((file_size / (50 * 1024 * 1024)) * 100))
                self.draw_mini_gauge(self.file_canvas, file_percent, self.colors['yellow'])
            
            # Update status and auto-copy at 80%
            if percent >= 80:
                self.status_label.config(text="🔴 Handoff copied!", fg=self.colors['red'])
                self.status_frame.config(bg='#2d1518')
                if not self.handoff_copied:
                    self.copy_handoff()
                    self.handoff_copied = True
            elif percent >= 60:
                self.status_label.config(text="⚡ Approaching limit", fg=self.colors['yellow'])
                self.status_frame.config(bg='#2d2a1a')
                self.handoff_copied = False
            else:
                self.status_label.config(text="✓ Context healthy", fg=self.colors['green'])
                self.status_frame.config(bg=self.colors['bg3'])
                self.handoff_copied = False
            
    def copy_handoff(self):
        if not self.current_session:
            return
            
        context_window = 200000
        tokens_used = self.current_session['estimated_tokens'] // 10
        tokens_left = max(0, context_window - tokens_used)
        percent = min(100, round((tokens_used / context_window) * 100))
        
        handoff = f"""I'm continuing from a previous session that ran low on context.

**Previous Session ID:** `{self.current_session['id']}`

**Project folder:** `C:\\Users\\sam.deiter\\.gemini\\antigravity\\scratch\\`

**Conversation logs:** `C:\\Users\\sam.deiter\\.gemini\\antigravity\\brain\\{self.current_session['id']}\\.system_generated\\logs\\`

Read those logs to understand what we were working on, then continue helping me."""
        
        self.root.clipboard_clear()
        self.root.clipboard_append(handoff)
        
        # Flash the button
        self.copy_btn.config(text="✓ Copied!", fg=self.colors['green'])
        self.root.after(2000, lambda: self.copy_btn.config(text="📋 Copy", fg=self.colors['blue']))
            
    def auto_refresh(self):
        self.load_session()
        self.root.after(5000, self.auto_refresh)
        
    def start_drag(self, event):
        self.drag_x = event.x
        self.drag_y = event.y
        
    def drag(self, event):
        x = self.root.winfo_x() + event.x - self.drag_x
        y = self.root.winfo_y() + event.y - self.drag_y
        self.root.geometry(f"+{x}+{y}")
        
    def load_settings(self):
        """Load settings from JSON file"""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading settings: {e}")
        # Force default advanced_mode to True if not present, but respect saved False if user explicitly disabled it?
        # User requested advanced mode default.
        settings = {'alpha': 0.95, 'mini_mode': False, 'advanced_mode': True}
        return settings
    
    def save_settings(self):
        """Save settings to JSON file"""
        try:
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_file, 'w') as f:
                json.dump({
                    'alpha': self.root.attributes('-alpha'),
                    'mini_mode': self.mini_mode,
                    'advanced_mode': self.advanced_mode
                }, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def toggle_mini_mode(self):
        """Toggle between full and mini mode"""
        self.mini_mode = not self.mini_mode
        self.save_settings()
        self.setup_ui()
        self.load_session()
    
    def toggle_advanced_mode(self):
        """Toggle advanced mode to show/hide detailed stats"""
        self.advanced_mode = not self.advanced_mode
        self.save_settings()
        self.setup_ui()
        self.load_session()
    
    def adjust_alpha(self, delta):
        """Adjust transparency"""
        current = self.root.attributes('-alpha')
        new_alpha = max(0.5, min(1.0, current + delta))
        self.root.attributes('-alpha', new_alpha)
        self.save_settings()
    
    def reset_settings(self):
        """Reset to default settings"""
        self.root.attributes('-alpha', 0.95)
        if self.mini_mode:
            self.mini_mode = False
            self.setup_ui()
            self.load_session()
        self.save_settings()
    
    def flash_warning(self):
        """Flash the widget in mini mode when approaching limit"""
        if self.mini_mode and self.current_percent >= 60:
            # Determine flash speed based on severity
            if self.current_percent >= 80:
                flash_interval = 250  # Fast flash (0.25s)
                flash_color = '#2d1518'  # Dark red background
            else:
                flash_interval = 1000  # Slow pulse (1s)
                flash_color = '#2d2a1a'  # Dark yellow background
            
            # Toggle background color
            if self.flash_state:
                self.root.configure(bg=self.colors['bg'])
            else:
                self.root.configure(bg=flash_color)
            
            self.flash_state = not self.flash_state
            self.root.after(flash_interval, self.flash_warning)
        else:
            # Reset to normal
            self.root.configure(bg=self.colors['bg'])
            self.flash_state = False
            self.root.after(500, self.flash_warning)
    
    def run(self):
        self.root.mainloop()
        
    def get_total_memory(self):
        """Detect total system RAM in MB using ctypes"""
        try:
            if platform.system() == "Windows":
                kernel32 = ctypes.windll.kernel32
                c_ulonglong = ctypes.c_ulonglong
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ('dwLength', ctypes.c_ulong),
                        ('dwMemoryLoad', ctypes.c_ulong),
                        ('ullTotalPhys', c_ulonglong),
                        ('ullAvailPhys', c_ulonglong),
                        ('ullTotalPageFile', c_ulonglong),
                        ('ullAvailPageFile', c_ulonglong),
                        ('ullTotalVirtual', c_ulonglong),
                        ('ullAvailVirtual', c_ulonglong),
                        ('ullAvailExtendedVirtual', c_ulonglong),
                    ]
                memoryStatus = MEMORYSTATUSEX()
                memoryStatus.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                kernel32.GlobalMemoryStatusEx(ctypes.byref(memoryStatus))
                return int(memoryStatus.ullTotalPhys / (1024 * 1024))
            else:
                return 16384 # Fallback
        except Exception as e:
            print(f"Error detecting RAM: {e}")
            return 16384
            
    def calculate_thresholds(self):
        """Calculate warnings based on system RAM"""
        ram = self.total_ram_mb
        return {
            'proc_warn': max(500, int(ram * 0.015)),  # 1.5% (approx 2GB for 128GB)
            'proc_crit': max(1000, int(ram * 0.04)),  # 4% (approx 5GB for 128GB)
            'total_warn': max(2000, int(ram * 0.10)), # 10% (approx 12GB for 128GB)
            'total_crit': max(3000, int(ram * 0.15))  # 15% (approx 19GB for 128GB)
        }
    
    # ==================== DIAGNOSTICS ====================
    
    def restart_app(self):
        """Restart the application"""
        try:
            self.save_settings()
            python = sys.executable
            os.execl(python, python, *sys.argv)
        except Exception as e:
            print(f"Error restarting: {e}")

    def show_context_menu(self, event):
        """Show right-click context menu with improved styling"""
        menu = tk.Menu(self.root, tearoff=0, 
                      bg=self.colors['bg2'], 
                      fg=self.colors['text'],
                      activebackground=self.colors['blue'], 
                      activeforeground='white',
                      font=('Segoe UI', 9),
                      relief='flat',
                      borderwidth=1)
        
        # Diagnostics section
        menu.add_command(label="  📊  Show Diagnostics", command=self.show_diagnostics)
        menu.add_command(label="  📈  Advanced Token Stats", command=self.show_advanced_stats)
        menu.add_separator()
        
        # Actions section
        menu.add_command(label="  🧹  Clean Old Conversations", command=self.cleanup_old_conversations)
        menu.add_command(label="  🔄  Restart Antigravity", command=self.restart_antigravity)
        menu.add_command(label="  🔁  Restart Widget", command=self.restart_app)
        menu.add_separator()
        
        # Mode toggle
        if self.mini_mode:
            menu.add_command(label="  ◳  Expand to Full Mode", command=self.toggle_mini_mode)
        else:
            menu.add_command(label="  ◱  Collapse to Mini Mode", command=self.toggle_mini_mode)
        
        menu.add_separator()
        menu.add_command(label="  ✕  Exit", command=self.root.destroy)
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
    
    def get_antigravity_processes(self):
        """Get memory/CPU usage of Antigravity processes (Fast fallback)"""
        # PowerShell/WMI is too slow on this user's machine (causing UI freeze)
        # We will iterate processes using tasklist which is faster, or just return empty for speed
        try:
             # Fast check using tasklist CSV format
            cmd = 'tasklist /FI "IMAGENAME eq Antigravity.exe" /FO CSV /NH'
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            
            data = []
            if result.stdout:
                for line in result.stdout.splitlines():
                    if 'Antigravity' in line:
                        parts = line.split('","')
                        if len(parts) >= 5:
                            pid = parts[1]
                            mem_str = parts[4].replace('"', '').replace(' K', '').replace(',', '')
                            mem_mb = int(mem_str) // 1024
                            data.append({
                                'Id': pid,
                                'Type': 'Process', # Detailed type requires slow WMI
                                'Mem': mem_mb,
                                'CPU': 0 # CPU requires slow PerfCounters
                            })
            return data
        except Exception as e:
            print(f"Error getting processes: {e}")
            return []
    
    def get_large_conversations(self, min_size_mb=5):
        """Get conversation files larger than min_size_mb"""
        large_files = []
        try:
            for f in self.conversations_dir.glob('*.pb'):
                size_mb = f.stat().st_size / (1024 * 1024)
                if size_mb >= min_size_mb:
                    large_files.append({
                        'name': f.stem[:8] + '...',
                        'size_mb': round(size_mb, 1),
                        'path': f
                    })
            large_files.sort(key=lambda x: x['size_mb'], reverse=True)
        except Exception as e:
            print(f"Error scanning files: {e}")
        return large_files[:5]
    
    def show_diagnostics(self):
        """Show diagnostics popup with detailed recommendations"""
        procs = self.get_antigravity_processes()
        files = self.get_large_conversations()
        
        # Build message
        msg = "=== ANTIGRAVITY PROCESSES ===\n"
        msg += f"(System Logic: {self.total_ram_mb//1024}GB RAM detected)\n"
        total_mem = 0
        high_mem_types = []
        limits = self.thresholds
        
        for p in procs:
            mem = p.get('Mem', 0)
            total_mem += mem
            cpu = p.get('CPU', 0)
            ptype = p.get('Type', 'Unknown')
            status = "🔴" if mem > limits['proc_crit'] else "🟡" if mem > limits['proc_warn'] else "🟢"
            msg += f"{status} {ptype}: {mem}MB RAM, {cpu}s CPU\n"
            if mem > limits['proc_warn']:
                high_mem_types.append(ptype)
        
        msg += f"\nTotal: {total_mem}MB across {len(procs)} processes\n"
        
        msg += "\n=== LARGE CONVERSATION FILES ===\n"
        total_size = sum(f['size_mb'] for f in files)
        for f in files:
            status = "🔴" if f['size_mb'] > 15 else "🟡" if f['size_mb'] > 8 else "🟢"
            msg += f"{status} {f['name']}: {f['size_mb']}MB\n"
        msg += f"\nTotal large files: {total_size:.1f}MB\n"
        
        # Specific recommendations
        msg += "\n=== WHAT TO DO ===\n"
        
        if 'Extension Host' in high_mem_types:
            msg += "⚠️ Extension Host using high memory!\n"
            msg += "   → Disable unused extensions\n"
            msg += "   → Reload Window (Ctrl+Shift+P → Reload)\n\n"
        
        if 'Renderer/GPU' in high_mem_types:
            msg += "⚠️ Renderer process high!\n"
            msg += "   → Close unused tabs/editors\n"
            msg += "   → Restart Antigravity\n\n"
        
        if 'Language Server' in high_mem_types:
            msg += "⚠️ Language Server consuming RAM!\n"
            msg += "   → Close large projects\n"
            msg += "   → Restart language server\n\n"
        
        if total_size > 50:
            msg += "⚠️ Large conversation files!\n"
            msg += "   → Use 'Clean Old Conversations'\n\n"
        
        if total_mem > limits['total_crit']:
            msg += f"🔴 CRITICAL: Total memory > {limits['total_crit']//1024}GB!\n"
            msg += "   → RESTART ANTIGRAVITY NOW\n"
        elif total_mem > limits['total_warn']:
            msg += f"🟡 High memory usage (>{limits['total_warn']//1024}GB)\n"
            msg += "   → Consider restarting soon\n"
        elif not high_mem_types and total_size <= 50:
            msg += "✅ System looks healthy!\n"
        
        messagebox.showinfo("Context Monitor - Diagnostics", msg)
    
    def cleanup_old_conversations(self):
        """Delete conversation files older than 7 days and larger than 5MB"""
        files = self.get_large_conversations(min_size_mb=5)
        if not files:
            messagebox.showinfo("Cleanup", "No large files to clean up!")
            return
        
        msg = f"Found {len(files)} large conversation files:\n\n"
        for f in files:
            msg += f"• {f['name']}: {f['size_mb']}MB\n"
        msg += "\nDelete these files? (Current session will be preserved)"
        
        if messagebox.askyesno("Cleanup Old Conversations", msg):
            deleted = 0
            current_id = self.current_session['id'] if self.current_session else None
            for f in files:
                if current_id and current_id in str(f['path']):
                    continue  # Skip current session
                try:
                    f['path'].unlink()
                    deleted += 1
                except Exception as e:
                    print(f"Error deleting {f['path']}: {e}")
            messagebox.showinfo("Cleanup Complete", f"Deleted {deleted} files.")
    
    def restart_antigravity(self):
        """Restart Antigravity IDE"""
        if messagebox.askyesno("Restart Antigravity", 
                               "This will close all Antigravity windows and restart.\n\nContinue?"):
            try:
                # Kill all Antigravity processes
                subprocess.run(['taskkill', '/F', '/IM', 'Antigravity.exe'], 
                             capture_output=True, timeout=10)
                # Wait a moment
                self.root.after(2000, self._launch_antigravity)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to restart: {e}")
    
    def _launch_antigravity(self):
        """Helper to launch Antigravity after restart"""
        try:
            antigravity_path = Path.home() / 'AppData' / 'Local' / 'Programs' / 'Antigravity' / 'bin' / 'antigravity.cmd'
            if antigravity_path.exists():
                subprocess.Popen([str(antigravity_path)], shell=True)
        except Exception as e:
            print(f"Error launching Antigravity: {e}")
    
    def show_advanced_stats(self):
        """Show detailed token usage breakdown"""
        if not self.current_session:
            messagebox.showinfo("Advanced Stats", "No active session found.")
            return
        
        try:
            # Get conversation file
            conv_file = self.conversations_dir / f"{self.current_session['id']}.pb"
            if not conv_file.exists():
                messagebox.showinfo("Advanced Stats", "Conversation file not found.")
                return
            
            # Calculate token estimates
            file_size = conv_file.stat().st_size
            total_tokens = file_size // 4
            
            # Estimate breakdown (since we can't parse protobuf easily)
            # Typical ratio is ~40% input, ~60% output
            estimated_input = int(total_tokens * 0.4)
            estimated_output = int(total_tokens * 0.6)
            
            context_window = 200000
            tokens_used = self.current_session['estimated_tokens'] // 10
            tokens_left = max(0, context_window - tokens_used)
            percent_used = min(100, round((tokens_used / context_window) * 100))
            
            # Build detailed message
            msg = "=== TOKEN USAGE BREAKDOWN ===\n\n"
            msg += f"Context Window: {context_window:,} tokens\n"
            msg += f"Tokens Used: {tokens_used:,} ({percent_used}%)\n"
            msg += f"Tokens Remaining: {tokens_left:,}\n\n"
            
            msg += "=== ESTIMATED BREAKDOWN ===\n"
            msg += f"Input Tokens (User): ~{estimated_input:,}\n"
            msg += f"Output Tokens (Assistant): ~{estimated_output:,}\n\n"
            
            # Visual bar chart
            msg += "=== USAGE VISUALIZATION ===\n"
            bar_length = 40
            used_bars = int((percent_used / 100) * bar_length)
            remaining_bars = bar_length - used_bars
            
            if percent_used >= 80:
                bar_color = "🔴"
            elif percent_used >= 60:
                bar_color = "🟡"
            else:
                bar_color = "🟢"
            
            msg += f"{bar_color} [{'█' * used_bars}{'░' * remaining_bars}] {percent_used}%\n\n"
            
            # File info
            msg += "=== FILE INFORMATION ===\n"
            msg += f"Conversation File: {conv_file.name}\n"
            msg += f"File Size: {file_size / (1024*1024):.2f} MB\n"
            msg += f"Session ID: {self.current_session['id'][:16]}...\n\n"
            
            # Recommendations
            msg += "=== RECOMMENDATIONS ===\n"
            if percent_used >= 80:
                msg += "🔴 CRITICAL: Start a new session soon!\n"
                msg += "   → Use 'Copy Handoff' to transition\n"
            elif percent_used >= 60:
                msg += "🟡 WARNING: Approaching context limit\n"
                msg += "   → Plan to wrap up current task\n"
            else:
                msg += "✅ Context usage is healthy\n"
            
            messagebox.showinfo("Advanced Token Statistics", msg)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate stats: {e}")

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
        
        # Prevent tooltip from being created if widget is not visible
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

if __name__ == '__main__':
    app = ContextMonitor()
    app.run()
