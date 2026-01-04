"""
Antigravity API Client
Fetches real quota data from the Antigravity language server.
Based on insights from Henrik-3/AntigravityQuota extension.
"""

import subprocess
import ssl
import json
import urllib.request
import re
import platform
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class ModelQuotaInfo:
    """Quota info for a single model."""
    label: str
    model_id: str
    remaining_fraction: float  # 0.0 to 1.0
    remaining_percentage: float  # 0 to 100
    is_exhausted: bool
    reset_time: Optional[datetime]
    time_until_reset_seconds: Optional[int]
    time_until_reset_formatted: str


@dataclass
class PromptCreditsInfo:
    """Prompt credits info."""
    available: int
    monthly: int
    used_percentage: float
    remaining_percentage: float


@dataclass
class QuotaSnapshot:
    """Complete quota snapshot from API."""
    timestamp: datetime
    models: List[ModelQuotaInfo]
    prompt_credits: Optional[PromptCreditsInfo]
    raw_response: Optional[Dict[str, Any]] = None


@dataclass
class ProcessInfo:
    """Antigravity process connection info."""
    extension_port: int
    connect_port: int
    csrf_token: str


class AntigravityAPI:
    """Client for Antigravity's local language server API."""
    
    def __init__(self):
        self.process_info: Optional[ProcessInfo] = None
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE
    
    def detect_process(self) -> Optional[ProcessInfo]:
        """Detect the Antigravity language server process and extract connection info."""
        if platform.system() != "Windows":
            print("[AntigravityAPI] Only Windows is supported currently")
            return None
        
        try:
            # Find language_server process with WMIC
            cmd = 'wmic process where "name like \'%language_server%\'" get CommandLine,ProcessId /FORMAT:CSV'
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=10)
            
            if not result.stdout:
                print("[AntigravityAPI] No language_server process found")
                return None
            
            for line in result.stdout.splitlines():
                if 'language_server' not in line.lower():
                    continue
                
                # Parse command line for extension port and CSRF token
                # Format: --extension_server_port XXXXX --csrf_token XXXXX
                ext_port_match = re.search(r'--extension_server_port\s+(\d+)', line)
                csrf_match = re.search(r'--csrf_token\s+([a-fA-F0-9-]+)', line)
                pid_match = re.search(r',(\d+)$', line)

                
                if ext_port_match and csrf_match:
                    extension_port = int(ext_port_match.group(1))
                    csrf_token = csrf_match.group(1)
                    pid = int(pid_match.group(1)) if pid_match else 0
                    
                    print(f"[AntigravityAPI] Found process: port={extension_port}, pid={pid}")
                    
                    # Find the actual listening port
                    connect_port = self._find_listening_port(pid, csrf_token)
                    
                    if connect_port:
                        self.process_info = ProcessInfo(
                            extension_port=extension_port,
                            connect_port=connect_port,
                            csrf_token=csrf_token
                        )
                        return self.process_info
            
            print("[AntigravityAPI] Could not parse process info from command line")
            return None
            
        except subprocess.TimeoutExpired:
            print("[AntigravityAPI] Process detection timed out")
            return None
        except Exception as e:
            print(f"[AntigravityAPI] Error detecting process: {e}")
            return None
    
    def _find_listening_port(self, pid: int, csrf_token: str) -> Optional[int]:
        """Find the actual listening port for the language server."""
        try:
            # Use netstat to find ports for this PID
            cmd = f'netstat -ano | findstr ":{pid}" | findstr LISTENING'
            result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=5)
            
            ports = set()
            for line in result.stdout.splitlines():
                match = re.search(r':(\d+)\s+', line)
                if match:
                    port = int(match.group(1))
                    if 10000 < port < 65535:  # Reasonable port range
                        ports.add(port)
            
            if not ports:
                # Fallback: try netstat with PID at end
                cmd = f'netstat -ano | findstr {pid}'
                result = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=5)
                for line in result.stdout.splitlines():
                    if 'LISTENING' in line:
                        match = re.search(r'127\.0\.0\.1:(\d+)', line)
                        if match:
                            ports.add(int(match.group(1)))
            
            # Test each port
            for port in sorted(ports):
                if self._test_port(port, csrf_token):
                    return port
            
            return None
            
        except Exception as e:
            print(f"[AntigravityAPI] Error finding listening port: {e}")
            return None
    
    def _test_port(self, port: int, csrf_token: str) -> bool:
        """Test if a port responds to the API."""
        try:
            url = f"https://127.0.0.1:{port}/exa.language_server_pb.LanguageServerService/GetUnleashData"
            
            data = json.dumps({"wrapper_data": {}}).encode('utf-8')
            
            req = urllib.request.Request(url, data=data, method='POST')
            req.add_header('Content-Type', 'application/json')
            req.add_header('X-Codeium-Csrf-Token', csrf_token)
            req.add_header('Connect-Protocol-Version', '1')
            
            with urllib.request.urlopen(req, timeout=3, context=self._ssl_context) as response:
                if response.status == 200:
                    return True
        except Exception:
            pass
        return False
    
    def fetch_quota(self) -> Optional[QuotaSnapshot]:
        """Fetch quota data from the Antigravity API."""
        if not self.process_info:
            self.detect_process()
        
        if not self.process_info:
            print("[AntigravityAPI] No process info available")
            return None
        
        try:
            url = f"https://127.0.0.1:{self.process_info.connect_port}/exa.language_server_pb.LanguageServerService/GetUserStatus"
            
            payload = {
                "metadata": {
                    "ideName": "antigravity",
                    "extensionName": "antigravity",
                    "locale": "en"
                }
            }
            
            data = json.dumps(payload).encode('utf-8')
            
            req = urllib.request.Request(url, data=data, method='POST')
            req.add_header('Content-Type', 'application/json')
            req.add_header('X-Codeium-Csrf-Token', self.process_info.csrf_token)
            req.add_header('Connect-Protocol-Version', '1')
            
            with urllib.request.urlopen(req, timeout=5, context=self._ssl_context) as response:
                response_data = json.loads(response.read().decode('utf-8'))
            
            return self._parse_response(response_data)
            
        except Exception as e:
            print(f"[AntigravityAPI] Error fetching quota: {e}")
            # Invalidate process info so we re-detect next time
            self.process_info = None
            return None
    
    def _parse_response(self, data: Dict[str, Any]) -> QuotaSnapshot:
        """Parse the API response into a QuotaSnapshot."""
        user_status = data.get('userStatus', {})
        plan_status = user_status.get('planStatus', {})
        plan_info = plan_status.get('planInfo', {})
        available_credits = plan_status.get('availablePromptCredits')
        
        # Parse prompt credits
        prompt_credits = None
        if plan_info and available_credits is not None:
            monthly = int(plan_info.get('monthlyPromptCredits', 0))
            available = int(available_credits)
            if monthly > 0:
                prompt_credits = PromptCreditsInfo(
                    available=available,
                    monthly=monthly,
                    used_percentage=((monthly - available) / monthly) * 100,
                    remaining_percentage=(available / monthly) * 100
                )
        
        # Parse model quotas
        models = []
        cascade_data = user_status.get('cascadeModelConfigData', {})
        raw_models = cascade_data.get('clientModelConfigs', [])
        
        for m in raw_models:
            quota_info = m.get('quotaInfo')
            if not quota_info:
                continue
            
            remaining_fraction = quota_info.get('remainingFraction', 1.0)
            reset_time_str = quota_info.get('resetTime')
            
            reset_time = None
            time_until_reset = None
            time_formatted = "Unknown"
            
            if reset_time_str:
                try:
                    reset_time = datetime.fromisoformat(reset_time_str.replace('Z', '+00:00'))
                    now = datetime.now(reset_time.tzinfo)
                    diff = (reset_time - now).total_seconds()
                    time_until_reset = max(0, int(diff))
                    time_formatted = self._format_time(time_until_reset)
                except Exception:
                    pass
            
            model_or_alias = m.get('modelOrAlias', {})
            
            models.append(ModelQuotaInfo(
                label=m.get('label', 'Unknown'),
                model_id=model_or_alias.get('model', 'unknown'),
                remaining_fraction=remaining_fraction,
                remaining_percentage=remaining_fraction * 100,
                is_exhausted=(remaining_fraction == 0),
                reset_time=reset_time,
                time_until_reset_seconds=time_until_reset,
                time_until_reset_formatted=time_formatted
            ))
        
        return QuotaSnapshot(
            timestamp=datetime.now(),
            models=models,
            prompt_credits=prompt_credits,
            raw_response=data
        )
    
    def _format_time(self, seconds: int) -> str:
        """Format seconds into human-readable time."""
        if seconds <= 0:
            return "Ready"
        
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m"
        
        hours = minutes // 60
        remaining_mins = minutes % 60
        return f"{hours}h {remaining_mins}m"


# Singleton instance
antigravity_api = AntigravityAPI()


# Convenience functions
def get_quota_snapshot() -> Optional[QuotaSnapshot]:
    """Get current quota snapshot from Antigravity API."""
    return antigravity_api.fetch_quota()


def get_model_quota(model_label: str) -> Optional[ModelQuotaInfo]:
    """Get quota for a specific model by label."""
    snapshot = antigravity_api.fetch_quota()
    if snapshot:
        for model in snapshot.models:
            if model.label.lower() == model_label.lower():
                return model
    return None
