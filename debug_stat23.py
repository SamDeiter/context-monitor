import os
import re
from pathlib import Path
import time

conversations_dir = Path.home() / '.gemini' / 'antigravity' / 'conversations'

def get_project_name(session_id):
    try:
        pb_file = conversations_dir / f"{session_id}.pb"
        if pb_file.exists():
            content = pb_file.read_bytes()
            text = content.decode('utf-8', errors='ignore')
            
            patterns = [
                r'CorpusName[:\s]+([A-Za-z0-9_-]+/[A-Za-z0-9_-]+)',
                r'GitHub[/\\]([A-Za-z0-9_-]+)',
                r'Users[/\\][^/\\]+[/\\]Documents[/\\]GitHub[/\\]([A-Za-z0-9_-]+)',
                r'([A-Za-z0-9_-]+)[/\\]\.git',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, text, re.IGNORECASE)
                if matches:
                    name = matches[-1]
                    if '/' in name:
                        name = name.split('/')[-1]
                    return name
        return "Unknown"
    except Exception as e:
        return f"Error: {e}"

def list_sessions():
    print(f"Conversations Dir: {conversations_dir}")
    files = list(conversations_dir.glob('*.pb'))
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    print(f"{'Session ID':<10} | {'Modified':<20} | {'Project Name'}")
    print("-" * 60)
    for f in files[:15]:
        mtime = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(f.stat().st_mtime))
        pname = get_project_name(f.stem)
        print(f"{f.stem[:8]:<10} | {mtime:<20} | {pname}")

if __name__ == "__main__":
    list_sessions()
