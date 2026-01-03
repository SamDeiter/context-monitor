"""
Data Service for Context Monitor
Handles all file I/O for history and analytics with caching and throttling.
"""
import json
import time
from pathlib import Path
from datetime import datetime

from config import HISTORY_FILE, ANALYTICS_FILE, HISTORY_CACHE_TTL, ANALYTICS_SAVE_THROTTLE, MAX_HISTORY_POINTS


class DataService:
    """Singleton-style data manager for history and analytics."""
    
    def __init__(self):
        self.history_file = HISTORY_FILE
        self.analytics_file = ANALYTICS_FILE
        
        # History cache
        self._history_cache = None
        self._history_cache_time = 0
        self._history_dirty = False
        self._last_history_save = 0
        
        # Analytics cache
        self._analytics_cache = None
        self._last_analytics_save = 0
    
    # === HISTORY ===
    
    def load_history(self, force_reload=False):
        """Load history with caching."""
        now = time.time()
        
        if not force_reload and self._history_cache is not None:
            if now - self._history_cache_time < HISTORY_CACHE_TTL:
                return self._history_cache
        
        try:
            if self.history_file.exists():
                with open(self.history_file, 'r') as f:
                    self._history_cache = json.load(f)
                    self._history_cache_time = now
                    return self._history_cache
        except Exception as e:
            print(f"History load error: {e}")
        
        self._history_cache = {}
        self._history_cache_time = now
        return self._history_cache
    
    def save_history(self, session_id, tokens, last_tokens, throttle_seconds=2):
        """Save history with throttled disk writes. Returns delta."""
        now = time.time()
        delta = tokens - last_tokens if last_tokens > 0 else 0
        
        data = self.load_history()
        if session_id not in data:
            data[session_id] = []
        
        data[session_id].append({
            'ts': now,
            'tokens': tokens,
            'delta': delta
        })
        
        # Trim to max points
        if len(data[session_id]) > MAX_HISTORY_POINTS:
            data[session_id] = data[session_id][-MAX_HISTORY_POINTS:]
        
        self._history_cache = data
        self._history_dirty = True
        
        if now - self._last_history_save >= throttle_seconds:
            self._flush_history()
            self._last_history_save = now
        
        return delta
    
    def _flush_history(self):
        """Write cached history to disk."""
        if not self._history_dirty or self._history_cache is None:
            return
        
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, 'w') as f:
                json.dump(self._history_cache, f)
            self._history_dirty = False
        except Exception as e:
            print(f"History flush error: {e}")
    
    # === ANALYTICS ===
    
    def load_analytics(self):
        """Load persistent analytics data."""
        try:
            if self.analytics_file.exists():
                with open(self.analytics_file, 'r') as f:
                    self._analytics_cache = json.load(f)
                    return self._analytics_cache
        except Exception as e:
            print(f"Analytics load error: {e}")
        
        self._analytics_cache = {'daily': {}, 'projects': {}, 'models': {}}
        return self._analytics_cache
    
    def save_analytics(self, tokens, last_tokens, project_name, model_name):
        """Track daily and project-level token usage with throttled writes."""
        now = time.time()
        analytics = self.load_analytics()
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Daily tracking
        if today not in analytics['daily']:
            analytics['daily'][today] = {'total': 0, 'sessions': 0}
        
        delta = tokens - last_tokens if last_tokens > 0 else 0
        if delta > 0:
            analytics['daily'][today]['total'] += delta
            
            # Project-level tracking
            if project_name not in analytics.get('projects', {}):
                analytics['projects'][project_name] = {'total': 0}
            analytics['projects'][project_name]['total'] += delta
            
            # Model-level tracking
            if 'models' not in analytics:
                analytics['models'] = {}
            if model_name not in analytics['models']:
                analytics['models'][model_name] = {'total': 0}
            analytics['models'][model_name]['total'] += delta
        
        self._analytics_cache = analytics
        
        # Throttled disk write
        if now - self._last_analytics_save >= ANALYTICS_SAVE_THROTTLE:
            self._flush_analytics()
            self._last_analytics_save = now
        
        return analytics
    
    def _flush_analytics(self):
        """Write cached analytics to disk."""
        if self._analytics_cache is None:
            return
        
        try:
            self.analytics_file.parent.mkdir(parents=True, exist_ok=True)
            save_data = {
                'daily': self._analytics_cache.get('daily', {}),
                'projects': {k: {'total': v.get('total', 0)} 
                            for k, v in self._analytics_cache.get('projects', {}).items()},
                'models': self._analytics_cache.get('models', {})
            }
            with open(self.analytics_file, 'w') as f:
                json.dump(save_data, f, indent=2)
        except Exception as e:
            print(f"Analytics flush error: {e}")
    
    def get_today_usage(self):
        """Get today's total token usage."""
        analytics = self.load_analytics()
        today = datetime.now().strftime('%Y-%m-%d')
        return analytics.get('daily', {}).get(today, {}).get('total', 0)


# Singleton instance
data_service = DataService()
