import pytest
from unittest.mock import patch

@pytest.fixture(autouse=True)
def reset_globals():
    """Ensure no mock patches or singletons bleed across tests."""
    yield
    # Stop all dangling mock patches
    patch.stopall()
    
    # Reset singletons
    try:
        from sentinel.service import SentinelService
        SentinelService._instance = None
    except ImportError as e:
        import warnings
        warnings.warn(f"reset_globals: could not reset singleton — {e}")
        
    try:
        from sentinel.intervention_controller import InterventionController
        InterventionController._instance = None
    except ImportError as e:
        import warnings
        warnings.warn(f"reset_globals: could not reset singleton — {e}")

    try:
        from overlay.metrics_collector import MetricsCollector
        # If there's a shared collector, reset it
        import overlay.metrics_collector as mc
        mc._SHARED_COLLECTOR = None
    except ImportError as e:
        import warnings
        warnings.warn(f"reset_globals: could not reset singleton — {e}")
        
    try:
        from optimize.ai_boost_service import AIBoostService
        AIBoostService._instance = None
    except ImportError as e:
        import warnings
        warnings.warn(f"reset_globals: could not reset singleton — {e}")
