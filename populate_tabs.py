import re

# Read the file
with open(r'c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.pyw', 'r', encoding='utf-8') as f:
    content = f.read()

# Find render_diagnostics_inline and replace with actual content
old_diagnostics = '''    def render_diagnostics_inline(self):
        \"\"\"Render system diagnostics inline\"\"\"
        container = tk.Frame(self.content_frame, bg=self.colors['bg2'], padx=15, pady=15)
        container.pack(fill='both', expand=True)
        
        tk.Label(container, text=\"System Diagnostics\", font=('Segoe UI', 12, 'bold'),
                bg=self.colors['bg2'], fg=self.colors['text']).pack(anchor='w', pady=(0, 10))
        
        # Placeholder - will add actual diagnostics
        tk.Label(container, text=\"System health information will appear here\",
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['muted']).pack()'''

new_diagnostics = '''    def render_diagnostics_inline(self):
        \"\"\"Render system diagnostics inline\"\"\"
        procs = self.get_antigravity_processes()
        files = self.get_large_conversations()
        limits = self.thresholds
        
        total_mem = sum(p.get('Mem', 0) for p in procs)
        
        container = tk.Frame(self.content_frame, bg=self.colors['bg2'], padx=15, pady=15)
        container.pack(fill='both', expand=True)
        
        # Title
        tk.Label(container, text=\"🔧 System Diagnostics\", font=('Segoe UI', 12, 'bold'),
                bg=self.colors['bg2'], fg=self.colors['text']).pack(anchor='w', pady=(0, 10))
        
        # System overview
        info_frame = tk.Frame(container, bg=self.colors['bg'], padx=10, pady=8)
        info_frame.pack(fill='x', pady=(0, 10))
        
        tk.Label(info_frame, text=f\"💾 RAM: {self.total_ram_mb // 1024} GB  |  ⚙️ Processes: {len(procs)}  |  📊 Total Memory: {total_mem}MB\",
                font=('Segoe UI', 10), bg=self.colors['bg'], fg=self.colors['text']).pack(anchor='w')
        
        # Process list
        tk.Label(container, text=\"Process Memory:\", font=('Segoe UI', 9, 'bold'),
                bg=self.colors['bg2'], fg=self.colors['text']).pack(anchor='w', pady=(5, 5))
        
        for p in procs[:8]:
            mem = p.get('Mem', 0)
            ptype = p.get('Type', 'Unknown')
            color = self.colors['red'] if mem > limits['proc_crit'] else (self.colors['yellow'] if mem > limits['proc_warn'] else self.colors['green'])
            
            tk.Label(container, text=f\"  • {ptype}: {mem}MB\",
                    font=('Segoe UI', 9), bg=self.colors['bg2'], fg=color).pack(anchor='w')'''

content = content.replace(old_diagnostics, new_diagnostics)

# Find render_token_stats_inline and replace
old_token_stats = '''    def render_token_stats_inline(self):
        \"\"\"Render token statistics inline\"\"\"
        container = tk.Frame(self.content_frame, bg=self.colors['bg2'], padx=15, pady=15)
        container.pack(fill='both', expand=True)
        
        tk.Label(container, text=\"Token Statistics\", font=('Segoe UI', 12, 'bold'),
                bg=self.colors['bg2'], fg=self.colors['text']).pack(anchor='w', pady=(0, 10))
        
        # Placeholder - will add actual stats
        tk.Label(container, text=\"Detailed token breakdown will appear here\",
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['muted']).pack()'''

new_token_stats = '''    def render_token_stats_inline(self):
        \"\"\"Render token statistics inline\"\"\"
        if not self.current_session:
            return
        
        context_window = self._context_window
        tokens_used = self.current_session['estimated_tokens'] // 10
        tokens_left = max(0, context_window - tokens_used)
        percent_used = min(100, round((tokens_used / context_window) * 100))
        
        container = tk.Frame(self.content_frame, bg=self.colors['bg2'], padx=15, pady=15)
        container.pack(fill='both', expand=True)
        
        # Title
        tk.Label(container, text=\"📊 Token Usage Dashboard\", font=('Segoe UI', 12, 'bold'),
                bg=self.colors['bg2'], fg=self.colors['text']).pack(anchor='w', pady=(0, 10))
        
        # Context window
        tk.Label(container, text=\"Context Window:\", font=('Segoe UI', 9, 'bold'),
                bg=self.colors['bg2'], fg=self.colors['text']).pack(anchor='w', pady=(5, 5))
        
        usage_color = self.colors['red'] if percent_used >= 80 else (self.colors['yellow'] if percent_used >= 60 else self.colors['green'])
        
        tk.Label(container, text=f\"  • Tokens Used: {tokens_used:,} ({percent_used}%)\",
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=usage_color).pack(anchor='w')
        tk.Label(container, text=f\"  • Tokens Remaining: {tokens_left:,}\",
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['blue']).pack(anchor='w')
        tk.Label(container, text=f\"  • Total Capacity: {context_window:,}\",
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['muted']).pack(anchor='w')
        
        # Breakdown
        estimated_input = int(tokens_used * 0.4)
        estimated_output = int(tokens_used * 0.6)
        
        tk.Label(container, text=\"Estimated Breakdown:\", font=('Segoe UI', 9, 'bold'),
                bg=self.colors['bg2'], fg=self.colors['text']).pack(anchor='w', pady=(10, 5))
        
        tk.Label(container, text=f\"  • Input (Your messages): {estimated_input:,}\",
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['blue']).pack(anchor='w')
        tk.Label(container, text=f\"  • Output (Assistant): {estimated_output:,}\",
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['green']).pack(anchor='w')'''

content = content.replace(old_token_stats, new_token_stats)

# Find render_analytics_inline and replace
old_analytics = '''    def render_analytics_inline(self):
        \"\"\"Render analytics dashboard inline\"\"\"
        container = tk.Frame(self.content_frame, bg=self.colors['bg2'], padx=15, pady=15)
        container.pack(fill='both', expand=True)
        
        tk.Label(container, text=\"Analytics Dashboard\", font=('Segoe UI', 12, 'bold'),
                bg=self.colors['bg2'], fg=self.colors['text']).pack(anchor='w', pady=(0, 10))
        
        # Placeholder - will add actual analytics
        tk.Label(container, text=\"Analytics data will appear here\",
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['muted']).pack()'''

new_analytics = '''    def render_analytics_inline(self):
        \"\"\"Render analytics dashboard inline\"\"\"
        container = tk.Frame(self.content_frame, bg=self.colors['bg2'], padx=15, pady=15)
        container.pack(fill='both', expand=True)
        
        # Title
        tk.Label(container, text=\"📊 Analytics Dashboard\", font=('Segoe UI', 12, 'bold'),
                bg=self.colors['bg2'], fg=self.colors['text']).pack(anchor='w', pady=(0, 10))
        
        # Get analytics data
        analytics = self.load_analytics()
        today_key = datetime.now().strftime(\"%Y-%m-%d\")
        today_data = analytics.get('daily', {}).get(today_key, {})
        
        # Today's usage
        tk.Label(container, text=\"Today's Usage:\", font=('Segoe UI', 9, 'bold'),
                bg=self.colors['bg2'], fg=self.colors['text']).pack(anchor='w', pady=(5, 5))
        
        total_today = today_data.get('total_tokens', 0)
        tk.Label(container, text=f\"  • Total Tokens: {total_today:,}\",
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['text']).pack(anchor='w')
        
        # Session count
        sessions_today = today_data.get('session_count', 0)
        tk.Label(container, text=f\"  • Sessions: {sessions_today}\",
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['text']).pack(anchor='w')
        
        # Weekly summary
        tk.Label(container, text=\"Last 7 Days:\", font=('Segoe UI', 9, 'bold'),
                bg=self.colors['bg2'], fg=self.colors['text']).pack(anchor='w', pady=(10, 5))
        
        week_total = 0
        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).strftime(\"%Y-%m-%d\")
            day_data = analytics.get('daily', {}).get(date, {})
            week_total += day_data.get('total_tokens', 0)
        
        tk.Label(container, text=f\"  • Total Tokens: {week_total:,}\",
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['text']).pack(anchor='w')
        tk.Label(container, text=f\"  • Daily Average: {week_total // 7:,}\",
                font=('Segoe UI', 10), bg=self.colors['bg2'], fg=self.colors['muted']).pack(anchor='w')'''

content = content.replace(old_analytics, new_analytics)

# Write back
with open(r'c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.pyw', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Populated all tab content with real data")
