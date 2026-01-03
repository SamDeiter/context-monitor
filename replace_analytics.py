"""
Replace analytics dashboard methods with delegated version
Lines 1615-2143 (529 lines) -> 5 lines
"""
from pathlib import Path

content = Path('context_monitor.pyw').read_text(encoding='utf-8', errors='replace')
lines = content.splitlines(keepends=True)

# Keep lines 1-1614, replace 1615-2143, keep 2144+
before = lines[:1614]  # 0-indexed, so line 1-1614 is index 0-1613
after = lines[2143:]   # Line 2144+ is index 2143+

# Delegated version (matches indent)
delegated = [
    "    def show_analytics_dashboard(self):\r\n",
    "        \"\"\"Delegated to dialogs module (Phase 3: V2.53)\"\"\"\r\n",
    "        from dialogs import show_analytics_dashboard\r\n",
    "        show_analytics_dashboard(self)\r\n",
    "\r\n",
]

# Combine
new_content = ''.join(before) + ''.join(delegated) + ''.join(after)

# Write
Path('context_monitor.pyw').write_text(new_content, encoding='utf-8')

# Verify
final_lines = len(new_content.splitlines())
print(f"Done! context_monitor.pyw now has {final_lines} lines")
print(f"Removed {2143 - 1614} lines, added {len(delegated)} lines")
print(f"Net reduction: {(2143-1614) - len(delegated)} lines")
