import ctypes
import sys
from typing import Optional

class TimerManager:
    """
    Manages the Windows multimedia timer resolution (timeBeginPeriod).
    Ensures that only one timer is active, cleanup is guaranteed,
    and exposes state for diagnostics.
    """
    def __init__(self):
        self.owns_timer: bool = False
        self.timer_period_ms: Optional[int] = None
        self.timer_request_count: int = 0
        
        self._winmm = None
        if sys.platform == "win32":
            try:
                self._winmm = ctypes.windll.winmm
                self._winmm.timeBeginPeriod.argtypes = [ctypes.c_uint]
                self._winmm.timeBeginPeriod.restype = ctypes.c_uint
                self._winmm.timeEndPeriod.argtypes = [ctypes.c_uint]
                self._winmm.timeEndPeriod.restype = ctypes.c_uint
            except Exception:
                pass

    def begin(self, resolution_ms: int = 1) -> bool:
        """Requests a higher timer resolution. Prevents duplicate requests."""
        if self.owns_timer:
            return True # Already owns a timer

        if self._winmm:
            result = self._winmm.timeBeginPeriod(resolution_ms)
            if result == 0:
                self.owns_timer = True
                self.timer_period_ms = resolution_ms
                self.timer_request_count += 1
                return True
        return False

    def end(self) -> bool:
        """Releases the timer resolution. Safe to call multiple times."""
        if not self.owns_timer or self.timer_period_ms is None:
            return True

        if self._winmm:
            result = self._winmm.timeEndPeriod(self.timer_period_ms)
            if result == 0:
                self.owns_timer = False
                self.timer_period_ms = None
                return True
        return False

    @property
    def is_active(self) -> bool:
        """Alias for owns_timer."""
        return self.owns_timer

    def get_state(self) -> dict:
        """Expose timer ownership state for diagnostics and snapshot ledger."""
        return {
            "owns_timer": self.owns_timer,
            "timer_period_ms": self.timer_period_ms,
            "timer_request_count": self.timer_request_count
        }
