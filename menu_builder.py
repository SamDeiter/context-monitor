"""
Menu Builder - Context menu for Context Monitor
Extracted from context_monitor.pyw (Phase 5: V2.48)
"""
import tkinter as tk
from collections import OrderedDict
from datetime import datetime
from functools import partial


def build_context_menu(monitor, event):
    """Build and show the right-click context menu"""
    menu = tk.Menu(monitor.root, tearoff=0, 
                  bg=monitor.colors['bg2'], 
                  fg=monitor.colors['text'],
                  activebackground=monitor.colors['blue'], 
                  activeforeground='white',
                  font=('Segoe UI', 9),
                  relief='flat',
                  borderwidth=1)
    
    # Diagnostics section
    menu.add_command(label="  📊  Show Diagnostics", command=monitor.show_diagnostics)
    menu.add_command(label="  📈  Advanced Token Stats", command=monitor.show_advanced_stats)
    menu.add_command(label="  📅  Usage History Graph", command=monitor.show_history)
    menu.add_command(label="  📊  Analytics Dashboard (D)", command=monitor.show_analytics_dashboard)
    menu.add_command(label="  💾  Export to CSV (E)", command=monitor.export_history_csv)
    menu.add_separator()
    
    menu.add_command(label="  🧹  Clean Old Conversations", command=monitor.cleanup_old_conversations)
    menu.add_command(label="  📦  Archive Old Sessions", command=monitor.archive_old_sessions)
    menu.add_command(label="  🔄  Restart Antigravity", command=monitor.restart_antigravity)
    menu.add_separator()
    
    # Sessions submenu
    sessions_menu = tk.Menu(menu, tearoff=0,
                          bg=monitor.colors['bg2'],
                          fg=monitor.colors['text'],
                          activebackground=monitor.colors['blue'],
                          activeforeground='white')
    
    current_id = monitor.current_session['id'] if monitor.current_session else None
    sessions = monitor.sessions_cache[:15]
    
    # Group by project
    known_projects = OrderedDict()
    unknown_sessions = []
    
    for s in sessions:
        if s['id'] in monitor.project_name_cache:
            project_name = monitor.project_name_cache[s['id']]
            if project_name not in known_projects:
                known_projects[project_name] = []
            known_projects[project_name].append(s)
        else:
            unknown_sessions.append(s)
    
    shown = 0
    for project_name, proj_sessions in known_projects.items():
        if shown >= 10:
            break
        
        display_project = (project_name[:28] + "…") if len(project_name) > 28 else project_name
        sessions_menu.add_command(label=f"📁 {display_project} ({len(proj_sessions)})", state='disabled')
        
        for s in proj_sessions[:3]:
            if shown >= 10:
                break
            check = "✓ " if s['id'] == current_id else "    "
            mod_time = datetime.fromtimestamp(s['modified']).strftime("%H:%M")
            label = f"{check}{mod_time}"
            sessions_menu.add_command(label=label, 
                                    command=lambda sid=s['id']: monitor.switch_session(sid))
            shown += 1
        
        if project_name != list(known_projects.keys())[-1] or unknown_sessions:
            sessions_menu.add_separator()
    
    if unknown_sessions and shown < 10:
        sessions_menu.add_command(label=f"📋 Other Sessions ({len(unknown_sessions)})", state='disabled')
        for s in unknown_sessions[:5]:
            if shown >= 10:
                break
            check = "✓ " if s['id'] == current_id else "    "
            short_id = s['id'][:8]
            mod_time = datetime.fromtimestamp(s['modified']).strftime("%H:%M")
            label = f"{check}{mod_time} • {short_id}…"
            sessions_menu.add_command(label=label, 
                                    command=lambda sid=s['id']: monitor.switch_session(sid))
            shown += 1
        
    menu.add_cascade(label="  🔀  Switch Session", menu=sessions_menu)
    menu.add_separator()
    
    # Mode toggle
    if monitor.mini_mode:
        menu.add_command(label="  ◳  Expand to Full Mode", command=monitor.toggle_mini_mode)
    else:
        menu.add_command(label="  ◱  Collapse to Mini Mode", command=monitor.toggle_mini_mode)
    
    menu.add_separator()
    
    # Polling speed submenu
    speed_menu = tk.Menu(menu, tearoff=0,
                        bg=monitor.colors['bg2'],
                        fg=monitor.colors['text'],
                        activebackground=monitor.colors['blue'],
                        activeforeground='white')
    
    speeds = [
        ("  ⚡  3 seconds (fast)", 3000),
        ("  🔄  5 seconds", 5000),
        ("  ⏱️  10 seconds (default)", 10000),
        ("  🐢  30 seconds (slow)", 30000),
    ]
    
    for label, interval in speeds:
        check = "✓ " if monitor.polling_interval == interval else "  "
        speed_menu.add_command(
            label=f"{check}{label}",
            command=partial(monitor.set_polling_speed, interval)
        )
    
    menu.add_cascade(label="  ⏱️  Refresh Speed", menu=speed_menu)
    
    # Model submenu
    model_menu = tk.Menu(menu, tearoff=0,
                         bg=monitor.colors['bg2'],
                         fg=monitor.colors['text'],
                         activebackground=monitor.colors['blue'],
                         activeforeground='white')
    
    current_model = monitor.settings.get('model', 'Unknown')
    for model_name, ctx_size in monitor.MODELS.items():
        check = "✓ " if current_model == model_name else "  "
        label = f"{check}{model_name}"
        def make_command(m, c):
            return lambda: (
                setattr(monitor, '_context_window', c),
                monitor.settings.update({'model': m, 'context_window': c}),
                monitor.save_settings()
            )
        model_menu.add_command(label=label, command=make_command(model_name, ctx_size))
    
    menu.add_cascade(label="  🤖  Active Model", menu=model_menu)
    menu.add_separator()
    
    menu.add_command(label="  📋  Copy Context Bridge", command=monitor.copy_handoff)
    menu.add_command(label="  🔄  Reload UI (Dev)", command=monitor.reload_ui)
    menu.add_separator()
    menu.add_command(label="  ✖  Exit", command=monitor.cleanup_and_exit)
    
    try:
        menu.tk_popup(event.x_root, event.y_root)
    finally:
        menu.grab_release()
