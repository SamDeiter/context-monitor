from pathlib import Path

def extract_pb_tokens(pb_file_path, default_context_window=1000000):
    """
    Extract token count from protobuf conversation file.
    Uses file-size estimation (st_size // 4) for refined accuracy and stability.
    Only reads partial content for project detection to avoid race conditions.
    """
    try:
        # Ensure Path object
        if isinstance(pb_file_path, str):
            from pathlib import Path
            pb_file_path = Path(pb_file_path)
            
        # Use valid file stat for size (Atomic-ish)
        # If file is locked/writing, stat usually gives current size or 0
        try:
            stat = pb_file_path.stat()
            file_size = stat.st_size
        except OSError:
            # File might be locked or moving
            return {
                'tokens_used': 0,
                'context_window': default_context_window,
                'tokens_remaining': default_context_window,
                'method': 'locked'
            }
        
        # Estimate: 4 bytes per token
        estimated_tokens = file_size // 4
        
        # Extract project name (Optimized: First 100KB only)
        project_name = None
        try:
            with open(pb_file_path, 'rb') as f:
                # Read header
                data = f.read(102400)
                project_match = re.search(rb'GitHub[/\\]([A-Za-z0-9_-]+)', data)
                if project_match:
                    project_name = project_match.group(1).decode('utf-8', errors='ignore')
        except:
            pass # Non-critical
            
        return {
            'tokens_used': estimated_tokens,
            'context_window': default_context_window,
            'tokens_remaining': default_context_window - estimated_tokens,
            'project_name': project_name,
            'method': 'stat_estimation'
        }
    except Exception as e:
        print(f"[Token Extraction] Error: {e}")
        return {
            'tokens_used': 0,
            'context_window': default_context_window,
            'tokens_remaining': default_context_window,
            'method': 'error'
        }
