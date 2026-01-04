"""
UI Dialog Windows for Context Monitor
Extracted from context_monitor.pyw for modularity (Phase 4: V2.47)

All dialogs receive the monitor instance to access state and methods.
"""
import tkinter as tk
from tkinter import messagebox
from datetime import datetime


def show_history_dialog(monitor):
    """Show usage history graph with time labels"""
    if not monitor.current_session:
        return
        
    sid = monitor.current_session['id']
    data = monitor.load_history().get(sid, [])
    
    if not data:
        messagebox.showinfo("History", "Not enough data collected yet.")
        return

    win = tk.Toplevel(monitor.root)
    win.title("Token Usage History")
    win.geometry("500x350")
    win.configure(bg=monitor.colors['bg'])
    win.attributes('-topmost', True)
    
    tk.Label(win, text=f"📊 {monitor.get_project_name(sid)}", 
            font=('Segoe UI', 12, 'bold'),
            bg=monitor.colors['bg'], fg=monitor.colors['text']).pack(pady=(10,5))
    
    canvas = tk.Canvas(win, width=460, height=280, bg=monitor.colors['bg2'], highlightthickness=0)
    canvas.pack(padx=20, pady=10)
    
    def draw_graph():
        canvas.delete('all')
        current_data = monitor.load_history().get(sid, [])
        if not current_data:
            return
        
        w, h = 460, 280
        left_pad, right_pad, top_pad, bottom_pad = 50, 20, 20, 40
        
        max_tokens = monitor._context_window
        for pct in [0, 25, 50, 75, 100]:
            y = h - bottom_pad - (pct / 100) * (h - top_pad - bottom_pad)
            canvas.create_line(left_pad, y, w - right_pad, y, 
                              fill=monitor.colors['bg3'], dash=(2, 4))
            canvas.create_text(left_pad - 5, y, text=f"{pct}%", 
                              fill=monitor.colors['muted'], font=('Segoe UI', 8), anchor='e')
        
        min_ts, max_ts = current_data[0]['ts'], current_data[-1]['ts']
        time_range = max(1, max_ts - min_ts)
        
        num_labels = min(5, len(current_data))
        for i in range(num_labels):
            idx = int(i * (len(current_data) - 1) / max(1, num_labels - 1))
            ts = current_data[idx]['ts']
            x = left_pad + (ts - min_ts) / time_range * (w - left_pad - right_pad)
            if time_range < 3600:
                label = datetime.fromtimestamp(ts).strftime("%H:%M")
            elif time_range < 86400:
                label = datetime.fromtimestamp(ts).strftime("%H:%M")
            else:
                label = datetime.fromtimestamp(ts).strftime("%m/%d %H:%M")
            canvas.create_text(x, h - bottom_pad + 15, text=label,
                              fill=monitor.colors['muted'], font=('Segoe UI', 7), anchor='n')
        
        points = []
        for p in current_data:
            x = left_pad + (p['ts'] - min_ts) / time_range * (w - left_pad - right_pad)
            pct = min(100, (p['tokens'] / max_tokens) * 100)
            y = h - bottom_pad - (pct / 100) * (h - top_pad - bottom_pad)
            points.append((x, y))
        
        if len(points) > 1:
            fill_points = [(left_pad, h - bottom_pad)] + points + [(w - right_pad, h - bottom_pad)]
            canvas.create_polygon(fill_points, fill='#1a3a5c', outline='')
            canvas.create_line(points, fill=monitor.colors['blue'], width=2, smooth=True)
        
        warn_y = h - bottom_pad - 0.8 * (h - top_pad - bottom_pad)
        canvas.create_line(left_pad, warn_y, w - right_pad, warn_y, 
                          fill=monitor.colors['red'], width=2, dash=(4, 4))
        canvas.create_text(w - right_pad - 5, warn_y - 8, text="80%", 
                          fill=monitor.colors['red'], font=('Segoe UI', 8), anchor='e')
        
        if points:
            last_x, last_y = points[-1]
            current_pct = min(100, (current_data[-1]['tokens'] / max_tokens) * 100)
            color = monitor.colors['green']
            if current_pct >= 80:
                color = monitor.colors['red']
            elif current_pct >= 60:
                color = monitor.colors['yellow']
            canvas.create_oval(last_x-5, last_y-5, last_x+5, last_y+5, 
                              fill=color, outline='white', width=2)
    
    draw_graph()
    
    refresh_id = None
    def auto_refresh():
        nonlocal refresh_id
        if win.winfo_exists():
            draw_graph()
            refresh_id = win.after(5000, auto_refresh)
    
    def on_close():
        nonlocal refresh_id
        if refresh_id:
            win.after_cancel(refresh_id)
        win.destroy()
    
    win.protocol("WM_DELETE_WINDOW", on_close)
    refresh_id = win.after(5000, auto_refresh)


def show_diagnostics_dialog(monitor):
    """Show diagnostics popup with styled visual design"""
    procs = monitor.get_antigravity_processes()
    files = monitor.get_large_conversations()
    limits = monitor.thresholds
    
    total_mem = sum(p.get('Mem', 0) for p in procs)
    total_file_size = sum(f['size_mb'] for f in files)
    
    win = tk.Toplevel(monitor.root)
    win.title("📊 System Diagnostics")
    win.geometry("450x700")
    win.configure(bg=monitor.colors['bg'])
    win.attributes('-topmost', True)
    win.resizable(True, True)
    
    header = tk.Frame(win, bg=monitor.colors['bg3'], height=50)
    header.pack(fill='x')
    header.pack_propagate(False)
    
    tk.Label(header, text="🔧 System Diagnostics", 
            font=('Segoe UI', 14, 'bold'),
            bg=monitor.colors['bg3'], fg=monitor.colors['text']).pack(pady=12)
    
    content = tk.Frame(win, bg=monitor.colors['bg'], padx=20, pady=15)
    content.pack(fill='both', expand=True)
    
    def create_bar(parent, label, value, max_val, color):
        frame = tk.Frame(parent, bg=monitor.colors['bg'])
        frame.pack(fill='x', pady=4)
        
        label_frame = tk.Frame(frame, bg=monitor.colors['bg'])
        label_frame.pack(fill='x')
        
        tk.Label(label_frame, text=label, font=('Segoe UI', 9),
                bg=monitor.colors['bg'], fg=monitor.colors['text']).pack(side='left')
        tk.Label(label_frame, text=f"{value}MB", font=('Segoe UI', 9, 'bold'),
                bg=monitor.colors['bg'], fg=color).pack(side='right')
        
        bar_canvas = tk.Canvas(frame, width=400, height=12, 
                               bg=monitor.colors['bg3'], highlightthickness=0)
        bar_canvas.pack(fill='x', pady=(2, 0))
        
        pct = min(100, (value / max_val) * 100) if max_val > 0 else 0
        bar_width = int((pct / 100) * 396)
        if bar_width > 0:
            bar_canvas.create_rectangle(2, 2, bar_width + 2, 10, fill=color, outline='')
    
    # System Overview
    tk.Label(content, text="SYSTEM OVERVIEW", font=('Segoe UI', 9),
            bg=monitor.colors['bg'], fg=monitor.colors['muted']).pack(anchor='w', pady=(0, 8))
    
    info_frame = tk.Frame(content, bg=monitor.colors['bg2'], padx=12, pady=10)
    info_frame.pack(fill='x')
    
    tk.Label(info_frame, text=f"💾 RAM Detected: {monitor.total_ram_mb // 1024} GB", 
            font=('Segoe UI', 10), bg=monitor.colors['bg2'], fg=monitor.colors['text']).pack(anchor='w')
    tk.Label(info_frame, text=f"⚙️ Processes: {len(procs)}", 
            font=('Segoe UI', 10), bg=monitor.colors['bg2'], fg=monitor.colors['text']).pack(anchor='w')
    
    if total_mem > limits['total_crit']:
        status_color, status_text = monitor.colors['red'], "🔴 CRITICAL"
    elif total_mem > limits['total_warn']:
        status_color, status_text = monitor.colors['yellow'], "🟡 HIGH"
    else:
        status_color, status_text = monitor.colors['green'], "🟢 HEALTHY"
    
    tk.Label(info_frame, text=f"📊 Total Memory: {total_mem}MB  {status_text}", 
            font=('Segoe UI', 10, 'bold'), bg=monitor.colors['bg2'], fg=status_color).pack(anchor='w', pady=(5,0))
    
    tk.Frame(content, bg=monitor.colors['bg3'], height=1).pack(fill='x', pady=12)
    
    # Process Memory
    tk.Label(content, text="PROCESS MEMORY", font=('Segoe UI', 9),
            bg=monitor.colors['bg'], fg=monitor.colors['muted']).pack(anchor='w', pady=(0, 8))
    
    max_mem = max((p.get('Mem', 0) for p in procs), default=500)
    for p in procs[:6]:
        mem = p.get('Mem', 0)
        ptype = p.get('Type', 'Unknown')
        if mem > limits['proc_crit']:
            color = monitor.colors['red']
        elif mem > limits['proc_warn']:
            color = monitor.colors['yellow']
        else:
            color = monitor.colors['green']
        create_bar(content, ptype, mem, max_mem * 1.2, color)
    
    tk.Frame(content, bg=monitor.colors['bg3'], height=1).pack(fill='x', pady=12)
    
    # Large Files
    tk.Label(content, text=f"LARGE FILES ({len(files)} files, {total_file_size:.1f}MB)", 
            font=('Segoe UI', 9), bg=monitor.colors['bg'], fg=monitor.colors['muted']).pack(anchor='w', pady=(0, 8))
    
    if files:
        for f in files[:4]:
            size = f['size_mb']
            color = monitor.colors['red'] if size > 15 else (monitor.colors['yellow'] if size > 8 else monitor.colors['green'])
            create_bar(content, f['name'][:20] + "...", size, 20, color)
    else:
        tk.Label(content, text="No large files found", font=('Segoe UI', 9, 'italic'),
                bg=monitor.colors['bg'], fg=monitor.colors['muted']).pack(anchor='w')


def show_advanced_stats_dialog(monitor):
    """Show detailed token usage breakdown with visual bars"""
    if not monitor.current_session:
        messagebox.showinfo("Advanced Stats", "No active session found.")
        return
    
    conv_file = monitor.conversations_dir / f"{monitor.current_session['id']}.pb"
    if not conv_file.exists():
        messagebox.showinfo("Advanced Stats", "Conversation file not found.")
        return
    
    file_size = conv_file.stat().st_size
    context_window = monitor._context_window
    tokens_used = monitor.current_session['estimated_tokens'] // 10
    tokens_left = max(0, context_window - tokens_used)
    percent_used = min(100, round((tokens_used / context_window) * 100))
    estimated_input = int(tokens_used * 0.4)
    estimated_output = int(tokens_used * 0.6)
    
    win = tk.Toplevel(monitor.root)
    win.title("📊 Advanced Token Statistics")
    win.geometry("420x500")
    win.configure(bg=monitor.colors['bg'])
    win.attributes('-topmost', True)
    win.resizable(True, True)
    
    header = tk.Frame(win, bg=monitor.colors['bg3'], height=50)
    header.pack(fill='x')
    header.pack_propagate(False)
    
    tk.Label(header, text="📊 Token Usage Dashboard", 
            font=('Segoe UI', 14, 'bold'),
            bg=monitor.colors['bg3'], fg=monitor.colors['text']).pack(pady=12)
    
    content = tk.Frame(win, bg=monitor.colors['bg'], padx=20, pady=15)
    content.pack(fill='both', expand=True)
    
    def create_bar(parent, label, value, max_val, color, show_percent=True):
        frame = tk.Frame(parent, bg=monitor.colors['bg'])
        frame.pack(fill='x', pady=8)
        
        label_frame = tk.Frame(frame, bg=monitor.colors['bg'])
        label_frame.pack(fill='x')
        
        tk.Label(label_frame, text=label, font=('Segoe UI', 10),
                bg=monitor.colors['bg'], fg=monitor.colors['text']).pack(side='left')
        
        if show_percent:
            pct = min(100, round((value / max_val) * 100)) if max_val > 0 else 0
            tk.Label(label_frame, text=f"{value:,} ({pct}%)", 
                    font=('Segoe UI', 10, 'bold'),
                    bg=monitor.colors['bg'], fg=color).pack(side='right')
        else:
            tk.Label(label_frame, text=f"{value:,}", 
                    font=('Segoe UI', 10, 'bold'),
                    bg=monitor.colors['bg'], fg=color).pack(side='right')
        
        bar_canvas = tk.Canvas(frame, width=380, height=20, 
                               bg=monitor.colors['bg3'], highlightthickness=0)
        bar_canvas.pack(fill='x', pady=(4, 0))
        
        pct = min(100, (value / max_val) * 100) if max_val > 0 else 0
        bar_width = int((pct / 100) * 376)
        if bar_width > 0:
            bar_canvas.create_rectangle(2, 2, bar_width + 2, 18, fill=color, outline='')
    
    tk.Label(content, text="CONTEXT WINDOW", font=('Segoe UI', 9),
            bg=monitor.colors['bg'], fg=monitor.colors['muted']).pack(anchor='w', pady=(0, 5))
    
    usage_color = monitor.colors['red'] if percent_used >= 80 else (monitor.colors['yellow'] if percent_used >= 60 else monitor.colors['green'])
    
    create_bar(content, "Tokens Used", tokens_used, context_window, usage_color)
    create_bar(content, "Tokens Remaining", tokens_left, context_window, monitor.colors['blue'])
    
    tk.Frame(content, bg=monitor.colors['bg3'], height=1).pack(fill='x', pady=15)
    
    tk.Label(content, text="ESTIMATED BREAKDOWN", font=('Segoe UI', 9),
            bg=monitor.colors['bg'], fg=monitor.colors['muted']).pack(anchor='w', pady=(0, 5))
    
    create_bar(content, "Input (Your messages)", estimated_input, tokens_used, monitor.colors['blue'])
    create_bar(content, "Output (Assistant)", estimated_output, tokens_used, monitor.colors['green'])
    
    tk.Frame(content, bg=monitor.colors['bg3'], height=1).pack(fill='x', pady=15)
    
    tk.Label(content, text="SESSION INFO", font=('Segoe UI', 9),
            bg=monitor.colors['bg'], fg=monitor.colors['muted']).pack(anchor='w', pady=(0, 5))
    
    info_frame = tk.Frame(content, bg=monitor.colors['bg2'], padx=12, pady=10)
    info_frame.pack(fill='x')
    
    tk.Label(info_frame, text=f"File Size: {file_size / 1024 / 1024:.2f} MB", 
            font=('Segoe UI', 9), bg=monitor.colors['bg2'], fg=monitor.colors['text']).pack(anchor='w')
    tk.Label(info_frame, text=f"Context Window: {context_window:,} tokens", 
            font=('Segoe UI', 9), bg=monitor.colors['bg2'], fg=monitor.colors['text']).pack(anchor='w')


# ==== ANALYTICS DASHBOARD (Extracted from context_monitor.pyw - Phase 3) ====

def show_analytics_dashboard(monitor):
    """Show comprehensive analytics dashboard with auto-refresh and flicker-free updates"""
    import time
    from datetime import timedelta
    
    # Create window
    win = tk.Toplevel(monitor.root)
    win.title("Analytics Dashboard")
    win.geometry("650x800")
    win.configure(bg=monitor.colors['bg'])
    win.attributes('-topmost', True)
    win.resizable(True, True)
    
    # Title
    tk.Label(win, text="📊 Token Analytics Dashboard",
            font=('Segoe UI', 14, 'bold'),
            bg=monitor.colors['bg'], fg=monitor.colors['text']).pack(pady=(15, 10))
    
    # Main container with scrollbar
    container = tk.Frame(win, bg=monitor.colors['bg'])
    container.pack(fill='both', expand=True, padx=20, pady=10)

    canvas = tk.Canvas(container, bg=monitor.colors['bg'], highlightthickness=0)
    scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
    
    main_frame = tk.Frame(canvas, bg=monitor.colors['bg'])
    
    # Configure scrolling
    main_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )
    
    canvas_frame = canvas.create_window((0, 0), window=main_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    
    def on_canvas_configure(event):
        canvas.itemconfig(canvas_frame, width=event.width)
    canvas.bind("<Configure>", on_canvas_configure)

    def _on_mousewheel(event):
        if canvas.winfo_exists():
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    canvas.bind_all("<MouseWheel>", _on_mousewheel)
    win.protocol("WM_DELETE_WINDOW", lambda: (canvas.unbind_all("<MouseWheel>"), win.destroy()))
    
    # ===== DYNAMIC CONTENT LABELS =====
    dashboard_refs = {}
    
    # 0. SESSION TREND GRAPH
    trend_frame = tk.Frame(main_frame, bg=monitor.colors['bg2'], padx=15, pady=10)
    trend_frame.pack(fill='x', pady=(0, 10))
    tk.Label(trend_frame, text="📈 Session Trend (Last Hour)",
            font=('Segoe UI', 10), bg=monitor.colors['bg2'], fg=monitor.colors['text2']).pack(anchor='w')
    
    dashboard_refs['trend_canvas'] = tk.Canvas(trend_frame, height=60, bg=monitor.colors['bg3'], highlightthickness=0)
    dashboard_refs['trend_canvas'].pack(fill='x', pady=(5,0))
    
    # 1. TIME TO HANDOFF
    ttf_frame = tk.Frame(main_frame, bg=monitor.colors['bg2'], padx=15, pady=10)
    ttf_frame.pack(fill='x', pady=(0, 10))
    
    tk.Label(ttf_frame, text="⏱️ Estimated Time to Handoff:",
            font=('Segoe UI', 10), bg=monitor.colors['bg2'], fg=monitor.colors['text2']).pack(side='left')
    
    dashboard_refs['ttf_label'] = tk.Label(ttf_frame, text="—",
            font=('Segoe UI', 16, 'bold'), bg=monitor.colors['bg2'], fg=monitor.colors['text'])
    dashboard_refs['ttf_label'].pack(side='right')

    # 2. TODAY'S USAGE
    today_frame = tk.Frame(main_frame, bg=monitor.colors['bg2'], padx=15, pady=10)
    today_frame.pack(fill='x', pady=(0, 10))
    
    tk.Label(today_frame, text="📅 Today's Usage:",
            font=('Segoe UI', 10), bg=monitor.colors['bg2'], fg=monitor.colors['text2']).pack(anchor='w')
    
    bar_frame = tk.Frame(today_frame, bg=monitor.colors['bg3'], height=20)
    bar_frame.pack(fill='x', pady=5)
    
    dashboard_refs['bar_fill'] = tk.Frame(bar_frame, bg=monitor.colors['green'], height=20)
    dashboard_refs['bar_fill'].place(relwidth=0, relheight=1)
    
    dashboard_refs['usage_label'] = tk.Label(today_frame, text="Calculating...",
            font=('Segoe UI', 9), bg=monitor.colors['bg2'], fg=monitor.colors['text'])
    dashboard_refs['usage_label'].pack(anchor='w')
    
    dashboard_refs['reset_label'] = tk.Label(today_frame, text="",
            font=('Segoe UI', 8, 'italic'), bg=monitor.colors['bg2'], fg=monitor.colors['muted'])
    dashboard_refs['reset_label'].pack(anchor='w', pady=(2,0))

    # 3. WEEKLY CHART
    week_container = tk.Frame(main_frame, bg=monitor.colors['bg2'])
    week_container.pack(fill='x', pady=(0, 10))
    
    week_frame_inner = tk.LabelFrame(week_container, text=" 📈 Last 7 Days ", 
                               bg=monitor.colors['bg2'], fg=monitor.colors['text'],
                               font=('Segoe UI', 10, 'bold'), padx=10, pady=10)
    week_frame_inner.pack(fill='x')
    
    chart_frame = tk.Frame(week_frame_inner, bg=monitor.colors['bg2'])
    chart_frame.pack(fill='x', expand=True)
    
    dashboard_refs['week_slots'] = []
    for i in range(7):
        col = tk.Frame(chart_frame, bg=monitor.colors['bg2'])
        col.pack(side='left', expand=True, fill='both', padx=2)
        
        bar_container = tk.Frame(col, bg=monitor.colors['bg2'], height=60, width=30)
        bar_container.pack(side='bottom')
        bar = tk.Frame(bar_container, bg=monitor.colors['blue'])
        bar.place(relx=0, rely=1.0, relwidth=1.0, relheight=0.0, anchor='sw')
        
        lbl_day = tk.Label(col, text="-", font=('Segoe UI', 8), bg=monitor.colors['bg2'], fg=monitor.colors['muted'])
        lbl_day.pack(side='bottom')
        
        lbl_val = tk.Label(col, text="0", font=('Consolas', 7), bg=monitor.colors['bg2'], fg=monitor.colors['text2'])
        lbl_val.pack(side='bottom')
        
        dashboard_refs['week_slots'].append({'bar': bar, 'day': lbl_day, 'val': lbl_val})

    # 4. PROJECT LIST
    proj_container = tk.Frame(main_frame, bg=monitor.colors['bg2'])
    proj_container.pack(fill='both', expand=True, pady=(0, 10))
    
    proj_frame = tk.LabelFrame(proj_container, text=" 🗂️ Token Usage by Project ",
                           bg=monitor.colors['bg2'], fg=monitor.colors['text'],
                           font=('Segoe UI', 10, 'bold'), padx=10, pady=10)
    proj_frame.pack(fill='both', expand=True)

    dashboard_refs['proj_slots'] = []
    for i in range(5):
        row = tk.Frame(proj_frame, bg=monitor.colors['bg2'])
        row.pack(fill='x', pady=2)
        lbl_name = tk.Label(row, text="", font=('Segoe UI', 9),
                bg=monitor.colors['bg2'], fg=monitor.colors['text'], width=25, anchor='w')
        lbl_name.pack(side='left')
        lbl_val = tk.Label(row, text="", font=('Consolas', 9), bg=monitor.colors['bg2'], fg=monitor.colors['blue'])
        lbl_val.pack(side='right')
        dashboard_refs['proj_slots'].append({'row': row, 'name': lbl_name, 'val': lbl_val})
        
    # 5. PROJECT DISTRIBUTION
    dist_frame = tk.Frame(main_frame, bg=monitor.colors['bg2'], padx=15, pady=10)
    dist_frame.pack(fill='x')
    tk.Label(dist_frame, text="📊 Project Distribution", font=('Segoe UI', 9),
            bg=monitor.colors['bg2'], fg=monitor.colors['muted']).pack(anchor='w', pady=(0,5))
    
    dashboard_refs['dist_bar'] = tk.Frame(dist_frame, bg=monitor.colors['bg3'], height=15)
    dashboard_refs['dist_bar'].pack(fill='x')
    
    # ===== SYSTEM DIAGNOSTICS SECTION =====
    diag_container = tk.Frame(main_frame, bg=monitor.colors['bg2'])
    diag_container.pack(fill='x', pady=(20, 10))
    
    diag_frame = tk.LabelFrame(diag_container, text=" 🔧 System Health ",
                           bg=monitor.colors['bg2'], fg=monitor.colors['text'],
                           font=('Segoe UI', 10, 'bold'), padx=10, pady=10)
    diag_frame.pack(fill='x')
    
    dashboard_refs['ram_label'] = tk.Label(diag_frame, text="RAM: Calculating...", 
                                    font=('Segoe UI', 9), bg=monitor.colors['bg2'], fg=monitor.colors['text'])
    dashboard_refs['ram_label'].pack(anchor='w')
    
    dashboard_refs['proc_label'] = tk.Label(diag_frame, text="Processes: Calculating...",
                                     font=('Segoe UI', 9), bg=monitor.colors['bg2'], fg=monitor.colors['text'])
    dashboard_refs['proc_label'].pack(anchor='w', pady=(2, 0))
    
    tk.Label(diag_frame, text="Top Processes (RAM):", font=('Segoe UI', 9, 'bold'),
            bg=monitor.colors['bg2'], fg=monitor.colors['text2']).pack(anchor='w', pady=(10, 5))
            
    dashboard_refs['proc_bars'] = []
    for i in range(5):
        f = tk.Frame(diag_frame, bg=monitor.colors['bg2'])
        f.pack(fill='x', pady=2)
        l = tk.Label(f, text="", font=('Consolas', 9), bg=monitor.colors['bg2'], fg=monitor.colors['text'], width=20, anchor='w')
        l.pack(side='left')
        b_bg = tk.Frame(f, bg=monitor.colors['bg3'], height=10)
        b_bg.pack(side='left', fill='x', expand=True, padx=5)
        b_fill = tk.Frame(b_bg, bg=monitor.colors['blue'], height=10)
        b_fill.place(relx=0, rely=0, relwidth=0, relheight=1)
        v = tk.Label(f, text="", font=('Consolas', 9), bg=monitor.colors['bg2'], fg=monitor.colors['text2'])
        v.pack(side='right')
        dashboard_refs['proc_bars'].append({'row': f, 'name': l, 'bar': b_fill, 'val': v})

    # ===== MODEL USAGE SECTION =====
    model_container = tk.Frame(main_frame, bg=monitor.colors['bg2'])
    model_container.pack(fill='x', pady=(20, 10))
    
    model_frame = tk.LabelFrame(model_container, text=" 🤖 AI Model Usage ",
                           bg=monitor.colors['bg2'], fg=monitor.colors['text'],
                           font=('Segoe UI', 10, 'bold'), padx=10, pady=10)
    model_frame.pack(fill='x')
    
    dashboard_refs['model_bars'] = []
    for i in range(4):
        f = tk.Frame(model_frame, bg=monitor.colors['bg2'])
        f.pack(fill='x', pady=2)
        l = tk.Label(f, text="", font=('Consolas', 9), bg=monitor.colors['bg2'], fg=monitor.colors['text'], width=20, anchor='w')
        l.pack(side='left')
        b_bg = tk.Frame(f, bg=monitor.colors['bg3'], height=10)
        b_bg.pack(side='left', fill='x', expand=True, padx=5)
        b_fill = tk.Frame(b_bg, bg=monitor.colors['green'], height=10)
        b_fill.place(relx=0, rely=0, relwidth=0, relheight=1)
        v = tk.Label(f, text="", font=('Consolas', 9), bg=monitor.colors['bg2'], fg=monitor.colors['text2'])
        v.pack(side='right')
        dashboard_refs['model_bars'].append({'row': f, 'name': l, 'bar': b_fill, 'val': v})

    # ===== BUDGET SETTING =====
    budget_frame = tk.Frame(main_frame, bg=monitor.colors['bg2'], padx=15, pady=10)
    budget_frame.pack(fill='x', pady=(10, 0))
    
    tk.Label(budget_frame, text="💰 Daily Budget:",
            font=('Segoe UI', 10), bg=monitor.colors['bg2'], fg=monitor.colors['text2']).pack(side='left')
    
    budget_var = tk.StringVar(value=str(monitor._daily_budget))
    budget_entry = tk.Entry(budget_frame, textvariable=budget_var, width=10,
                           bg=monitor.colors['bg3'], fg=monitor.colors['text'],
                           insertbackground=monitor.colors['text'], font=('Consolas', 10))
    budget_entry.pack(side='left', padx=10)
    
    def save_budget():
        try:
            new_budget = int(budget_var.get())
            monitor._daily_budget = new_budget
            monitor.settings['daily_budget'] = new_budget
            monitor.save_settings()
            tk.Label(budget_frame, text="✓ Saved", font=('Segoe UI', 9),
                    bg=monitor.colors['bg2'], fg=monitor.colors['green']).pack(side='left')
        except ValueError:
            pass
    
    tk.Button(budget_frame, text="Save", command=save_budget,
             bg=monitor.colors['blue'], fg='white', font=('Segoe UI', 9),
             relief='flat', padx=10).pack(side='left')
    
    # ===== CONTEXT WINDOW SETTING =====
    ctx_frame = tk.Frame(main_frame, bg=monitor.colors['bg2'], padx=15, pady=10)
    ctx_frame.pack(fill='x', pady=(10, 0))
    
    tk.Label(ctx_frame, text="🎯 Context Window:",
            font=('Segoe UI', 10), bg=monitor.colors['bg2'], fg=monitor.colors['text2']).pack(side='left')
    
    ctx_var = tk.StringVar(value=str(monitor._context_window))
    ctx_entry = tk.Entry(ctx_frame, textvariable=ctx_var, width=12,
                        bg=monitor.colors['bg3'], fg=monitor.colors['text'],
                        insertbackground=monitor.colors['text'], font=('Consolas', 10))
    ctx_entry.pack(side='left', padx=10)
    
    ctx_status = tk.Label(ctx_frame, text="", font=('Segoe UI', 9),
                         bg=monitor.colors['bg2'], fg=monitor.colors['green'])
    
    def save_context():
        try:
            new_ctx = int(ctx_var.get())
            monitor._context_window = new_ctx
            monitor.settings['context_window'] = new_ctx
            monitor.save_settings()
            ctx_status.config(text="✓")
            win.after(1500, lambda: ctx_status.config(text=""))
        except ValueError:
            pass
    
    tk.Button(ctx_frame, text="Save", command=save_context,
             bg=monitor.colors['blue'], fg='white', font=('Segoe UI', 9),
             relief='flat', padx=5).pack(side='left')
    
    ctx_status.pack(side='left', padx=5)
    
    # Model selector dropdown
    model_sel_frame = tk.Frame(main_frame, bg=monitor.colors['bg2'], padx=15, pady=10)
    model_sel_frame.pack(fill='x', pady=(10, 0))
    
    tk.Label(model_sel_frame, text="🤖 AI Model:",
            font=('Segoe UI', 10), bg=monitor.colors['bg2'], fg=monitor.colors['text2']).pack(side='left')
    
    models = monitor.MODELS
    
    if 'model' not in monitor.settings:
         current_model = "Custom"
         for name, ctx in models.items():
             if ctx == monitor._context_window:
                 current_model = name
                 break
         monitor.settings['model'] = current_model
    
    current_model = monitor.settings.get('model', 'Custom')
    
    model_var = tk.StringVar(value=current_model)
    
    model_menu = tk.OptionMenu(model_sel_frame, model_var, *models.keys())
    model_menu.config(bg=monitor.colors['bg3'], fg=monitor.colors['text'],
                     activebackground=monitor.colors['blue'], activeforeground='white',
                     highlightthickness=0, font=('Segoe UI', 9))
    model_menu['menu'].config(bg=monitor.colors['bg3'], fg=monitor.colors['text'],
                              activebackground=monitor.colors['blue'], activeforeground='white')
    model_menu.pack(side='left', padx=10)
    
    model_status = tk.Label(model_sel_frame, text="", font=('Segoe UI', 9),
                           bg=monitor.colors['bg2'], fg=monitor.colors['green'])
    model_status.pack(side='left')
    
    def on_model_change(*args):
        selected = model_var.get()
        ctx = models.get(selected)
        if ctx is not None:
            monitor._context_window = ctx
            ctx_var.set(str(ctx))
            monitor.settings['context_window'] = ctx
            monitor.settings['model'] = selected
            monitor.save_settings()
            model_status.config(text=f"✓ {ctx:,} tokens")
            win.after(2000, lambda: model_status.config(text=""))
    
    model_var.trace('w', on_model_change)

    # Start update loop
    update_dashboard_stats(monitor, win, dashboard_refs)


def update_dashboard_stats(monitor, win, dashboard_refs):
    """Update dashboard statistics flicker-free"""
    import time
    from datetime import timedelta
    
    if not win.winfo_exists():
        return
        
    try:
        analytics = monitor.load_analytics()
        
        # --- 0. UPDATE TREND GRAPH ---
        if monitor.current_session:
            history = monitor.load_history().get(monitor.current_session['id'], [])
            cutoff = time.time() - 3600
            recent = [h for h in history if h['ts'] > cutoff]
            
            canvas = dashboard_refs['trend_canvas']
            canvas.delete('all')
            
            if len(recent) > 1:
                w = canvas.winfo_width()
                h = 60
                min_ts = recent[0]['ts']
                time_span = recent[-1]['ts'] - min_ts or 1
                max_tok = max(p['tokens'] for p in recent)
                min_tok = min(p['tokens'] for p in recent)
                val_span = max_tok - min_tok or 1
                
                points = []
                for p in recent:
                    x = (p['ts'] - min_ts) / time_span * w
                    y = h - ((p['tokens'] - min_tok) / val_span * (h - 10) + 5)
                    points.append((x, y))
                
                if len(points) > 1:
                    canvas.create_line(points, fill=monitor.colors['blue'], width=2, smooth=True)
                    canvas.create_oval(points[-1][0]-3, points[-1][1]-3, points[-1][0]+3, points[-1][1]+3, fill=monitor.colors['green'], outline='')
        
        # --- 1. UPDATE TIME TO HANDOFF ---
        seconds_remaining = monitor.calculate_time_to_handoff()
        time_str = monitor.format_time_remaining(seconds_remaining)
        
        time_color = monitor.colors['green']
        if seconds_remaining is not None:
            if seconds_remaining < 300: time_color = monitor.colors['red']
            elif seconds_remaining < 900: time_color = monitor.colors['yellow']
        
        dashboard_refs['ttf_label'].config(text=time_str, fg=time_color)
        
        # --- 2. UPDATE TODAY'S USAGE ---
        today = datetime.now().strftime('%Y-%m-%d')
        today_tokens = analytics['daily'].get(today, {}).get('total', 0)
        budget = monitor._daily_budget
        budget_pct = min(100, (today_tokens / budget) * 100) if budget > 0 else 0
        
        bar_color = monitor.colors['green']
        if budget_pct >= 90: bar_color = monitor.colors['red']
        elif budget_pct >= 75: bar_color = monitor.colors['yellow']
        
        dashboard_refs['bar_fill'].configure(bg=bar_color)
        dashboard_refs['bar_fill'].place(relwidth=budget_pct/100, relheight=1)
        
        dashboard_refs['usage_label'].config(
            text=f"{today_tokens:,} / {budget:,} tokens ({budget_pct:.0f}%)"
        )
        
        # Reset Countdown
        now_utc = datetime.utcnow()
        today_reset = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        if now_utc >= today_reset:
            next_reset = today_reset + timedelta(days=1)
        else:
            next_reset = today_reset
        
        time_until = next_reset - now_utc
        h_val, r = divmod(time_until.seconds, 3600)
        m_val = r // 60
        dashboard_refs['reset_label'].config(text=f"🔄 Daily Stats Reset in: {h_val}h {m_val}m (Midnight UTC)")

        # --- 3. UPDATE WEEKLY CHART ---
        weekly = monitor.get_weekly_summary()
        weekly_rev = list(reversed(weekly))
        max_tokens = max((d['tokens'] for d in weekly), default=1)
        
        for i, slot in enumerate(dashboard_refs['week_slots']):
            if i < len(weekly_rev):
                day = weekly_rev[i]
                pct = (day['tokens'] / max_tokens) if max_tokens > 0 else 0
                
                slot['bar'].place(relheight=pct)
                slot['day'].config(text=day['day_name'])
                tokens_k = day['tokens'] / 1000
                slot['val'].config(text=f"{tokens_k:.0f}k" if day['tokens'] > 0 else "0")
            else:
                slot['bar'].place(relheight=0)
                slot['day'].config(text="-")
                slot['val'].config(text="")

        # --- 4. UPDATE PROJECT LIST ---
        projects = monitor.get_project_summary()
        total_proj = sum(p['tokens'] for p in projects)
        
        for i, slot in enumerate(dashboard_refs['proj_slots']):
            if i < len(projects):
                proj = projects[i]
                pct = (proj['tokens'] / total_proj * 100) if total_proj > 0 else 0
                slot['name'].config(text=proj['name'])
                slot['val'].config(text=f"{proj['tokens']:,} ({pct:.0f}%)")
                slot['row'].pack(fill='x', pady=2)
            else:
                slot['name'].config(text="")
                slot['val'].config(text="")
                slot['row'].pack_forget()
                
        # --- 5. UPDATE PROJECT DISTRIBUTION BAR ---
        dist_bar = dashboard_refs['dist_bar']
        for widget in dist_bar.winfo_children():
            widget.destroy()
        
        colors = [monitor.colors['blue'], monitor.colors['green'], monitor.colors['yellow'], monitor.colors['red']]
        running_pct = 0
        for i, proj in enumerate(projects[:4]):
            pct = (proj['tokens'] / total_proj) if total_proj > 0 else 0
            if pct > 0.05:
                col = colors[i % len(colors)]
                f = tk.Frame(dist_bar, bg=col)
                f.place(relx=running_pct, relwidth=pct, relheight=1)
                running_pct += pct
        
        # --- 6. UPDATE SYSTEM DIAGNOSTICS ---
        procs = monitor.get_antigravity_processes()
        total_mem = sum(p.get('Mem', 0) for p in procs)
        limits = monitor.thresholds
        
        mem_color = monitor.colors['green']
        if total_mem > limits['total_crit']: mem_color = monitor.colors['red']
        elif total_mem > limits['total_warn']: mem_color = monitor.colors['yellow']
        
        dashboard_refs['ram_label'].config(text=f"RAM Detected: {monitor.total_ram_mb // 1024} GB | Total Usage: {total_mem}MB", fg=mem_color)
        dashboard_refs['proc_label'].config(text=f"Active Processes: {len(procs)}")
        
        max_p_mem = max((p.get('Mem', 0) for p in procs), default=500)
        
        for i, slot in enumerate(dashboard_refs['proc_bars']):
            if i < len(procs):
                p = procs[i]
                mem = p.get('Mem', 0)
                pct = (mem / max_p_mem) if max_p_mem > 0 else 0
                ptype = p.get('Type', 'Unknown')
                
                p_color = monitor.colors['blue']
                if mem > limits['proc_crit']: p_color = monitor.colors['red']
                elif mem > limits['proc_warn']: p_color = monitor.colors['yellow']

                slot['name'].config(text=ptype)
                slot['val'].config(text=f"{mem}MB")
                slot['bar'].config(bg=p_color)
                slot['bar'].place(relwidth=pct)
                slot['row'].pack(fill='x', pady=2)
            else:
                slot['row'].pack_forget()

        # --- 7. UPDATE MODEL USAGE ---
        models_data = analytics.get('models', {})
        sorted_models = sorted(models_data.items(), key=lambda x: x[1]['total'], reverse=True)
        total_model_tokens = sum(m[1]['total'] for m in sorted_models)
        
        for i, slot in enumerate(dashboard_refs['model_bars']):
            if i < len(sorted_models):
                m_name, m_data = sorted_models[i]
                m_tokens = m_data['total']
                pct = (m_tokens / total_model_tokens) if total_model_tokens > 0 else 0
                
                slot['name'].config(text=m_name)
                slot['val'].config(text=f"{m_tokens:,} ({pct:.0%})")
                slot['bar'].place(relwidth=pct)
                slot['row'].pack(fill='x', pady=2)
            else:
                slot['row'].pack_forget()

        # Schedule next update
        win.after(1000, lambda: update_dashboard_stats(monitor, win, dashboard_refs))
        
    except Exception as e:
        print(f"Dashboard update error: {e}")

# ==== MAINTENANCE DIALOGS (Extracted from context_monitor.pyw - Phase 4) ====
from tkinter import messagebox, filedialog
import csv
import gzip
import shutil
from datetime import datetime
from utils import get_large_conversations

def cleanup_old_conversations(monitor):
    """Delete conversation files older than 7 days and larger than 5MB"""
    files = get_large_conversations(monitor.conversations_dir, min_size_mb=5)
    if not files:
        messagebox.showinfo("Cleanup", "No large files to clean up!")
        return
    
    msg = f"Found {len(files)} large conversation files:\n\n"
    for f in files:
        msg += f"• {f['name']}: {f['size_mb']}MB\n"
    msg += "\nDelete these files? (Current session will be preserved)"
    
    if messagebox.askyesno("Cleanup Old Conversations", msg):
        deleted = 0
        current_id = monitor.current_session['id'] if monitor.current_session else None
        for f in files:
            if current_id and current_id in str(f['path']):
                continue  # Skip current session
            try:
                f['path'].unlink()
                deleted += 1
            except Exception as e:
                print(f"Error deleting {f['path']}: {e}")
        messagebox.showinfo("Cleanup Complete", f"Deleted {deleted} files.")

def archive_old_sessions(monitor):
    """Compress old session files using gzip to save disk space"""
    # Find sessions older than 3 days that aren't already compressed
    cutoff = datetime.now().timestamp() - (3 * 24 * 60 * 60)  # 3 days ago
    current_id = monitor.current_session['id'] if monitor.current_session else None
    
    to_compress = []
    total_size = 0
    
    for f in monitor.conversations_dir.glob('*.pb'):
        if '.tmp' in f.name:
            continue
        if current_id and current_id in f.stem:
            continue  # Skip current session
        
        stat = f.stat()
        if stat.st_mtime < cutoff and stat.st_size > 100000:  # Older than 3 days, > 100KB
            to_compress.append({
                'path': f,
                'size_mb': round(stat.st_size / 1024 / 1024, 2),
                'age_days': int((datetime.now().timestamp() - stat.st_mtime) / 86400)
            })
            total_size += stat.st_size
    
    if not to_compress:
        messagebox.showinfo("Archive", "No old sessions to compress!\n(Sessions must be >3 days old)")
        return
    
    msg = f"Found {len(to_compress)} old sessions ({total_size/1024/1024:.1f} MB total):\n\n"
    for f in to_compress[:5]:
        msg += f"• {f['path'].stem[:16]}... ({f['size_mb']}MB, {f['age_days']}d old)\n"
    if len(to_compress) > 5:
        msg += f"... and {len(to_compress) - 5} more\n"
    msg += f"\nCompress these to save ~70% disk space?"
    
    if messagebox.askyesno("Archive Old Sessions", msg):
        compressed = 0
        saved_bytes = 0
        
        for f in to_compress:
            try:
                orig_path = f['path']
                gz_path = orig_path.with_suffix('.pb.gz')
                
                # Compress the file
                with open(orig_path, 'rb') as f_in:
                    with gzip.open(gz_path, 'wb', compresslevel=6) as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                # Calculate savings
                orig_size = orig_path.stat().st_size
                new_size = gz_path.stat().st_size
                saved_bytes += orig_size - new_size
                
                # Delete original
                orig_path.unlink()
                compressed += 1
                
            except Exception as e:
                print(f"Error compressing {f['path']}: {e}")
        
        saved_mb = saved_bytes / 1024 / 1024
        messagebox.showinfo("Archive Complete", 
                          f"Compressed {compressed} sessions\nSaved {saved_mb:.1f} MB of disk space!")

def export_history_csv(monitor):
    """Export history to CSV via dialog"""
    try:
        # Get all history data
        history = monitor.load_history()
        analytics = monitor.load_analytics()
        
        # Flatten data for CSV
        rows = []
        for session_id, points in history.items():
            proj_name = monitor.project_name_cache.get(session_id, "Unknown")
            for p in points:
                rows.append({
                    'timestamp': datetime.fromtimestamp(p['ts']).strftime('%Y-%m-%d %H:%M:%S'),
                    'session_id': session_id,
                    'project': proj_name,
                    'tokens': p['tokens'],
                    'delta': p.get('delta', 0)
                })
        
        if not rows:
            messagebox.showinfo("Export", "No history data to export.")
            return

        # Sort by time
        rows.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Save dialog
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")],
            initialfile=f"context_history_{datetime.now().strftime('%Y%m%d')}.csv"
        )
        
        if filename:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['timestamp', 'session_id', 'project', 'tokens', 'delta'])
                writer.writeheader()
                writer.writerows(rows)
            messagebox.showinfo("Export Successful", f"Saved {len(rows)} records to\n{filename}")
            
    except Exception as e:
        messagebox.showerror("Export Error", f"Failed to export CSV:\n{e}")
