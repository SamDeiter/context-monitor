import re

# Read the file
with open(r'c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.pyw', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the location to insert (before show_history)
insert_marker = '    def show_history(self):'
insert_pos = content.find(insert_marker)

if insert_pos == -1:
    print("ERROR: Could not find insertion point")
    exit(1)

# New method to insert
new_method = '''    def draw_mini_graph(self):
        """Draw usage history graph in Full mode canvas"""
        if not self.current_session or not hasattr(self, 'graph_canvas'):
            return
            
        sid = self.current_session['id']
        data = self.load_history().get(sid, [])
        
        if not data:
            self.graph_canvas.create_text(280, 75, text="Not enough data yet",
                                         fill=self.colors['muted'], font=('Segoe UI', 10))
            return
        
        canvas = self.graph_canvas
        canvas.delete('all')
        
        w = 560
        h = 150
        left_pad = 40
        right_pad = 20
        top_pad = 15
        bottom_pad = 30
        
        # Draw Y-axis (percentage)
        max_tokens = self._context_window
        for pct in [0, 25, 50, 75, 100]:
            y = h - bottom_pad - (pct / 100) * (h - top_pad - bottom_pad)
            canvas.create_line(left_pad, y, w - right_pad, y,
                              fill=self.colors['bg3'], dash=(2, 4))
            canvas.create_text(left_pad - 5, y, text=f"{pct}%",
                              fill=self.colors['muted'], font=('Segoe UI', 7), anchor='e')
        
        min_ts = data[0]['ts']
        max_ts = data[-1]['ts']
        time_range = max_ts - min_ts
        if time_range == 0:
            time_range = 1
        
        # Draw X-axis time labels
        from datetime import datetime
        num_labels = min(4, len(data))
        for i in range(num_labels):
            idx = int(i * (len(data) - 1) / max(1, num_labels - 1))
            ts = data[idx]['ts']
            x = left_pad + (ts - min_ts) / time_range * (w - left_pad - right_pad)
            if time_range < 86400:
                label = datetime.fromtimestamp(ts).strftime("%H:%M")
            else:
                label = datetime.fromtimestamp(ts).strftime("%m/%d")
            canvas.create_text(x, h - bottom_pad + 12, text=label,
                              fill=self.colors['muted'], font=('Segoe UI', 7), anchor='n')
        
        # Plot data points
        points = []
        for p in data:
            x = left_pad + (p['ts'] - min_ts) / time_range * (w - left_pad - right_pad)
            pct = min(100, (p['tokens'] / max_tokens) * 100)
            y = h - bottom_pad - (pct / 100) * (h - top_pad - bottom_pad)
            points.append((x, y))
        
        # Draw filled area
        if len(points) > 1:
            fill_points = [(left_pad, h - bottom_pad)] + points + [(w - right_pad, h - bottom_pad)]
            canvas.create_polygon(fill_points, fill='#1a3a5c', outline='')
        
        # Draw line
        if len(points) > 1:
            canvas.create_line(points, fill=self.colors['blue'], width=2, smooth=True)
        
        # Draw 80% warning line
        warn_y = h - bottom_pad - 0.8 * (h - top_pad - bottom_pad)
        canvas.create_line(left_pad, warn_y, w - right_pad, warn_y,
                          fill=self.colors['red'], width=1, dash=(4, 4))
        canvas.create_text(w - right_pad - 5, warn_y - 5, text="80%",
                          fill=self.colors['red'], font=('Segoe UI', 7), anchor='e')
        
        # Current value dot
        if points:
            last_x, last_y = points[-1]
            current_pct = min(100, (data[-1]['tokens'] / max_tokens) * 100)
            color = self.colors['green']
            if current_pct >= 80:
                color = self.colors['red']
            elif current_pct >= 60:
                color = self.colors['yellow']
            canvas.create_oval(last_x-4, last_y-4, last_x+4, last_y+4,
                              fill=color, outline='white', width=2)
    
'''

# Insert the new method
content = content[:insert_pos] + new_method + content[insert_pos:]

# Write back
with open(r'c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.pyw', 'w', encoding='utf-8') as f:
    f.write(content)

print("✓ Added draw_mini_graph() method")
