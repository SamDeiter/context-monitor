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
