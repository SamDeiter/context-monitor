"""
Sprint 5: Settings & QoL Implementation
Adds a Settings Panel and Windows Startup support to context_monitor.py
"""
import re
from pathlib import Path

source_file = Path(r"c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.py")

with open(source_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add show_settings method
settings_method = '''
    def show_settings(self):
        """Show settings configuration modal (Sprint 5: Feature 4.2)"""
        from tkinter import ttk
        win = tk.Toplevel(self.root)
        win.title("Monitor Settings")
        win.geometry("350x450")
        win.configure(bg=self.colors['bg'])
        win.attributes('-topmost', True)
        win.resizable(False, False)
        
        # Header
        tk.Label(win, text="⚙️ Widget Settings", font=('Segoe UI', 12, 'bold'),
                bg=self.colors['bg'], fg=self.colors['text']).pack(pady=15)
        
        # Form Container
        container = tk.Frame(win, bg=self.colors['bg'], padx=20)
        container.pack(fill='both', expand=True)
        
        # 1. Polling Interval
        tk.Label(container, text="Refresh Speed (ms)", bg=self.colors['bg'], fg=self.colors['text2']).pack(anchor='w')
        speed_var = tk.IntVar(value=self.polling_interval)
        speed_slider = tk.Scale(container, from_=1000, to=30000, orient='horizontal',
                               variable=speed_var, bg=self.colors['bg'], fg=self.colors['text'],
                               highlightthickness=0)
        speed_slider.pack(fill='x', pady=(0, 15))
        
        # 2. Transparency
        tk.Label(container, text="Transparency", bg=self.colors['bg'], fg=self.colors['text2']).pack(anchor='w')
        alpha_var = tk.DoubleVar(value=self.root.attributes('-alpha'))
        alpha_slider = tk.Scale(container, from_=0.3, to=1.0, resolution=0.05, orient='horizontal',
                               variable=alpha_var, bg=self.colors['bg'], fg=self.colors['text'],
                               highlightthickness=0)
        alpha_slider.pack(fill='x', pady=(0, 15))
        
        # 3. Startup Toggle
        startup_var = tk.BooleanVar(value=self.check_startup_status())
        startup_check = tk.Checkbutton(container, text="Launch on Windows Startup", 
                                      variable=startup_var, bg=self.colors['bg'], fg=self.colors['text'],
                                      selectcolor=self.colors['bg2'], activebackground=self.colors['bg'])
        startup_check.pack(anchor='w', pady=(0, 10))
        
        # 4. Notifications Toggle
        notify_var = tk.BooleanVar(value=getattr(self, 'notifications_enabled', True))
        notify_check = tk.Checkbutton(container, text="Enable Token Notifications", 
                                     variable=notify_var, bg=self.colors['bg'], fg=self.colors['text'],
                                     selectcolor=self.colors['bg2'], activebackground=self.colors['bg'])
        notify_check.pack(anchor='w', pady=(0, 15))
        
        def save_and_close():
            self.polling_interval = speed_var.get()
            self.root.attributes('-alpha', alpha_var.get())
            self.notifications_enabled = notify_var.get()
            self.toggle_startup(startup_var.get())
            self.save_settings()
            win.destroy()
            messagebox.showinfo("Settings", "Settings saved successfully!")
            
        # Save Button
        save_btn = tk.Button(win, text="Save & Apply", command=save_and_close,
                            bg=self.colors['blue'], fg='white', font=('Segoe UI', 10, 'bold'),
                            padx=20, pady=5, bd=0, cursor='hand2')
        save_btn.pack(pady=20)

    def check_startup_status(self):
        """Check if app is in Windows Run registry (Sprint 5: Feature 4.3)"""
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\\Microsoft\\Windows\\CurrentVersion\\Run", 0, winreg.KEY_READ)
            try:
                winreg.QueryValueEx(key, "AntigravityContextMonitor")
                return True
            except FileNotFoundError:
                return False
            finally:
                winreg.CloseKey(key)
        except:
            return False

    def toggle_startup(self, enable):
        """Add/Remove from Windows startup (Sprint 5: Feature 4.3)"""
        import sys
        import winreg
        
        path = r"Software\\Microsoft\\Windows\\CurrentVersion\\Run"
        app_path = f'"{sys.executable}" "{Path(__file__).absolute()}"'
        
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_SET_VALUE)
            if enable:
                winreg.SetValueEx(key, "AntigravityContextMonitor", 0, winreg.REG_SZ, app_path)
            else:
                try:
                    winreg.DeleteValue(key, "AntigravityContextMonitor")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as e:
            print(f"Startup toggle error: {e}")
'''

# Insert methods before load_session
if 'def show_settings' not in content:
    content = content.replace('    def load_session(self):', settings_method + '    def load_session(self):')

# 2. Add "Settings" to Context Menu
if 'menu.add_command(label="⚙️ Settings"' not in content:
    content = content.replace(
        'menu.add_command(label="📈 Show Chart", command=self.show_history)',
        'menu.add_command(label="📈 Show Chart", command=self.show_history)\n        menu.add_command(label="⚙️ Settings", command=self.show_settings)'
    )

# 3. Update the ENHANCEMENT_PLAN
plan_file = Path(r"c:\Users\Sam Deiter\Documents\GitHub\context-monitor\.gemini\ENHANCEMENT_PLAN.md")
with open(plan_file, 'r', encoding='utf-8') as f:
    plan = f.read()

plan = plan.replace('- [ ] 4.2 Settings Panel GUI', '- [x] 4.2 Settings Panel GUI ✅')
plan = plan.replace('- [ ] 4.3 Optional Windows Startup', '- [x] 4.3 Optional Windows Startup ✅')
plan = plan.replace('*Last Updated: 2025-12-21 (Sprint 1-4 complete)*', '*Last Updated: 2025-12-21 (Sprint 1-5 complete)*')

with open(plan_file, 'w', encoding='utf-8') as f:
    f.write(plan)

with open(source_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("Sprint 5 Implementation Complete!")
