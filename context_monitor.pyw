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
import threading
import time
import csv
from datetime import timedelta
from utils import get_total_memory, calculate_thresholds, extract_pb_tokens
from widgets import ToolTip
from config import COLORS, MODELS, DEFAULT_SETTINGS, SETTINGS_FILE, HISTORY_FILE, ANALYTICS_FILE, CONVERSATIONS_DIR, VSCODE_CACHE_TTL
from data_service import data_service
from dialogs import show_history_dialog, show_diagnostics_dialog, show_advanced_stats_dialog
from menu_builder import build_context_menu

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
        
        # Settings (using config paths)
        self.settings_file = SETTINGS_FILE
        self.settings = self.load_settings()
        
        # Borderless, always on top
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', self.settings.get('alpha', DEFAULT_SETTINGS['alpha']))
        
        # Dark theme colors (from config)
        self.colors = COLORS
        
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
        
        # Tab caching (Sprint 1: Performance)
        self.tab_frames = {}
        self.tab_buttons = {}
        self.active_tab = self.settings.get('active_tab', 'diagnostics')
        self.sessions_cache = [] # Cache for context menu
        
        # Polling settings (in milliseconds)
        self.polling_interval = self.settings.get('polling_interval', 10000)  # Default 10s
        self.last_tokens = 0  # For delta tracking
        
        # Performance/Lag Caching (Sprint 3)
        self.session_metadata_cache = {} # Key: session_id, Value: {mtime, size, token_data, project_name}
        self.conversations_mtime = 0
        
        # VS Code detection cache (reduce ctypes calls)
        self._vscode_project_cache = None
        self._vscode_cache_time = 0
        
        # Threading for background updates
        self._update_lock = threading.Lock()
        self._pending_update = None
        
        # Paths (from config)
        self.conversations_dir = CONVERSATIONS_DIR
        self.history_file = HISTORY_FILE
        self.analytics_file = ANALYTICS_FILE
        
        # Analytics tracking
        self._rate_samples = []  # For time-to-handoff calculation
        self._last_notification_time = 0
        self._notifier = ToastNotifier() if HAS_TOAST else None
        self._daily_budget = self.settings.get('daily_budget', DEFAULT_SETTINGS['daily_budget'])
        self._context_window = self.settings.get('context_window', DEFAULT_SETTINGS['context_window'])
        # Migration: Force reset from old 2.1M default to 1M safe limit
        if self._context_window > 2000000:
            self._context_window = DEFAULT_SETTINGS['context_window']
        self.save_settings()
        
        # Supported Models (from config)
        self.MODELS = MODELS

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
        self.total_ram_mb = get_total_memory()
        self.thresholds = calculate_thresholds(self.total_ram_mb)
        
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
        """Setup UI by delegating to ui_builder module (Phase 5: V2.52)"""
        from ui_builder import setup_mini_mode, setup_compact_mode, setup_full_mode, bind_keyboard_shortcuts
        
        # Clear existing widgets
        for widget in self.root.winfo_children():
            widget.destroy()
        
        # Preserve current position
        current_geometry = self.root.geometry()
        pos = current_geometry.split('+')
        size = pos[0].split('x')
        w_px = size[0] if len(size) > 0 else "480"
        h_px = size[1] if len(size) > 1 else "240"
        x_pos = pos[1] if len(pos) > 1 else "50"
        y_pos = pos[2] if len(pos) > 2 else "50"
        
        # Load saved dimensions from settings
        if self.display_mode == 'compact':
            w_px = self.settings.get('window_w', w_px)
            h_px = self.settings.get('window_h', h_px)
        elif self.display_mode == 'full':
            w_px = self.settings.get('full_w', "650")
            h_px = self.settings.get('full_h', "650")
        
        # Delegate to ui_builder based on mode
        if self.display_mode == 'mini':
            setup_mini_mode(self, x_pos, y_pos)
        elif self.display_mode == 'compact':
            setup_compact_mode(self, w_px, h_px, x_pos, y_pos)
        else:
            setup_full_mode(self, w_px, h_px, x_pos, y_pos)
        
        # Bind keyboard shortcuts
        bind_keyboard_shortcuts(self)
        
    def create_tooltip(self, widget, text):
        _tooltip = ToolTip(widget, text, self.colors)  # noqa: F841 - returns None, keeps reference
        
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
        pct_font_size = 20 if self.mini_mode else 14
        
        # Drop shadow for mini mode (offset dark text behind) - only for percentage
        if self.mini_mode:
            shadow_offset = 2
            shadow_color = '#000000'
            
            # Draw percentage at top area
            self.gauge_canvas.create_text(cx+shadow_offset, cy-18+shadow_offset, text=f"{percent}%", 
                                          font=('Segoe UI', pct_font_size, 'bold'), fill=shadow_color, tags='text')
            self.gauge_canvas.create_text(cx, cy-18, text=f"{percent}%", 
                                          font=('Segoe UI', pct_font_size, 'bold'), fill=self.colors['text'], tags='text')
            
            # Show latest delta in middle
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
                    
                    # Draw delta in middle
                    self.gauge_canvas.create_text(cx+1, cy+6+1, text=delta_text, 
                                                  font=('Consolas', 9), fill=shadow_color, tags='text')
                    self.gauge_canvas.create_text(cx, cy+6, text=delta_text, 
                                                  font=('Consolas', 9), fill=delta_color, tags='text')
                
                # Time to handoff at bottom
                seconds = self.calculate_time_to_handoff()
                time_str = self.format_time_remaining(seconds)
                
                # Color based on urgency
                if seconds is None:
                    ttf_color = self.colors['muted']
                elif seconds <= 0:
                    ttf_color = self.colors['red']
                elif seconds < 300:  # < 5 min
                    ttf_color = self.colors['red']
                elif seconds < 900:  # < 15 min
                    ttf_color = self.colors['yellow']
                else:
                    ttf_color = self.colors['green']
                
                # Draw TTF at bottom with shadow
                self.gauge_canvas.create_text(cx+1, cy+26+1, text=f"⏱{time_str}", 
                                              font=('Segoe UI', 8), fill=shadow_color, tags='text')
                self.gauge_canvas.create_text(cx, cy+26, text=f"⏱{time_str}", 
                                              font=('Segoe UI', 8), fill=ttf_color, tags='text')
        else:
            # Full mode - just draw percentage centered
            self.gauge_canvas.create_text(cx, cy, text=f"{percent}%", 
                                          font=('Segoe UI', pct_font_size, 'bold'), fill=self.colors['text'], tags='text')
        
    def get_sessions(self):
        sessions = []
        try:
            if not self.conversations_dir.exists():
                return []
                
            # DIRTY CHECK: Skip scan if directory mtime hasn't changed
            try:
                current_mtime = self.conversations_dir.stat().st_mtime
                if current_mtime <= self.conversations_mtime and self.sessions_cache:
                    return self.sessions_cache
                self.conversations_mtime = current_mtime
            except:
                pass

            # FAST SCAN: Use os.scandir for raw speed
            with os.scandir(self.conversations_dir) as entries:
                for entry in entries:
                    name = entry.name
                    if not entry.is_file() or not (name.endswith('.pb') or name.endswith('.pb.gz')):
                        continue
                    if '.tmp' in name: continue
                    
                    try:
                        stat = entry.stat()
                        sid = name[:-3] if name.endswith('.pb') else name[:-6]
                        
                        # LAZY LOADING: Use cached metadata if file hasn't changed
                        cached = self.session_metadata_cache.get(sid)
                        if cached and cached['mtime'] == stat.st_mtime and cached['size'] == stat.st_size:
                            token_data = cached['token_data']
                            project_name = cached['project_name']
                        else:
                            # Placeholder - will be deep-scanned on demand or in background
                            token_data = None
                            project_name = None

                        sessions.append({
                            'id': sid,
                            'size': stat.st_size,
                            'modified': stat.st_mtime,
                            'estimated_tokens': stat.st_size // 4,
                            'token_data': token_data,
                            'project_name': project_name,
                            'compressed': name.endswith('.pb.gz'),
                            'pb_path': Path(entry.path)
                        })
                    except: continue
                            
            sessions.sort(key=lambda x: x['modified'], reverse=True)
            self.sessions_cache = sessions
        except Exception as e:
            print(f"Error scanning sessions: {e}")
        return sessions

    def resolve_session_metadata(self, session, force=False):
        """Deep scan a session for tokens and project name with caching (Heavy I/O)"""
        if not session: return None, None
        
        sid = session['id']
        pb_path = session['pb_path']
        mtime = session['modified']
        size = session['size']
        
        # Check cache
        cached = self.session_metadata_cache.get(sid)
        if not force and cached and cached['mtime'] == mtime and cached['size'] == size:
            session['token_data'] = cached['token_data']
            session['project_name'] = cached['project_name']
            return cached['token_data'], cached['project_name']
            
        # Perform expensive scan
        token_data = extract_pb_tokens(pb_path, self._context_window)
        project_name = token_data.get('project_name')
        
        # Update cache
        self.session_metadata_cache[sid] = {
            'mtime': mtime,
            'size': size,
            'token_data': token_data,
            'project_name': project_name
        }
        
        # Update session object
        session['token_data'] = token_data
        session['project_name'] = project_name
        
        return token_data, project_name

    def background_metadata_scan(self):
        """Resolve metadata for top sessions in a background thread"""
        try:
            # Small delay to let the active session render first
            time.sleep(1.0)
            
            # Get copy of sessions to avoid iterator mutation
            if not hasattr(self, 'sessions_cache') or not self.sessions_cache:
                return
                
            sessions_to_scan = self.sessions_cache[:15]
            for s in sessions_to_scan:
                # Skip if already resolved
                if s.get('token_data'): continue
                
                # Resolve (Heavy I/O)
                self.resolve_session_metadata(s)
                time.sleep(0.05)
        except Exception:
            pass  # Silently ignore metadata resolution errors

    def get_active_vscode_project(self):
        """Get active VS Code project using ctypes with caching (Zero-overhead process check)"""
        import time
        now = time.time()
        
        # Return cached result if still valid
        if now - self._vscode_cache_time < VSCODE_CACHE_TTL:
            return self._vscode_project_cache
        
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
                            # Cache the successful result
                            self._vscode_project_cache = clean
                            self._vscode_cache_time = now
                            return clean
        except Exception:
            # Fail silently to avoid log spam/crashes on weird Windows APIs
            self._vscode_project_cache = None
            self._vscode_cache_time = now
            return None
        
        self._vscode_project_cache = None
        self._vscode_cache_time = now
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
        except Exception:
            pass  # Silently ignore project detection errors
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
                            # Priority 1: Specific project keywords
                            if 'UE5' in content or 'Blueprint' in content:
                                project_name = 'UE5Blueprint'
                                break
                            elif 'context-monitor' in content.lower() or 'Context Monitor' in content:
                                project_name = 'context-monitor'
                                break
                            
                            # Priority 2: Look for project-specific files like task.md or implementation_plan.md
                            # which often contain the project name in headings or paths
                            if 'Implementation Plan' in content or '# Task' in content:
                                # Try to find a project name in bracketed links or paths
                                pat = r'[/\\]GitHub[/\\]([A-Za-z0-9_-]+)'
                                match = re.search(pat, content)
                                if match:
                                    project_name = match.group(1)
                                    break
                            
                            # Priority 3: Generic GitHub path detection
                            match = re.search(r'GitHub[/\\]([A-Za-z0-9_-]+)', content)
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
    
    def ensure_logs_dir(self, session_id):
        """Proactively ensure the logs directory exists for agents to scan."""
        try:
            logs_dir = Path.home() / '.gemini' / 'antigravity' / 'brain' / session_id / '.system_generated' / 'logs'
            if not logs_dir.exists():
                logs_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"[Maintenance] Could not create logs dir: {e}")

    def load_session(self):
        # 1. Get raw session list (Fast dirty-check/scandir only)
        sessions = self.get_sessions()
        
        if not sessions:
            if not self.mini_mode and hasattr(self, 'status_label'):
                self.status_label.config(text="⚠ No sessions")
            return
            
        # 2. Pick current session
        self.current_session = sessions[0]
        if self.selected_session_id:
            found = next((s for s in sessions if s['id'] == self.selected_session_id), None)
            if found: self.current_session = found
            else: self.selected_session_id = None

        # 3. Resolve Metadata for ACTIVE session (Sync, but only 1 file read)
        token_data, project_name = self.resolve_session_metadata(self.current_session)
        
        # 4. Start Background scan for context menu optimization
        threading.Thread(target=self.background_metadata_scan, daemon=True).start()

        # Ensure logs directory exists for the current session
        self.ensure_logs_dir(self.current_session['id'])

        context_window = self._context_window
        
        # Use accurate token data
        token_data = self.current_session.get('token_data')
        if token_data:
            tokens_used = token_data['tokens_used']
            context_window = token_data['context_window']
            tokens_left = token_data['tokens_remaining']
        else:
            # Fallback if first read failed
            tokens_used = self.current_session['size'] // 40
            tokens_left = max(0, context_window - tokens_used)
        
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
            # PERFORMANCE: Cap display name to prevent layout breakage
            capped_name = (display_name[:25] + "...") if len(display_name) > 25 else display_name
        
            # Update UI labels if they exist (Compact/Full mode)
            if hasattr(self, 'session_label'):
                self.session_label.config(text=capped_name)
            if hasattr(self, 'project_label'):
                self.project_label.config(text=capped_name)

        # Update tray icon (Run in all modes)
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
                    if i == 0: # Latest delta
                        lbl.config(text=text, fg=color, font=('Consolas', 11, 'bold'))
                    else:
                        lbl.config(text=text, fg=color, font=('Consolas', 11))
                else:
                    lbl.config(text="—", fg=self.colors['muted'], font=('Consolas', 11))
        
        # Update time-to-handoff label if exists (Compact/Full mode)
        if hasattr(self, 'ttf_label') and self.ttf_label.winfo_exists():
            seconds = self.calculate_time_to_handoff()
            time_str = self.format_time_remaining(seconds)
            
            # Color based on urgency
            if seconds is None:
                ttf_color = self.colors['text2']
            elif seconds <= 0:
                ttf_color = self.colors['red']
            elif seconds < 300:  # < 5 min
                ttf_color = self.colors['red']
            elif seconds < 900:  # < 15 min
                ttf_color = self.colors['yellow']
            else:
                ttf_color = self.colors['green']
            
            self.ttf_label.config(text=f"⏱️ {time_str}", fg=ttf_color)
        
        # Update tab-specific labels if they exist (Full Mode Caching)
        if hasattr(self, 'stats_tokens_used_label') and self.stats_tokens_used_label.winfo_exists():
            usage_color = self.colors['red'] if percent >= 80 else (self.colors['yellow'] if percent >= 60 else self.colors['green'])
            self.stats_tokens_used_label.config(text=f"  • Tokens Used: {tokens_used:,} ({percent}%)", fg=usage_color)
        if hasattr(self, 'stats_tokens_left_label') and self.stats_tokens_left_label.winfo_exists():
            self.stats_tokens_left_label.config(text=f"  • Tokens Remaining: {tokens_left:,}")
            
        # Refresh high-frequency tabs if visible
        if self.display_mode == 'full':
            if self.active_tab == 'diagnostics':
                # Re-render diagnostics to get fresh process list
                if self.active_tab in self.tab_frames and self.tab_frames[self.active_tab].winfo_exists():
                    frame = self.tab_frames[self.active_tab]
                    for widget in frame.winfo_children():
                        widget.destroy()
                    self.render_diagnostics_inline(frame)
            elif self.active_tab == 'history':
                self.draw_mini_graph()
        
        # Last updated timestamp
        updated_time = datetime.now().strftime("%H:%M:%S")
        if hasattr(self, 'status_label'):
            current_status = self.status_label.cget('text').split(' | ')[0]
            self.status_label.config(text=f"{current_status} | {updated_time}")
        
        # Update status and auto-copy at 80% (Requires status_label/frame)
        if hasattr(self, 'status_label') and hasattr(self, 'status_frame'):
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
    
    def start_drag(self, event):
        self.drag_x = event.x
        self.drag_y = event.y
        
    def drag(self, event):
        x = self.root.winfo_x() + event.x - self.drag_x
        y = self.root.winfo_y() + event.y - self.drag_y
        self.root.geometry(f"+{x}+{y}")

    def start_resize(self, event):
        self.resize_start_x = event.x_root
        self.resize_start_y = event.y_root
        self.resize_start_w = self.root.winfo_width()
        self.resize_start_h = self.root.winfo_height()
        
    def resize_window(self, event):
        # Calculate new dimensions
        new_w = max(400, self.resize_start_w + (event.x_root - self.resize_start_x))
        new_h = max(200, self.resize_start_h + (event.y_root - self.resize_start_y))
        
        # Apply to window (maintaining position)
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self.root.geometry(f"{new_w}x{new_h}+{x}+{y}")
        self.save_settings()
        
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
            
            # Get current dimensions with floor to prevent 1x1 window bugs
            curr_w = self.root.winfo_width()
            curr_h = self.root.winfo_height()
            
            # Save logic with safeguards
            save_data = {
                'alpha': self.root.attributes('-alpha'),
                'display_mode': self.display_mode,
                'polling_interval': self.polling_interval,
                'daily_budget': self._daily_budget,
                'context_window': self._context_window,
                'model': self.settings.get('model'),
                'window_x': self.root.winfo_x(),
                'window_y': self.root.winfo_y()
            }
            
            if self.display_mode == 'compact':
                save_data['window_w'] = max(400, curr_w)
                save_data['window_h'] = max(200, curr_h)
            else:
                save_data['window_w'] = self.settings.get('window_w', 480)
                save_data['window_h'] = self.settings.get('window_h', 240)
                
            if self.display_mode == 'full':
                save_data['full_w'] = max(400, curr_w)
                save_data['full_h'] = max(400, curr_h)
            else:
                save_data['full_w'] = self.settings.get('full_w', 650)
                save_data['full_h'] = self.settings.get('full_h', 650)
                
            with open(self.settings_file, 'w') as f:
                json.dump(save_data, f, indent=2)
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
        """Load history using data_service (V2.46: Modularized)"""
        return data_service.load_history(force_reload)
    def save_history(self, session_id, tokens):
        """Save history using data_service (V2.46: Modularized)"""
        throttle_seconds = max(2, self.polling_interval / 1000)
        delta = data_service.save_history(session_id, tokens, self.last_tokens, throttle_seconds)
        self.last_tokens = tokens
        return delta
    def _flush_history_cache(self):
        """Flush via data_service (V2.46: Modularized)"""
        data_service._flush_history()
    def _flush_analytics_cache(self):
        """Flush via data_service (V2.46: Modularized)"""
        data_service._flush_analytics()
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
    
    def switch_tab(self, tab_id):
        """Switch active tab in Full mode with widget caching"""
        if self.active_tab == tab_id and tab_id in self.tab_frames:
            return
            
        # Update buttons
        for tid, btn in self.tab_buttons.items():
            if tid == tab_id:
                btn.config(bg=self.colors['blue'], fg='white')
            else:
                btn.config(bg=self.colors['bg3'], fg=self.colors['text'])
                
        # Hide current tab frame
        if self.active_tab in self.tab_frames:
            self.tab_frames[self.active_tab].pack_forget()
            
        self.active_tab = tab_id
        self.render_tab_content()
        self.save_settings()
    
    def render_tab_content(self):
        """Render content for the active tab using cache"""
        if not hasattr(self, 'content_frame'):
            return
        
        # If tab is already rendered, just show it
        if self.active_tab in self.tab_frames:
            self.tab_frames[self.active_tab].pack(fill='both', expand=True)
            return

        # Create new tab frame
        tab_frame = tk.Frame(self.content_frame, bg=self.colors['bg2'])
        self.tab_frames[self.active_tab] = tab_frame
        tab_frame.pack(fill='both', expand=True)
        
        # Render based on active tab
        if self.active_tab == 'diagnostics':
            self.render_diagnostics_inline(tab_frame)
        elif self.active_tab == 'token_stats':
            self.render_token_stats_inline(tab_frame)
        elif self.active_tab == 'history':
            self.render_history_inline(tab_frame)
        elif self.active_tab == 'analytics':
            self.render_analytics_inline(tab_frame)
    


    def show_history(self):
        """Delegated to dialogs module (Phase 4: V2.47)"""
        show_history_dialog(self)
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
    
    
    # ==================== DIAGNOSTICS ====================
    
    def show_context_menu(self, event):
        """Delegated to menu_builder (Phase 5: V2.48)"""
        build_context_menu(self, event)
    def set_polling_speed(self, interval):
        """Set refresh rate and save to settings"""
        self.polling_interval = interval
        self.settings['polling_interval'] = interval
        self.save_settings()
        self.status_label.config(text=f"✓ Polling: {interval/1000}s", fg=self.colors['blue'])
        self.root.after(2000, lambda: self.status_label.config(text="✓ Ready", fg=self.colors['green']))

    def copy_handoff(self):
        """Generate high-density 'Context Bridge' for the next agent"""
        if not self.current_session:
            self.root.clipboard_clear()
            self.root.clipboard_append("No active session detected.")
            return

        sid = self.current_session['id']
        tokens = self.current_session.get('token_data', {})
        used = tokens.get('tokens_used', 0)
        limit = tokens.get('context_window', self._context_window)
        pct = (used / limit) * 100 if limit > 0 else 0
        
        # Project detection
        project = self.project_name_cache.get(sid, "Unknown")
        
        # Build "Context Bridge" Briefing
        bridge = [
            f"🚀 **CONTEXT BRIDGE: {project.upper()}**",
            f"Session: `{sid}`",
            f"Tokens: {used:,} / {limit:,} ({pct:.1f}%)",
            "",
            "📂 **CRITICAL PATHS**",
            f"- Conversation: `C:\\Users\\Sam Deiter\\.gemini\\antigravity\\conversations\\{sid}.pb`",
            f"- Brain Folder: `C:\\Users\\Sam Deiter\\.gemini\\antigravity\\brain\\{sid}`",
            f"- Task List: `C:\\Users\\Sam Deiter\\.gemini\\antigravity\\brain\\{sid}\\task.md`",
            f"- Implementation Plan: `C:\\Users\\Sam Deiter\\.gemini\\antigravity\\brain\\{sid}\\implementation_plan.md`",
            f"- Logs: `C:\\Users\\Sam Deiter\\.gemini\\antigravity\\brain\\{sid}\\.system_generated\\logs`",
            "",
            "📝 **HANDOFF BRIEFING**",
            "This project is at a critical checkpoint. Please follow these steps:",
            "1. Read `task.md` for current status and pending items.",
            "2. Review `implementation_plan.md` for upcoming architecture changes.",
            "3. Check the `.system_generated\\logs` for recent error patterns.",
            "",
            "**Next Step:** [Paste User's Last Objective Here]"
        ]
        
        final_brief = "\n".join(bridge)
        self.root.clipboard_clear()
        self.root.clipboard_append(final_brief)
        
        self.status_label.config(text="✓ Bridge Copied!", fg=self.colors['blue'])
        self.root.after(3000, lambda: self.status_label.config(text="✓ Ready", fg=self.colors['green']))
        
        # Visual feedback on copy button if it exists
        if hasattr(self, 'copy_btn'):
            self.copy_btn.config(fg=self.colors['green'])
            self.root.after(1000, lambda: self.copy_btn.config(fg=self.colors['blue']))

    def set_model(self, model_name):
        """Configure context window based on model presets"""
        if model_name in self.MODELS:
            limit = self.MODELS[model_name]
            if limit:
                self._context_window = limit
                self.settings['context_window'] = limit
            
            self.settings['model'] = model_name
            self.save_settings()
            
            # Update UI immediately
            self.status_label.config(text=f"✓ Model: {model_name}", fg=self.colors['blue'])
            self.load_session() # Force refresh with new window size
            self.root.after(2000, lambda: self.status_label.config(text="✓ Ready", fg=self.colors['green']))

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
        """Delegated to dialogs module (Phase 4: V2.47)"""
        show_diagnostics_dialog(self)
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
        """Delegated to dialogs module (Phase 4: V2.47)"""
        show_advanced_stats_dialog(self)
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
        """Load analytics using data_service (V2.46: Modularized)"""
        analytics = data_service.load_analytics()
        self._analytics_cache = analytics  # Keep local reference for compatibility
        return analytics
    def save_analytics(self, tokens, project_name):
        """Track analytics using data_service (V2.46: Modularized)"""
        model_name = self.settings.get('model', 'Unknown')
        analytics = data_service.save_analytics(tokens, self.last_tokens, project_name, model_name)
        self._analytics_cache = analytics  # Keep local reference for compatibility
        
        # Check budget notification
        today = datetime.now().strftime('%Y-%m-%d')
        self.check_budget_notification(analytics, today)
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
        """Delegated to dialogs module (Phase 3: V2.53)"""
        from dialogs import show_analytics_dashboard
        show_analytics_dashboard(self)

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
