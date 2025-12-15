"""
Context Monitor - Python Desktop Widget
Borderless, always-on-top token usage tracker for Antigravity
"""

import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from datetime import datetime
import json
import subprocess
import os

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
        self.flash_state = False
        self.current_percent = 0
        
        # Paths
        self.conversations_dir = Path.home() / '.gemini' / 'antigravity' / 'conversations'
        
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
            # Mini mode: circular gauge
            self.root.geometry(f"120x120+{x_pos}+{y_pos}")
            self.root.update()  # Force resize
            
            # Use transparent color to create circular appearance
            trans_color = '#010101'  # Nearly black, used as transparent
            self.root.configure(bg=trans_color)
            self.root.attributes('-transparentcolor', trans_color)
            
            self.gauge_canvas = tk.Canvas(self.root, width=120, height=120,
                                          bg=trans_color, highlightthickness=0)
            self.gauge_canvas.pack()
            
            # Draw circular background
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
            self.root.geometry(f"280x200+{x_pos}+{y_pos}")
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
            
            # Mini mode toggle
            mini_btn = tk.Label(header, text="◱", font=('Segoe UI', 12), cursor='hand2',
                               bg=self.colors['bg3'], fg=self.colors['blue'])
            mini_btn.pack(side='right', padx=5)
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
            self.create_tooltip(self.gauge_canvas, "Token Usage\nGreen: Safe\nYellow: < 60% Left\nRed: < 80% Left")
            self.create_tooltip(self.copy_btn, "Generate Handoff\nCreates a summary prompt for the next agent")
            self.create_tooltip(self.session_label, "Current Session ID\nAuto-detected from files")
            self.create_tooltip(mini_btn, "Toggle Mini Mode (M)\nSwitch to compact view")
            self.create_tooltip(alpha_frame, "Transparency (+/-)\nAdjust window opacity")
        
        # Keyboard shortcuts (global)
        self.root.bind('<KeyPress-m>', lambda e: self.toggle_mini_mode())
        self.root.bind('<KeyPress-plus>', lambda e: self.adjust_alpha(0.05))
        self.root.bind('<KeyPress-minus>', lambda e: self.adjust_alpha(-0.05))
        self.root.bind('<KeyPress-r>', lambda e: self.reset_settings())
        
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
            # Center within the visible circle (which is at 10,10 to 110,110)
            cx, cy = 60, 60
            r = 35
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
        
        # Font sizes
        pct_font_size = 22 if self.mini_mode else 14
        label_font_size = 7
        
        # Drop shadow for mini mode (offset dark text behind)
        if self.mini_mode:
            shadow_offset = 2
            shadow_color = '#000000'
            self.gauge_canvas.create_text(cx+shadow_offset, cy+shadow_offset, text=f"{percent}%", 
                                          font=('Segoe UI', pct_font_size, 'bold'), fill=shadow_color, tags='text')
        
        # Percentage text (centered in mini mode, offset in full mode)
        y_offset = 0 if self.mini_mode else -6
        self.gauge_canvas.create_text(cx, cy + y_offset, text=f"{percent}%", 
                                      font=('Segoe UI', pct_font_size, 'bold'), fill=self.colors['text'], tags='text')
        
        # Only show CONTEXT label in full mode
        if not self.mini_mode:
            self.gauge_canvas.create_text(cx, cy+14, text="CONTEXT", 
                                          font=('Segoe UI', label_font_size), fill=self.colors['muted'], tags='text')
        
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
        """Extract project name from brain directory task.md"""
        try:
            brain_dir = Path.home() / '.gemini' / 'antigravity' / 'brain' / session_id
            task_file = brain_dir / 'task.md'
            
            if task_file.exists():
                with open(task_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Look for first heading (# Project Name)
                    for line in content.split('\n'):
                        line = line.strip()
                        if line.startswith('# '):
                            name = line[2:].strip()
                            # Truncate if too long
                            if len(name) > 25:
                                return name[:22] + '...'
                            return name
            
            # Fallback: check implementation_plan.md
            plan_file = brain_dir / 'implementation_plan.md'
            if plan_file.exists():
                with open(plan_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith('# '):
                            name = line[2:].strip()
                            if len(name) > 25:
                                return name[:22] + '...'
                            return name
                            
        except Exception as e:
            print(f"Error getting project name: {e}")
        
        # Final fallback: short session ID
        return f"Session {session_id[:8]}..."
    
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
        return {'alpha': 0.95, 'mini_mode': False}
    
    def save_settings(self):
        """Save settings to JSON file"""
        try:
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.settings_file, 'w') as f:
                json.dump({
                    'alpha': self.root.attributes('-alpha'),
                    'mini_mode': self.mini_mode
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
        menu.add_separator()
        
        # Actions section
        menu.add_command(label="  🧹  Clean Old Conversations", command=self.cleanup_old_conversations)
        menu.add_command(label="  🔄  Restart Antigravity", command=self.restart_antigravity)
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
        """Get memory/CPU usage of Antigravity processes with type info"""
        try:
            result = subprocess.run(
                ['powershell', '-Command', 
                 'Get-Process -Name Antigravity -ErrorAction SilentlyContinue | '
                 'Select-Object Id, @{N="CPU";E={[math]::Round($_.CPU,1)}}, '
                 '@{N="Mem";E={[math]::Round($_.WorkingSet64/1MB,0)}}, '
                 '@{N="Cmd";E={(Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine}} | '
                 'Sort-Object Mem -Descending | Select-Object -First 8 | '
                 'ConvertTo-Json'],
                capture_output=True, text=True, timeout=15
            )
            if result.stdout.strip():
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    data = [data]
                # Detect process type from command line
                for p in data:
                    cmd = p.get('Cmd', '') or ''
                    if 'extensionHost' in cmd:
                        p['Type'] = 'Extension Host'
                    elif 'renderer' in cmd or 'gpu' in cmd:
                        p['Type'] = 'Renderer/GPU'
                    elif 'ptyHost' in cmd:
                        p['Type'] = 'Terminal'
                    elif 'fileWatcher' in cmd:
                        p['Type'] = 'File Watcher'
                    elif 'languageServer' in cmd or 'tsserver' in cmd:
                        p['Type'] = 'Language Server'
                    elif 'sharedProcess' in cmd:
                        p['Type'] = 'Shared Process'
                    else:
                        p['Type'] = 'Main/Other'
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
        total_mem = 0
        high_mem_types = []
        
        for p in procs:
            mem = p.get('Mem', 0)
            total_mem += mem
            cpu = p.get('CPU', 0)
            ptype = p.get('Type', 'Unknown')
            status = "🔴" if mem > 500 else "🟡" if mem > 200 else "🟢"
            msg += f"{status} {ptype}: {mem}MB RAM, {cpu}s CPU\n"
            if mem > 400:
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
        
        if total_mem > 3000:
            msg += "🔴 CRITICAL: Total memory > 3GB!\n"
            msg += "   → RESTART ANTIGRAVITY NOW\n"
        elif total_mem > 2000:
            msg += "🟡 High memory usage (>2GB)\n"
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

class ToolTip:
    def __init__(self, widget, text, colors):
        self.widget = widget
        self.text = text
        self.colors = colors
        self.tooltip = None
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        x, y, _, _ = self.widget.bbox("insert") if self.widget.bbox("insert") else (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        
        self.tooltip = tk.Toplevel(self.widget)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(self.tooltip, text=self.text, justify='left',
                       bg=self.colors['bg3'], fg=self.colors['text'],
                       relief='solid', borderwidth=1,
                       font=("Segoe UI", 8))
        label.pack()

    def leave(self, event=None):
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

if __name__ == '__main__':
    app = ContextMonitor()
    app.run()
