import os
from pathlib import Path
import time

conversations_dir = Path.home() / '.gemini' / 'antigravity' / 'conversations'

files = list(conversations_dir.glob('*.pb'))
files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

print(f"Total sessions: {len(files)}")
print(f"{'Session ID':<36} | {'Modified'}")
print("-" * 60)
for f in files[:30]:
    mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(f.stat().st_mtime))
    print(f"{f.stem:<36} | {mtime}")
