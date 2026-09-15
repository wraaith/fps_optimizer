import os
import secrets
import threading
import time
from enum import Enum
from typing import Dict, Any, Optional

class TokenValidationResult(str, Enum):
    VALID = "valid"
    MISSING = "missing"
    EXPIRED = "expired"
    ALREADY_CONSUMED = "already_consumed"
    IDENTITY_MISMATCH = "identity_mismatch"
    OPERATION_MISMATCH = "operation_mismatch"
    SESSION_MISMATCH = "session_mismatch"

    def __str__(self) -> str:
        return self.value

class ProcessTokenManager:
    """Session-scoped, thread-safe token manager for legacy process cleanup."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self._tokens: Dict[str, Dict[str, Any]] = {}
        self._consumed_tokens: set = set()
        self._lock = threading.Lock()
        
    def reset(self):
        """Invalidate all active and consumed tokens."""
        with self._lock:
            self._tokens.clear()
            self._consumed_tokens.clear()
            
    def generate_token(
        self,
        pid: int,
        exe_path: str,
        create_time: float,
        operation: str,
        session_id: str,
        expires_in: float = 60.0
    ) -> str:
        """
        Generates a cryptographically random, single-use, session-bound token.
        Uses secrets.token_urlsafe(32) and monotonic time for expiration.
        """
        token = secrets.token_urlsafe(32)
        normalized_path = os.path.normcase(os.path.normpath(exe_path)) if exe_path else ""
        
        with self._lock:
            self._tokens[token] = {
                "pid": pid,
                "exe_path": normalized_path,
                "create_time": create_time,
                "operation": operation,
                "session_id": session_id,
                "expires_at": time.monotonic() + expires_in
            }
        return token
        
    def consume_token(
        self,
        token: str,
        pid: int,
        exe_path: str,
        create_time: float,
        operation: str,
        session_id: str
    ) -> TokenValidationResult:
        """
        Validates and consumes a single-use token under lock.
        Immediately removes token from active store upon single consumption.
        """
        if not token:
            return TokenValidationResult.MISSING
            
        with self._lock:
            if token in self._consumed_tokens:
                return TokenValidationResult.ALREADY_CONSUMED
                
            if token not in self._tokens:
                return TokenValidationResult.ALREADY_CONSUMED
                
            data = self._tokens.pop(token)
            self._consumed_tokens.add(token)
            
        # Check expiration using monotonic time
        if time.monotonic() > data["expires_at"]:
            return TokenValidationResult.EXPIRED
            
        # Check session binding
        if data["session_id"] != session_id:
            return TokenValidationResult.SESSION_MISMATCH
            
        # Check operation binding
        if data["operation"] != operation:
            return TokenValidationResult.OPERATION_MISMATCH
            
        # Check PID binding
        if data["pid"] != pid:
            return TokenValidationResult.IDENTITY_MISMATCH
            
        # Check normalized executable path binding
        normalized_path = os.path.normcase(os.path.normpath(exe_path)) if exe_path else ""
        if data["exe_path"] != normalized_path:
            return TokenValidationResult.IDENTITY_MISMATCH
            
        # Check process creation time binding
        if abs(data["create_time"] - create_time) > 0.01:
            return TokenValidationResult.IDENTITY_MISMATCH
            
        return TokenValidationResult.VALID
