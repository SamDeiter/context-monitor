"""
Feature Update Script for Context Monitor
Adds: Analytics Dashboard, Daily/Weekly Tracking, Time-to-Handoff, Desktop Notifications, CSV Export
"""
import re

def update_context_monitor():
    filepath = r"c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.py"
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # ========== 1. Add new imports at the top ==========
    old_imports = '''import threading
import sys'''
    new_imports = '''import threading
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
    HAS_TOAST = False'''
    
    content = content.replace(old_imports, new_imports)
    
    # ========== 2. Add new state variables in __init__ ==========
    old_state = '''        # Paths
        self.conversations_dir = Path.home() / '.gemini' / 'antigravity' / 'conversations'
        self.history_file = Path.home() / '.gemini' / 'antigravity' / 'scratch' / 'token-widget' / 'history.json'

        
        # Hardware Scan'''
    
    new_state = '''        # Paths
        self.conversations_dir = Path.home() / '.gemini' / 'antigravity' / 'conversations'
        self.history_file = Path.home() / '.gemini' / 'antigravity' / 'scratch' / 'token-widget' / 'history.json'
        self.analytics_file = Path.home() / '.gemini' / 'antigravity' / 'scratch' / 'token-widget' / 'analytics.json'
        
        # Analytics tracking
        self._analytics_cache = None
        self._rate_samples = []  # For time-to-handoff calculation
        self._last_notification_time = 0
        self._notifier = ToastNotifier() if HAS_TOAST else None
        self._daily_budget = self.settings.get('daily_budget', 500000)  # Default 500k tokens/day
        
        # Hardware Scan'''
    
    content = content.replace(old_state, new_state)
    
    # ========== 3. Add new keyboard shortcut for Analytics ==========
    old_shortcuts = '''        self.root.bind('<KeyPress-a>', lambda e: self.show_advanced_stats())'''
    new_shortcuts = '''        self.root.bind('<KeyPress-a>', lambda e: self.show_advanced_stats())
        self.root.bind('<KeyPress-d>', lambda e: self.show_analytics_dashboard())
        self.root.bind('<KeyPress-e>', lambda e: self.export_history_csv())'''
    
    content = content.replace(old_shortcuts, new_shortcuts)
    
    # ========== 4. Find and update show_context_menu to add new options ==========
    # Find the line with "📅  Usage History Graph" and add new menu items after
    old_menu = '''        menu.add_command(label="  📅  Usage History Graph", command=self.show_history)
        menu.add_separator()'''
    
    new_menu = '''        menu.add_command(label="  📅  Usage History Graph", command=self.show_history)
        menu.add_command(label="  📊  Analytics Dashboard (D)", command=self.show_analytics_dashboard)
        menu.add_command(label="  💾  Export to CSV (E)", command=self.export_history_csv)
        menu.add_separator()'''
    
    content = content.replace(old_menu, new_menu)
    
    # ========== 5. Add all new methods before the last class methods ==========
    # Find the cleanup_and_exit method and add new methods before it
    
    new_methods = '''
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
        """Track daily and project-level token usage"""
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
                analytics['projects'][project_name] = {'total': 0, 'sessions': set()}
            analytics['projects'][project_name]['total'] += delta
        
        # Save to disk (throttled)
        try:
            self.analytics_file.parent.mkdir(parents=True, exist_ok=True)
            # Convert sets to lists for JSON
            save_data = {
                'daily': analytics['daily'],
                'projects': {k: {'total': v['total']} for k, v in analytics['projects'].items()}
            }
            with open(self.analytics_file, 'w') as f:
                json.dump(save_data, f, indent=2)
        except Exception as e:
            print(f"Analytics save error: {e}")
        
        self._analytics_cache = analytics
        
        # Check budget and send notification
        self.check_budget_notification(analytics, today)
    
    def check_budget_notification(self, analytics, today):
        """Send desktop notification if approaching daily budget"""
        if not HAS_TOAST or not self._notifier:
            return
            
        daily_usage = analytics['daily'].get(today, {}).get('total', 0)
        budget = self._daily_budget
        
        # Throttle notifications (max once per 5 minutes)
        now = time.time()
        if now - self._last_notification_time < 300:
            return
        
        if daily_usage >= budget * 0.9:
            self._notifier.show_toast(
                "Context Monitor ⚠️",
                f"Daily budget 90% used! ({daily_usage:,} / {budget:,} tokens)",
                duration=5,
                threaded=True
            )
            self._last_notification_time = now
        elif daily_usage >= budget * 0.75:
            self._notifier.show_toast(
                "Context Monitor 📊",
                f"Daily budget 75% used ({daily_usage:,} / {budget:,} tokens)",
                duration=3,
                threaded=True
            )
            self._last_notification_time = now
    
    def calculate_time_to_handoff(self):
        """Estimate time until context limit based on recent token burn rate"""
        if not self.current_session:
            return None
            
        # Get recent history for rate calculation
        history = self.load_history().get(self.current_session['id'], [])
        if len(history) < 3:
            return None
        
        # Use last 10 samples for rate calculation
        recent = history[-10:]
        if len(recent) < 2:
            return None
        
        # Calculate tokens per second
        time_span = recent[-1]['ts'] - recent[0]['ts']
        token_span = recent[-1]['tokens'] - recent[0]['tokens']
        
        if time_span <= 0 or token_span <= 0:
            return None
        
        rate_per_second = token_span / time_span
        
        # Calculate remaining tokens until 80% (handoff point)
        context_window = 200000
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
        """Show comprehensive analytics dashboard"""
        win = tk.Toplevel(self.root)
        win.title("Analytics Dashboard")
        win.geometry("600x500")
        win.configure(bg=self.colors['bg'])
        win.attributes('-topmost', True)
        win.resizable(True, True)
        
        # Title
        tk.Label(win, text="📊 Token Analytics Dashboard",
                font=('Segoe UI', 14, 'bold'),
                bg=self.colors['bg'], fg=self.colors['text']).pack(pady=(15, 10))
        
        # Main container with scrollbar
        main_frame = tk.Frame(win, bg=self.colors['bg'])
        main_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # ===== TIME TO HANDOFF =====
        ttf_frame = tk.Frame(main_frame, bg=self.colors['bg2'], padx=15, pady=10)
        ttf_frame.pack(fill='x', pady=(0, 10))
        
        seconds_remaining = self.calculate_time_to_handoff()
        time_str = self.format_time_remaining(seconds_remaining)
        
        tk.Label(ttf_frame, text="⏱️ Estimated Time to Handoff:",
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['text2']).pack(side='left')
        
        time_color = self.colors['green']
        if seconds_remaining is not None:
            if seconds_remaining < 300:  # < 5 mins
                time_color = self.colors['red']
            elif seconds_remaining < 900:  # < 15 mins
                time_color = self.colors['yellow']
        
        tk.Label(ttf_frame, text=time_str,
                font=('Segoe UI', 16, 'bold'), bg=self.colors['bg2'], fg=time_color).pack(side='right')
        
        # ===== TODAY'S USAGE =====
        today_frame = tk.Frame(main_frame, bg=self.colors['bg2'], padx=15, pady=10)
        today_frame.pack(fill='x', pady=(0, 10))
        
        analytics = self.load_analytics()
        today = datetime.now().strftime('%Y-%m-%d')
        today_tokens = analytics['daily'].get(today, {}).get('total', 0)
        budget = self._daily_budget
        budget_pct = min(100, (today_tokens / budget) * 100) if budget > 0 else 0
        
        tk.Label(today_frame, text="📅 Today's Usage:",
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['text2']).pack(anchor='w')
        
        # Progress bar
        bar_frame = tk.Frame(today_frame, bg=self.colors['bg3'], height=20)
        bar_frame.pack(fill='x', pady=5)
        
        bar_color = self.colors['green']
        if budget_pct >= 90:
            bar_color = self.colors['red']
        elif budget_pct >= 75:
            bar_color = self.colors['yellow']
        
        bar_fill = tk.Frame(bar_frame, bg=bar_color, height=20)
        bar_fill.place(relwidth=budget_pct/100, relheight=1)
        
        tk.Label(today_frame, text=f"{today_tokens:,} / {budget:,} tokens ({budget_pct:.0f}%)",
                font=('Segoe UI', 9), bg=self.colors['bg2'], fg=self.colors['text']).pack(anchor='w')
        
        # ===== WEEKLY CHART =====
        week_frame = tk.LabelFrame(main_frame, text=" 📈 Last 7 Days ", 
                                   bg=self.colors['bg2'], fg=self.colors['text'],
                                   font=('Segoe UI', 10, 'bold'), padx=10, pady=10)
        week_frame.pack(fill='x', pady=(0, 10))
        
        weekly = self.get_weekly_summary()
        max_tokens = max(d['tokens'] for d in weekly) if weekly else 1
        
        chart_frame = tk.Frame(week_frame, bg=self.colors['bg2'])
        chart_frame.pack(fill='x')
        
        for day in reversed(weekly):  # Most recent on right
            col = tk.Frame(chart_frame, bg=self.colors['bg2'])
            col.pack(side='left', expand=True, fill='both', padx=2)
            
            # Bar
            bar_height = int((day['tokens'] / max_tokens) * 60) if max_tokens > 0 else 0
            bar = tk.Frame(col, bg=self.colors['blue'], width=30, height=max(2, bar_height))
            bar.pack(side='bottom')
            
            # Day label
            tk.Label(col, text=day['day_name'], font=('Segoe UI', 8),
                    bg=self.colors['bg2'], fg=self.colors['muted']).pack(side='bottom')
            
            # Token count
            tokens_k = day['tokens'] / 1000
            tk.Label(col, text=f"{tokens_k:.0f}k" if day['tokens'] > 0 else "0",
                    font=('Consolas', 7), bg=self.colors['bg2'], fg=self.colors['text2']).pack(side='bottom')
        
        # ===== PROJECT BREAKDOWN =====
        proj_frame = tk.LabelFrame(main_frame, text=" 🗂️ Token Usage by Project ",
                                   bg=self.colors['bg2'], fg=self.colors['text'],
                                   font=('Segoe UI', 10, 'bold'), padx=10, pady=10)
        proj_frame.pack(fill='both', expand=True)
        
        projects = self.get_project_summary()
        if projects:
            total_proj = sum(p['tokens'] for p in projects)
            for proj in projects[:5]:  # Top 5
                pct = (proj['tokens'] / total_proj * 100) if total_proj > 0 else 0
                row = tk.Frame(proj_frame, bg=self.colors['bg2'])
                row.pack(fill='x', pady=2)
                
                tk.Label(row, text=proj['name'], font=('Segoe UI', 9),
                        bg=self.colors['bg2'], fg=self.colors['text'], width=25, anchor='w').pack(side='left')
                tk.Label(row, text=f"{proj['tokens']:,} ({pct:.0f}%)",
                        font=('Consolas', 9), bg=self.colors['bg2'], fg=self.colors['blue']).pack(side='right')
        else:
            tk.Label(proj_frame, text="No project data yet",
                    font=('Segoe UI', 9, 'italic'), bg=self.colors['bg2'], fg=self.colors['muted']).pack()
        
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
                               f"Files exported to:\\n{export_dir}\\n\\n"
                               f"• session_history_{timestamp}.csv\\n"
                               f"• daily_summary_{timestamp}.csv\\n"
                               f"• project_summary_{timestamp}.csv")
            
            # Open folder
            os.startfile(export_dir)
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export: {e}")

'''
    
    # Find where to insert - before cleanup_and_exit method
    insert_marker = "    def cleanup_and_exit(self):"
    if insert_marker in content:
        content = content.replace(insert_marker, new_methods + "\n    def cleanup_and_exit(self):")
    
    # ========== 6. Update load_session to call analytics ==========
    old_save_history = "        self.save_history(self.current_session['id'], tokens_used)"
    new_save_history = '''        self.save_history(self.current_session['id'], tokens_used)
        
        # Track analytics
        project_name = self.get_project_name(self.current_session['id'])
        self.save_analytics(tokens_used, project_name)'''
    
    content = content.replace(old_save_history, new_save_history)
    
    # Write updated file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ All features added successfully!")
    print("New features:")
    print("  - Daily/Weekly token tracking with persistent storage")
    print("  - Project-level aggregation")  
    print("  - Time-to-handoff estimation")
    print("  - Desktop notifications (win10toast)")
    print("  - CSV export to ~/Documents/ContextMonitor/")
    print("  - Analytics Dashboard (press D or right-click)")
    print("  - Daily budget setting with alerts")

if __name__ == "__main__":
    update_context_monitor()
