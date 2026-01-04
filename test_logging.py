"""
Test Logging
Verifies proper integration of quota_tracker and quota_manager.
"""
import time
from quota_manager import quota_manager
from quota_tracker import tracked_action

def dummy_task():
    print("Performing dummy task...")
    time.sleep(0.1)
    return "Result"

def test_integration():
    print("Testing logging integration...")
    
    # 1. Test tracked_action wrapper
    meta = {
        "agent_id": "test_agent_001",
        "task_id": "verify_logging",
        "action_type": "model_inference",
        "model_used": "gemini-3-pro",
        "estimated_token_cost": "low",
        "artifacts_produced": 1
    }
    
    tracked_action(dummy_task, usage_meta=meta)
    print("Tracked action executed.")
    
    # 2. Test QuotaManager passthrough
    quota_manager.add_usage(
        usage_type="agentic", 
        agent_meta={
            "agent_id": "test_agent_001",
            "task_id": "verify_logging",
            "action_type": "code_edit",
            "estimated_token_cost": "medium"
        }
    )
    print("QuotaManager usage added.")

if __name__ == "__main__":
    test_integration()
