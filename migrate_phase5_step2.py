"""
Phase 5 Step 2 - Extract show_analytics_dashboard and update_dashboard_stats
"""
from pathlib import Path
import re

TARGET_FILE = Path(r"C:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.pyw")
content = TARGET_FILE.read_text(encoding='utf-8')
original_lines = len(content.split('\n'))

print(f"[Phase 5 Step 2] Starting analytics extraction from {original_lines} lines")

def replace_method_body(content, method_name, new_body):
    """Replace a method's body with a thin wrapper"""
    lines = content.split('\n')
    result = []
    in_target_method = False
    method_indent = 0
    skip_lines = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        if f'def {method_name}(self' in line and not in_target_method:
            in_target_method = True
            method_indent = len(line) - len(line.lstrip())
            # Preserve original signature
            result.append(line)
            result.append(f'{" " * method_indent}    """Delegated to analytics_dashboard module (Phase 5: V2.48)"""')
            result.append(f'{" " * method_indent}    {new_body}')
            skip_lines = True
            i += 1
            continue
        
        if skip_lines:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and not stripped.startswith('"""') and not stripped.startswith("'''"):
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= method_indent and (stripped.startswith('def ') or stripped.startswith('class ')):
                    skip_lines = False
                    in_target_method = False
                    result.append(line)
            i += 1
            continue
        
        result.append(line)
        i += 1
    
    return '\n'.join(result)

# Add import
if 'from analytics_dashboard import' not in content:
    content = content.replace(
        'from menu_builder import build_context_menu',
        'from menu_builder import build_context_menu\nfrom analytics_dashboard import show_analytics_dashboard_dialog, update_dashboard_stats_impl'
    )

# Replace show_analytics_dashboard
print("[Phase 5] Replacing show_analytics_dashboard...")
content = replace_method_body(content, 'show_analytics_dashboard', 'show_analytics_dashboard_dialog(self)')

# Replace update_dashboard_stats  
print("[Phase 5] Replacing update_dashboard_stats...")
content = replace_method_body(content, 'update_dashboard_stats', 'update_dashboard_stats_impl(self, win)')

# Write result
TARGET_FILE.write_text(content, encoding='utf-8')

new_lines = len(content.split('\n'))
print(f"\n[✓] Phase 5 Step 2 complete!")
print(f"    Lines: {original_lines} → {new_lines} ({original_lines - new_lines} lines removed)")
