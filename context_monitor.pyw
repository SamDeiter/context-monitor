"""
Context Monitor - Python Desktop Widget
Borderless, always-on-top token usage tracker for Antigravity
"""

import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from datetime import datetime
import json
import re
import subprocess
import os
import sys
import atexit
import ctypes
from ctypes import wintypes
import platform
import threading
import sys
import time
import csv
from datetime import timedelta
from collections import defaultdict

# Windows toast notifications
try:
    from win10toast import ToastNotifier
    HAS_TOAST = True
except ImportError:
    HAS_TOAST = False
try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False
    print("System tray dependencies missing. Run: pip install pystray Pillow")

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
        self.selected_session_id = None  # Manually selected session
        self.handoff_copied = False
        
        # Display mode: 'mini', 'compact', 'full'
        self.display_mode = self.settings.get('display_mode', 'compact')
        # Legacy: convert old mini_mode boolean to display_mode
        if 'mini_mode' in self.settings and 'display_mode' not in self.settings:
            self.display_mode = 'mini' if self.settings['mini_mode'] else 'compact'
        self.mini_mode = (self.display_mode == 'mini')  # Keep for compatibility
        self.flash_state = False
        self.current_percent = 0
        self.tray_icon = None
        self.tray_thread = None
        
        # Project name cache
        self.project_name_cache = {}
        self.project_name_timestamp = {}
        
        # Polling settings (in milliseconds)
        self.polling_interval = self.settings.get('polling_interval', 10000)  # Default 10s
        self.last_tokens = 0  # For delta tracking
        
        # History cache (Sprint 1: Performance)
        self._history_cache = None
        self._history_cache_time = 0
        self._history_dirty = False  # Track if cache needs to be written
        
        # Threading for background updates (Sprint 1: Performance)
        self._update_lock = threading.Lock()
        self._pending_update = None
        
        # Paths
        self.conversations_dir = Path.home() / '.gemini' / 'antigravity' / 'conversations'
        self.history_file = Path.home() / '.gemini' / 'antigravity' / 'scratch' / 'token-widget' / 'history.json'
        self.analytics_file = Path.home() / '.gemini' / 'antigravity' / 'scratch' / 'token-widget' / 'analytics.json'
        
        # Analytics tracking
        self._analytics_cache = None
        self._rate_samples = []  # For time-to-handoff calculation
        self._last_notification_time = 0
        self._notifier = ToastNotifier() if HAS_TOAST else None
        self._daily_budget = self.settings.get('daily_budget', 1000000)  # Default 1M tokens/day
        self._context_window = self.settings.get('context_window', 1000000)
        # Migration: Force reset from old 2.1M default to 1M safe limit
        if self._context_window > 2000000:
            self._context_window = 1000000
        self.save_settings()
        
        # Supported Models
        self.MODELS = {
            "Gemini 2.0 Flash": 1000000,
            "Gemini 1.5 Pro": 2000000,
            "Claude 3.5 Sonnet": 200000,
            "GPT-4o": 128000,
            "GPT-4 Turbo": 128000,
            "Custom": None
        }

        # Initialize model setting if missing or mismatched
        if 'model' not in self.settings:
            current = "Custom"
            for name, limit in self.MODELS.items():
                if limit == self._context_window:
                    current = name
                    break
            self.settings['model'] = current
            self.save_settings()
        
        # Migration: Fix "Unknown" model in analytics
        try:
            analytics = self.load_analytics()
            if 'models' in analytics and 'Unknown' in analytics['models']:
                unknown_data = analytics['models'].pop('Unknown')
                target_model = self.settings.get('model', 'Custom')
                
                if target_model not in analytics['models']:
                    analytics['models'][target_model] = {'total': 0}
                
                analytics['models'][target_model]['total'] += unknown_data.get('total', 0)
                
                # Force save to disk
                self._analytics_cache = analytics
                with open(self.analytics_file, 'w') as f:
                     json.dump({
                        'daily': analytics['daily'],
                        'projects': analytics.get('projects', {}),
                        'models': analytics['models']
                     }, f, indent=2)
        except Exception as e:
            print(f"Migration error: {e}")
            
        # Hardware Scan
        self.total_ram_mb = self.get_total_memory()
        self.thresholds = self.calculate_thresholds()
        
        # Register cleanup on exit
        atexit.register(self._cleanup_processes)
        self.root.protocol("WM_DELETE_WINDOW", self.cleanup_and_exit)
        
        # Register event handlers
        self.root.bind('<Button-3>', self.show_context_menu)  # Right-click anywhere
        
        self.setup_ui()
        self.load_session()
        self.root.after(self.polling_interval, self.auto_refresh)
        self.root.after(500, self.flash_warning)
        
        # Restore window position after UI is ready
        self.root.after(100, self.restore_window_position)
    
    def parse_varint(self, data, offset):
        """Parse a protobuf varint from data at offset."""
        result = 0
        shift = 0
        while offset < len(data):
            byte = data[offset]
            offset += 1
            result |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                return result, offset
            shift += 7
        return None, offset
    
    def extract_pb_tokens(self, pb_file_path):
        """
        Extract accurate token count from protobuf conversation file.
        
        Returns dict with:
            - tokens_used: actual tokens consumed
            - context_window: total context window size
            - tokens_remaining: tokens left
        
        Falls back to file size estimation if parsing fails.
        """
        try:
            with open(pb_file_path, 'rb') as f:
                data = f.read()
            
            file_size = len(data)
            
            # Search last 50KB for token metadata (most recent data)
            search_region = data[-50000:] if len(data) > 50000 else data
            
            # Extract all varint numbers in reasonable token range
            candidates = []
            offset = 0
            while offset < len(search_region) - 10:
                num, new_offset = self.parse_varint(search_region, offset)
                if num and 100000 < num < 20000000:  # 100K to 20M tokens
                    candidates.append({
                        'value': num,
                        'position': offset
                    })
                offset += 1
            
            if not candidates:
                # Fallback to old estimation
                estimated = file_size // 4
                return {
                    'tokens_used': estimated // 10,
                    'context_window': self._context_window,
                    'tokens_remaining': self._context_window - (estimated // 10),
                    'method': 'fallback'
                }
            
            # Sort by position (most recent last)
            candidates.sort(key=lambda x: x['position'])
            recent = candidates[-5:]  # Last 5 candidates
            
            # Heuristic: Look for large number (context window) followed by smaller (remaining)
            context_window = None
            tokens_remaining = None
            
            for i in range(len(recent) - 1):
                curr = recent[i]['value']
                next_val = recent[i + 1]['value']
                
                if curr > next_val and curr > 1000000:
                    context_window = curr
                    tokens_remaining = next_val
                    break
            
            # Fallback: use largest as window, second-largest as remaining
            if not context_window:
                sorted_vals = sorted([c['value'] for c in recent], reverse=True)
                context_window = sorted_vals[0] if sorted_vals else self._context_window
                tokens_remaining = sorted_vals[1] if len(sorted_vals) > 1 else context_window // 2
            
            tokens_used = context_window - tokens_remaining
            
            return {
                'tokens_used': tokens_used,
                'context_window': context_window,
                'tokens_remaining': tokens_remaining,
                'method': 'protobuf'
            }
            
        except Exception as e:
            # Fallback to old method on any error
            print(f"[Token Extraction] Error parsing {pb_file_path.name}: {e}")
            estimated = pb_file_path.stat().st_size // 4
            return {
                'tokens_used': estimated // 10,
                'context_window': self._context_window,
                'tokens_remaining': self._context_window - (estimated // 10),
                'method': 'fallback'
            }

        
    def create_button(self, parent, text, command):
        """Create a styled button for Full mode"""
        btn = tk.Label(parent, text=text, font=('Segoe UI', 8),
                      bg=self.colors['bg3'], fg=self.colors['text'],
                      cursor='hand2', padx=8, pady=4,
                      relief='flat', borderwidth=1)
        btn.bind('<Button-1>', lambda e: command())
        btn.bind('<Enter>', lambda e: btn.config(bg=self.colors['blue'], fg='white'))
        btn.bind('<Leave>', lambda e: btn.config(bg=self.colors['bg3'], fg=self.colors['text']))
        return btn
    
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
        
        if self.display_mode == 'mini':
            # Mini mode: circular gauge - reduced size, tighter fit
            self.root.geometry(f"120x120+{x_pos}+{y_pos}")
            self.root.update()  # Force resize
            
            # Use transparent color to create circular appearance
            trans_color = '#010101'  # Nearly black, used as transparent
            self.root.configure(bg=trans_color)
            self.root.attributes('-transparentcolor', trans_color)
            
            self.gauge_canvas = tk.Canvas(self.root, width=120, height=120,
                                          bg=trans_color, highlightthickness=0)
            self.gauge_canvas.pack()
            
            # Draw circular background - reduced padding (was 10, now 4)
            self.gauge_canvas.create_oval(4, 4, 116, 116, fill=self.colors['bg'], outline='')
            
            self.draw_gauge(self.current_percent)
            
            # Interactions
            self.gauge_canvas.bind('<Double-Button-1>', lambda e: self.toggle_mini_mode())
            self.gauge_canvas.bind('<Button-3>', self.show_context_menu)
            
            # Bind drag to canvas
            self.gauge_canvas.bind('<Button-1>', self.start_drag)
            self.gauge_canvas.bind('<B1-Motion>', self.drag)
            
        elif self.display_mode == 'compact':
            # Compact mode (current "full" mode) - reset transparency
            self.root.attributes('-transparentcolor', '')
            self.root.geometry(f"320x220+{x_pos}+{y_pos}")
            self.root.update()  # Force resize
            
            # Header
            header = tk.Frame(self.root, bg=self.colors['bg3'], height=30)
            header.pack(fill='x')
            header.pack_propagate(False)
            
            title = tk.Label(header, text="📊 Context Monitor", font=('Segoe UI', 10, 'bold'),
                            bg=self.colors['bg3'], fg=self.colors['text'])
            title.pack(side='left', padx=10, pady=5)
            
            # Close button (packed first to be at far right)
            close_btn = tk.Label(header, text="✕", font=('Segoe UI', 10),
                                bg=self.colors['bg3'], fg=self.colors['text2'], cursor='hand2')
            close_btn.pack(side='right', padx=8)
            close_action = self.minimize_to_tray if HAS_TRAY else self.cleanup_and_exit
            close_btn.bind('<Button-1>', lambda e: close_action())
            
            # Mini mode toggle
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
            
            # Content
            content = tk.Frame(self.root, bg=self.colors['bg2'], padx=15, pady=12)
            content.pack(fill='both', expand=True)
            content.bind('<Button-3>', self.show_context_menu)
            
            # Main row
            main = tk.Frame(content, bg=self.colors['bg2'])
            main.pack(fill='x')
            main.bind('<Button-3>', self.show_context_menu)
            
            # Gauge
            self.gauge_canvas = tk.Canvas(main, width=90, height=90, 
                                          bg=self.colors['bg2'], highlightthickness=0)
            self.gauge_canvas.pack(side='left', padx=(0, 12))
            self.gauge_canvas.bind('<Button-3>', self.show_context_menu)
            self.gauge_canvas.bind('<Double-Button-1>', lambda e: self.toggle_mini_mode())
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
            
            # Delta label (tokens used since last refresh)
            self.delta_label = tk.Label(info, text="", font=('Segoe UI', 8),
                                        bg=self.colors['bg2'], fg=self.colors['muted'])
            self.delta_label.pack(anchor='w')
            self.delta_label.bind('<Button-3>', self.show_context_menu)
            
            tk.Label(info, text="PROJECT", font=('Segoe UI', 8),
                    bg=self.colors['bg2'], fg=self.colors['muted']).pack(anchor='w', pady=(8,0))
            self.session_label = tk.Label(info, text="—", font=('Segoe UI', 8),
                                          bg=self.colors['bg2'], fg=self.colors['text2'])
            self.session_label.pack(anchor='w')
            self.session_label.bind('<Button-3>', self.show_context_menu)
            
            # Mini history panel (right side) - shows recent deltas
            history_frame = tk.Frame(main, bg=self.colors['bg3'], padx=6, pady=4)
            history_frame.pack(side='right', fill='y', padx=(8, 0))
            history_frame.bind('<Button-3>', self.show_context_menu)
            
            tk.Label(history_frame, text="RECENT", font=('Segoe UI', 7),
                    bg=self.colors['bg3'], fg=self.colors['muted']).pack(anchor='center')
            
            self.history_labels = []
            for i in range(5):  # Show last 5 deltas
                lbl = tk.Label(history_frame, text="—", font=('Consolas', 8),
                              bg=self.colors['bg3'], fg=self.colors['text2'])
                lbl.pack(anchor='e')
                lbl.bind('<Button-3>', self.show_context_menu)
                self.history_labels.append(lbl)
            
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
            
            # Refresh button
            self.refresh_btn = tk.Label(self.status_frame, text="🔄", 
                                       font=('Segoe UI', 10), cursor='hand2',
                                       bg=self.colors['bg3'], fg=self.colors['blue'])
            self.refresh_btn.pack(side='right', padx=(0, 8))
            self.refresh_btn.bind('<Button-1>', lambda e: self.force_refresh())
            
            # Tooltips (full mode only)
            self.create_tooltip(self.gauge_canvas, "Token Usage\nGreen: Safe\nYellow: < 60% Left\nRed: < 80% Left")
            self.create_tooltip(self.copy_btn, "Generate Handoff\nCreates a summary prompt for the next agent")
            self.create_tooltip(self.refresh_btn, "Refresh (R)\nForce refresh project detection")
            self.create_tooltip(self.session_label, "Current Project\nAuto-detected from VS Code/GitHub")
            self.create_tooltip(mini_btn, "Toggle Mini Mode (M)\nSwitch to compact view")
            self.create_tooltip(alpha_frame, "Transparency (+/-)\nAdjust window opacity")
        
        else:  # full mode
            # Full mode - larger window with embedded analytics
            self.root.attributes('-transparentcolor', '')
            self.root.geometry(f"600x450+{x_pos}+{y_pos}")
            self.root.update()
            
            # Reuse compact mode header and content (copy from above)
            # Header
            header = tk.Frame(self.root, bg=self.colors['bg3'], height=30)
            header.pack(fill='x')
            header.pack_propagate(False)
            
            title = tk.Label(header, text="📊 Context Monitor - Full", font=('Segoe UI', 10, 'bold'),
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
            
            # Main content area
            main_content = tk.Frame(self.root, bg=self.colors['bg2'])
            main_content.pack(fill='both', expand=True)
            
            # Top section: Gauge + Info (compact mode style)
            top_section = tk.Frame(main_content, bg=self.colors['bg2'], padx=15, pady=12)
            top_section.pack(fill='x')
            
            # Gauge
            self.gauge_canvas = tk.Canvas(top_section, width=90, height=90,
                                          bg=self.colors['bg2'], highlightthickness=0)
            self.gauge_canvas.pack(side='left', padx=(0, 12))
            self.gauge_canvas.bind('<Button-3>', self.show_context_menu)
            self.gauge_canvas.bind('<Double-Button-1>', lambda e: self.toggle_mini_mode())
            self.draw_gauge(self.current_percent)
            
            # Info panel (simplified from compact mode)
            info = tk.Frame(top_section, bg=self.colors['bg2'])
            info.pack(side='left', fill='both', expand=True)
            
            tk.Label(info, text="TOKENS LEFT", font=('Segoe UI', 8),
                    bg=self.colors['bg2'], fg=self.colors['muted']).pack(anchor='w')
            
            self.tokens_label = tk.Label(info, text="Loading...", font=('Segoe UI', 16, 'bold'),
                                        bg=self.colors['bg2'], fg=self.colors['text'])
            self.tokens_label.pack(anchor='w')
            
            self.delta_label = tk.Label(info, text="", font=('Segoe UI', 9),
                                       bg=self.colors['bg2'], fg=self.colors['blue'])
            self.delta_label.pack(anchor='w')
            
            self.project_label = tk.Label(info, text="", font=('Segoe UI', 9),
                                         bg=self.colors['bg2'], fg=self.colors['muted'])
            self.project_label.pack(anchor='w', pady=(4, 0))
            
            # Graph section (NEW for full mode)
            graph_section = tk.Frame(main_content, bg=self.colors['bg'], padx=15, pady=10)
            graph_section.pack(fill='both', expand=True)
            
            tk.Label(graph_section, text="📈 Usage History (Last 24h)", font=('Segoe UI', 9, 'bold'),
                    bg=self.colors['bg'], fg=self.colors['text']).pack(anchor='w', pady=(0, 5))
            
            # Graph canvas
            self.graph_canvas = tk.Canvas(graph_section, width=560, height=150,
                                         bg=self.colors['bg2'], highlightthickness=1,
                                         highlightbackground=self.colors['bg3'])
            self.graph_canvas.pack(fill='both', expand=True)
            
            # Draw mini graph after widget is ready
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
            
            # Status bar
            status = tk.Frame(self.root, bg=self.colors['bg3'], height=28)
            status.pack(fill='x', side='bottom')
            status.pack_propagate(False)
            
            self.status_label = tk.Label(status, text="✓ Ready", font=('Segoe UI', 8),
                                        bg=self.colors['bg3'], fg=self.colors['green'], anchor='w')
            self.status_label.pack(side='left', padx=10, fill='x', expand=True)
        
        # Keyboard shortcuts (global)
        self.root.bind('<KeyPress-m>', lambda e: self.toggle_mini_mode())
        self.root.bind('<KeyPress-plus>', lambda e: self.adjust_alpha(0.05))
        self.root.bind('<KeyPress-minus>', lambda e: self.adjust_alpha(-0.05))
        self.root.bind('<KeyPress-r>', lambda e: self.force_refresh())
        self.root.bind('<KeyPress-a>', lambda e: self.show_advanced_stats())
        self.root.bind('<KeyPress-d>', lambda e: self.show_analytics_dashboard())
        self.root.bind('<KeyPress-e>', lambda e: self.export_history_csv())
        
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
            # Center within the visible circle (120x120 with 4px padding = 4,4 to 116,116)
            cx, cy = 60, 60
            r = 44  # Larger radius to fill more space
            arc_width = 8
        else:
            cx, cy = width // 2, width // 2
            r = (width // 2) - 12
            arc_width = 6
        
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
        
        # Larger fonts for mini mode
        pct_font_size = 22 if self.mini_mode else 14
        
        # Drop shadow for mini mode (offset dark text behind) - only for percentage
        if self.mini_mode:
            shadow_offset = 2
            shadow_color = '#000000'
            # Draw percentage slightly higher to make room for delta
            self.gauge_canvas.create_text(cx+shadow_offset, cy-8+shadow_offset, text=f"{percent}%", 
                                          font=('Segoe UI', pct_font_size, 'bold'), fill=shadow_color, tags='text')
            self.gauge_canvas.create_text(cx, cy-8, text=f"{percent}%", 
                                          font=('Segoe UI', pct_font_size, 'bold'), fill=self.colors['text'], tags='text')
            
            # Show latest delta below percentage
            if hasattr(self, 'current_session') and self.current_session:
                history_data = self.load_history().get(self.current_session['id'], [])
                recent_deltas = [h for h in history_data if h.get('delta', 0) != 0]
                if recent_deltas:
                    last_delta = recent_deltas[-1].get('delta', 0)
                    if last_delta > 0:
                        delta_text = f"+{last_delta:,}"
                        if last_delta > 5000:
                            delta_color = self.colors['red']
                        elif last_delta > 2000:
                            delta_color = self.colors['yellow']
                        else:
                            delta_color = self.colors['green']
                    else:
                        delta_text = f"{last_delta:,}"
                        delta_color = self.colors['blue']
                    
                    # Draw delta with shadow
                    self.gauge_canvas.create_text(cx+1, cy+18+1, text=delta_text, 
                                                  font=('Consolas', 10, 'bold'), fill=shadow_color, tags='text')
                    self.gauge_canvas.create_text(cx, cy+18, text=delta_text, 
                                                  font=('Consolas', 10, 'bold'), fill=delta_color, tags='text')
        else:
            # Full mode - just draw percentage centered
            self.gauge_canvas.create_text(cx, cy, text=f"{percent}%", 
                                          font=('Segoe UI', pct_font_size, 'bold'), fill=self.colors['text'], tags='text')
        
    def get_sessions(self):
        sessions = []
        try:
            # FAST SCAN: Use os.scandir instead of pathlib for better performance
            # This avoids creating thousands of Path objects and is much faster on Windows
            if self.conversations_dir.exists():
                with os.scandir(self.conversations_dir) as entries:
                    for entry in entries:
                        name = entry.name
                        if not entry.is_file():
                            continue
                            
                        # Filter extensions manually
                        is_pb = name.endswith('.pb')
                        is_gz = name.endswith('.pb.gz')
                        if not (is_pb or is_gz):
                            continue
                            
                        if '.tmp' in name:
                            continue
                            
                        try:
                            # Get stats from the entry directly (cached)
                            stat = entry.stat()
                            
                            # Extract session ID
                            if is_pb:
                                session_id = name[:-3]
                            else:
                                session_id = name[:-6]  # .pb.gz
                            
                            # Build full path for token extraction
                            pb_path = self.conversations_dir / name
                            
                            # Extract accurate token data from protobuf
                            token_data = self.extract_pb_tokens(pb_path)
                            
                            sessions.append({
                                'id': session_id,
                                'size': stat.st_size,
                                'modified': stat.st_mtime,
                                'estimated_tokens': stat.st_size // 4,  # Keep for comparison
                                'token_data': token_data,  # Accurate extraction
                                'compressed': is_gz,
                                'pb_path': pb_path
                            })
                        except Exception:
                            continue
                            
            sessions.sort(key=lambda x: x['modified'], reverse=True)
        except Exception as e:
            print(f"Error: {e}")
        return sessions

    def get_active_vscode_project(self):
        """Get active VS Code project using ctypes (Zero-overhead process check)"""
        try:
            # Use ctypes directly to avoid expensive subprocess/PowerShell calls
            user32 = ctypes.windll.user32
            
            # REMOVED EXPLICIT TYPE DEFINITIONS to avoid global user32 conflicts
            
            # Get foreground window handle
            
            # Get foreground window handle
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return None
                
            # Get window title length
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return None
            
            # Get window title
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value
            
            # Check if it's a VS Code window
            if 'Visual Studio Code' in title:
                parts = title.split(' - ')
                if len(parts) >= 2:
                    # The second-to-last part before "Visual Studio Code" is usually the project
                    for part in reversed(parts):
                        if 'Visual Studio Code' in part:
                            continue
                        clean = part.strip()
                        if clean and not clean.endswith('.py') and not clean.endswith('.js'):
                            return clean
        except Exception:
            # Fail silently to avoid log spam/crashes on weird Windows APIs
            return None
        return None
    
    def get_recently_modified_project(self):
        """Find the most recently modified project in GitHub folder"""
        try:
            github_dir = Path.home() / 'Documents' / 'GitHub'
            if github_dir.exists():
                projects = []
                for project_dir in github_dir.iterdir():
                    if project_dir.is_dir() and not project_dir.name.startswith('.'):
                        # Check for recent activity (any file modified in last 10 minutes)
                        try:
                            # Check .git/index or any recent file
                            git_index = project_dir / '.git' / 'index'
                            if git_index.exists():
                                mtime = git_index.stat().st_mtime
                                projects.append((project_dir.name, mtime))
                            else:
                                # Check the folder itself
                                mtime = project_dir.stat().st_mtime
                                projects.append((project_dir.name, mtime))
                        except:
                            pass
                
                if projects:
                    # Sort by modification time, newest first
                    projects.sort(key=lambda x: x[1], reverse=True)
                    return projects[0][0]
        except Exception as e:
            pass
        return None

    def get_project_name(self, session_id, skip_vscode=False):
        """Extract project name using multiple detection strategies"""
        # Check cache first (60 second cache to prevent PowerShell lag)
        import time
        now = time.time()
        if session_id in self.project_name_cache:
            if session_id in self.project_name_timestamp:
                if now - self.project_name_timestamp[session_id] < 60:  # 60s cache
                    return self.project_name_cache[session_id]
        
        project_name = None

        # Strategy 1: Check active VS Code window (ONLY for current session - PowerShell is slow)
        if not skip_vscode:
            vscode_project = self.get_active_vscode_project()
            if vscode_project:
                project_name = vscode_project

        # Strategy 2: Check brain folder for this session - has markdown files with project info
        if not project_name:
            try:
                brain_dir = Path.home() / '.gemini' / 'antigravity' / 'brain' / session_id
                if brain_dir.exists():
                    # Check markdown files for project name mentions
                    for md_file in brain_dir.glob('*.md'):
                        try:
                            content = md_file.read_text(encoding='utf-8', errors='ignore')[:2000]
                            # Look for project patterns
                            if 'UE5' in content or 'Blueprint' in content:
                                project_name = 'UE5LMSBlueprint'
                                break
                            elif 'context-monitor' in content.lower() or 'Context Monitor' in content:
                                project_name = 'context-monitor'
                                break
                            # Check for GitHub folder pattern in content
                            pattern = r'GitHub[/\\]([A-Za-z0-9_-]+)'
                            match = re.search(pattern, content)
                            if match:
                                project_name = match.group(1)
                                break
                        except:
                            pass
            except Exception as e:
                print(f"Error checking brain folder: {e}")

        # Note: code_tracker detection removed - it picks most recent project globally, not session-specific

        # Strategy 3: Check recently modified GitHub folder
        if not project_name:
            recent_project = self.get_recently_modified_project()
            if recent_project:
                project_name = recent_project
        
        # Cache the result
        if project_name:
            self.project_name_cache[session_id] = project_name
            self.project_name_timestamp[session_id] = now
            return project_name
        
        # Fallback to truncated session ID
        return session_id[:16] + "..."
    
    def load_session(self):
        sessions = self.get_sessions()
        if not sessions:
            if not self.mini_mode and hasattr(self, 'status_label'):
                self.status_label.config(text="⚠ No sessions")
            return
            
        self.current_session = sessions[0]
        
        # specific session selection logic
        if self.selected_session_id:
            found = next((s for s in sessions if s['id'] == self.selected_session_id), None)
            if found:
                self.current_session = found
            else:
                # Session disappeared, reset selection
                self.selected_session_id = None

        context_window = self._context_window
        
        # Use accurate token data from protobuf extraction
        if 'token_data' in self.current_session and self.current_session['token_data']:
            token_data = self.current_session['token_data']
            tokens_used = token_data['tokens_used']
            context_window = token_data['context_window']
            tokens_left = token_data['tokens_remaining']
            
            # Log extraction method for debugging
            if token_data.get('method') == 'protobuf':
                # Successfully extracted from protobuf
                pass
            else:
                # Fallback was used
                print(f"[Token Extraction] Using fallback for {self.current_session['id'][:16]}...")
        else:
            # Fallback to old estimation if token_data not available
            tokens_used = self.current_session['estimated_tokens'] // 10
            tokens_left = max(0, context_window - tokens_used)
            print(f"[Token Extraction] No token_data available, using old estimation")
        
        percent = min(100, round((tokens_used / context_window) * 100))
        
        # Calculate delta from last reading
        delta = tokens_used - self.last_tokens if self.last_tokens > 0 else 0
        
        self.current_percent = percent
        self.draw_gauge(percent)
        
        # Track analytics - skip VS Code detection if session was manually selected
        # MUST run before save_history to capture correct delta (save_history updates self.last_tokens)
        is_manual_session = self.selected_session_id is not None
        project_name = self.get_project_name(self.current_session['id'], skip_vscode=is_manual_session)
        self.save_analytics(tokens_used, project_name)
        
        # Save history (throttle: save max once per 5 mins)
        self.save_history(self.current_session['id'], tokens_used)
        
        # Check for context window alerts (handoff warnings)
        self.check_context_alerts(percent, tokens_used)
        
        # DEBUG ALERTS
        if time.time() % 5 < 0.1: # Print every ~5s
            ana = self.load_analytics()
            today = datetime.now().strftime('%Y-%m-%d')
            tod_total = ana['daily'].get(today, {}).get('total', 0)
            print(f"[DEBUG] Window%: {percent} | Tokens: {tokens_used} | Budget: {self._daily_budget} | Today: {tod_total}")
        
        if not self.mini_mode:
            self.tokens_label.config(text=f"{tokens_left:,}")
            
            # Update delta label
            if hasattr(self, 'delta_label'):
                if delta > 0:
                    self.delta_label.config(text=f"↑ +{delta:,} since last", fg=self.colors['yellow'])
                elif delta < 0:
                    self.delta_label.config(text=f"↓ {delta:,} (new session)", fg=self.colors['blue'])
                else:
                    self.delta_label.config(text="— no change", fg=self.colors['muted'])
            
            # Use project name from file if session was manually selected
            display_name = self.get_project_name(self.current_session['id'], skip_vscode=is_manual_session)
            self.session_label.config(text=display_name)
            
            # Update tray icon
            if HAS_TRAY:
                self.update_tray_icon()
            
            # Update mini history panel with recent deltas
            if hasattr(self, 'history_labels'):
                history_data = self.load_history().get(self.current_session['id'], [])
                # Get last 5 entries with non-zero deltas
                recent_deltas = [h for h in history_data if h.get('delta', 0) != 0][-5:]
                
                for i, lbl in enumerate(self.history_labels):
                    if i < len(recent_deltas):
                        d = recent_deltas[-(i+1)]  # Reverse order (newest first)
                        delta_val = d.get('delta', 0)
                        if delta_val > 0:
                            text = f"+{delta_val:,}"
                            # Color based on magnitude
                            if delta_val > 5000:
                                color = self.colors['red']
                            elif delta_val > 2000:
                                color = self.colors['yellow']
                            else:
                                color = self.colors['green']
                        else:
                            text = f"{delta_val:,}"
                            color = self.colors['blue']
                        lbl.config(text=text, fg=color)
                    else:
                        lbl.config(text="—", fg=self.colors['muted'])
            
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
                self.status_label.config(text="✓ Plenty of fuel", fg=self.colors['green'])
                self.status_frame.config(bg=self.colors['bg3'])
                self.handoff_copied = False
            
    def copy_handoff(self):
        if not self.current_session:
            return
            
        context_window = self._context_window
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
        self.root.after(self.polling_interval, self.auto_refresh)
    
    def force_refresh(self):
        """Force refresh project detection by clearing cache"""
        # Clear the cache to force re-detection
        self.project_name_cache.clear()
        self.project_name_timestamp.clear()
        
        # Show visual feedback
        if not self.mini_mode and hasattr(self, 'refresh_btn'):
            self.refresh_btn.config(fg=self.colors['green'])
            self.root.after(500, lambda: self.refresh_btn.config(fg=self.colors['blue']))
        
        # Reload session data
        self.load_session()
        
        # Print debug info
        if self.current_session:
            project = self.get_project_name(self.current_session['id'])
            print(f"[Refresh] Detected project: {project}")
        
        
    def switch_session(self, session_id):
        """Manually switch to a specific session"""
        self.selected_session_id = session_id
        # Clear project name cache for this session to force refresh
        if session_id in self.project_name_cache:
            del self.project_name_cache[session_id]
        self.load_session()
    
    def set_polling_speed(self, interval_ms):
        """Set the polling interval in milliseconds"""
        self.polling_interval = interval_ms
        self.save_settings()
        print(f"[Settings] Polling interval set to {interval_ms}ms")
        
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
        return {'alpha': 0.95, 'mini_mode': False}
    
    def save_settings(self):
        """Save settings to JSON file"""
        try:
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_file, 'w') as f:
                json.dump({
                    'alpha': self.root.attributes('-alpha'),
                    'display_mode': self.display_mode,  # Save new display_mode
                    'polling_interval': self.polling_interval,
                    'daily_budget': self._daily_budget,
                    'context_window': self._context_window,
                    'window_x': self.root.winfo_x(),
                    'window_y': self.root.winfo_y()
                }, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def restore_window_position(self):
        """Restore window to last saved position"""
        x = self.settings.get('window_x')
        y = self.settings.get('window_y')
        if x is not None and y is not None:
            # Ensure window is on screen
            screen_w = self.root.winfo_screenwidth()
            screen_h = self.root.winfo_screenheight()
            x = max(0, min(x, screen_w - 100))
            y = max(0, min(y, screen_h - 100))
            self.root.geometry(f"+{x}+{y}")
    
    def reload_ui(self):
        """Reload UI without restarting app (for development)"""
        try:
            # Save current state
            current_mode = self.mini_mode
            current_session = self.selected_session_id
            
            # Rebuild UI
            self.setup_ui()
            
            # Restore state
            self.mini_mode = current_mode
            if current_session:
                self.selected_session_id = current_session
            
            # Reload data
            self.load_session()
            
            print("[Reload] UI reloaded successfully")
        except Exception as e:
            print(f"[Reload] Error: {e}")
    
    def toggle_mini_mode(self):
        """Cycle through display modes: mini → compact → full → mini"""
        # Cycle through modes
        if self.display_mode == 'mini':
            self.display_mode = 'compact'
        elif self.display_mode == 'compact':
            self.display_mode = 'full'
        else:  # full
            self.display_mode = 'mini'
        
        # Update legacy mini_mode for compatibility
        self.mini_mode = (self.display_mode == 'mini')
        
        self.save_settings()
        self.setup_ui()
        # Don't call load_session() - it's expensive and not needed for mode switch
    
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
    
    
    def load_history(self, force_reload=False):
        """Load history with caching (Sprint 1: Performance)"""
        import time
        now = time.time()
        
        # Return cache if valid (less than 5 seconds old for fast updates)
        if not force_reload and self._history_cache is not None:
            if now - self._history_cache_time < 5:
                return self._history_cache
        
        # Load from disk
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r') as f:
                    self._history_cache = json.load(f)
                    self._history_cache_time = now
                    return self._history_cache
        except Exception as e:
            print(f"History load error: {e}")
        
        self._history_cache = {}
        self._history_cache_time = now
        return self._history_cache

    def save_history(self, session_id, tokens):
        """Save history with caching and deferred writes (Sprint 1: Performance)"""
        import time
        now = time.time()
        
        # Calculate delta from last reading
        delta = tokens - self.last_tokens if self.last_tokens > 0 else 0
        self.last_tokens = tokens
        
        # Throttle based on polling interval (convert ms to seconds, minimum 2s)
        throttle_seconds = max(2, self.polling_interval / 1000)
        
        if not hasattr(self, 'last_history_save'):
            self.last_history_save = 0
            
        # Always update cache, but throttle disk writes
        data = self.load_history()
        if session_id not in data:
            data[session_id] = []
        
        # Add point with delta
        data[session_id].append({
            'ts': now,
            'tokens': tokens,
            'delta': delta
        })
        
        # Keep last 200 points per session
        if len(data[session_id]) > 200:
            data[session_id] = data[session_id][-200:]
        
        # Update cache
        self._history_cache = data
        self._history_dirty = True
        
        # Only write to disk if throttle time has passed
        if now - self.last_history_save >= throttle_seconds:
            self._flush_history_cache()
            self.last_history_save = now
    
    def _flush_history_cache(self):
        """Write cached history to disk (Sprint 1: Performance)"""
        if not self._history_dirty or self._history_cache is None:
            return
            
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, 'w') as f:
                json.dump(self._history_cache, f)
            self._history_dirty = False
        except Exception as e:
            print(f"History flush error: {e}")

    def _flush_analytics_cache(self):
        """Write cached analytics to disk immediately"""
        if self._analytics_cache is None:
            return
            
        try:
            self.analytics_file.parent.mkdir(parents=True, exist_ok=True)
            save_data = {
                'daily': self._analytics_cache.get('daily', {}),
                'projects': {k: {'total': v['total']} for k, v in self._analytics_cache.get('projects', {}).items()}
            }
            with open(self.analytics_file, 'w') as f:
                json.dump(save_data, f, indent=2)
            # Minimal logging on exit
            # print(f"[Analytics] Flushed to disk: {len(save_data.get('daily', {}))} days")
        except Exception as e:
            print(f"Analytics flush error: {e}")

    def draw_mini_graph(self):
        """Draw usage history graph in Full mode canvas"""
        if not self.current_session or not hasattr(self, 'graph_canvas'):
            return
            
        sid = self.current_session['id']
        data = self.load_history().get(sid, [])
        
        if not data:
            self.graph_canvas.create_text(280, 75, text="Not enough data yet",
                                         fill=self.colors['muted'], font=('Segoe UI', 10))
            return
        
        canvas = self.graph_canvas
        canvas.delete('all')
        
        w = 560
        h = 150
        left_pad = 40
        right_pad = 20
        top_pad = 15
        bottom_pad = 30
        
        # Draw Y-axis (percentage)
        max_tokens = self._context_window
        for pct in [0, 25, 50, 75, 100]:
            y = h - bottom_pad - (pct / 100) * (h - top_pad - bottom_pad)
            canvas.create_line(left_pad, y, w - right_pad, y,
                              fill=self.colors['bg3'], dash=(2, 4))
            canvas.create_text(left_pad - 5, y, text=f"{pct}%",
                              fill=self.colors['muted'], font=('Segoe UI', 7), anchor='e')
        
        min_ts = data[0]['ts']
        max_ts = data[-1]['ts']
        time_range = max_ts - min_ts
        if time_range == 0:
            time_range = 1
        
        # Draw X-axis time labels
        from datetime import datetime
        num_labels = min(4, len(data))
        for i in range(num_labels):
            idx = int(i * (len(data) - 1) / max(1, num_labels - 1))
            ts = data[idx]['ts']
            x = left_pad + (ts - min_ts) / time_range * (w - left_pad - right_pad)
            if time_range < 86400:
                label = datetime.fromtimestamp(ts).strftime("%H:%M")
            else:
                label = datetime.fromtimestamp(ts).strftime("%m/%d")
            canvas.create_text(x, h - bottom_pad + 12, text=label,
                              fill=self.colors['muted'], font=('Segoe UI', 7), anchor='n')
        
        # Plot data points
        points = []
        for p in data:
            x = left_pad + (p['ts'] - min_ts) / time_range * (w - left_pad - right_pad)
            pct = min(100, (p['tokens'] / max_tokens) * 100)
            y = h - bottom_pad - (pct / 100) * (h - top_pad - bottom_pad)
            points.append((x, y))
        
        # Draw filled area
        if len(points) > 1:
            fill_points = [(left_pad, h - bottom_pad)] + points + [(w - right_pad, h - bottom_pad)]
            canvas.create_polygon(fill_points, fill='#1a3a5c', outline='')
        
        # Draw line
        if len(points) > 1:
            canvas.create_line(points, fill=self.colors['blue'], width=2, smooth=True)
        
        # Draw 80% warning line
        warn_y = h - bottom_pad - 0.8 * (h - top_pad - bottom_pad)
        canvas.create_line(left_pad, warn_y, w - right_pad, warn_y,
                          fill=self.colors['red'], width=1, dash=(4, 4))
        canvas.create_text(w - right_pad - 5, warn_y - 5, text="80%",
                          fill=self.colors['red'], font=('Segoe UI', 7), anchor='e')
        
        # Current value dot
        if points:
            last_x, last_y = points[-1]
            current_pct = min(100, (data[-1]['tokens'] / max_tokens) * 100)
            color = self.colors['green']
            if current_pct >= 80:
                color = self.colors['red']
            elif current_pct >= 60:
                color = self.colors['yellow']
            canvas.create_oval(last_x-4, last_y-4, last_x+4, last_y+4,
                              fill=color, outline='white', width=2)
    
    def show_history(self):
        """Show usage history graph with time labels"""
        if not self.current_session:
            return
            
        sid = self.current_session['id']
        data = self.load_history().get(sid, [])
        
        if not data:
            messagebox.showinfo("History", "Not enough data collected yet.")
            return

        # Create window
        win = tk.Toplevel(self.root)
        win.title("Token Usage History")
        win.geometry("500x350")
        win.configure(bg=self.colors['bg'])
        win.attributes('-topmost', True)
        
        # Title
        tk.Label(win, text=f"📊 {self.get_project_name(sid)}", 
                font=('Segoe UI', 12, 'bold'),
                bg=self.colors['bg'], fg=self.colors['text']).pack(pady=(10,5))
        
        canvas = tk.Canvas(win, width=460, height=280, bg=self.colors['bg2'], highlightthickness=0)
        canvas.pack(padx=20, pady=10)
        
        def draw_graph():
            canvas.delete('all')
            current_data = self.load_history().get(sid, [])
            if not current_data:
                return
            
            w = 460
            h = 280
            left_pad = 50
            right_pad = 20
            top_pad = 20
            bottom_pad = 40
            
            # Draw Y-axis (percentage)
            max_tokens = self._context_window
            for pct in [0, 25, 50, 75, 100]:
                y = h - bottom_pad - (pct / 100) * (h - top_pad - bottom_pad)
                canvas.create_line(left_pad, y, w - right_pad, y, 
                                  fill=self.colors['bg3'], dash=(2, 4))
                canvas.create_text(left_pad - 5, y, text=f"{pct}%", 
                                  fill=self.colors['muted'], font=('Segoe UI', 8), anchor='e')
            
            min_ts = current_data[0]['ts']
            max_ts = current_data[-1]['ts']
            time_range = max_ts - min_ts
            if time_range == 0: 
                time_range = 1
            
            # Draw X-axis time labels
            from datetime import datetime
            num_labels = min(5, len(current_data))
            for i in range(num_labels):
                idx = int(i * (len(current_data) - 1) / max(1, num_labels - 1))
                ts = current_data[idx]['ts']
                x = left_pad + (ts - min_ts) / time_range * (w - left_pad - right_pad)
                if time_range < 3600:
                    label = datetime.fromtimestamp(ts).strftime("%H:%M")
                elif time_range < 86400:
                    label = datetime.fromtimestamp(ts).strftime("%H:%M")
                else:
                    label = datetime.fromtimestamp(ts).strftime("%m/%d %H:%M")
                canvas.create_text(x, h - bottom_pad + 15, text=label,
                                  fill=self.colors['muted'], font=('Segoe UI', 7), anchor='n')
            
            # Plot data points
            points = []
            for p in current_data:
                x = left_pad + (p['ts'] - min_ts) / time_range * (w - left_pad - right_pad)
                pct = min(100, (p['tokens'] / max_tokens) * 100)
                y = h - bottom_pad - (pct / 100) * (h - top_pad - bottom_pad)
                points.append((x, y))
            
            # Draw filled area
            if len(points) > 1:
                fill_points = [(left_pad, h - bottom_pad)] + points + [(w - right_pad, h - bottom_pad)]
                canvas.create_polygon(fill_points, fill='#1a3a5c', outline='')
            
            # Draw line
            if len(points) > 1:
                canvas.create_line(points, fill=self.colors['blue'], width=2, smooth=True)
            
            # Draw 80% warning line
            warn_y = h - bottom_pad - 0.8 * (h - top_pad - bottom_pad)
            canvas.create_line(left_pad, warn_y, w - right_pad, warn_y, 
                              fill=self.colors['red'], width=2, dash=(4, 4))
            canvas.create_text(w - right_pad - 5, warn_y - 8, text="80%", 
                              fill=self.colors['red'], font=('Segoe UI', 8), anchor='e')
            
            # Current value
            if points:
                last_x, last_y = points[-1]
                current_pct = min(100, (current_data[-1]['tokens'] / max_tokens) * 100)
                color = self.colors['green']
                if current_pct >= 80:
                    color = self.colors['red']
                elif current_pct >= 60:
                    color = self.colors['yellow']
                canvas.create_oval(last_x-5, last_y-5, last_x+5, last_y+5, 
                                  fill=color, outline='white', width=2)
        
        draw_graph()
        
        # Auto-refresh
        refresh_id = None
        def auto_refresh():
            nonlocal refresh_id
            if win.winfo_exists():
                draw_graph()
                refresh_id = win.after(5000, auto_refresh)
        
        def on_close():
            nonlocal refresh_id
            if refresh_id:
                win.after_cancel(refresh_id)
            win.destroy()
        
        win.protocol("WM_DELETE_WINDOW", on_close)
        refresh_id = win.after(5000, auto_refresh)
        
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
        menu.add_command(label="  📅  Usage History Graph", command=self.show_history)
        menu.add_command(label="  📊  Analytics Dashboard (D)", command=self.show_analytics_dashboard)
        menu.add_command(label="  💾  Export to CSV (E)", command=self.export_history_csv)
        menu.add_separator()
        
        # Actions section
        menu.add_command(label="  🧹  Clean Old Conversations", command=self.cleanup_old_conversations)
        menu.add_command(label="  📦  Archive Old Sessions", command=self.archive_old_sessions)
        menu.add_command(label="  🔄  Restart Antigravity", command=self.restart_antigravity)
        menu.add_separator()
        
        # Sessions submenu
        sessions_menu = tk.Menu(menu, tearoff=0,
                              bg=self.colors['bg2'],
                              fg=self.colors['text'],
                              activebackground=self.colors['blue'],
                              activeforeground='white')
        
        current_id = self.current_session['id'] if self.current_session else None
    
        # PERFORMANCE: Use lightweight session list (no protobuf parsing)
        # Only parse protobuf for the current session, not all sessions in menu
        from functools import partial
        from collections import OrderedDict
        
        # Get lightweight session list (file stats only, no token extraction)
        sessions = []
        try:
            if self.conversations_dir.exists():
                import os
                with os.scandir(self.conversations_dir) as entries:
                    for entry in entries:
                        if not entry.is_file() or '.tmp' in entry.name:
                            continue
                        if entry.name.endswith('.pb') or entry.name.endswith('.pb.gz'):
                            stat = entry.stat()
                            session_id = entry.name[:-3] if entry.name.endswith('.pb') else entry.name[:-6]
                            sessions.append({
                                'id': session_id,
                                'modified': stat.st_mtime
                            })
                sessions.sort(key=lambda x: x['modified'], reverse=True)
                sessions = sessions[:15]  # Top 15 most recent
        except Exception:
            sessions = []
        
        
        # Group sessions by project name
        projects = OrderedDict()
        for s in sessions:
            # PERFORMANCE: Only use cached names in menu (no expensive detection)
            if s['id'] in self.project_name_cache:
                project_name = self.project_name_cache[s['id']]
            else:
                # Fallback to session ID for uncached sessions (fast)
                project_name = s['id'][:16] + "..."
            
            if project_name not in projects:
                projects[project_name] = []
            projects[project_name].append(s)
        
        # Show sessions grouped by project
        shown = 0
        for project_name, proj_sessions in projects.items():
            if shown >= 10:
                break
            
            # Add project header
            sessions_menu.add_command(label=f"── {project_name} ──", state='disabled')
            
            # Add sessions under this project
            for s in proj_sessions[:3]:  # Max 3 per project
                if shown >= 10:
                    break
                check = "✓ " if s['id'] == current_id else "  "
                short_id = s['id'][:8]
                label = f"{check}{project_name} ({short_id}...)"
                sessions_menu.add_command(label=label, 
                                        command=lambda sid=s['id']: self.switch_session(sid))
                shown += 1
            
            # Separator between projects
            if shown < 10 and project_name != list(projects.keys())[-1]:
                sessions_menu.add_separator()
            
        menu.add_cascade(label="  🔀  Switch Session", menu=sessions_menu)
        menu.add_separator()
        
        # Mode toggle
        if self.mini_mode:
            menu.add_command(label="  ◳  Expand to Full Mode", command=self.toggle_mini_mode)
        else:
            menu.add_command(label="  ◱  Collapse to Mini Mode", command=self.toggle_mini_mode)
        
        menu.add_separator()
        
        # Polling speed submenu
        speed_menu = tk.Menu(menu, tearoff=0,
                            bg=self.colors['bg2'],
                            fg=self.colors['text'],
                            activebackground=self.colors['blue'],
                            activeforeground='white')
        
        speeds = [
            ("  ⚡  3 seconds (fast)", 3000),
            ("  🔄  5 seconds", 5000),
            ("  ⏱️  10 seconds (default)", 10000),
            ("  🐢  30 seconds (slow)", 30000),
        ]
        
        for label, interval in speeds:
            check = "✓ " if self.polling_interval == interval else "  "
            from functools import partial
            speed_menu.add_command(
                label=f"{check}{label}",
                command=partial(self.set_polling_speed, interval)
            )
        
        menu.add_cascade(label="  ⏱️  Refresh Speed", menu=speed_menu)
        
        menu.add_separator()
        menu.add_command(label="  🔄  Reload UI (Dev)", command=self.reload_ui)
        menu.add_separator()
        menu.add_command(label="  ✕  Exit", command=self.cleanup_and_exit)
        
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
            cmd = "tasklist /FI \"IMAGENAME eq Antigravity.exe\" /FO CSV /NH"
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
        """Show diagnostics popup with styled visual design"""
        procs = self.get_antigravity_processes()
        files = self.get_large_conversations()
        limits = self.thresholds
        
        # Calculate totals
        total_mem = sum(p.get('Mem', 0) for p in procs)
        total_file_size = sum(f['size_mb'] for f in files)
        high_mem_types = [p.get('Type', 'Unknown') for p in procs if p.get('Mem', 0) > limits['proc_warn']]
        
        # Create styled window
        win = tk.Toplevel(self.root)
        win.title("📊 System Diagnostics")
        win.geometry("450x950")
        win.configure(bg=self.colors['bg'])
        win.attributes('-topmost', True)
        win.resizable(True, True)
        
        # Header
        header = tk.Frame(win, bg=self.colors['bg3'], height=50)
        header.pack(fill='x')
        header.pack_propagate(False)
        
        tk.Label(header, text="🔧 System Diagnostics", 
                font=('Segoe UI', 14, 'bold'),
                bg=self.colors['bg3'], fg=self.colors['text']).pack(pady=12)
        
        # Main content with scrollbar
        content = tk.Frame(win, bg=self.colors['bg'], padx=20, pady=15)
        content.pack(fill='both', expand=True)
        
        def create_bar(parent, label, value, max_val, color):
            """Create a visual progress bar"""
            frame = tk.Frame(parent, bg=self.colors['bg'])
            frame.pack(fill='x', pady=4)
            
            label_frame = tk.Frame(frame, bg=self.colors['bg'])
            label_frame.pack(fill='x')
            
            tk.Label(label_frame, text=label, font=('Segoe UI', 9),
                    bg=self.colors['bg'], fg=self.colors['text']).pack(side='left')
            tk.Label(label_frame, text=f"{value}MB", font=('Segoe UI', 9, 'bold'),
                    bg=self.colors['bg'], fg=color).pack(side='right')
            
            bar_canvas = tk.Canvas(frame, width=400, height=12, 
                                   bg=self.colors['bg3'], highlightthickness=0)
            bar_canvas.pack(fill='x', pady=(2, 0))
            
            pct = min(100, (value / max_val) * 100) if max_val > 0 else 0
            bar_width = int((pct / 100) * 396)
            if bar_width > 0:
                bar_canvas.create_rectangle(2, 2, bar_width + 2, 10, fill=color, outline='')
        
        # Section: System Overview
        tk.Label(content, text="SYSTEM OVERVIEW", font=('Segoe UI', 9),
                bg=self.colors['bg'], fg=self.colors['muted']).pack(anchor='w', pady=(0, 8))
        
        info_frame = tk.Frame(content, bg=self.colors['bg2'], padx=12, pady=10)
        info_frame.pack(fill='x')
        
        tk.Label(info_frame, text=f"💾 RAM Detected: {self.total_ram_mb // 1024} GB", 
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['text']).pack(anchor='w')
        tk.Label(info_frame, text=f"⚙️ Processes: {len(procs)}", 
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['text']).pack(anchor='w')
        
        # Total memory status
        if total_mem > limits['total_crit']:
            status_color = self.colors['red']
            status_text = "🔴 CRITICAL"
        elif total_mem > limits['total_warn']:
            status_color = self.colors['yellow']
            status_text = "🟡 HIGH"
        else:
            status_color = self.colors['green']
            status_text = "🟢 HEALTHY"
        
        tk.Label(info_frame, text=f"📊 Total Memory: {total_mem}MB  {status_text}", 
                font=('Segoe UI', 10, 'bold'), bg=self.colors['bg2'], fg=status_color).pack(anchor='w', pady=(5,0))
        
        # Separator
        tk.Frame(content, bg=self.colors['bg3'], height=1).pack(fill='x', pady=12)
        
        # Section: Process Memory
        tk.Label(content, text="PROCESS MEMORY", font=('Segoe UI', 9),
                bg=self.colors['bg'], fg=self.colors['muted']).pack(anchor='w', pady=(0, 8))
        
        max_mem = max((p.get('Mem', 0) for p in procs), default=500)
        for p in procs[:6]:  # Show top 6
            mem = p.get('Mem', 0)
            ptype = p.get('Type', 'Unknown')
            if mem > limits['proc_crit']:
                color = self.colors['red']
            elif mem > limits['proc_warn']:
                color = self.colors['yellow']
            else:
                color = self.colors['green']
            create_bar(content, ptype, mem, max_mem * 1.2, color)
        
        # Separator
        tk.Frame(content, bg=self.colors['bg3'], height=1).pack(fill='x', pady=12)
        
        # Section: Large Files
        tk.Label(content, text=f"LARGE CONVERSATION FILES ({len(files)} files, {total_file_size:.1f}MB total)", 
                font=('Segoe UI', 9), bg=self.colors['bg'], fg=self.colors['muted']).pack(anchor='w', pady=(0, 8))
        
        if files:
            for f in files[:4]:  # Show top 4
                size = f['size_mb']
                if size > 15:
                    color = self.colors['red']
                elif size > 8:
                    color = self.colors['yellow']
                else:
                    color = self.colors['green']
                create_bar(content, f['name'][:20] + "...", size, 20, color)
        else:
            tk.Label(content, text="✅ No large files found", font=('Segoe UI', 10),
                    bg=self.colors['bg'], fg=self.colors['green']).pack(anchor='w')
        
        # Separator
        tk.Frame(content, bg=self.colors['bg3'], height=1).pack(fill='x', pady=12)
        
        # Section: Recommendations
        tk.Label(content, text="RECOMMENDATIONS", font=('Segoe UI', 9),
                bg=self.colors['bg'], fg=self.colors['muted']).pack(anchor='w', pady=(0, 8))
        
        rec_frame = tk.Frame(content, bg=self.colors['bg2'], padx=12, pady=10)
        rec_frame.pack(fill='x')
        
        recommendations = []
        if 'Extension Host' in high_mem_types:
            recommendations.append("⚠️ Disable unused extensions")
        if 'Renderer/GPU' in high_mem_types:
            recommendations.append("⚠️ Close unused tabs/editors")
        if total_file_size > 50:
            recommendations.append("⚠️ Run 'Clean Old Conversations'")
        if total_mem > limits['total_crit']:
            recommendations.append("🔴 RESTART ANTIGRAVITY NOW")
        elif total_mem > limits['total_warn']:
            recommendations.append("🟡 Consider restarting soon")
        
        if not recommendations:
            recommendations.append("✅ System looks healthy!")
        
        for rec in recommendations:
            color = self.colors['red'] if '🔴' in rec else self.colors['yellow'] if '⚠️' in rec or '🟡' in rec else self.colors['green']
            tk.Label(rec_frame, text=rec, font=('Segoe UI', 10),
                    bg=self.colors['bg2'], fg=color).pack(anchor='w', pady=2)
    
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
    
    def archive_old_sessions(self):
        """Compress old session files using gzip to save disk space"""
        import gzip
        import shutil
        from datetime import datetime, timedelta
        
        # Find sessions older than 3 days that aren't already compressed
        cutoff = datetime.now().timestamp() - (3 * 24 * 60 * 60)  # 3 days ago
        current_id = self.current_session['id'] if self.current_session else None
        
        to_compress = []
        total_size = 0
        
        for f in self.conversations_dir.glob('*.pb'):
            if '.tmp' in f.name:
                continue
            if current_id and current_id in f.stem:
                continue  # Skip current session
            
            stat = f.stat()
            if stat.st_mtime < cutoff and stat.st_size > 100000:  # Older than 3 days, > 100KB
                to_compress.append({
                    'path': f,
                    'size_mb': round(stat.st_size / 1024 / 1024, 2),
                    'age_days': int((datetime.now().timestamp() - stat.st_mtime) / 86400)
                })
                total_size += stat.st_size
        
        if not to_compress:
            messagebox.showinfo("Archive", "No old sessions to compress!\n(Sessions must be >3 days old)")
            return
        
        msg = f"Found {len(to_compress)} old sessions ({total_size/1024/1024:.1f} MB total):\n\n"
        for f in to_compress[:5]:
            msg += f"• {f['path'].stem[:16]}... ({f['size_mb']}MB, {f['age_days']}d old)\n"
        if len(to_compress) > 5:
            msg += f"... and {len(to_compress) - 5} more\n"
        msg += f"\nCompress these to save ~70% disk space?"
        
        if messagebox.askyesno("Archive Old Sessions", msg):
            compressed = 0
            saved_bytes = 0
            
            for f in to_compress:
                try:
                    orig_path = f['path']
                    gz_path = orig_path.with_suffix('.pb.gz')
                    
                    # Compress the file
                    with open(orig_path, 'rb') as f_in:
                        with gzip.open(gz_path, 'wb', compresslevel=6) as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    
                    # Calculate savings
                    orig_size = orig_path.stat().st_size
                    new_size = gz_path.stat().st_size
                    saved_bytes += orig_size - new_size
                    
                    # Delete original
                    orig_path.unlink()
                    compressed += 1
                    
                except Exception as e:
                    print(f"Error compressing {f['path']}: {e}")
            
            saved_mb = saved_bytes / 1024 / 1024
            messagebox.showinfo("Archive Complete", 
                              f"Compressed {compressed} sessions\nSaved {saved_mb:.1f} MB of disk space!")
    
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
        """Show detailed token usage breakdown with visual bars"""
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
            context_window = self._context_window
            tokens_used = self.current_session['estimated_tokens'] // 10
            tokens_left = max(0, context_window - tokens_used)
            percent_used = min(100, round((tokens_used / context_window) * 100))
            
            # Estimate breakdown
            estimated_input = int(tokens_used * 0.4)
            estimated_output = int(tokens_used * 0.6)
            
            # Create window
            win = tk.Toplevel(self.root)
            win.title("📊 Advanced Token Statistics")
            win.geometry("420x700")
            win.configure(bg=self.colors['bg'])
            win.attributes('-topmost', True)
            win.resizable(True, True)
            
            # Header
            header = tk.Frame(win, bg=self.colors['bg3'], height=50)
            header.pack(fill='x')
            header.pack_propagate(False)
            
            tk.Label(header, text="📊 Token Usage Dashboard", 
                    font=('Segoe UI', 14, 'bold'),
                    bg=self.colors['bg3'], fg=self.colors['text']).pack(pady=12)
            
            # Main content
            content = tk.Frame(win, bg=self.colors['bg'], padx=20, pady=15)
            content.pack(fill='both', expand=True)
            
            def create_bar(parent, label, value, max_val, color, show_percent=True):
                """Create a visual progress bar with label"""
                frame = tk.Frame(parent, bg=self.colors['bg'])
                frame.pack(fill='x', pady=8)
                
                # Label row
                label_frame = tk.Frame(frame, bg=self.colors['bg'])
                label_frame.pack(fill='x')
                
                tk.Label(label_frame, text=label, font=('Segoe UI', 10),
                        bg=self.colors['bg'], fg=self.colors['text']).pack(side='left')
                
                if show_percent:
                    pct = min(100, round((value / max_val) * 100)) if max_val > 0 else 0
                    tk.Label(label_frame, text=f"{value:,} ({pct}%)", 
                            font=('Segoe UI', 10, 'bold'),
                            bg=self.colors['bg'], fg=color).pack(side='right')
                else:
                    tk.Label(label_frame, text=f"{value:,}", 
                            font=('Segoe UI', 10, 'bold'),
                            bg=self.colors['bg'], fg=color).pack(side='right')
                
                # Bar
                bar_canvas = tk.Canvas(frame, width=380, height=20, 
                                       bg=self.colors['bg3'], highlightthickness=0)
                bar_canvas.pack(fill='x', pady=(4, 0))
                
                # Calculate bar width
                pct = min(100, (value / max_val) * 100) if max_val > 0 else 0
                bar_width = int((pct / 100) * 376)
                
                # Draw bar
                if bar_width > 0:
                    bar_canvas.create_rectangle(2, 2, bar_width + 2, 18, 
                                               fill=color, outline='')
                
                return frame
            
            # Section: Context Window Usage
            tk.Label(content, text="CONTEXT WINDOW", font=('Segoe UI', 9),
                    bg=self.colors['bg'], fg=self.colors['muted']).pack(anchor='w', pady=(0, 5))
            
            # Choose color based on usage
            if percent_used >= 80:
                usage_color = self.colors['red']
            elif percent_used >= 60:
                usage_color = self.colors['yellow']
            else:
                usage_color = self.colors['green']
            
            create_bar(content, "Tokens Used", tokens_used, context_window, usage_color)
            create_bar(content, "Tokens Remaining", tokens_left, context_window, self.colors['blue'])
            
            # Separator
            tk.Frame(content, bg=self.colors['bg3'], height=1).pack(fill='x', pady=15)
            
            # Section: Estimated Breakdown
            tk.Label(content, text="ESTIMATED BREAKDOWN", font=('Segoe UI', 9),
                    bg=self.colors['bg'], fg=self.colors['muted']).pack(anchor='w', pady=(0, 5))
            
            create_bar(content, "Input (Your messages)", estimated_input, tokens_used, self.colors['blue'])
            create_bar(content, "Output (Assistant)", estimated_output, tokens_used, self.colors['green'])
            
            # Separator
            tk.Frame(content, bg=self.colors['bg3'], height=1).pack(fill='x', pady=15)
            
            # Section: Session Info
            tk.Label(content, text="SESSION INFO", font=('Segoe UI', 9),
                    bg=self.colors['bg'], fg=self.colors['muted']).pack(anchor='w', pady=(0, 5))
            
            info_frame = tk.Frame(content, bg=self.colors['bg2'], padx=10, pady=10)
            info_frame.pack(fill='x')
            
            project_name = self.get_project_name(self.current_session['id'])
            
            info_items = [
                ("Project", project_name),
                ("File Size", f"{file_size / (1024*1024):.2f} MB"),
                ("Session ID", f"{self.current_session['id'][:16]}..."),
            ]
            
            for label, value in info_items:
                row = tk.Frame(info_frame, bg=self.colors['bg2'])
                row.pack(fill='x', pady=2)
                tk.Label(row, text=label, font=('Segoe UI', 9),
                        bg=self.colors['bg2'], fg=self.colors['muted']).pack(side='left')
                tk.Label(row, text=value, font=('Segoe UI', 9),
                        bg=self.colors['bg2'], fg=self.colors['text']).pack(side='right')
            
            # Status/Recommendation at bottom
            status_frame = tk.Frame(win, bg=self.colors['bg3'], height=50)
            status_frame.pack(fill='x', side='bottom')
            status_frame.pack_propagate(False)
            
            if percent_used >= 80:
                status_text = "🔴 CRITICAL: Start a new session soon!"
                status_color = self.colors['red']
            elif percent_used >= 60:
                status_text = "⚠️ WARNING: Approaching context limit"
                status_color = self.colors['yellow']
            else:
                status_text = "✅ Context usage is healthy"
                status_color = self.colors['green']
            
            tk.Label(status_frame, text=status_text, font=('Segoe UI', 10, 'bold'),
                    bg=self.colors['bg3'], fg=status_color).pack(pady=14)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate stats: {e}")
    # ==================== SYSTEM TRAY ====================

    def create_tray_icon(self, color):
        """Create a circle icon for the tray"""
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), (0, 0, 0))
        dc = ImageDraw.Draw(image)
        dc.ellipse((0, 0, width, height), fill=color)
        return image

    def setup_tray(self):
        """Initialize system tray icon"""
        if not HAS_TRAY:
            return

        def on_open(icon, item):
            self.root.after(0, self.restore_from_tray)

        def on_exit(icon, item):
            self.root.after(0, self.cleanup_and_exit)

        menu = pystray.Menu(
            pystray.MenuItem('Show Context Monitor', on_open, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('Exit', on_exit)
        )

        self.tray_icon = pystray.Icon(
            "ContextMonitor",
            self.create_tray_icon(self.colors['green']),
            "Context Monitor",
            menu
        )

    def run_tray(self):
        """Run tray icon in background thread"""
        if self.tray_icon:
            self.tray_icon.run()

    def update_tray_icon(self):
        """Update tray icon color based on usage"""
        if not self.tray_icon:
            return
            
        color = self.colors['green']
        if self.current_percent >= 80:
            color = self.colors['red']
        elif self.current_percent >= 60:
            color = self.colors['yellow']
            
        # We need to create a new icon image
        self.tray_icon.icon = self.create_tray_icon(color)
        self.tray_icon.title = f"Context Monitor: {self.current_percent}%"

    def minimize_to_tray(self):
        """Hide window and show notification if first time"""
        self.root.withdraw()
        
    def restore_from_tray(self):
        """Show window"""
        self.root.deiconify()
        self.root.lift()

    # ==================== CLEANUP & RUN ====================

    def _cleanup_processes(self):
        """Clean up any related processes on exit"""
        try:
            # Get current process ID to avoid killing ourselves prematurely
            current_pid = os.getpid()
            
            # Find and terminate any orphaned pythonw processes running context_monitor
            cmd = 'tasklist /FI "IMAGENAME eq pythonw.exe" /FO CSV /NH'
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=5)
            
            if result.stdout:
                for line in result.stdout.splitlines():
                    if 'pythonw' in line.lower():
                        parts = line.replace('"', '').split(',')
                        if len(parts) >= 2:
                            try:
                                pid = int(parts[1])
                                if pid != current_pid:
                                    subprocess.run(['taskkill', '/F', '/PID', str(pid)], 
                                                 capture_output=True, timeout=3)
                            except (ValueError, subprocess.TimeoutExpired):
                                pass
        except Exception as e:
            print(f"Cleanup error (non-fatal): {e}")
    

    # ==================== ANALYTICS SYSTEM ====================
    
    def load_analytics(self):
        """Load persistent analytics data"""
        try:
            if self.analytics_file.exists():
                with open(self.analytics_file, 'r') as f:
                    self._analytics_cache = json.load(f)
                    return self._analytics_cache
        except Exception as e:
            print(f"Analytics load error: {e}")
        self._analytics_cache = {'daily': {}, 'projects': {}}
        return self._analytics_cache
    
    def save_analytics(self, tokens, project_name):
        """Track daily and project-level token usage (with disk throttling)"""
        import time
        now = time.time()
        
        # Throttle disk writes to max once per 30 seconds
        if not hasattr(self, '_last_analytics_save'):
            self._last_analytics_save = 0
        
        analytics = self.load_analytics()
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Daily tracking
        if today not in analytics['daily']:
            analytics['daily'][today] = {'total': 0, 'sessions': 0}
        
        # Only increment if tokens increased (not session switch)
        delta = tokens - self.last_tokens if self.last_tokens > 0 else 0
        if delta > 0:
            analytics['daily'][today]['total'] += delta
            
            # Project-level tracking
            if project_name not in analytics['projects']:
                analytics['projects'][project_name] = {'total': 0, 'sessions': []}
            analytics['projects'][project_name]['total'] += delta

            # Model-level tracking
            current_model = self.settings.get('model', 'Unknown')
            if 'models' not in analytics:
                analytics['models'] = {}
            if current_model not in analytics['models']:
                analytics['models'][current_model] = {'total': 0}
            analytics['models'][current_model]['total'] += delta
        
        self._analytics_cache = analytics
        
        # Only save to disk if 30 seconds have passed
        if now - self._last_analytics_save >= 30:
            try:
                self.analytics_file.parent.mkdir(parents=True, exist_ok=True)
                save_data = {
                    'daily': analytics['daily'],
                    'projects': {k: {'total': v['total']} for k, v in analytics['projects'].items()},
                    'models': analytics.get('models', {})
                }
                with open(self.analytics_file, 'w') as f:
                    json.dump(save_data, f, indent=2)
                self._last_analytics_save = now
            except Exception as e:
                print(f"Analytics save error: {e}")
        
        # Check budget notification (already throttled internally)
        self.check_budget_notification(analytics, today)
    
    def check_budget_notification(self, analytics, today):
        """Send desktop notification if approaching daily budget"""
        if not HAS_TOAST or not self._notifier:
            return
            
        daily_usage = analytics['daily'].get(today, {}).get('total', 0)
        budget = self._daily_budget
        
    def check_budget_notification(self, analytics, today):
        """Send desktop notification if approaching daily budget"""
        daily_usage = analytics['daily'].get(today, {}).get('total', 0)
        budget = self._daily_budget
        
        # Throttle notifications (max once per 5 minutes)
        now = time.time()
        if now - self._last_notification_time < 300:
            return
        
        if daily_usage >= budget * 0.9:
            print(f"ALERTS: Daily budget 90% used! ({daily_usage:,} / {budget:,} tokens)")
            self._last_notification_time = now
        elif daily_usage >= budget * 0.75:
            print(f"ALERTS: Daily budget 75% used ({daily_usage:,} / {budget:,} tokens)")
            self._last_notification_time = now
    
    def check_context_alerts(self, percent, tokens_used):
        """Check for context window usage alerts (handoff warnings)"""
        now = time.time()
        
        # Only alert max once per 5 minutes to avoid spamming
        if hasattr(self, '_last_context_alert_time') and now - self._last_context_alert_time < 300:
            return
            
        context_window = self._context_window
        
        if percent >= 80:
            # Force show widget so user sees the red status and copied handoff
            self.restore_from_tray()
            
            if percent >= 90:
                print(f"ALERTS: Context window 90% full! ({tokens_used:,} / {context_window:,} tokens)")
            else:
                print(f"ALERTS: Context window 80% full ({tokens_used:,} / {context_window:,} tokens)")
                
            self._last_context_alert_time = now

    def calculate_time_to_handoff(self):
        """Estimate time until context limit based on recent token burn rate"""
        if not self.current_session:
            return None
            
        # Get recent history for rate calculation
        history = self.load_history().get(self.current_session['id'], [])
        if len(history) < 3:
            return None
        
        # Use last 10 minutes (approx 60 samples at 10s interval) for smoother rate
        recent = history[-60:]
        if len(recent) < 2:
            return None
        
        # Calculate tokens per second
        time_span = recent[-1]['ts'] - recent[0]['ts']
        token_span = recent[-1]['tokens'] - recent[0]['tokens']
        
        if time_span <= 0 or token_span <= 0:
            return None
        
        rate_per_second = token_span / time_span
        
        # Calculate remaining tokens until 80% (handoff point)
        context_window = self._context_window
        current_tokens = recent[-1]['tokens']
        handoff_threshold = context_window * 0.8
        remaining = handoff_threshold - current_tokens
        
        if remaining <= 0:
            return 0  # Already at/past handoff
        
        if rate_per_second <= 0:
            return None  # No burn rate
        
        seconds_remaining = remaining / rate_per_second
        return int(seconds_remaining)
    
    def format_time_remaining(self, seconds):
        """Format seconds into human-readable time"""
        if seconds is None:
            return "—"
        if seconds <= 0:
            return "Now!"
        if seconds < 60:
            return f"{seconds}s"
        if seconds < 3600:
            mins = seconds // 60
            return f"{mins}m"
        hours = seconds // 3600
        mins = (seconds % 3600) // 60
        return f"{hours}h {mins}m"
    
    def get_weekly_summary(self):
        """Get token usage for the past 7 days"""
        analytics = self.load_analytics()
        today = datetime.now()
        
        weekly = []
        for i in range(7):
            day = (today - timedelta(days=i)).strftime('%Y-%m-%d')
            daily_data = analytics['daily'].get(day, {'total': 0})
            weekly.append({
                'date': day,
                'tokens': daily_data.get('total', 0),
                'day_name': (today - timedelta(days=i)).strftime('%a')
            })
        
        return weekly
    
    def get_project_summary(self):
        """Get token usage by project"""
        analytics = self.load_analytics()
        projects = []
        for name, data in analytics.get('projects', {}).items():
            projects.append({
                'name': name,
                'tokens': data.get('total', 0)
            })
        # Sort by usage
        projects.sort(key=lambda x: x['tokens'], reverse=True)
        return projects[:10]  # Top 10
    
    def show_analytics_dashboard(self):
        """Show comprehensive analytics dashboard with auto-refresh and flicker-free updates"""
        # Create window
        win = tk.Toplevel(self.root)
        win.title("Analytics Dashboard")
        win.geometry("650x800") # Safer height, use scrollbar
        win.configure(bg=self.colors['bg'])
        win.attributes('-topmost', True)
        win.resizable(True, True)
        
        # Title
        tk.Label(win, text="📊 Token Analytics Dashboard",
                font=('Segoe UI', 14, 'bold'),
                bg=self.colors['bg'], fg=self.colors['text']).pack(pady=(15, 10))
        
        # Main container with ACTUAL scrollbar
        container = tk.Frame(win, bg=self.colors['bg'])
        container.pack(fill='both', expand=True, padx=20, pady=10)

        canvas = tk.Canvas(container, bg=self.colors['bg'], highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        
        main_frame = tk.Frame(canvas, bg=self.colors['bg'])
        
        # Configure scrolling
        main_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas_frame = canvas.create_window((0, 0), window=main_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack scrollbar and canvas
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        # Ensure frame width matches canvas
        def on_canvas_configure(event):
            canvas.itemconfig(canvas_frame, width=event.width)
        canvas.bind("<Configure>", on_canvas_configure)

        # Allow mousewheel scrolling
        def _on_mousewheel(event):
            if canvas.winfo_exists():
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        # Bind mousewheel to canvas and all children
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        win.protocol("WM_DELETE_WINDOW", lambda: (canvas.unbind_all("<MouseWheel>"), win.destroy()))
        
        # ===== DYNAMIC CONTENT LABELS =====
        self._dashboard_refs = {}
        
        # 0. SESSION TREND GRAPH (Sparkline)
        trend_frame = tk.Frame(main_frame, bg=self.colors['bg2'], padx=15, pady=10)
        trend_frame.pack(fill='x', pady=(0, 10))
        tk.Label(trend_frame, text="📈 Session Trend (Last Hour)",
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['text2']).pack(anchor='w')
        
        self._dashboard_refs['trend_canvas'] = tk.Canvas(trend_frame, height=60, bg=self.colors['bg3'], highlightthickness=0)
        self._dashboard_refs['trend_canvas'].pack(fill='x', pady=(5,0))
        
        # 1. TIME TO HANDOFF
        ttf_frame = tk.Frame(main_frame, bg=self.colors['bg2'], padx=15, pady=10)
        ttf_frame.pack(fill='x', pady=(0, 10))
        
        tk.Label(ttf_frame, text="⏱️ Estimated Time to Handoff:",
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['text2']).pack(side='left')
        
        self._dashboard_refs['ttf_label'] = tk.Label(ttf_frame, text="—",
                font=('Segoe UI', 16, 'bold'), bg=self.colors['bg2'], fg=self.colors['text'])
        self._dashboard_refs['ttf_label'].pack(side='right')

        # 2. TODAY'S USAGE
        today_frame = tk.Frame(main_frame, bg=self.colors['bg2'], padx=15, pady=10)
        today_frame.pack(fill='x', pady=(0, 10))
        
        tk.Label(today_frame, text="📅 Today's Usage:",
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['text2']).pack(anchor='w')
        
        # Progress bar container
        bar_frame = tk.Frame(today_frame, bg=self.colors['bg3'], height=20)
        bar_frame.pack(fill='x', pady=5)
        
        # Dynamic fill bar
        self._dashboard_refs['bar_fill'] = tk.Frame(bar_frame, bg=self.colors['green'], height=20)
        self._dashboard_refs['bar_fill'].place(relwidth=0, relheight=1)
        
        # Usage Text
        self._dashboard_refs['usage_label'] = tk.Label(today_frame, text="Calculating...",
                font=('Segoe UI', 9), bg=self.colors['bg2'], fg=self.colors['text'])
        self._dashboard_refs['usage_label'].pack(anchor='w')
        
        # Reset Countdown
        self._dashboard_refs['reset_label'] = tk.Label(today_frame, text="",
                font=('Segoe UI', 8, 'italic'), bg=self.colors['bg2'], fg=self.colors['muted'])
        self._dashboard_refs['reset_label'].pack(anchor='w', pady=(2,0))

        # 3. WEEKLY CHART (Fixed Slots)
        week_container = tk.Frame(main_frame, bg=self.colors['bg2'])
        week_container.pack(fill='x', pady=(0, 10))
        
        week_frame_inner = tk.LabelFrame(week_container, text=" 📈 Last 7 Days ", 
                                   bg=self.colors['bg2'], fg=self.colors['text'],
                                   font=('Segoe UI', 10, 'bold'), padx=10, pady=10)
        week_frame_inner.pack(fill='x')
        
        chart_frame = tk.Frame(week_frame_inner, bg=self.colors['bg2'])
        chart_frame.pack(fill='x', expand=True)
        
        self._dashboard_refs['week_slots'] = []
        for i in range(7):
            col = tk.Frame(chart_frame, bg=self.colors['bg2'])
            col.pack(side='left', expand=True, fill='both', padx=2)
            
            # Bar (uses place for dynamic height)
            bar_container = tk.Frame(col, bg=self.colors['bg2'], height=60, width=30)
            bar_container.pack(side='bottom')
            bar = tk.Frame(bar_container, bg=self.colors['blue'])
            bar.place(relx=0, rely=1.0, relwidth=1.0, relheight=0.0, anchor='sw')
            
            lbl_day = tk.Label(col, text="-", font=('Segoe UI', 8), bg=self.colors['bg2'], fg=self.colors['muted'])
            lbl_day.pack(side='bottom')
            
            lbl_val = tk.Label(col, text="0", font=('Consolas', 7), bg=self.colors['bg2'], fg=self.colors['text2'])
            lbl_val.pack(side='bottom')
            
            self._dashboard_refs['week_slots'].append({
                'bar': bar, 'day': lbl_day, 'val': lbl_val
            })

        # 4. PROJECT LIST (Fixed Slots)
        proj_container = tk.Frame(main_frame, bg=self.colors['bg2'])
        proj_container.pack(fill='both', expand=True, pady=(0, 10))
        
        proj_frame = tk.LabelFrame(proj_container, text=" 🗂️ Token Usage by Project ",
                               bg=self.colors['bg2'], fg=self.colors['text'],
                               font=('Segoe UI', 10, 'bold'), padx=10, pady=10)
        proj_frame.pack(fill='both', expand=True)

        self._dashboard_refs['proj_slots'] = []
        for i in range(5): # Top 5 projects
            row = tk.Frame(proj_frame, bg=self.colors['bg2'])
            row.pack(fill='x', pady=2)
            lbl_name = tk.Label(row, text="", font=('Segoe UI', 9),
                    bg=self.colors['bg2'], fg=self.colors['text'], width=25, anchor='w')
            lbl_name.pack(side='left')
            lbl_val = tk.Label(row, text="", font=('Consolas', 9), bg=self.colors['bg2'], fg=self.colors['blue'])
            lbl_val.pack(side='right')
            self._dashboard_refs['proj_slots'].append({'row': row, 'name': lbl_name, 'val': lbl_val})
            
        # 5. PROJECT DISTRIBUTION (Stacked Bar)
        dist_frame = tk.Frame(main_frame, bg=self.colors['bg2'], padx=15, pady=10)
        dist_frame.pack(fill='x')
        tk.Label(dist_frame, text="📊 Project Distribution", font=('Segoe UI', 9),
                bg=self.colors['bg2'], fg=self.colors['muted']).pack(anchor='w', pady=(0,5))
        
        self._dashboard_refs['dist_bar'] = tk.Frame(dist_frame, bg=self.colors['bg3'], height=15)
        self._dashboard_refs['dist_bar'].pack(fill='x')
        # We will create sub-frames inside this bar dynamically (or use fixed slots if preferred, but dynamic is okay here as it's just a few rects)
        
        # ===== SYSTEM DIAGNOSTICS SECTION =====
        diag_container = tk.Frame(main_frame, bg=self.colors['bg2'])
        diag_container.pack(fill='x', pady=(20, 10))
        
        diag_frame = tk.LabelFrame(diag_container, text=" 🔧 System Health ",
                               bg=self.colors['bg2'], fg=self.colors['text'],
                               font=('Segoe UI', 10, 'bold'), padx=10, pady=10)
        diag_frame.pack(fill='x')
        
        # RAM Usage
        self._dashboard_refs['ram_label'] = tk.Label(diag_frame, text="RAM: Calculating...", 
                                        font=('Segoe UI', 9), bg=self.colors['bg2'], fg=self.colors['text'])
        self._dashboard_refs['ram_label'].pack(anchor='w')
        
        # Process Count
        self._dashboard_refs['proc_label'] = tk.Label(diag_frame, text="Processes: Calculating...",
                                         font=('Segoe UI', 9), bg=self.colors['bg2'], fg=self.colors['text'])
        self._dashboard_refs['proc_label'].pack(anchor='w', pady=(2, 0))
        
        # Top Systems Processes
        tk.Label(diag_frame, text="Top Processes (RAM):", font=('Segoe UI', 9, 'bold'),
                bg=self.colors['bg2'], fg=self.colors['text2']).pack(anchor='w', pady=(10, 5))
                
        self._dashboard_refs['proc_bars'] = []
        for i in range(5):
            f = tk.Frame(diag_frame, bg=self.colors['bg2'])
            f.pack(fill='x', pady=2)
            l = tk.Label(f, text="", font=('Consolas', 9), bg=self.colors['bg2'], fg=self.colors['text'], width=20, anchor='w')
            l.pack(side='left')
            b_bg = tk.Frame(f, bg=self.colors['bg3'], height=10)
            b_bg.pack(side='left', fill='x', expand=True, padx=5)
            b_fill = tk.Frame(b_bg, bg=self.colors['blue'], height=10)
            b_fill.place(relx=0, rely=0, relwidth=0, relheight=1)
            v = tk.Label(f, text="", font=('Consolas', 9), bg=self.colors['bg2'], fg=self.colors['text2'])
            v.pack(side='right')
            self._dashboard_refs['proc_bars'].append({'row': f, 'name': l, 'bar': b_fill, 'val': v})

        # ===== MODEL USAGE SECTION =====
        model_container = tk.Frame(main_frame, bg=self.colors['bg2'])
        model_container.pack(fill='x', pady=(20, 10))
        
        model_frame = tk.LabelFrame(model_container, text=" 🤖 AI Model Usage ",
                               bg=self.colors['bg2'], fg=self.colors['text'],
                               font=('Segoe UI', 10, 'bold'), padx=10, pady=10)
        model_frame.pack(fill='x')
        
        self._dashboard_refs['model_bars'] = []
        for i in range(4): # Top 4 models
            f = tk.Frame(model_frame, bg=self.colors['bg2'])
            f.pack(fill='x', pady=2)
            l = tk.Label(f, text="", font=('Consolas', 9), bg=self.colors['bg2'], fg=self.colors['text'], width=20, anchor='w')
            l.pack(side='left')
            b_bg = tk.Frame(f, bg=self.colors['bg3'], height=10)
            b_bg.pack(side='left', fill='x', expand=True, padx=5)
            b_fill = tk.Frame(b_bg, bg=self.colors['green'], height=10)
            b_fill.place(relx=0, rely=0, relwidth=0, relheight=1)
            v = tk.Label(f, text="", font=('Consolas', 9), bg=self.colors['bg2'], fg=self.colors['text2'])
            v.pack(side='right')
            self._dashboard_refs['model_bars'].append({'row': f, 'name': l, 'bar': b_fill, 'val': v})

        # Start update loop
        self.update_dashboard_stats(win)

    def update_dashboard_stats(self, win):
        """Update dashboard statistics flicker-free"""
        if not win.winfo_exists():
            return
            
        try:
            analytics = self.load_analytics()
            
            # --- 0. UPDATE TREND GRAPH ---
            # Get recent history points for current session
            if self.current_session:
                history = self.load_history().get(self.current_session['id'], [])
                # Filter to last hour
                cutoff = time.time() - 3600
                recent = [h for h in history if h['ts'] > cutoff]
                
                canvas = self._dashboard_refs['trend_canvas']
                canvas.delete('all')
                
                if len(recent) > 1:
                    w = canvas.winfo_width()
                    h = 60
                    # Normalize
                    min_ts = recent[0]['ts']
                    time_span = recent[-1]['ts'] - min_ts or 1
                    max_tok = max(p['tokens'] for p in recent)
                    min_tok = min(p['tokens'] for p in recent)
                    val_span = max_tok - min_tok or 1
                    
                    points = []
                    for p in recent:
                        x = (p['ts'] - min_ts) / time_span * w
                        # Inverted Y (higher value = lower Y)
                        y = h - ((p['tokens'] - min_tok) / val_span * (h - 10) + 5)
                        points.append((x, y))
                    
                    if len(points) > 1:
                        canvas.create_line(points, fill=self.colors['blue'], width=2, smooth=True)
                        # End dot
                        canvas.create_oval(points[-1][0]-3, points[-1][1]-3, points[-1][0]+3, points[-1][1]+3, fill=self.colors['green'], outline='')
            
            # --- 1. UPDATE TIME TO HANDOFF ---
            seconds_remaining = self.calculate_time_to_handoff()
            time_str = self.format_time_remaining(seconds_remaining)
            
            time_color = self.colors['green']
            if seconds_remaining is not None:
                if seconds_remaining < 300: time_color = self.colors['red']
                elif seconds_remaining < 900: time_color = self.colors['yellow']
            
            self._dashboard_refs['ttf_label'].config(text=time_str, fg=time_color)
            
            # --- 2. UPDATE TODAY'S USAGE ---
            today = datetime.now().strftime('%Y-%m-%d')
            today_tokens = analytics['daily'].get(today, {}).get('total', 0)
            budget = self._daily_budget
            budget_pct = min(100, (today_tokens / budget) * 100) if budget > 0 else 0
            
            # Bar color
            bar_color = self.colors['green']
            if budget_pct >= 90: bar_color = self.colors['red']
            elif budget_pct >= 75: bar_color = self.colors['yellow']
            
            self._dashboard_refs['bar_fill'].configure(bg=bar_color)
            self._dashboard_refs['bar_fill'].place(relwidth=budget_pct/100, relheight=1)
            
            self._dashboard_refs['usage_label'].config(
                text=f"{today_tokens:,} / {budget:,} tokens ({budget_pct:.0f}%)"
            )
            
            # Reset Countdown
            now_utc = datetime.utcnow()
            today_reset = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
            if now_utc >= today_reset:
                next_reset = today_reset + timedelta(days=1)
            else:
                next_reset = today_reset
            
            time_until = next_reset - now_utc
            h, r = divmod(time_until.seconds, 3600)
            m = r // 60
            self._dashboard_refs['reset_label'].config(text=f"🔄 Daily Stats Reset in: {h}h {m}m (Midnight UTC)")

            # --- 3. UPDATE WEEKLY CHART ---
            weekly = self.get_weekly_summary()
            weekly_rev = list(reversed(weekly)) # Left to right (Oldest to Newest)
            max_tokens = max((d['tokens'] for d in weekly), default=1)
            
            for i, slot in enumerate(self._dashboard_refs['week_slots']):
                if i < len(weekly_rev):
                    day = weekly_rev[i]
                    pct = (day['tokens'] / max_tokens) if max_tokens > 0 else 0
                    
                    slot['bar'].place(relheight=pct)
                    slot['day'].config(text=day['day_name'])
                    tokens_k = day['tokens'] / 1000
                    slot['val'].config(text=f"{tokens_k:.0f}k" if day['tokens'] > 0 else "0")
                else:
                    slot['bar'].place(relheight=0)
                    slot['day'].config(text="-")
                    slot['val'].config(text="")

            # --- 4. UPDATE PROJECT LIST ---
            projects = self.get_project_summary()
            total_proj = sum(p['tokens'] for p in projects)
            
            for i, slot in enumerate(self._dashboard_refs['proj_slots']):
                if i < len(projects):
                    proj = projects[i]
                    pct = (proj['tokens'] / total_proj * 100) if total_proj > 0 else 0
                    slot['name'].config(text=proj['name'])
                    slot['val'].config(text=f"{proj['tokens']:,} ({pct:.0f}%)")
                    slot['row'].pack(fill='x', pady=2) # Ensure visible
                else:
                    slot['name'].config(text="")
                    slot['val'].config(text="")
                    slot['row'].pack_forget() # Hide empty rows
                    
            # --- 5. UPDATE PROJECT DISTRIBUTION BAR ---
            dist_bar = self._dashboard_refs['dist_bar']
            for widget in dist_bar.winfo_children():
                widget.destroy()
            
            colors = [self.colors['blue'], self.colors['green'], self.colors['yellow'], self.colors['red']]
            running_pct = 0
            for i, proj in enumerate(projects[:4]): # Top 4 only
                pct = (proj['tokens'] / total_proj) if total_proj > 0 else 0
                if pct > 0.05: # Only show if > 5%
                    col = colors[i % len(colors)]
                    f = tk.Frame(dist_bar, bg=col)
                    f.place(relx=running_pct, relwidth=pct, relheight=1)
                    running_pct += pct
            
            # --- 6. UPDATE SYSTEM DIAGNOSTICS ---
            procs = self.get_antigravity_processes()
            total_mem = sum(p.get('Mem', 0) for p in procs)
            limits = self.thresholds
            
            # Update Header Labels
            mem_color = self.colors['green']
            if total_mem > limits['total_crit']: mem_color = self.colors['red']
            elif total_mem > limits['total_warn']: mem_color = self.colors['yellow']
            
            self._dashboard_refs['ram_label'].config(text=f"RAM Detected: {self.total_ram_mb // 1024} GB | Total Usage: {total_mem}MB", fg=mem_color)
            self._dashboard_refs['proc_label'].config(text=f"Active Processes: {len(procs)}")
            
            # Update Process Bars
            max_p_mem = max((p.get('Mem', 0) for p in procs), default=500)
            
            for i, slot in enumerate(self._dashboard_refs['proc_bars']):
                if i < len(procs):
                    p = procs[i]
                    mem = p.get('Mem', 0)
                    pct = (mem / max_p_mem) if max_p_mem > 0 else 0
                    ptype = p.get('Type', 'Unknown')
                    
                    p_color = self.colors['blue']
                    if mem > limits['proc_crit']: p_color = self.colors['red']
                    elif mem > limits['proc_warn']: p_color = self.colors['yellow']

                    slot['name'].config(text=ptype)
                    slot['val'].config(text=f"{mem}MB")
                    slot['bar'].config(bg=p_color)
                    slot['bar'].place(relwidth=pct)
                    slot['row'].pack(fill='x', pady=2)
                else:
                    slot['row'].pack_forget()

            # --- 7. UPDATE MODEL USAGE ---
            models_data = analytics.get('models', {})
            # Sort by usage
            sorted_models = sorted(models_data.items(), key=lambda x: x[1]['total'], reverse=True)
            total_model_tokens = sum(m[1]['total'] for m in sorted_models)
            
            for i, slot in enumerate(self._dashboard_refs['model_bars']):
                if i < len(sorted_models):
                    m_name, m_data = sorted_models[i]
                    m_tokens = m_data['total']
                    pct = (m_tokens / total_model_tokens) if total_model_tokens > 0 else 0
                    
                    slot['name'].config(text=m_name)
                    slot['val'].config(text=f"{m_tokens:,} ({pct:.0%})")
                    slot['bar'].place(relwidth=pct)
                    slot['row'].pack(fill='x', pady=2)
                else:
                    slot['row'].pack_forget()

            # Schedule next update (1 second)
            win.after(1000, lambda: self.update_dashboard_stats(win))
            
        except Exception as e:
            print(f"Dashboard update error: {e}")
        
        # ===== BUDGET SETTING =====
        budget_frame = tk.Frame(main_frame, bg=self.colors['bg2'], padx=15, pady=10)
        budget_frame.pack(fill='x', pady=(10, 0))
        
        tk.Label(budget_frame, text="💰 Daily Budget:",
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['text2']).pack(side='left')
        
        budget_var = tk.StringVar(value=str(self._daily_budget))
        budget_entry = tk.Entry(budget_frame, textvariable=budget_var, width=10,
                               bg=self.colors['bg3'], fg=self.colors['text'],
                               insertbackground=self.colors['text'], font=('Consolas', 10))
        budget_entry.pack(side='left', padx=10)
        
        def save_budget():
            try:
                new_budget = int(budget_var.get())
                self._daily_budget = new_budget
                self.settings['daily_budget'] = new_budget
                self.save_settings()
                tk.Label(budget_frame, text="✓ Saved", font=('Segoe UI', 9),
                        bg=self.colors['bg2'], fg=self.colors['green']).pack(side='left')
            except ValueError:
                pass
        
        tk.Button(budget_frame, text="Save", command=save_budget,
                 bg=self.colors['blue'], fg='white', font=('Segoe UI', 9),
                 relief='flat', padx=10).pack(side='left')
        
        # ===== CONTEXT WINDOW SETTING =====
        ctx_frame = tk.Frame(main_frame, bg=self.colors['bg2'], padx=15, pady=10)
        ctx_frame.pack(fill='x', pady=(10, 0))
        
        tk.Label(ctx_frame, text="🎯 Context Window:",
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['text2']).pack(side='left')
        
        ctx_var = tk.StringVar(value=str(self._context_window))
        ctx_entry = tk.Entry(ctx_frame, textvariable=ctx_var, width=12,
                            bg=self.colors['bg3'], fg=self.colors['text'],
                            insertbackground=self.colors['text'], font=('Consolas', 10))
        ctx_entry.pack(side='left', padx=10)
        
        def save_context():
            try:
                new_ctx = int(ctx_var.get())
                self._context_window = new_ctx
                self.settings['context_window'] = new_ctx
                self.save_settings()
                ctx_status.config(text="✓")
                win.after(1500, lambda: ctx_status.config(text=""))
            except ValueError:
                pass
        
        tk.Button(ctx_frame, text="Save", command=save_context,
                 bg=self.colors['blue'], fg='white', font=('Segoe UI', 9),
                 relief='flat', padx=5).pack(side='left')
        
        ctx_status = tk.Label(ctx_frame, text="", font=('Segoe UI', 9),
                             bg=self.colors['bg2'], fg=self.colors['green'])
        ctx_status.pack(side='left', padx=5)
        # Model selector dropdown
        model_frame = tk.Frame(main_frame, bg=self.colors['bg2'], padx=15, pady=10)
        model_frame.pack(fill='x', pady=(10, 0))
        
        tk.Label(model_frame, text="🤖 AI Model:",
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['text2']).pack(side='left')
        
        # Model presets with context windows
        models = self.MODELS
        
        # Determine current model from context window if not saved
        if 'model' not in self.settings:
             current_model = "Custom"
             for name, ctx in models.items():
                 if ctx == self._context_window:
                     current_model = name
                     break
             self.settings['model'] = current_model
        
        current_model = self.settings.get('model', 'Custom')
        
        model_var = tk.StringVar(value=current_model)
        
        # Create dropdown menu
        model_menu = tk.OptionMenu(model_frame, model_var, *models.keys())
        model_menu.config(bg=self.colors['bg3'], fg=self.colors['text'],
                         activebackground=self.colors['blue'], activeforeground='white',
                         highlightthickness=0, font=('Segoe UI', 9))
        model_menu['menu'].config(bg=self.colors['bg3'], fg=self.colors['text'],
                                  activebackground=self.colors['blue'], activeforeground='white')
        model_menu.pack(side='left', padx=10)
        
        model_status = tk.Label(model_frame, text="", font=('Segoe UI', 9),
                               bg=self.colors['bg2'], fg=self.colors['green'])
        model_status.pack(side='left')
        
        def on_model_change(*args):
            selected = model_var.get()
            ctx = models.get(selected)
            if ctx is not None:
                self._context_window = ctx
                ctx_var.set(str(ctx))
                self.settings['context_window'] = ctx
                self.settings['model'] = selected
                self.save_settings()
                model_status.config(text=f"✓ {ctx:,} tokens")
                win.after(2000, lambda: model_status.config(text=""))
        
        model_var.trace('w', on_model_change)
    
    def export_history_csv(self):
        """Export token history to CSV file"""
        try:
            # Get all history data
            history = self.load_history()
            analytics = self.load_analytics()
            
            # Create export directory
            export_dir = Path.home() / 'Documents' / 'ContextMonitor'
            export_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Export session history
            session_file = export_dir / f'session_history_{timestamp}.csv'
            with open(session_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Session ID', 'Project', 'Timestamp', 'Tokens', 'Delta'])
                
                for session_id, data_points in history.items():
                    project = self.get_project_name(session_id)
                    for point in data_points:
                        ts = datetime.fromtimestamp(point['ts']).strftime('%Y-%m-%d %H:%M:%S')
                        writer.writerow([session_id[:16], project, ts, point['tokens'], point.get('delta', 0)])
            
            # Export daily summary
            daily_file = export_dir / f'daily_summary_{timestamp}.csv'
            with open(daily_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Date', 'Total Tokens'])
                
                for date, data in sorted(analytics.get('daily', {}).items()):
                    writer.writerow([date, data.get('total', 0)])
            
            # Export project summary
            project_file = export_dir / f'project_summary_{timestamp}.csv'
            with open(project_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Project', 'Total Tokens'])
                
                for name, data in analytics.get('projects', {}).items():
                    writer.writerow([name, data.get('total', 0)])
            
            messagebox.showinfo("Export Complete", 
                               f"Files exported to:\n{export_dir}\n\n"
                               f"• session_history_{timestamp}.csv\n"
                               f"• daily_summary_{timestamp}.csv\n"
                               f"• project_summary_{timestamp}.csv")
            
            # Open folder
            os.startfile(export_dir)
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export: {e}")


    def cleanup_and_exit(self):
        """Properly cleanup and exit the application"""
        try:
            # Save settings before exit
            self.save_settings()
            
            # Cancel any pending after callbacks
            for after_id in self.root.tk.call('after', 'info'):
                try:
                    self.root.after_cancel(after_id)
                except:
                    pass
            
            # Destroy the window
            if self.tray_icon:
                self.tray_icon.stop()
            self.root.quit()
            self.root.destroy()
            
        except Exception as e:
            print(f"Exit error: {e}")
        finally:
            # Force cleanup and exit
            self._flush_history_cache()  # Save any pending history
            self._flush_analytics_cache()  # Save any pending analytics
            self._cleanup_processes()
            # Use os._exit to ensure all threads are terminated
            os._exit(0)
    
    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self.minimize_to_tray if HAS_TRAY else self.cleanup_and_exit)
        
        if HAS_TRAY:
            self.setup_tray()
            self.tray_thread = threading.Thread(target=self.run_tray, daemon=True)
            self.tray_thread.start()
            
        self.root.mainloop()

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
    try:
        # Redirect stderr to file for debugging pythonw
        if sys.stderr is None:
            sys.stderr = open('error.log', 'w')
            sys.stdout = open('output.log', 'w')
            
        app = ContextMonitor()
        app.run()
    except Exception as e:
        import traceback
        with open("crash_log.txt", "w") as f:
            f.write(traceback.format_exc())
        messagebox.showerror("Context Monitor Crash", f"Application crashed:\n{e}")
