"""
Quota Tracker
Implements the mandatory structured usage logging for Antigravity Agents.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from quota_config import AUDIT_LOG_FILE, ACTION_TYPES

def emit_usage_log(
    agent_id: str,
    task_id: str,
    action_type: str,
    model_used: Optional[str],
    estimated_token_cost: str,
    success: bool,
    artifacts_produced: int
):
    """
    Emits a structured JSON usage log to the audit file.
    Mandatory for all agent actions.
    """
    if action_type not in ACTION_TYPES:
        # We don't error, just warn, to prevent crashing the agent
        print(f"WARNING: Unknown action_type '{action_type}'. Valid types: {ACTION_TYPES}")

    log_entry = {
        "type": "USAGE_LOG",
        "agent_id": agent_id,
        "task_id": task_id,
        "action_type": action_type,
        "model_used": model_used,
        "estimated_token_cost": estimated_token_cost,
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "success": success,
        "artifacts_produced": artifacts_produced,
    }

    try:
        # Ensure directory exists
        AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Append to JSONL file
        with open(AUDIT_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
            
        # Optional: Print to stdout for immediate visibility
        # print(json.dumps(log_entry, indent=2))
        
    except Exception as e:
        print(f"CRITICAL: Failed to write usage log: {e}")

def tracked_action(action_fn: Callable, *, usage_meta: Dict[str, Any]):
    """
    Wraps any agent action and guarantees a usage log.
    
    usage_meta must contain:
    - agent_id
    - task_id
    - action_type
    - model_used
    - estimated_token_cost
    - artifacts_produced (initial/expected)
    """
    try:
        result = action_fn()
        
        # If success, log it
        emit_usage_log(
            success=True,
            **usage_meta
        )
        return result
        
    except Exception as e:
        # If failure, log it
        emit_usage_log(
            success=False,
            **usage_meta
        )
        raise e

def emit_task_summary(
    task_id: str,
    total_actions: int,
    model_calls: int,
    high_cost_actions: int,
    artifacts_created: int,
    suspected_rate_limit_events: int
):
    """
    Emits the final task summary report.
    """
    summary = {
        "type": "TASK_USAGE_SUMMARY",
        "task_id": task_id,
        "total_actions": total_actions,
        "model_calls": model_calls,
        "high_cost_actions": high_cost_actions,
        "artifacts_created": artifacts_created,
        "suspected_rate_limit_events": suspected_rate_limit_events,
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    }
    
    try:
        with open(AUDIT_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json.dumps(summary) + '\n')
    except Exception as e:
        print(f"CRITICAL: Failed to write task summary: {e}")
