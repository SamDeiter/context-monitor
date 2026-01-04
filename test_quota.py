"""
Test Script for Quota Manager
Verifies rolling window resets and tier switching.
"""
import time
from quota_manager import QuotaManager

def test_quota_manager():
    qm = QuotaManager()
    
    # Reset state for testing
    qm.usage_history.clear()
    qm.set_tier("Pro") # 5 hour window, limit 100
    
    print(f"Testing {qm.get_config()['label']}...")
    
    # 1. Fill quota
    print("Flooding 100 requests...")
    for i in range(100):
        qm.add_usage()
        
    status = qm.get_status()
    print(f"Used: {status['used']}/{status['limit']}")
    print(f"Remaining: {status['remaining']}")
    
    assert status['remaining'] == 0, "Should be empty"
    
    # 2. Simulate time passing (Hack: modify history timestamps)
    print("\nSimulating 6 hours passing...")
    old_history = list(qm.usage_history)
    new_history = [t - (6 * 3600) for t in old_history]
    qm.usage_history.clear()
    qm.usage_history.extend(new_history)
    
    status = qm.get_status()
    print(f"Used after reset: {status['used']}")
    print(f"Remaining: {status['remaining']}")
    
    assert status['used'] == 0, "Should be fully reset"
    assert status['remaining'] == 100
    
    # 3. Test Rolling Window (Partial expiration)
    print("\nTesting Rolling Window...")
    qm.usage_history.clear()
    now = time.time()
    # Add 50 requests 6 hours ago (Expired)
    for _ in range(50):
        qm.usage_history.append(now - (6 * 3600))
    # Add 40 requests 1 hour ago (Active)
    for _ in range(40):
        qm.usage_history.append(now - (1 * 3600))
        
    status = qm.get_status()
    print(f"Used (should be 40): {status['used']}")
    print(f"Next Reset In: {int(status['next_reset_seconds'] // 60)}m")
    
    assert status['used'] == 40, f"Expected 40 used, got {status['used']}"
    
    print("\n✅ Verification Passed!")

if __name__ == "__main__":
    test_quota_manager()
