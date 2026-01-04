"""
UI Builder for Context Monitor
Extracted from context_monitor.pyw for modularity (Phase 5: V2.52)

All UI setup functions receive the monitor instance to set widget references.
"""
import tkinter as tk
from widgets import ToolTip

# Check for optional tray support at module level
try:
    import pystray  # noqa: F401
    HAS_TRAY = True
except ImportError:
    HAS_TRAY = False


def _create_tooltip(monitor, widget, text):
    """Helper to create tooltip with monitor's colors."""
    ToolTip(widget, text, monitor.colors)


def _create_header(monitor, has_tray_support):
    """Create the standard header bar used by compact and full modes."""
    header = tk.Frame(monitor.root, bg=monitor.colors['bg3'], height=30)
    header.pack(fill='x')
    header.pack_propagate(False)
    
    title = tk.Label(header, text="📊 Context Monitor", font=('Segoe UI', 10, 'bold'),
                    bg=monitor.colors['bg3'], fg=monitor.colors['text'])
    title.pack(side='left', padx=10, pady=5)
    
    # Close button
    close_btn = tk.Label(header, text="✕", font=('Segoe UI', 10),
                        bg=monitor.colors['bg3'], fg=monitor.colors['text2'], cursor='hand2')
    close_btn.pack(side='right', padx=8)
    close_action = monitor.minimize_to_tray if has_tray_support else monitor.cleanup_and_exit
    close_btn.bind('<Button-1>', lambda e: close_action())
    
    # Resize handle
    resize_grip = tk.Label(header, text="⤡", font=('Segoe UI', 14),
                          bg=monitor.colors['bg3'], fg=monitor.colors['blue'], cursor='size_nw_se')
    resize_grip.pack(side='right', padx=4)
    resize_grip.bind('<Button-1>', monitor.start_resize)
    resize_grip.bind('<B1-Motion>', monitor.resize_window)
    _create_tooltip(monitor, resize_grip, "Drag to resize")
    
    # Mode toggle
    mini_btn = tk.Label(header, text="◱", font=('Segoe UI', 12), cursor='hand2',
                       bg=monitor.colors['bg3'], fg=monitor.colors['blue'])
    mini_btn.pack(side='right', padx=5)
    mini_btn.bind('<Button-1>', lambda e: monitor.toggle_mini_mode())
    
    # Transparency controls
    alpha_frame = tk.Frame(header, bg=monitor.colors['bg3'])
    alpha_frame.pack(side='right', padx=5)
    
    tk.Label(alpha_frame, text="−", font=('Segoe UI', 10), cursor='hand2',
            bg=monitor.colors['bg3'], fg=monitor.colors['text2']).pack(side='left', padx=2)
    alpha_frame.winfo_children()[-1].bind('<Button-1>', lambda e: monitor.adjust_alpha(-0.05))
    
    tk.Label(alpha_frame, text="+", font=('Segoe UI', 10), cursor='hand2',
            bg=monitor.colors['bg3'], fg=monitor.colors['text2']).pack(side='left', padx=2)
    alpha_frame.winfo_children()[-1].bind('<Button-1>', lambda e: monitor.adjust_alpha(0.05))
    
    for w in [header, title]:
        w.bind('<Button-1>', monitor.start_drag)
        w.bind('<B1-Motion>', monitor.drag)
        w.bind('<Button-3>', monitor.show_context_menu)
    
    return header, mini_btn, alpha_frame


def setup_mini_mode(monitor, x_pos, y_pos):
    """Build mini mode UI (circular gauge with transparency)."""
    monitor.root.geometry(f"120x120+{x_pos}+{y_pos}")
    monitor.root.update()
    
    # Use transparent color to create circular appearance
    trans_color = '#010101'
    monitor.root.configure(bg=trans_color)
    monitor.root.attributes('-transparentcolor', trans_color)
    
    monitor.gauge_canvas = tk.Canvas(monitor.root, width=120, height=120,
                                      bg=trans_color, highlightthickness=0)
    monitor.gauge_canvas.pack()
    
    # Draw circular background
    monitor.gauge_canvas.create_oval(4, 4, 116, 116, fill=monitor.colors['bg'], outline='')
    
    monitor.draw_gauge(monitor.current_percent)
    
    # Interactions
    monitor.gauge_canvas.bind('<Double-Button-1>', lambda e: monitor.toggle_mini_mode())
    monitor.gauge_canvas.bind('<Button-3>', monitor.show_context_menu)
    monitor.gauge_canvas.bind('<Button-1>', monitor.start_drag)
    monitor.gauge_canvas.bind('<B1-Motion>', monitor.drag)


def setup_compact_mode(monitor, w_px, h_px, x_pos, y_pos):
    """Build compact mode UI with gauge, tokens, and mini history."""
    monitor.root.attributes('-transparentcolor', '')
    monitor.root.geometry(f"{w_px}x{h_px}+{x_pos}+{y_pos}")
    monitor.root.update()
    
    # Header
    header, mini_btn, alpha_frame = _create_header(monitor, HAS_TRAY)
    
    # Content
    content = tk.Frame(monitor.root, bg=monitor.colors['bg2'], padx=15, pady=12)
    content.pack(fill='both', expand=True)
    content.bind('<Button-3>', monitor.show_context_menu)
    
    # Main row
    main = tk.Frame(content, bg=monitor.colors['bg2'])
    main.pack(fill='x')
    main.bind('<Button-3>', monitor.show_context_menu)
    
    # Gauge
    monitor.gauge_canvas = tk.Canvas(main, width=90, height=90,
                                      bg=monitor.colors['bg2'], highlightthickness=0)
    monitor.gauge_canvas.pack(side='left', padx=(0, 12))
    monitor.gauge_canvas.bind('<Button-3>', monitor.show_context_menu)
    monitor.gauge_canvas.bind('<Double-Button-1>', lambda e: monitor.toggle_mini_mode())
    monitor.draw_gauge(monitor.current_percent)
    
    # Info panel
    info = tk.Frame(main, bg=monitor.colors['bg2'])
    info.pack(side='left', fill='both', expand=True)
    info.bind('<Button-3>', monitor.show_context_menu)
    
    tk.Label(info, text="TOKENS LEFT", font=('Segoe UI', 8),
            bg=monitor.colors['bg2'], fg=monitor.colors['muted']).pack(anchor='w')
    monitor.tokens_label = tk.Label(info, text="—", font=('Segoe UI', 18, 'bold'),
                                     bg=monitor.colors['bg2'], fg=monitor.colors['text'])
    monitor.tokens_label.pack(anchor='w')
    monitor.tokens_label.bind('<Button-3>', monitor.show_context_menu)
    
    monitor.delta_label = tk.Label(info, text="", font=('Segoe UI', 8),
                                    bg=monitor.colors['bg2'], fg=monitor.colors['muted'])
    monitor.delta_label.pack(anchor='w')
    monitor.delta_label.bind('<Button-3>', monitor.show_context_menu)
    
    monitor.ttf_label = tk.Label(info, text="⏱️ —", font=('Segoe UI', 8),
                                  bg=monitor.colors['bg2'], fg=monitor.colors['text2'])
    monitor.ttf_label.pack(anchor='w')
    monitor.ttf_label.bind('<Button-3>', monitor.show_context_menu)
    _create_tooltip(monitor, monitor.ttf_label, "Estimated Time to Handoff\nBased on recent token burn rate")
    
    tk.Label(info, text="PROJECT", font=('Segoe UI', 8),
            bg=monitor.colors['bg2'], fg=monitor.colors['muted']).pack(anchor='w', pady=(8,0))
    monitor.session_label = tk.Label(info, text="—", font=('Segoe UI', 10),
                                      bg=monitor.colors['bg2'], fg=monitor.colors['text2'])
    monitor.session_label.pack(anchor='w')
    monitor.session_label.bind('<Button-3>', monitor.show_context_menu)
    
    # Mini history panel (right side)
    history_frame = tk.Frame(main, bg=monitor.colors['bg3'], padx=6, pady=4)
    history_frame.pack(side='right', fill='y', padx=(8, 0))
    history_frame.bind('<Button-3>', monitor.show_context_menu)
    
    tk.Label(history_frame, text="RECENT", font=('Segoe UI', 9, 'bold'),
            bg=monitor.colors['bg3'], fg=monitor.colors['muted']).pack(anchor='center')
    
    monitor.history_labels = []
    for _ in range(5):
        lbl = tk.Label(history_frame, text="—", font=('Consolas', 11),
                      bg=monitor.colors['bg3'], fg=monitor.colors['text2'])
        lbl.pack(anchor='e')
        lbl.bind('<Button-3>', monitor.show_context_menu)
        monitor.history_labels.append(lbl)
    
    # Status bar
    monitor.status_frame = tk.Frame(monitor.root, bg=monitor.colors['bg3'], padx=8, pady=6)
    monitor.status_frame.pack(fill='x', side='bottom')
    monitor.status_frame.bind('<Button-3>', monitor.show_context_menu)
    
    monitor.status_label = tk.Label(monitor.status_frame, text="✓ Loading...",
                                     font=('Segoe UI', 9),
                                     bg=monitor.colors['bg3'], fg=monitor.colors['text2'])
    monitor.status_label.pack(side='left')
    monitor.status_label.bind('<Button-3>', monitor.show_context_menu)
    
    monitor.copy_btn = tk.Label(monitor.status_frame, text="📋 Copy",
                                 font=('Segoe UI', 8), cursor='hand2',
                                 bg=monitor.colors['bg3'], fg=monitor.colors['blue'])
    monitor.copy_btn.pack(side='right')
    monitor.copy_btn.bind('<Button-1>', lambda e: monitor.copy_handoff())
    
    monitor.refresh_btn = tk.Label(monitor.status_frame, text="🔄",
                                    font=('Segoe UI', 10), cursor='hand2',
                                    bg=monitor.colors['bg3'], fg=monitor.colors['blue'])
    monitor.refresh_btn.pack(side='right', padx=(0, 8))
    monitor.refresh_btn.bind('<Button-1>', lambda e: monitor.force_refresh())
    
    # Tooltips
    _create_tooltip(monitor, monitor.gauge_canvas, "Token Usage\nGreen: Safe\nYellow: < 60% Left\nRed: < 80% Left")
    _create_tooltip(monitor, monitor.copy_btn, "Generate Handoff\nCreates a summary prompt for the next agent")
    _create_tooltip(monitor, monitor.refresh_btn, "Refresh (R)\nForce refresh project detection")
    _create_tooltip(monitor, monitor.session_label, "Current Project\nAuto-detected from VS Code/GitHub")
    _create_tooltip(monitor, mini_btn, "Toggle Mini Mode (M)\nSwitch to compact view")
    _create_tooltip(monitor, alpha_frame, "Transparency (+/-)\nAdjust window opacity")


def setup_full_mode(monitor, w_px, h_px, x_pos, y_pos):
    """Build full mode UI with tabbed analytics."""
    monitor.root.attributes('-transparentcolor', '')
    monitor.root.geometry(f"{w_px}x{h_px}+{x_pos}+{y_pos}")
    monitor.root.update()
    
    # Initialize tab state
    if not hasattr(monitor, 'active_tab'):
        monitor.active_tab = 'history'
    
    # Header
    _create_header(monitor, HAS_TRAY)
    
    # Top info bar (gauge + tokens)
    top_bar = tk.Frame(monitor.root, bg=monitor.colors['bg2'], padx=15, pady=10)
    top_bar.pack(fill='x')
    
    # Gauge (smaller)
    monitor.gauge_canvas = tk.Canvas(top_bar, width=70, height=70,
                                      bg=monitor.colors['bg2'], highlightthickness=0)
    monitor.gauge_canvas.pack(side='left', padx=(0, 12))
    monitor.gauge_canvas.bind('<Button-3>', monitor.show_context_menu)
    monitor.gauge_canvas.bind('<Double-Button-1>', lambda e: monitor.toggle_mini_mode())
    monitor.draw_gauge(monitor.current_percent)
    
    # Info
    info = tk.Frame(top_bar, bg=monitor.colors['bg2'])
    info.pack(side='left', fill='both', expand=True)
    
    tk.Label(info, text="TOKENS LEFT", font=('Segoe UI', 8),
            bg=monitor.colors['bg2'], fg=monitor.colors['muted']).pack(anchor='w')
    
    monitor.tokens_label = tk.Label(info, text="Loading...", font=('Segoe UI', 14, 'bold'),
                                    bg=monitor.colors['bg2'], fg=monitor.colors['text'])
    monitor.tokens_label.pack(anchor='w')
    
    monitor.delta_label = tk.Label(info, text="", font=('Segoe UI', 9),
                                   bg=monitor.colors['bg2'], fg=monitor.colors['blue'])
    monitor.delta_label.pack(anchor='w')
    
    monitor.ttf_label = tk.Label(info, text="⏱️ —", font=('Segoe UI', 9),
                                  bg=monitor.colors['bg2'], fg=monitor.colors['text2'])
    monitor.ttf_label.pack(anchor='w')
    
    monitor.project_label = tk.Label(info, text="", font=('Segoe UI', 9),
                                     bg=monitor.colors['bg2'], fg=monitor.colors['muted'])
    monitor.project_label.pack(anchor='w', pady=(2, 0))
    
    # Tab bar
    tab_bar = tk.Frame(monitor.root, bg=monitor.colors['bg3'], height=35)
    tab_bar.pack(fill='x')
    tab_bar.pack_propagate(False)
    
    tabs = [
        ('📊 Diagnostics', 'diagnostics'),
        ('📈 Token Stats', 'token_stats'),
        ('📅 History', 'history'),
        ('📊 Analytics', 'analytics')
    ]
    
    monitor.tab_buttons = {}
    for label, tab_id in tabs:
        tab_btn = tk.Label(tab_bar, text=label, font=('Segoe UI', 9),
                          bg=monitor.colors['bg3'], fg=monitor.colors['text'],
                          cursor='hand2', padx=15, pady=8)
        tab_btn.pack(side='left')
        tab_btn.bind('<Button-1>', lambda e, t=tab_id: monitor.switch_tab(t))
        monitor.tab_buttons[tab_id] = tab_btn
        
        if tab_id == monitor.active_tab:
            tab_btn.config(bg=monitor.colors['blue'], fg='white')
    
    # Content area
    monitor.content_frame = tk.Frame(monitor.root, bg=monitor.colors['bg2'])
    monitor.content_frame.pack(fill='both', expand=True)
    monitor.tab_frames = {}
    
    # Render active tab content immediately
    monitor.render_tab_content()
    
    # Action buttons at bottom
    actions_bar = tk.Frame(monitor.root, bg=monitor.colors['bg3'], padx=10, pady=8)
    actions_bar.pack(fill='x')
    
    monitor.create_button(actions_bar, "💾 Export CSV", monitor.export_history_csv).pack(side='left', padx=2)
    monitor.create_button(actions_bar, "🧹 Clean Old", monitor.cleanup_old_conversations).pack(side='left', padx=2)
    monitor.create_button(actions_bar, "📦 Archive", monitor.archive_old_sessions).pack(side='left', padx=2)
    monitor.create_button(actions_bar, "🔄 Restart", monitor.restart_antigravity).pack(side='left', padx=2)
    
    # Status bar
    monitor.status_frame = tk.Frame(monitor.root, bg=monitor.colors['bg3'], height=28)
    monitor.status_frame.pack(fill='x', side='bottom')
    monitor.status_frame.pack_propagate(False)
    
    monitor.status_label = tk.Label(monitor.status_frame, text="✓ Ready", font=('Segoe UI', 8),
                                    bg=monitor.colors['bg3'], fg=monitor.colors['green'], anchor='w')
    monitor.status_label.pack(side='left', padx=10)
    
    monitor.copy_btn = tk.Label(monitor.status_frame, text="📋 Copy",
                                 font=('Segoe UI', 8), cursor='hand2',
                                 bg=monitor.colors['bg3'], fg=monitor.colors['blue'])
    monitor.copy_btn.pack(side='right', padx=10)
    monitor.copy_btn.bind('<Button-1>', lambda e: monitor.copy_handoff())
    
    monitor.refresh_btn = tk.Label(monitor.status_frame, text="🔄",
                                    font=('Segoe UI', 10), cursor='hand2',
                                    bg=monitor.colors['bg3'], fg=monitor.colors['blue'])
    monitor.refresh_btn.pack(side='right', padx=5)
    monitor.refresh_btn.bind('<Button-1>', lambda e: monitor.force_refresh())


def bind_keyboard_shortcuts(monitor):
    """Bind global keyboard shortcuts."""
    monitor.root.bind('<KeyPress-m>', lambda e: monitor.toggle_mini_mode())
    monitor.root.bind('<KeyPress-plus>', lambda e: monitor.adjust_alpha(0.05))
    monitor.root.bind('<KeyPress-minus>', lambda e: monitor.adjust_alpha(-0.05))
    monitor.root.bind('<KeyPress-r>', lambda e: monitor.force_refresh())
    # 'a' shortcut removed (use 'd' for dashboard)
    monitor.root.bind('<KeyPress-d>', lambda e: monitor.show_analytics_dashboard())
    monitor.root.bind('<KeyPress-e>', lambda e: monitor.export_history_csv())


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
