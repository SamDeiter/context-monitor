"""Find analytics dashboard method boundaries"""
from pathlib import Path

# Read file
content = Path('context_monitor.pyw').read_text(encoding='utf-8', errors='replace')
lines = content.splitlines()

print(f"Total lines: {len(lines)}")

# Find method boundaries
for i, line in enumerate(lines):
    if 'def show_analytics_dashboard' in line:
        print(f'show_analytics_dashboard at line {i+1}')
    if 'def update_dashboard_stats' in line:
        print(f'update_dashboard_stats at line {i+1}')
    if 'def export_history_csv' in line:
        print(f'export_history_csv at line {i+1}')
