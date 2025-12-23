
    def check_context_alerts(self, percent, tokens_used):
        """Check for context window usage alerts (handoff warnings)"""
        now = time.time()
        
        # Only alert max once per 5 minutes to avoid spamming
        if hasattr(self, '_last_context_alert_time') and now - self._last_context_alert_time < 300:
            return
            
        context_window = self._context_window
        
        if percent >= 90:
            self._notifier.show_toast(
                "Context Critical 🚨",
                f"Context window 90% full! ({tokens_used:,} / {context_window:,} tokens)\nHandoff IMMINENT.",
                duration=7,
                threaded=True
            )
            self._last_context_alert_time = now
        elif percent >= 80:
            self._notifier.show_toast(
                "Context Warning ⚠️",
                f"Context window 80% full ({tokens_used:,} / {context_window:,} tokens).\nPrepare for handoff soon.",
                duration=5,
                threaded=True
            )
            self._last_context_alert_time = now
