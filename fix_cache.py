"""
Script to apply cache invalidation fixes to context_monitor.py
"""
import re

def apply_fixes():
    file_path = r"c:\Users\Sam Deiter\Documents\GitHub\context-monitor\context_monitor.py"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix 1: Add defensive check in get_project_name() cache lookup
    old_cache_check = """        if session_id in self.project_name_cache:
            if session_id in self.project_name_timestamp:
                if now - self.project_name_timestamp[session_id] < 5:
                    return self.project_name_cache[session_id]"""
    
    new_cache_check = """        if session_id in self.project_name_cache:
            if session_id in self.project_name_timestamp:
                if now - self.project_name_timestamp[session_id] < 5:
                    # Verify file still exists before returning cached value
                    pb_file = self.conversations_dir / f"{session_id}.pb"
                    if pb_file.exists():
                        return self.project_name_cache[session_id]
                    else:
                        # File was deleted, clear cache
                        del self.project_name_cache[session_id]
                        del self.project_name_timestamp[session_id]"""
    
    content = content.replace(old_cache_check, new_cache_check)
    
    # Fix 2: Add cache cleanup to cleanup_old_conversations()
    old_cleanup = """            messagebox.showinfo("Cleanup Complete", f"Deleted {deleted} files.")"""
    
    new_cleanup = """            # Clear cache entries for deleted sessions
            for f in files:
                session_id = f['path'].stem
                if session_id in self.project_name_cache:
                    del self.project_name_cache[session_id]
                if session_id in self.project_name_timestamp:
                    del self.project_name_timestamp[session_id]
            
            messagebox.showinfo("Cleanup Complete", f"Deleted {deleted} files.")"""
    
    content = content.replace(old_cleanup, new_cleanup)
    
    # Fix 3: Add cleanup_project_cache() method after cleanup_old_conversations()
    # Find the position after cleanup_old_conversations method
    cleanup_method = """    def cleanup_old_conversations(self):
        \"\"\"Delete conversation files older than 7 days and larger than 5MB\"\"\"
        files = self.get_large_conversations(min_size_mb=5)
        if not files:
            messagebox.showinfo("Cleanup", "No large files to clean up!")
            return
        
        msg = f"Found {len(files)} large conversation files:\\n\\n"
        for f in files:
            msg += f"• {f['name']}: {f['size_mb']}MB\\n"
        msg += "\\nDelete these files? (Current session will be preserved)"
        
        if messagebox.askyesno("Cleanup Old Conversations", msg):
            deleted = 0
            current_id = self.current_session['id'] if self.current_session else None
            for f in files:
                if current_id and current_id in str(f['path']):
                    continue  # Skip current session
                try:
                    f['path'].unlink()
                    deleted += 1
                except Exception as e:
                    print(f"Error deleting {f['path']}: {e}")
            # Clear cache entries for deleted sessions
            for f in files:
                session_id = f['path'].stem
                if session_id in self.project_name_cache:
                    del self.project_name_cache[session_id]
                if session_id in self.project_name_timestamp:
                    del self.project_name_timestamp[session_id]
            
            messagebox.showinfo("Cleanup Complete", f"Deleted {deleted} files.")
    """
    
    new_method = """    def cleanup_project_cache(self):
        \"\"\"Remove cache entries for sessions that no longer exist\"\"\"
        valid_sessions = {s['id'] for s in self.get_sessions()}
        
        # Remove orphaned cache entries
        orphaned_ids = set(self.project_name_cache.keys()) - valid_sessions
        for session_id in orphaned_ids:
            if session_id in self.project_name_cache:
                del self.project_name_cache[session_id]
            if session_id in self.project_name_timestamp:
                del self.project_name_timestamp[session_id]
    
"""
    
    # Insert the new method after cleanup_old_conversations
    pattern = r'(            messagebox\.showinfo\("Cleanup Complete", f"Deleted \{deleted\} files\."\)\r?\n    \r?\n)'
    replacement = r'\1' + new_method
    content = re.sub(pattern, replacement, content)
    
    # Fix 4: Call cleanup_project_cache in force_refresh
    old_force_refresh = """    def force_refresh(self, event=None):
        \"\"\"Force refresh project detection by clearing cache\"\"\"
        # Clear the cache to force re-detection
        self.project_name_cache.clear()
        self.project_name_timestamp.clear()"""
    
    new_force_refresh = """    def force_refresh(self, event=None):
        \"\"\"Force refresh project detection by clearing cache\"\"\"
        # Clear the cache to force re-detection
        self.project_name_cache.clear()
        self.project_name_timestamp.clear()
        
        # Also cleanup orphaned cache entries
        self.cleanup_project_cache()"""
    
    content = content.replace(old_force_refresh, new_force_refresh)
    
    # Write the modified content back
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✓ Applied all cache invalidation fixes successfully!")
    print("  - Added defensive file existence check in get_project_name()")
    print("  - Added cache cleanup to cleanup_old_conversations()")
    print("  - Added cleanup_project_cache() helper method")
    print("  - Updated force_refresh() to call cleanup_project_cache()")

if __name__ == "__main__":
    apply_fixes()
