"""
Phase 4 Step 2 - Replace dialog method bodies with thin wrappers
"""
from pathlib import Path
import re

TARGET_FILE = Path(r"C:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.pyw")

content = TARGET_FILE.read_text(encoding='utf-8')
original_lines = len(content.split('\n'))

# Replacement patterns - find method start and replace entire body
# Pattern: def method_name(self): ... until next def at same indentation level

def replace_method_body(content, method_name, new_body):
    """Replace a method's body with a thin wrapper, preserving indentation."""
    lines = content.split('\n')
    result = []
    in_target_method = False
    method_indent = 0
    skip_lines = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check if this is the start of our target method
        if f'def {method_name}(self)' in line and not in_target_method:
            in_target_method = True
            method_indent = len(line) - len(line.lstrip())
            # Add the new wrapper
            result.append(f'{" " * method_indent}def {method_name}(self):')
            result.append(f'{" " * method_indent}    """Delegated to dialogs module (Phase 4: V2.47)"""')
            result.append(f'{" " * method_indent}    {new_body}')
            skip_lines = True
            i += 1
            continue
        
        if skip_lines:
            # Check if we've hit the next method or class at same/higher level
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

# Apply replacements
print("[Phase 4] Replacing show_history body...")
content = replace_method_body(content, 'show_history', 'show_history_dialog(self)')

print("[Phase 4] Replacing show_diagnostics body...")
content = replace_method_body(content, 'show_diagnostics', 'show_diagnostics_dialog(self)')

print("[Phase 4] Replacing show_advanced_stats body...")
content = replace_method_body(content, 'show_advanced_stats', 'show_advanced_stats_dialog(self)')

# Write result
TARGET_FILE.write_text(content, encoding='utf-8')

new_lines = len(content.split('\n'))
print(f"\n[✓] Migration complete!")
print(f"    Lines: {original_lines} → {new_lines} ({original_lines - new_lines} lines removed)")
