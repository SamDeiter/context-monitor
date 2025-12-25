import re

# Read the file
with open(r'c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.pyw', 'r', encoding='utf-8') as f:
    content = f.read()

# Find where to add create_button method (before setup_ui)
insert_marker = '    def setup_ui(self):'
insert_pos = content.find(insert_marker)

if insert_pos == -1:
    print("ERROR: Could not find insertion point")
    exit(1)

# New method to insert
new_method = '''    def create_button(self, parent, text, command):
        """Create a styled button for Full mode"""
        btn = tk.Label(parent, text=text, font=('Segoe UI', 8),
                      bg=self.colors['bg3'], fg=self.colors['text'],
                      cursor='hand2', padx=8, pady=4,
                      relief='flat', borderwidth=1)
        btn.bind('<Button-1>', lambda e: command())
        btn.bind('<Enter>', lambda e: btn.config(bg=self.colors['blue'], fg='white'))
        btn.bind('<Leave>', lambda e: btn.config(bg=self.colors['bg3'], fg=self.colors['text']))
        return btn
    
'''

# Insert the new method
content = content[:insert_pos] + new_method + content[insert_pos:]

# Write back
with open(r'c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.pyw', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Added create_button() helper method")
