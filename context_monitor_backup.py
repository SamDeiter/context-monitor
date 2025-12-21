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
import platform
import threading
import sys
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
        self.mini_mode = self.settings.get('mini_mode', False)
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

        
        # Hardware Scan
        self.total_ram_mb = self.get_total_memory()
        self.thresholds = self.calculate_thresholds()
        
        # Register cleanup on exit
        atexit.register(self._cleanup_processes)
        self.root.protocol("WM_DELETE_WINDOW", self.cleanup_and_exit)
        
        self.setup_ui()
        self.root.bind('<Button-3>', self.show_context_menu)  # Right-click anywhere
        self.load_session()
        self.root.after(15000, self.auto_refresh)
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
            
        else:
            # Full mode - reset transparency
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
        
        # Keyboard shortcuts (global)
        self.root.bind('<KeyPress-m>', lambda e: self.toggle_mini_mode())
        self.root.bind('<KeyPress-plus>', lambda e: self.adjust_alpha(0.05))
        self.root.bind('<KeyPress-minus>', lambda e: self.adjust_alpha(-0.05))
        self.root.bind('<KeyPress-r>', lambda e: self.force_refresh())
        self.root.bind('<KeyPress-a>', lambda e: self.show_advanced_stats())
        
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

    def get_active_vscode_project(self):
        """Try to get the active project from VS Code window title"""
        try:
            # Use PowerShell to get the foreground window title (most recently active)
            cmd = '''powershell -Command "Add-Type @'
using System;
using System.Runtime.InteropServices;
public class Win32 {
    [DllImport(\"user32.dll\")]
    public static extern IntPtr GetForegroundWindow();
    [DllImport(\"user32.dll\")]
    public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder text, int count);
}
'@
$h = [Win32]::GetForegroundWindow()
$sb = New-Object System.Text.StringBuilder 256
[Win32]::GetWindowText($h, $sb, 256) | Out-Null
$sb.ToString()
"'''
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=3)
            if result.returncode == 0 and result.stdout.strip():
                title = result.stdout.strip()
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
        except Exception as e:
            print(f"[Debug] Active window detection error: {e}")
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

    def get_project_name(self, session_id):
        """Extract project name using multiple detection strategies"""
        # Check cache first (but invalidate after 10 seconds for active detection)
        import time
        now = time.time()
        if session_id in self.project_name_cache:
            if session_id in self.project_name_timestamp:
                if now - self.project_name_timestamp[session_id] < 10:  # Reduced from 60s for faster detection
                    return self.project_name_cache[session_id]
        
        project_name = None

        # Strategy 1: Check active VS Code window (MOST RELIABLE for current project)
        vscode_project = self.get_active_vscode_project()
        if vscode_project:
            project_name = vscode_project

        # Strategy 2: Parse from conversation file - look for ACTIVE DOCUMENT path only
        if not project_name:
            try:
                pb_file = self.conversations_dir / f"{session_id}.pb"
                if pb_file.exists():
                    # Read only the last 50KB for recent context (faster & more accurate)
                    with open(pb_file, 'rb') as f:
                        f.seek(0, 2)  # Seek to end
                        size = f.tell()
                        start = max(0, size - 50000)  # Last 50KB
                        f.seek(start)
                        content = f.read()
                    text = content.decode('utf-8', errors='ignore')
                    
                    # Only look for Active Document path (most reliable for current context)
                    pattern = r'Active Document:.*GitHub[/\\]([A-Za-z0-9_-]+)[/\\]'
                    matches = list(re.finditer(pattern, text))
                    if matches:
                        project_name = matches[-1].group(1)  # Use last (most recent) match
            except Exception as e:
                print(f"Error getting project name from file: {e}")

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

        context_window = 200000
        tokens_used = self.current_session['estimated_tokens'] // 10
        tokens_left = max(0, context_window - tokens_used)
        percent = min(100, round((tokens_used / context_window) * 100))
        
        # Calculate delta from last reading
        delta = tokens_used - self.last_tokens if self.last_tokens > 0 else 0
        
        self.current_percent = percent
        self.draw_gauge(percent)
        
        # Save history (throttle: save max once per 5 mins)
        self.save_history(self.current_session['id'], tokens_used)
        
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
            
            project_name = self.get_project_name(self.current_session['id'])
            self.session_label.config(text=project_name)
            
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
                    'mini_mode': self.mini_mode,
                    'polling_interval': self.polling_interval
                }, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def toggle_mini_mode(self):
        """Toggle between full and mini mode"""
        self.mini_mode = not self.mini_mode
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
    
    
    def load_history(self, force_reload=False):
        """Load history with caching (Sprint 1: Performance)"""
        import time
        now = time.time()
        
        # Return cache if valid (less than 30 seconds old)
        if not force_reload and self._history_cache is not None:
            if now - self._history_cache_time < 30:
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
            max_tokens = 200000
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
        menu.add_separator()
        
        # Actions section
        menu.add_command(label="  🧹  Clean Old Conversations", command=self.cleanup_old_conversations)
        menu.add_command(label="  🔄  Restart Antigravity", command=self.restart_antigravity)
        menu.add_separator()
        
        # Sessions submenu
        sessions_menu = tk.Menu(menu, tearoff=0,
                              bg=self.colors['bg2'],
                              fg=self.colors['text'],
                              activebackground=self.colors['blue'],
                              activeforeground='white')
        
        current_id = self.current_session['id'] if self.current_session else None
        
        # Get top 5 sessions
        sessions = self.get_sessions()[:5]
        for s in sessions:
            # Format: "Project Name (ID...)" or "ID..."
            name = self.get_project_name(s['id'])
            label = f"{'✓ ' if s['id'] == current_id else '  '}{name}"
            # Use partial to capture the loop variable
            from functools import partial
            sessions_menu.add_command(label=label, 
                                    command=partial(self.switch_session, s['id']))
            
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
            context_window = 200000
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
    app = ContextMonitor()
    app.run()
