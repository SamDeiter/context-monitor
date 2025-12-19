"""
Script to add conversation selection dropdown to context_monitor.py
"""
import re

def add_conversation_selector():
    file_path = r"c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.py"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix 1: Add ttk import
    old_import = "from tkinter import messagebox"
    new_import = "from tkinter import messagebox, ttk"
    content = content.replace(old_import, new_import)
    
    # Fix 2: Add selected_session_id in __init__
    old_init_cache = """        # Project name cache
        self.project_name_cache = {}
        self.project_name_timestamp = {}"""
    
    new_init_cache = """        # Project name cache
        self.project_name_cache = {}
        self.project_name_timestamp = {}
        
        # Selected session (None = auto-select most recent)
        self.selected_session_id = self.settings.get('selected_session_id', None)
        self.session_display_map = {}"""
    
    content = content.replace(old_init_cache, new_init_cache)
    
    # Fix 3: Replace static label with Combobox in setup_ui()
    old_session_ui = """            tk.Label(info, text="PROJECT", font=('Segoe UI', 8),
                    bg=self.colors['bg2'], fg=self.colors['muted']).pack(anchor='w', pady=(8,0))
            self.session_label = tk.Label(info, text="—", font=('Segoe UI', 8),
                                          bg=self.colors['bg2'], fg=self.colors['text2'])
            self.session_label.pack(anchor='w')
            self.session_label.bind('<Button-3>', self.show_context_menu)"""
    
    new_session_ui = """            tk.Label(info, text="PROJECT", font=('Segoe UI', 8),
                    bg=self.colors['bg2'], fg=self.colors['muted']).pack(anchor='w', pady=(8,0))
            
            # Conversation selector dropdown
            style = ttk.Style()
            style.theme_use('clam')
            style.configure('TCombobox',
                            fieldbackground=self.colors['bg3'],
                            background=self.colors['bg2'],
                            foreground=self.colors['text'],
                            arrowcolor=self.colors['blue'],
                            borderwidth=0,
                            selectbackground=self.colors['blue'],
                            selectforeground='white')
            style.map('TCombobox', 
                      fieldbackground=[('readonly', self.colors['bg3'])],
                      selectbackground=[('readonly', self.colors['bg3'])])
            
            self.session_combo = ttk.Combobox(info, state='readonly', 
                                               font=('Segoe UI', 8),
                                               width=25,
                                               style='TCombobox')
            self.session_combo.pack(anchor='w', fill='x', pady=(2,0))
            self.session_combo.bind('<<ComboboxSelected>>', self.on_session_selected)
            self.session_combo.bind('<Button-3>', self.show_context_menu)"""
    
    content = content.replace(old_session_ui, new_session_ui)
    
    # Fix 4: Update tooltip reference from session_label to session_combo
    old_tooltip = """            self.create_tooltip(self.session_label, "Current Project\\nAuto-detected from VS Code/GitHub")"""
    new_tooltip = """            self.create_tooltip(self.session_combo, "Select Conversation\\nChoose which conversation to monitor")"""
    content = content.replace(old_tooltip, new_tooltip)
    
    # Fix 5: Add populate_session_dropdown() and on_session_selected() methods after get_sessions()
    # Find the end of get_sessions method
    pattern = r'(    def get_sessions\(self\):.*?return sessions\r?\n)'
    
    new_methods = r'''\1
    def populate_session_dropdown(self):
        """Populate the conversation dropdown with available sessions"""
        if self.mini_mode or not hasattr(self, 'session_combo'):
            return
            
        sessions = self.get_sessions()
        if not sessions:
            self.session_combo['values'] = ['No sessions available']
            self.session_combo.current(0)
            self.session_combo.config(state='disabled')
            return
        
        # Build dropdown options: "ProjectName (session_id[:8])"
        options = []
        session_map = {}  # Map display text to session ID
        
        for session in sessions:
            session_id = session['id']
            project_name = self.get_project_name(session_id)
            display_text = f"{project_name} ({session_id[:8]}...)"
            options.append(display_text)
            session_map[display_text] = session_id
        
        self.session_combo['values'] = options
        self.session_combo.config(state='readonly')
        self.session_display_map = session_map
        
        # Select the previously selected session, or default to most recent
        if self.selected_session_id:
            # Find the display text for the selected session
            for display_text, sid in session_map.items():
                if sid == self.selected_session_id:
                    self.session_combo.set(display_text)
                    return
        
        # Default to most recent (first in list)
        if options:
            self.session_combo.current(0)
            self.selected_session_id = sessions[0]['id']
    
    def on_session_selected(self, event=None):
        """Handle conversation selection from dropdown"""
        selected_text = self.session_combo.get()
        if selected_text in self.session_display_map:
            self.selected_session_id = self.session_display_map[selected_text]
            self.save_settings()  # Persist selection
            self.load_session()  # Reload with new selection
    
'''
    
    content = re.sub(pattern, new_methods, content, flags=re.DOTALL)
    
    # Fix 6: Update load_session() to use selected session
    old_load_session_start = """    def load_session(self):
        sessions = self.get_sessions()
        if not sessions:
            if not self.mini_mode and hasattr(self, 'status_label'):
                self.status_label.config(text="⚠ No sessions")
            return
            
        self.current_session = sessions[0]"""
    
    new_load_session_start = """    def load_session(self):
        sessions = self.get_sessions()
        if not sessions:
            if not self.mini_mode and hasattr(self, 'status_label'):
                self.status_label.config(text="⚠ No sessions")
            return
        
        # Use selected session if available, otherwise most recent
        if self.selected_session_id:
            # Find the selected session in the list
            selected = next((s for s in sessions if s['id'] == self.selected_session_id), None)
            if selected:
                self.current_session = selected
            else:
                # Selected session no longer exists, fall back to most recent
                self.current_session = sessions[0]
                self.selected_session_id = sessions[0]['id']
        else:
            # Auto-select most recent
            self.current_session = sessions[0]
            self.selected_session_id = sessions[0]['id']"""
    
    content = content.replace(old_load_session_start, new_load_session_start)
    
    # Fix 7: Update save_settings() to persist selected_session_id
    old_save_settings = """            json.dump({
                'alpha': self.root.attributes('-alpha'),
                'mini_mode': self.mini_mode
            }, f, indent=2)"""
    
    new_save_settings = """            json.dump({
                'alpha': self.root.attributes('-alpha'),
                'mini_mode': self.mini_mode,
                'selected_session_id': self.selected_session_id
            }, f, indent=2)"""
    
    content = content.replace(old_save_settings, new_save_settings)
    
    # Fix 8: Update auto_refresh() to refresh dropdown
    old_auto_refresh = """    def auto_refresh(self, reschedule=True):
        self.load_session()
        if reschedule:
            self.root.after(15000, self.auto_refresh)"""
    
    new_auto_refresh = """    def auto_refresh(self, reschedule=True):
        if not self.mini_mode and hasattr(self, 'session_combo'):
            self.populate_session_dropdown()
        self.load_session()
        if reschedule:
            self.root.after(15000, self.auto_refresh)"""
    
    content = content.replace(old_auto_refresh, new_auto_refresh)
    
    # Fix 9: Call populate_session_dropdown in setup_ui after creating the combo
    # Add it right after the session_combo creation
    old_setup_end = """            self.setup_ui()
            self.load_session()"""
    
    new_setup_end = """            self.setup_ui()
            if not self.mini_mode and hasattr(self, 'session_combo'):
                self.populate_session_dropdown()
            self.load_session()"""
    
    content = content.replace(old_setup_end, new_setup_end)
    
    # Write the modified content back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✓ Successfully added conversation selection dropdown!")
    print("  - Added ttk import")
    print("  - Added selected_session_id state variable")
    print("  - Replaced static label with Combobox")
    print("  - Added populate_session_dropdown() method")
    print("  - Added on_session_selected() handler")
    print("  - Updated load_session() to use selected session")
    print("  - Updated save_settings() to persist selection")
    print("  - Updated auto_refresh() to refresh dropdown")
    print("  - Added dark theme styling for Combobox")

if __name__ == "__main__":
    add_conversation_selector()
