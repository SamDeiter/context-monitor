import re

# Read the file
with open(r'c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.pyw', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the Full mode header section and add session menu button
old_section = '''            title = tk.Label(header, text="📊 Context Monitor - Full", font=('Segoe UI', 10, 'bold'),
                            bg=self.colors['bg3'], fg=self.colors['text'])
            title.pack(side='left', padx=10, pady=5)'''

new_section = '''            title = tk.Label(header, text="📊 Context Monitor - Full", font=('Segoe UI', 10, 'bold'),
                            bg=self.colors['bg3'], fg=self.colors['text'])
            title.pack(side='left', padx=10, pady=5)
            
            # Session menu button
            session_btn = tk.Label(header, text="📂 Sessions", font=('Segoe UI', 9),
                                  bg=self.colors['bg3'], fg=self.colors['blue'], cursor='hand2',
                                  padx=8, pady=2)
            session_btn.pack(side='left', padx=5)
            session_btn.bind('<Button-1>', self.show_context_menu)'''

content = content.replace(old_section, new_section)

# Write back
with open(r'c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.pyw', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Added session menu button to Full mode header")
