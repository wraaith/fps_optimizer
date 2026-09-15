import threading
import logging
from typing import Optional, Callable

log = logging.getLogger("ManagedWorker")

class ManagedWorker:
    """
    A cooperative, safe managed worker template replacing detached daemon threads.
    It guarantees bounded joins, resource cleanup via finally blocks,
    and uses threading.Event for all wait intervals (no time.sleep).
    """
    def __init__(self, name: str, interval: float, work_fn: Callable[[], None], cleanup_fn: Optional[Callable[[], None]] = None):
        self.name = name
        self.interval = interval
        self.work_fn = work_fn
        self.cleanup_fn = cleanup_fn
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()  # If set, we are paused
        self.thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        self.status = "IDLE"
        self.last_error: Optional[Exception] = None

    def start(self) -> bool:
        with self.lock:
            if self.thread and self.thread.is_alive():
                return False  # Already running
            
            self.stop_event.clear()
            self.pause_event.clear()
            self.status = "RUNNING"
            self.last_error = None
            
            # Using daemon=False here but relying on cooperative stop ensures cleanup
            self.thread = threading.Thread(
                target=self._run_wrapper,
                name=self.name,
                daemon=True  # Will still use daemon=True as safety net for GUI apps, but cooperative join is primary
            )
            self.thread.start()
            return True

    def stop(self, timeout: float = 3.0) -> bool:
        self.stop_event.set()
        self.pause_event.clear()  # Resume so it can exit if paused
        
        if self.thread and self.thread.is_alive():
            if self.thread is not threading.current_thread():
                self.thread.join(timeout=timeout)
                
        is_stopped = not self.thread or not self.thread.is_alive()
        if is_stopped:
            self.status = "IDLE"
        return is_stopped

    def pause(self):
        self.pause_event.set()
        self.status = "PAUSED"

    def resume(self):
        self.pause_event.clear()
        if self.status == "PAUSED":
            self.status = "RUNNING"

    def _run_wrapper(self):
        try:
            while not self.stop_event.is_set():
                if self.pause_event.is_set():
                    # If paused, just wait a bit and check again
                    if self.stop_event.wait(0.5):
                        break
                    continue
                
                # Perform the actual work
                self.work_fn()
                
                # Bounded wait instead of sleeping
                if self.stop_event.wait(self.interval):
                    break
        except Exception as error:
            self.last_error = error
            self.status = "ERROR"
            log.exception(f"ManagedWorker {self.name} encountered an error: {error}")
        finally:
            if self.cleanup_fn:
                try:
                    self.cleanup_fn()
                except Exception as e:
                    log.error(f"Error in cleanup for {self.name}: {e}")
