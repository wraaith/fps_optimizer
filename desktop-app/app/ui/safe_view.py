import logging

class SafeViewMixin:
    """
    A mixin to provide safe Tkinter lifecycle management for views.
    Guarantees that asynchronous callbacks, theme listeners, and background
    workers won't trigger exceptions if the view is destroyed.
    """
    def __init__(self, *args, **kwargs):
        # We must call super().__init__ to propagate cooperative inheritance (MRO)
        super().__init__(*args, **kwargs)
        if not hasattr(self, "_is_destroyed"):
            self._is_destroyed = False
        if not hasattr(self, "_after_ids"):
            self._after_ids = set()

    def _init_safe_view(self):
        """Must be called in the view's __init__ to initialize state."""
        self._is_destroyed = False
        self._after_ids = set()

    def is_view_alive(self) -> bool:
        """Check if the view is still active and exists in Tkinter."""
        if getattr(self, "_is_destroyed", True):
            return False
        try:
            return bool(self.winfo_exists())
        except Exception:
            return False

    def schedule_ui_callback(self, delay_ms: int, callback, *args):
        """Schedule an after() callback that won't fire if the view is destroyed."""
        if not self.is_view_alive():
            return None

        def guarded_callback():
            if not self.is_view_alive():
                return
            try:
                callback(*args)
            except Exception as e:
                logging.warning(f"[SafeView] Exception in scheduled callback {callback.__name__}: {e}")

        try:
            callback_id = self.after(delay_ms, guarded_callback)
            self._after_ids.add(callback_id)
            return callback_id
        except Exception:
            return None

    def cancel_all_ui_callbacks(self):
        """Cancel all pending after() callbacks requested via schedule_ui_callback."""
        if not hasattr(self, "_after_ids"):
            return
            
        for callback_id in tuple(self._after_ids):
            try:
                self.after_cancel(callback_id)
            except Exception:
                pass
        self._after_ids.clear()

    def destroy(self):
        """Safely destroy the view and cancel all callbacks."""
        if getattr(self, "_is_destroyed", False):
            return
            
        self._is_destroyed = True
        self.cancel_all_ui_callbacks()
        
        try:
            super().destroy()
        except Exception:
            pass
