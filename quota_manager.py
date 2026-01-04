"""
Quota Manager
Handles rolling window logic for usage tracking.
Now integrates with Antigravity API for real quota data.
"""
import time
import json
from collections import deque
from pathlib import Path
from typing import Optional, Dict, Any, List
from quota_config import TIERS, DEFAULT_TIER, USAGE_COSTS
from quota_tracker import emit_usage_log, tracked_action, emit_task_summary

QUOTA_FILE = Path.home() / '.gemini' / 'antigravity' / 'quota_state.json'

# Try to import the API (optional dependency)
try:
    from antigravity_api import antigravity_api, QuotaSnapshot, ModelQuotaInfo
    HAS_API = True
except ImportError:
    HAS_API = False
    print("[QuotaManager] antigravity_api not available, using fallback mode")


class QuotaManager:
    def __init__(self):
        self.tier_id = DEFAULT_TIER
        self.usage_history = deque() # List of timestamps [t1, t2, ...]
        self.flow_credits_used = 0
        self.last_flow_reset = time.time()
        
        # API-based quota cache
        self._api_cache: Optional[QuotaSnapshot] = None
        self._api_cache_time = 0
        self._api_cache_ttl = 60  # Cache for 60 seconds
        
        self.load_state()

    def set_tier(self, tier_id):
        if tier_id in TIERS:
            self.tier_id = tier_id
            self.save_state()

    def get_config(self):
        return TIERS.get(self.tier_id, TIERS[DEFAULT_TIER])

    def add_usage(self, usage_type="standard", manual_count=None, agent_meta=None):
        """
        Log usage.
        usage_type: 'standard' (+1) or 'agentic' (+5)
        manual_count: If set, overrides type and adds specific amount
        agent_meta: Optional dict with 'agent_id', 'task_id', 'action_type', 'model_used', 'estimated_token_cost'
        """
        cost = manual_count if manual_count is not None else USAGE_COSTS.get(usage_type, 1)
        
        # 1. Update Legacy Rolling Window
        now = time.time()
        for _ in range(cost):
            self.usage_history.append(now)
        
        # 2. Emit Structured Agent Log (if meta provided)
        if agent_meta:
            # Safely extract with defaults
            emit_usage_log(
                agent_id=agent_meta.get('agent_id', 'unknown_agent'),
                task_id=agent_meta.get('task_id', 'unknown_task'),
                action_type=agent_meta.get('action_type', 'model_inference'),
                model_used=agent_meta.get('model_used'),
                estimated_token_cost=agent_meta.get('estimated_token_cost', 'low'),
                success=agent_meta.get('success', True),
                artifacts_produced=agent_meta.get('artifacts_produced', 0)
            )
        
        # 3. Invalidate API cache (force refresh on next get_status)
        self._api_cache = None
            
        self.save_state()

    def log_agent_action(self, agent_id, task_id, action_type, model_used=None, 
                        token_cost='low', success=True, artifacts=0):
        """Direct wrapper for emit_usage_log"""
        emit_usage_log(agent_id, task_id, action_type, model_used, token_cost, success, artifacts)

    def add_flow_usage(self, credits=1):
        """Log ancillary credit usage (monthly reset)"""
        self.check_flow_reset()
        self.flow_credits_used += credits
        self.save_state()

    def check_flow_reset(self):
        """Reset flow credits if 30 days have passed"""
        now = time.time()
        # 30 days in seconds = 30 * 24 * 3600 = 2592000
        if now - self.last_flow_reset > 2592000:
            self.flow_credits_used = 0
            self.last_flow_reset = now

    def get_api_quota(self, force_refresh=False) -> Optional[QuotaSnapshot]:
        """Fetch quota from Antigravity API with caching."""
        if not HAS_API:
            return None
        
        now = time.time()
        
        # Check cache
        if not force_refresh and self._api_cache and (now - self._api_cache_time) < self._api_cache_ttl:
            return self._api_cache
        
        # Fetch from API
        try:
            snapshot = antigravity_api.fetch_quota()
            if snapshot:
                self._api_cache = snapshot
                self._api_cache_time = now
            return snapshot
        except Exception as e:
            print(f"[QuotaManager] API fetch error: {e}")
            return self._api_cache  # Return stale cache if available
    
    def get_model_quotas(self) -> List[Dict[str, Any]]:
        """Get quota info for all models."""
        snapshot = self.get_api_quota()
        if not snapshot:
            return []
        
        return [
            {
                "label": m.label,
                "model_id": m.model_id,
                "remaining_percent": m.remaining_percentage,
                "is_exhausted": m.is_exhausted,
                "reset_time": m.time_until_reset_formatted
            }
            for m in snapshot.models
        ]
    
    def get_prompt_credits(self) -> Optional[Dict[str, Any]]:
        """Get prompt credits info."""
        snapshot = self.get_api_quota()
        if not snapshot or not snapshot.prompt_credits:
            return None
        
        pc = snapshot.prompt_credits
        return {
            "available": pc.available,
            "monthly": pc.monthly,
            "used_percent": pc.used_percentage,
            "remaining_percent": pc.remaining_percentage
        }

    def get_status(self):
        """Calculate quota status - now uses API when available."""
        # Try API first
        api_snapshot = self.get_api_quota()
        
        if api_snapshot and api_snapshot.models:
            # Use API data
            # Find the "primary" model (usually Gemini 3 Pro High or first model)
            primary = api_snapshot.models[0]
            for m in api_snapshot.models:
                if 'Pro' in m.label and 'High' in m.label:
                    primary = m
                    break
            
            prompt_credits = api_snapshot.prompt_credits
            
            return {
                "tier": "API",
                "source": "antigravity_api",
                "used": 100 - primary.remaining_percentage,
                "limit": 100,
                "remaining": primary.remaining_percentage,
                "percent_remaining": primary.remaining_percentage,
                "next_reset_seconds": primary.time_until_reset_seconds or 0,
                "next_reset_formatted": primary.time_until_reset_formatted,
                "primary_model": primary.label,
                "is_exhausted": primary.is_exhausted,
                "all_models": self.get_model_quotas(),
                "prompt_credits": self.get_prompt_credits(),
                # Legacy fields
                "flow_used": self.flow_credits_used,
                "flow_limit": 500,
                "flow_remaining": max(0, 500 - self.flow_credits_used)
            }
        
        # Fallback to rolling window logic
        config = self.get_config()
        now = time.time()
        window = config['window_seconds']
        capacity = config['limit']
        
        # 1. Prune old history
        while self.usage_history and (now - self.usage_history[0] > window):
            self.usage_history.popleft()
            
        used = len(self.usage_history)
        remaining = max(0, capacity - used)
        
        # 2. Calculate time to next recovery
        recover_in = 0
        if used >= capacity and self.usage_history:
            oldest = self.usage_history[0]
            recover_in = max(0, (oldest + window) - now)
            
        # 3. Flow/Whisk Status
        flow_limit = config['ancillary_limit']
        flow_remaining = max(0, flow_limit - self.flow_credits_used)
        
        return {
            "tier": config['label'],
            "source": "rolling_window",
            "used": used,
            "limit": capacity,
            "remaining": remaining,
            "percent_remaining": (remaining / capacity) * 100 if capacity > 0 else 0,
            "next_reset_seconds": recover_in,
            "flow_used": self.flow_credits_used,
            "flow_limit": flow_limit,
            "flow_remaining": flow_remaining
        }

    def save_state(self):
        try:
            QUOTA_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "tier_id": self.tier_id,
                "usage_history": list(self.usage_history),
                "flow_credits_used": self.flow_credits_used,
                "last_flow_reset": self.last_flow_reset
            }
            with open(QUOTA_FILE, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Error saving quota state: {e}")

    def load_state(self):
        try:
            if QUOTA_FILE.exists():
                with open(QUOTA_FILE, 'r') as f:
                    data = json.load(f)
                    self.tier_id = data.get("tier_id", DEFAULT_TIER)
                    self.usage_history = deque(data.get("usage_history", []))
                    self.flow_credits_used = data.get("flow_credits_used", 0)
                    self.last_flow_reset = data.get("last_flow_reset", time.time())
        except Exception as e:
            print(f"Error loading quota state: {e}")

# Singleton
quota_manager = QuotaManager()

