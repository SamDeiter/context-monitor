"""
Migration Script - Replace legacy history/analytics methods with data_service
Phase 3 of Context Monitor modularization

This script:
1. Replaces load_history, save_history, _flush_history_cache
2. Replaces load_analytics, save_analytics, _flush_analytics_cache
3. Uses data_service singleton for all I/O
"""
import re
from pathlib import Path

TARGET_FILE = Path(r"C:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.pyw")
BACKUP_FILE = TARGET_FILE.parent / "context_monitor_pre_migration.py"

# Read original content
content = TARGET_FILE.read_text(encoding='utf-8')

# Backup first
BACKUP_FILE.write_text(content, encoding='utf-8')
print(f"[✓] Backed up to {BACKUP_FILE.name}")

# === PHASE 1: Replace legacy methods with thin wrappers ===

# Old load_history method - replace with delegation to data_service
OLD_LOAD_HISTORY = r'''    def load_history\(self, force_reload=False\):
        """Load history with caching \(Sprint 1: Performance\)"""
        import time
        now = time\.time\(\)
        
        # Return cache if valid \(less than 5 seconds old for fast updates\)
        if not force_reload and self\._history_cache is not None:
            if now - self\._history_cache_time < 5:
                return self\._history_cache
        
        # Load from disk
        try:
            if self\.history_file\.exists\(\):
                with open\(self\.history_file, 'r'\) as f:
                    self\._history_cache = json\.load\(f\)
                    self\._history_cache_time = now
                    return self\._history_cache
        except Exception as e:
            print\(f"History load error: \{e\}"\)
        
        self\._history_cache = \{\}
        self\._history_cache_time = now
        return self\._history_cache'''

NEW_LOAD_HISTORY = '''    def load_history(self, force_reload=False):
        """Load history using data_service (V2.46: Modularized)"""
        return data_service.load_history(force_reload)'''

# Old save_history method  
OLD_SAVE_HISTORY = r'''    def save_history\(self, session_id, tokens\):
        """Save history with caching and deferred writes \(Sprint 1: Performance\)"""
        import time
        now = time\.time\(\)
        
        # Calculate delta from last reading
        delta = tokens - self\.last_tokens if self\.last_tokens > 0 else 0
        self\.last_tokens = tokens
        
        # Throttle based on polling interval \(convert ms to seconds, minimum 2s\)
        throttle_seconds = max\(2, self\.polling_interval / 1000\)
        
        if not hasattr\(self, 'last_history_save'\):
            self\.last_history_save = 0
            
        # Always update cache, but throttle disk writes
        data = self\.load_history\(\)
        if session_id not in data:
            data\[session_id\] = \[\]
        
        # Add point with delta
        data\[session_id\]\.append\(\{
            'ts': now,
            'tokens': tokens,
            'delta': delta
        \}\)
        
        # Keep last 200 points per session
        if len\(data\[session_id\]\) > 200:
            data\[session_id\] = data\[session_id\]\[-200:\]
        
        # Update cache
        self\._history_cache = data
        self\._history_dirty = True
        
        # Only write to disk if throttle time has passed
        if now - self\.last_history_save >= throttle_seconds:
            self\._flush_history_cache\(\)
            self\.last_history_save = now'''

NEW_SAVE_HISTORY = '''    def save_history(self, session_id, tokens):
        """Save history using data_service (V2.46: Modularized)"""
        throttle_seconds = max(2, self.polling_interval / 1000)
        delta = data_service.save_history(session_id, tokens, self.last_tokens, throttle_seconds)
        self.last_tokens = tokens
        return delta'''

# Old _flush_history_cache method
OLD_FLUSH_HISTORY = r'''    def _flush_history_cache\(self\):
        """Write cached history to disk \(Sprint 1: Performance\)"""
        if not self\._history_dirty or self\._history_cache is None:
            return
            
        try:
            self\.history_file\.parent\.mkdir\(parents=True, exist_ok=True\)
            with open\(self\.history_file, 'w'\) as f:
                json\.dump\(self\._history_cache, f\)
            self\._history_dirty = False
        except Exception as e:
            print\(f"History flush error: \{e\}"\)'''

NEW_FLUSH_HISTORY = '''    def _flush_history_cache(self):
        """Flush via data_service (V2.46: Modularized)"""
        data_service._flush_history()'''

# Old _flush_analytics_cache method
OLD_FLUSH_ANALYTICS = r'''    def _flush_analytics_cache\(self\):
        """Write cached analytics to disk immediately"""
        if self\._analytics_cache is None:
            return
            
        try:
            self\.analytics_file\.parent\.mkdir\(parents=True, exist_ok=True\)
            save_data = \{
                'daily': self\._analytics_cache\.get\('daily', \{\}\),
                'projects': \{k: \{'total': v\['total'\]\} for k, v in self\._analytics_cache\.get\('projects', \{\}\)\.items\(\)\}
            \}
            with open\(self\.analytics_file, 'w'\) as f:
                json\.dump\(save_data, f, indent=2\)
            # Minimal logging on exit
            # print\(f"\[Analytics\] Flushed to disk: \{len\(save_data\.get\('daily', \{\}\)\)\} days"\)
        except Exception as e:
            print\(f"Analytics flush error: \{e\}"\)'''

NEW_FLUSH_ANALYTICS = '''    def _flush_analytics_cache(self):
        """Flush via data_service (V2.46: Modularized)"""
        data_service._flush_analytics()'''

# Apply replacements using simpler approach (literal match with line-by-line)
def find_and_replace_method(content, method_name, new_code):
    """Find a method by name and replace the entire definition"""
    lines = content.split('\n')
    result = []
    in_method = False
    method_indent = 0
    skip_until_next_def = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check if this is the start of our target method
        if f'def {method_name}(self' in line:
            in_method = True
            method_indent = len(line) - len(line.lstrip())
            # Add the new replacement code
            result.extend(new_code.split('\n'))
            skip_until_next_def = True
            i += 1
            continue
        
        if skip_until_next_def:
            # Check if we've hit the next method or class at same/higher level
            stripped = line.lstrip()
            if stripped and not stripped.startswith('#'):
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= method_indent and (stripped.startswith('def ') or stripped.startswith('class ')):
                    skip_until_next_def = False
                    result.append(line)
                # Skip this line (it's part of the old method)
            i += 1
            continue
        
        result.append(line)
        i += 1
    
    return '\n'.join(result)

# Apply all replacements
print("\n[Phase 1] Replacing load_history...")
content = find_and_replace_method(content, 'load_history', NEW_LOAD_HISTORY)

print("[Phase 1] Replacing save_history...")
content = find_and_replace_method(content, 'save_history', NEW_SAVE_HISTORY)

print("[Phase 1] Replacing _flush_history_cache...")
content = find_and_replace_method(content, '_flush_history_cache', NEW_FLUSH_HISTORY)

print("[Phase 1] Replacing _flush_analytics_cache...")
content = find_and_replace_method(content, '_flush_analytics_cache', NEW_FLUSH_ANALYTICS)

# === PHASE 2: Update load_analytics and save_analytics to use data_service ===
# These are more complex - save_analytics calls check_budget_notification

NEW_LOAD_ANALYTICS = '''    def load_analytics(self):
        """Load analytics using data_service (V2.46: Modularized)"""
        analytics = data_service.load_analytics()
        self._analytics_cache = analytics  # Keep local reference for compatibility
        return analytics'''

NEW_SAVE_ANALYTICS = '''    def save_analytics(self, tokens, project_name):
        """Track analytics using data_service (V2.46: Modularized)"""
        model_name = self.settings.get('model', 'Unknown')
        analytics = data_service.save_analytics(tokens, self.last_tokens, project_name, model_name)
        self._analytics_cache = analytics  # Keep local reference for compatibility
        
        # Check budget notification
        today = datetime.now().strftime('%Y-%m-%d')
        self.check_budget_notification(analytics, today)'''

print("[Phase 2] Replacing load_analytics...")
content = find_and_replace_method(content, 'load_analytics', NEW_LOAD_ANALYTICS)

print("[Phase 2] Replacing save_analytics...")
content = find_and_replace_method(content, 'save_analytics', NEW_SAVE_ANALYTICS)

# === PHASE 3: Remove unused cache variables from __init__ ===
# These are now handled by data_service, but we keep them for compatibility
# Actually, let's leave them - they're still referenced in migrations etc.

# Write the updated content
TARGET_FILE.write_text(content, encoding='utf-8')
print(f"\n[✓] Migration complete! Updated {TARGET_FILE.name}")
print(f"[i] Backup saved as: {BACKUP_FILE.name}")
print("\n[!] Please run the monitor to verify changes work correctly.")
