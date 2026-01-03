"""
Phase 3+4 Extraction Script
Extracts analytics dashboard to dialogs.py and inline renderers to ui_builder.py
Then updates context_monitor.pyw to use delegated methods.
"""

import re
from pathlib import Path

# Paths
BASE = Path(r"c:\Users\Sam Deiter\Documents\GitHub\context-monitor")
MONITOR = BASE / "context_monitor.pyw"
DIALOGS = BASE / "dialogs.py"
UI_BUILDER = BASE / "ui_builder.py"

# Read current files
monitor_code = MONITOR.read_text(encoding='utf-8', errors='replace')
dialogs_code = DIALOGS.read_text(encoding='utf-8', errors='replace')
ui_builder_code = UI_BUILDER.read_text(encoding='utf-8', errors='replace')

# ===== STEP 1: Extract inline renderers to ui_builder.py =====
# These are relatively simple methods that just need the monitor instance

inline_renderers_code = '''

# ==== INLINE TAB RENDERERS (Extracted from context_monitor.pyw) ====

def render_history_inline(monitor, parent):
    """Render usage history graph inline"""
    # Add title
    title = tk.Label(parent, text="📅 Usage History (Last 24h)", 
                    font=('Segoe UI', 12, 'bold'),
                    bg=monitor.colors['bg2'], fg=monitor.colors['text'])
    title.pack(anchor='w', padx=15, pady=(15, 5))
    
    # Graph canvas
    canvas = tk.Canvas(parent, width=620, height=380,
                      bg=monitor.colors['bg2'], highlightthickness=1,
                      highlightbackground=monitor.colors['bg3'])
    canvas.pack(padx=15, pady=10, fill='both', expand=True)
    
    # Draw graph immediately
    monitor.graph_canvas = canvas
    try:
        monitor.draw_mini_graph()
    except Exception as e:
        canvas.create_text(310, 190, text=f"Graph error: {e}",
                         fill=monitor.colors['muted'], font=('Segoe UI', 10))


def render_diagnostics_inline(monitor, parent):
    """Render system diagnostics inline"""
    procs = monitor.get_antigravity_processes()
    limits = monitor.thresholds
    
    total_mem = sum(p.get('Mem', 0) for p in procs)
    
    container = tk.Frame(parent, bg=monitor.colors['bg2'], padx=15, pady=15)
    container.pack(fill='both', expand=True)
    
    # Title
    tk.Label(container, text="🔧 System Diagnostics", font=('Segoe UI', 12, 'bold'),
            bg=monitor.colors['bg2'], fg=monitor.colors['text']).pack(anchor='w', pady=(0, 10))
    
    # System overview
    info_frame = tk.Frame(container, bg=monitor.colors['bg'], padx=10, pady=8)
    info_frame.pack(fill='x', pady=(0, 10))
    
    tk.Label(info_frame, text=f"💾 RAM: {monitor.total_ram_mb // 1024} GB  |  ⚙️ Processes: {len(procs)}  |  📊 Total Memory: {total_mem}MB",
            font=('Segoe UI', 10), bg=monitor.colors['bg'], fg=monitor.colors['text']).pack(anchor='w')
    
    # Process list
    tk.Label(container, text="Process Memory:", font=('Segoe UI', 9, 'bold'),
            bg=monitor.colors['bg2'], fg=monitor.colors['text']).pack(anchor='w', pady=(5, 5))
    
    for p in procs[:8]:
        mem = p.get('Mem', 0)
        ptype = p.get('Type', 'Unknown')
        color = monitor.colors['red'] if mem > limits['proc_crit'] else (monitor.colors['yellow'] if mem > limits['proc_warn'] else monitor.colors['green'])
        
        tk.Label(container, text=f"  • {ptype}: {mem}MB",
                font=('Segoe UI', 9), bg=monitor.colors['bg2'], fg=color).pack(anchor='w')


def render_token_stats_inline(monitor, parent):
    """Render token statistics inline"""
    if not monitor.current_session:
        return
    
    context_window = monitor._context_window
    tokens_used = monitor.current_session['estimated_tokens'] // 10
    context_limit = monitor._context_window
    percent_used = min(100, (tokens_used / context_limit) * 100)
    tokens_left = max(0, context_limit - tokens_used)
    
    container = tk.Frame(parent, bg=monitor.colors['bg2'], padx=15, pady=15)
    container.pack(fill='both', expand=True)
    
    # Title
    tk.Label(container, text="📊 Token Usage Dashboard", font=('Segoe UI', 12, 'bold'),
            bg=monitor.colors['bg2'], fg=monitor.colors['text']).pack(anchor='w', pady=(0, 10))
    
    # Context window
    tk.Label(container, text="Context Window:", font=('Segoe UI', 9, 'bold'),
            bg=monitor.colors['bg2'], fg=monitor.colors['text']).pack(anchor='w', pady=(5, 5))
    
    usage_color = monitor.colors['red'] if percent_used >= 80 else (monitor.colors['yellow'] if percent_used >= 60 else monitor.colors['green'])
    
    # Store these for updates
    monitor.stats_tokens_used_label = tk.Label(container, text=f"  • Tokens Used: {tokens_used:,} ({percent_used}%)",
            font=('Segoe UI', 10), bg=monitor.colors['bg2'], fg=usage_color)
    monitor.stats_tokens_used_label.pack(anchor='w')
    
    monitor.stats_tokens_left_label = tk.Label(container, text=f"  • Tokens Remaining: {tokens_left:,}",
            font=('Segoe UI', 10), bg=monitor.colors['bg2'], fg=monitor.colors['blue'])
    monitor.stats_tokens_left_label.pack(anchor='w')
    
    tk.Label(container, text=f"  • Total Capacity: {context_window:,}",
            font=('Segoe UI', 10), bg=monitor.colors['bg2'], fg=monitor.colors['muted']).pack(anchor='w')
    
    # Breakdown
    estimated_input = int(tokens_used * 0.4)
    estimated_output = int(tokens_used * 0.6)
    
    tk.Label(container, text="Estimated Breakdown:", font=('Segoe UI', 9, 'bold'),
            bg=monitor.colors['bg2'], fg=monitor.colors['text']).pack(anchor='w', pady=(10, 5))
    
    tk.Label(container, text=f"  • Input (Your messages): {estimated_input:,}",
            font=('Segoe UI', 10), bg=monitor.colors['bg2'], fg=monitor.colors['blue']).pack(anchor='w')
    tk.Label(container, text=f"  • Output (Assistant): {estimated_output:,}",
            font=('Segoe UI', 10), bg=monitor.colors['bg2'], fg=monitor.colors['green']).pack(anchor='w')


def render_analytics_inline(monitor, parent):
    """Render analytics dashboard inline"""
    from datetime import datetime, timedelta
    
    container = tk.Frame(parent, bg=monitor.colors['bg2'], padx=15, pady=15)
    container.pack(fill='both', expand=True)
    
    # Title
    tk.Label(container, text="📊 Analytics Dashboard", font=('Segoe UI', 12, 'bold'),
            bg=monitor.colors['bg2'], fg=monitor.colors['text']).pack(anchor='w', pady=(0, 10))
    
    # Get analytics data
    analytics = monitor.load_analytics()
    today_key = datetime.now().strftime("%Y-%m-%d")
    today_data = analytics.get('daily', {}).get(today_key, {})
    
    # Today's usage
    tk.Label(container, text="Today's Usage:", font=('Segoe UI', 9, 'bold'),
            bg=monitor.colors['bg2'], fg=monitor.colors['text']).pack(anchor='w', pady=(5, 5))
    
    total_today = today_data.get('total', 0)
    tk.Label(container, text=f"  • Total Tokens: {total_today:,}",
            font=('Segoe UI', 10), bg=monitor.colors['bg2'], fg=monitor.colors['text']).pack(anchor='w')
    
    # Weekly summary
    tk.Label(container, text="Last 7 Days:", font=('Segoe UI', 9, 'bold'),
            bg=monitor.colors['bg2'], fg=monitor.colors['text']).pack(anchor='w', pady=(10, 5))
    
    week_total = 0
    for i in range(7):
        date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        day_data = analytics.get('daily', {}).get(date, {})
        week_total += day_data.get('total', 0)
    
    tk.Label(container, text=f"  • Total Tokens: {week_total:,}",
            font=('Segoe UI', 10), bg=monitor.colors['bg2'], fg=monitor.colors['text']).pack(anchor='w')
    tk.Label(container, text=f"  • Daily Average: {week_total // 7:,}",
            font=('Segoe UI', 10), bg=monitor.colors['bg2'], fg=monitor.colors['muted']).pack(anchor='w')
'''

# Append inline renderers to ui_builder.py
ui_builder_code += inline_renderers_code
UI_BUILDER.write_text(ui_builder_code, encoding='utf-8')
print(f"✓ Added inline renderers to ui_builder.py ({len(inline_renderers_code)} chars)")

# ===== STEP 2: Update render_tab_content in context_monitor.pyw =====
# Replace the method bodies to call the extracted functions

# Find and replace render_tab_content method to use ui_builder imports
old_render_tab = '''    def render_tab_content(self):
        """Render content for the active tab using cache"""
        # Destroy old content
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        # Create new frame for this tab
        tab_frame = tk.Frame(self.content_frame, bg=self.colors['bg2'])
        tab_frame.pack(fill='both', expand=True)
        self.tab_frames[self.active_tab] = tab_frame
        
        # Render based on active tab
        if self.active_tab == 'diagnostics':
            self.render_diagnostics_inline(tab_frame)
        elif self.active_tab == 'token_stats':
            self.render_token_stats_inline(tab_frame)
        elif self.active_tab == 'history':
            self.render_history_inline(tab_frame)
        elif self.active_tab == 'analytics':
            self.render_analytics_inline(tab_frame)'''

new_render_tab = '''    def render_tab_content(self):
        """Render content for the active tab using cache (delegated to ui_builder)"""
        from ui_builder import (render_history_inline, render_diagnostics_inline,
                                render_token_stats_inline, render_analytics_inline)
        
        # Destroy old content
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        # Create new frame for this tab
        tab_frame = tk.Frame(self.content_frame, bg=self.colors['bg2'])
        tab_frame.pack(fill='both', expand=True)
        self.tab_frames[self.active_tab] = tab_frame
        
        # Render based on active tab (delegated to ui_builder)
        if self.active_tab == 'diagnostics':
            render_diagnostics_inline(self, tab_frame)
        elif self.active_tab == 'token_stats':
            render_token_stats_inline(self, tab_frame)
        elif self.active_tab == 'history':
            render_history_inline(self, tab_frame)
        elif self.active_tab == 'analytics':
            render_analytics_inline(self, tab_frame)'''

monitor_code = monitor_code.replace(old_render_tab, new_render_tab)

# ===== STEP 3: Remove old inline renderer methods from context_monitor.pyw =====
# We need to find and remove the 4 render_*_inline methods

# Pattern to match the inline methods (from def to the next def at same indent level)
methods_to_remove = [
    'render_history_inline',
    'render_diagnostics_inline', 
    'render_token_stats_inline',
    'render_analytics_inline'
]

for method in methods_to_remove:
    # Match the method definition to the start of the next method
    pattern = rf'(    def {method}\(self, parent\):.*?)(?=\n    def |\n\nif __name__)'
    match = re.search(pattern, monitor_code, re.DOTALL)
    if match:
        monitor_code = monitor_code.replace(match.group(1), '')
        print(f"✓ Removed {method} from context_monitor.pyw")

# Clean up any triple newlines
monitor_code = re.sub(r'\n{4,}', '\n\n\n', monitor_code)

# Write updated monitor code
MONITOR.write_text(monitor_code, encoding='utf-8')
print(f"✓ Updated context_monitor.pyw")

# Count lines
lines = len(MONITOR.read_text().splitlines())
print(f"\n📊 context_monitor.pyw now has {lines} lines")
