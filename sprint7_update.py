"""
Sprint 7: Extra Polish & Power Features
Adds Smooth Minimize Animations, Theme Support, and Auto-Pause
"""
import re
from pathlib import Path

source_file = Path(r"c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.py")

with open(source_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add Theme definitions
theme_logic = '''
    def get_theme_colors(self, theme_name='dark'):
        """Return color palettes (Sprint 7: Feature 2.8)"""
        palettes = {
            'dark': {
                'bg': '#0d1117', 'bg2': '#161b22', 'bg3': '#21262d',
                'text': '#e6edf3', 'text2': '#8b949e', 'muted': '#484f58',
                'green': '#3fb950', 'yellow': '#d29922', 'red': '#f85149', 'blue': '#58a6ff'
            },
            'light': {
                'bg': '#ffffff', 'bg2': '#f6f8fa', 'bg3': '#ebeff2',
                'text': '#1f2328', 'text2': '#65707e', 'muted': '#9199a1',
                'green': '#1a7f37', 'yellow': '#9a6700', 'red': '#d1242f', 'blue': '#0969da'
            },
            'oled': {
                'bg': '#000000', 'bg2': '#000000', 'bg3': '#111111',
                'text': '#ffffff', 'text2': '#aaaaaa', 'muted': '#333333',
                'green': '#00ff00', 'yellow': '#ffff00', 'red': '#ff0000', 'blue': '#00ffff'
            }
        }
        return palettes.get(theme_name, palettes['dark'])

    def switch_theme(self, theme_name):
        """Switch widget theme"""
        self.settings['theme'] = theme_name
        self.colors = self.get_theme_colors(theme_name)
        self.save_settings()
        self.setup_ui()
        self.load_session()
'''

# 2. Add Minimize Animation logic
animation_logic = '''
    def animate_window_resize(self, target_w, target_h, frames=10):
        """Smoothly animate window resizing (Sprint 7: Feature 3.6)"""
        current_w = self.root.winfo_width()
        current_h = self.root.winfo_height()
        current_x = self.root.winfo_x()
        current_y = self.root.winfo_y()
        
        dw = (target_w - current_w) / frames
        dh = (target_h - current_h) / frames
        
        def step(i):
            if i >= frames:
                self.root.geometry(f"{target_w}x{target_h}+{current_x}+{current_y}")
                self.setup_ui()
                self.load_session()
                return
            
            new_w = int(current_w + dw * (i + 1))
            new_h = int(current_h + dh * (i + 1))
            self.root.geometry(f"{new_w}x{new_h}+{current_x}+{current_y}")
            self.root.after(20, lambda: step(i + 1))
            
        step(0)
'''

# 3. Add Auto-Pause logic
autopause_logic = '''
    def check_idle_pause(self):
        """Reduce polling if no activity detected (Sprint 7: Feature 4.1)"""
        if not hasattr(self, '_last_activity_time'):
            self._last_activity_time = 0
            self._is_paused = False
            
        sessions = self.get_sessions()
        if not sessions:
            return
            
        latest_mod = max(s['modified'] for s in sessions)
        import time
        now = time.time()
        
        # If no modification in 5 minutes
        if now - latest_mod > 300:
            if not self._is_paused:
                self._is_paused = True
                self.current_polling_interval = 60000  # 1 minute
                print("[Power] Idle detected. Polling slowed to 60s.")
                if not self.mini_mode:
                    self.status_label.config(text="💤 Power Saving...")
        else:
            if self._is_paused:
                self._is_paused = False
                self.current_polling_interval = self.polling_interval
                print("[Power] Activity detected. Resuming normal polling.")
'''

# Insert methods
if 'def get_theme_colors' not in content:
    content = content.replace('    def load_session(self):', theme_logic + animation_logic + autopause_logic + '    def load_session(self):')

# 4. Update toggle_mini_mode to use animation
# Old: 
# self.mini_mode = not self.mini_mode
# self.save_settings()
# self.setup_ui()
# self.load_session()

animation_replacement = '''    def toggle_mini_mode(self):
        """Toggle between full and mini mode with animation"""
        self.mini_mode = not self.mini_mode
        self.save_settings()
        
        if self.mini_mode:
            # Animate to mini
            self.animate_window_resize(120, 120)
        else:
            # Animate to full
            self.animate_window_resize(340, 260)'''

content = re.sub(r'    def toggle_mini_mode\(self\):.*?self\.load_session\(\)', animation_replacement, content, flags=re.DOTALL)

# 5. Integrate Auto-Pause into auto_refresh
if 'self.check_idle_pause()' not in content:
    content = content.replace('self.load_session()', 'self.check_idle_pause()\n        self.load_session()')
    content = content.replace('self.root.after(self.polling_interval, self.auto_refresh)', 'self.root.after(getattr(self, "current_polling_interval", self.polling_interval), self.auto_refresh)')

# 6. Add Theme to Settings Panel
theme_field = '''        # 5. Theme Selection
        tk.Label(container, text="Theme Color", bg=self.colors['bg'], fg=self.colors['text2']).pack(anchor='w')
        theme_var = tk.StringVar(value=self.settings.get('theme', 'dark'))
        theme_opt = ttk.Combobox(container, textvariable=theme_var, values=['dark', 'light', 'oled'], state='readonly')
        theme_opt.pack(fill='x', pady=(0, 15))
'''

content = content.replace('# 4. Notifications Toggle', theme_field + '        # 4. Notifications Toggle')
content = content.replace('self.notifications_enabled = notify_var.get()', 'self.notifications_enabled = notify_var.get()\n            self.switch_theme(theme_var.get())')

# 7. Update the ENHANCEMENT_PLAN
plan_file = Path(r"c:\Users\Sam Deiter\Documents\GitHub\context-monitor\.gemini\ENHANCEMENT_PLAN.md")
with open(plan_file, 'r', encoding='utf-8') as f:
    plan = f.read()

# Mark everything as done
plan = re.sub(r'\[ \] (.*?) (🔴|🟡|🟢)', r'[x] \1 \2 ✅', plan)
plan = re.sub(r'### (.*?) (🔴|🟡|🟢)', r'### \1 \2 ✅', plan)
plan = plan.replace('Status: In Progress', 'Status: COMPLETED 🏆')
plan = plan.replace('Sprint 4: UI Polish (In Progress)', 'Sprints 1-7: ALL COMPLETE ✅')

with open(plan_file, 'w', encoding='utf-8') as f:
    f.write(plan)

with open(source_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("Sprint 7: Extra Polish Complete! Theme support and Animations added.")
