"""
Sprint 4 UI Polish Implementation
Adds Sparkline Graph and Status LED to context_monitor.py
"""
import re
from pathlib import Path

source_file = Path(r"c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.py")

with open(source_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

content = "".join(lines)

# 1. Add draw_sparkline method
sparkline_method = '''
    def draw_sparkline(self):
        """Draw a mini bar graph of recent deltas (Sprint 4: Feature 3.2)"""
        if not hasattr(self, 'sparkline_canvas') or not self.current_session:
            return
            
        self.sparkline_canvas.delete('all')
        
        history_data = self.load_history().get(self.current_session['id'], [])
        # Get last 12 non-zero deltas (or just recent entries if zero is common)
        recent_deltas = [h.get('delta', 0) for h in history_data][-12:]
        
        if not recent_deltas:
            return
            
        w = 80
        h = 40
        max_delta = max(max(recent_deltas), 1000) # Scale at least to 1k
        bar_width = (w // len(recent_deltas)) - 2
        
        for i, delta in enumerate(recent_deltas):
            # Calculate height (min 2px)
            bar_h = max(2, int((delta / max_delta) * (h - 4)))
            x0 = i * (bar_width + 2)
            y0 = h - bar_h
            x1 = x0 + bar_width
            y1 = h
            
            # Color based on magnitude
            if delta > 5000:
                color = self.colors['red']
            elif delta > 2000:
                color = self.colors['yellow']
            elif delta > 0:
                color = self.colors['green']
            else:
                color = self.colors['blue']
                
            self.sparkline_canvas.create_rectangle(x0, y0, x1, y1, fill=color, outline='')
'''

# 2. Add update_led method
led_method = '''
    def update_led(self):
        """Update the status LED indicator (Sprint 4: Feature 3.4)"""
        if not hasattr(self, 'led_canvas'):
            return
            
        self.led_canvas.delete('all')
        
        color = self.colors['green']
        if self.current_percent >= 80:
            color = self.colors['red']
        elif self.current_percent >= 60:
            color = self.colors['yellow']
            
        # Draw the LED circle
        r = 5
        self.led_canvas.create_oval(2, 2, 12, 12, fill=color, outline='')
        
        # Add a subtle glow/shine
        self.led_canvas.create_oval(4, 4, 7, 7, fill='white', outline='', stipple='gray50')
'''

# Insert methods before load_session
if 'def draw_sparkline' not in content:
    content = content.replace('    def load_session(self):', sparkline_method + led_method + '    def load_session(self):')

# 3. Modify setup_ui to include Sparkline and LED
# Find the history_frame labels section and replace it
history_pattern = r'            tk\.Label\(history_frame, text="RECENT".*?            for i in range\(5\):.*?self\.history_labels\.append\(lbl\)'
history_replacement = '''            tk.Label(history_frame, text="RECENT", font=('Segoe UI', 7),
                    bg=self.colors['bg3'], fg=self.colors['muted']).pack(anchor='center')
            
            self.sparkline_canvas = tk.Canvas(history_frame, width=80, height=45, 
                                            bg=self.colors['bg3'], highlightthickness=0)
            self.sparkline_canvas.pack(pady=4)
            self.sparkline_canvas.bind('<Button-3>', self.show_context_menu)'''

content = re.sub(history_pattern, history_replacement, content, flags=re.DOTALL)

# Add LED canvas to status bar
led_pattern = r'self\.status_label = tk\.Label\(self\.status_frame, text="✓ Loading\.\.\.",'
led_replacement = '''self.led_canvas = tk.Canvas(self.status_frame, width=15, height=15, 
                                       bg=self.colors['bg3'], highlightthickness=0)
            self.led_canvas.pack(side='left', padx=(0, 5))
            self.update_led()
            
            self.status_label = tk.Label(self.status_frame, text="✓ Loading...",'''

content = re.sub(led_pattern, led_replacement, content)

# 4. Update load_session to refresh these widgets
content = content.replace('self.draw_gauge(percent)', 'self.draw_gauge(percent)\n        self.draw_sparkline()\n        self.update_led()')

# 5. Remove the old history labels code in load_session
history_labels_pattern = r'            # Update mini history panel with recent deltas\s+if hasattr\(self, \'history_labels\'\):.*?lbl\.config\(text="—", fg=self\.colors\[\'muted\'\]\)'
content = re.sub(history_labels_pattern, '', content, flags=re.DOTALL)

# 6. Final Polish: Update the ENHANCEMENT_PLAN
plan_file = Path(r"c:\Users\Sam Deiter\Documents\GitHub\context-monitor\.gemini\ENHANCEMENT_PLAN.md")
with open(plan_file, 'r', encoding='utf-8') as f:
    plan = f.read()

plan = plan.replace('- [ ] 3.2 Compact Sparkline Graph', '- [x] 3.2 Compact Sparkline Graph ✅')
plan = plan.replace('- [ ] 3.4 Status LED Indicator', '- [x] 3.4 Status LED Indicator ✅')
plan = plan.replace('*Last Updated: 2025-12-21 (Sprint 1-3 complete)*', '*Last Updated: 2025-12-21 (Sprint 1-4 complete)*')

with open(plan_file, 'w', encoding='utf-8') as f:
    f.write(plan)

with open(source_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("Sprint 4 Implementation Complete!")
