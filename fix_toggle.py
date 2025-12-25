import re

# Read the file
with open(r'c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.pyw', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the toggle_mini_mode function
old_function = '''    def toggle_mini_mode(self):
        """Toggle between full and mini mode"""
        self.mini_mode = not self.mini_mode
        self.save_settings()
        self.setup_ui()
        self.load_session()'''

new_function = '''    def toggle_mini_mode(self):
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
        # Don't call load_session() - it's expensive and not needed for mode switch'''

content = content.replace(old_function, new_function)

# Write back
with open(r'c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.pyw', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Updated toggle_mini_mode function")
