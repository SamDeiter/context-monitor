"""
Sprint 6: Final Polish & Master Features
Adds Session Picker Dropdown and Global Hotkey support
"""
import re
from pathlib import Path

source_file = Path(r"c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.py")

with open(source_file, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Add ttk and hotkey imports
if 'from tkinter import ttk' not in content:
    content = content.replace('from tkinter import messagebox', 'from tkinter import messagebox, ttk')

# 2. Add Hotkey registration method
hotkey_methods = '''
    def setup_hotkey(self):
        """Register Win+Shift+T as a global hotkey (Sprint 6: Feature 2.6)"""
        try:
            # Register hotkey (Win + Shift + T)
            # MOD_WIN = 0x0008, MOD_SHIFT = 0x0004
            # T key code = 0x54
            hotkey_id = 1
            if ctypes.windll.user32.RegisterHotKey(None, hotkey_id, 0x0008 | 0x0004, 0x54):
                print("✓ Global Hotkey registered: Win+Shift+T")
                thread = threading.Thread(target=self.wait_for_hotkey, daemon=True)
                thread.start()
            else:
                print("✗ Failed to register Hotkey")
        except Exception as e:
            print(f"Hotkey error: {e}")

    def wait_for_hotkey(self):
        """Wait for the hotkey event in a separate thread"""
        import ctypes.wintypes
        msg = ctypes.wintypes.MSG()
        while ctypes.windll.user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == 0x0312: # WM_HOTKEY
                self.root.after(0, self.toggle_visibility)
            ctypes.windll.user32.TranslateMessage(ctypes.byref(msg))
            ctypes.windll.user32.DispatchMessageW(ctypes.byref(msg))

    def toggle_visibility(self):
        """Toggle widget visibility"""
        if self.root.winfo_viewable():
            self.root.withdraw()
            if HAS_TRAY and hasattr(self, 'icon'):
                self.icon.notify("Monitor Hidden. Press Win+Shift+T to show.", "Context Monitor")
        else:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes('-topmost', True)
'''

# 3. Add handle_session_change method
session_change_method = '''
    def handle_session_change(self, event):
        """Handle session selection from dropdown (Sprint 6: Feature 2.1)"""
        selection = self.session_picker.get()
        # Find session ID from the selected display name
        sessions = self.get_sessions()
        for s in sessions:
            name = self.get_project_name(s['id'])
            if name == selection:
                self.switch_session(s['id'])
                break
'''

# Insert methods
if 'def setup_hotkey' not in content:
    content = content.replace('    def load_session(self):', hotkey_methods + session_change_method + '    def load_session(self):')

# 4. Modify setup_ui for Session Picker
session_label_pattern = r'self\.session_label = tk\.Label\(info, text="—", font=\(\'Segoe UI\', 8\),.*?self\.session_label\.pack\(anchor=\'w\'\).*?self\.session_label\.bind\(\'\<Button-3\>\', self\.show_context_menu\)'
session_picker_replacement = '''self.session_picker = ttk.Combobox(info, font=('Segoe UI', 8), state='readonly')
            self.session_picker.pack(fill='x', pady=(2, 0))
            self.session_picker.bind('<<ComboboxSelected>>', self.handle_session_change)
            self.session_picker.bind('<Button-3>', self.show_context_menu)'''

content = re.sub(session_label_pattern, session_picker_replacement, content, flags=re.DOTALL)

# 5. Update load_session to refresh Picker values
refresh_picker_code = '''
            # Update Session Picker values
            sessions = self.get_sessions()
            project_names = [self.get_project_name(s['id']) for s in sessions]
            self.session_picker['values'] = project_names
            
            # Set current selection
            current_name = self.get_project_name(self.current_session['id'])
            if self.session_picker.get() != current_name:
                self.session_picker.set(current_name)
'''

content = content.replace('self.session_label.config(text=project_name)', refresh_picker_code)

# 6. Initialize Hotkey in __init__
if 'self.setup_hotkey()' not in content:
    content = content.replace('self.setup_ui()', 'self.setup_hotkey()\n        self.setup_ui()')

# 7. Update layout for better fit with Combobox
content = content.replace('self.root.geometry(f"340x240+{x_pos}+{y_pos}")', 'self.root.geometry(f"340x260+{x_pos}+{y_pos}")')

# 8. Update ENHANCEMENT_PLAN
plan_file = Path(r"c:\Users\Sam Deiter\Documents\GitHub\context-monitor\.gemini\ENHANCEMENT_PLAN.md")
with open(plan_file, 'r', encoding='utf-8') as f:
    plan = f.read()

plan = plan.replace('- [ ] 2.1 Session Picker Dropdown', '- [x] 2.1 Session Picker Dropdown ✅')
plan = plan.replace('- [ ] 2.6 Global Hotkey (Win+Shift+T)', '- [x] 2.6 Global Hotkey (Win+Shift+T) ✅')
plan = plan.replace('Status: In Progress (Sprint 1-5 complete)', 'Status: COMPLETED 🎉')
plan = plan.replace('*Last Updated: 2025-12-21 (Sprint 1-5 complete)*', '*Last Updated: 2025-12-21 (ALL SPRINTS COMPLETE)*')

with open(plan_file, 'w', encoding='utf-8') as f:
    f.write(plan)

with open(source_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("Final Polish Complete! All Sprints Finished.")
