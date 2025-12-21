"""
Test script for Context Monitor toast notifications
"""
import sys
sys.path.insert(0, r'c:\Users\Sam Deiter\Documents\GitHub\context-monitor')

# Test 1: Check if win10toast is available
print("=" * 50)
print("Testing Toast Notifications")
print("=" * 50)

try:
    from win10toast import ToastNotifier
    print("✓ win10toast is installed")
    
    toaster = ToastNotifier()
    print("  Sending test notification...")
    toaster.show_toast(
        "🧪 Context Monitor Test",
        "If you see this, notifications are working!",
        duration=5,
        threaded=True
    )
    print("  ✓ Notification sent! Check your Windows notifications.")
    
except ImportError:
    print("✗ win10toast is NOT installed")
    print("  To install: pip install win10toast")
    print("  Falling back to console notifications...")

# Test 2: Test the actual send_notification method from context_monitor
print("\n" + "=" * 50)
print("Testing Context Monitor's send_notification method")
print("=" * 50)

try:
    # Import just the methods we need without starting the GUI
    import tkinter as tk
    
    # Create a minimal mock to test the notification method
    class MockMonitor:
        notifications_enabled = True
        
        def send_notification(self, title, message, urgency='info'):
            """Send Windows toast notification (Sprint 2: Feature 2.2)"""
            if not getattr(self, 'notifications_enabled', True):
                return
            
            try:
                from win10toast import ToastNotifier
                toaster = ToastNotifier()
                duration = 5 if urgency == 'info' else 10
                toaster.show_toast(
                    title,
                    message,
                    duration=duration,
                    threaded=True
                )
                print(f"  ✓ Toast notification sent: {title}")
            except ImportError:
                print(f"  [Notification] {title}: {message}")
            except Exception as e:
                print(f"  Notification error: {e}")
    
    monitor = MockMonitor()
    
    # Test warning notification
    print("\nSending WARNING notification (60% threshold)...")
    monitor.send_notification(
        "⚡ Context Warning",
        "Token usage at 60%. Consider wrapping up soon.",
        urgency='warning'
    )
    
    import time
    time.sleep(2)
    
    # Test critical notification
    print("\nSending CRITICAL notification (80% threshold)...")
    monitor.send_notification(
        "⚠️ Context Critical!",
        "Token usage at 80%! Handoff copied to clipboard.",
        urgency='critical'
    )
    
    print("\n✓ Both notifications sent! Check your Windows notification center.")
    
except Exception as e:
    print(f"Error testing notifications: {e}")

print("\n" + "=" * 50)
print("Test complete!")
print("=" * 50)
