import ctypes
import ctypes.wintypes as wt
import time

class _DWM_TIMING_INFO(ctypes.Structure):
    """Partial DWM_TIMING_INFO — we only need the first few fields."""
    _pack_ = 1
    _fields_ = [
        ("cbSize", ctypes.c_uint32),
        ("rateRefreshNumerator", ctypes.c_uint32),
        ("rateRefreshDenominator", ctypes.c_uint32),
        ("qpcRefreshPeriod", ctypes.c_uint64),
        ("rateComposeNumerator", ctypes.c_uint32),
        ("rateComposeDenominator", ctypes.c_uint32),
        ("qpcVBlank", ctypes.c_uint64),
        ("cRefresh", ctypes.c_uint64),
        ("cDXRefresh", ctypes.c_uint32),
        ("qpcCompose", ctypes.c_uint64),
        ("cFrame", ctypes.c_uint64),
        ("cDXPresent", ctypes.c_uint32),
        ("cRefreshFrame", ctypes.c_uint64),
        ("cFrameSubmitted", ctypes.c_uint64),
        ("cDXPresentSubmitted", ctypes.c_uint32),
        ("cFrameConfirmed", ctypes.c_uint64),
        ("cDXPresentConfirmed", ctypes.c_uint32),
        ("cRefreshConfirmed", ctypes.c_uint64),
        ("cDXRefreshConfirmed", ctypes.c_uint32),
        ("cFramesLate", ctypes.c_uint64),
        ("cFramesOutstanding", ctypes.c_uint32),
        ("cFrameDisplayed", ctypes.c_uint64),
        ("_padding", ctypes.c_byte * 160), # Ensure struct is large enough for DWM to write 292 bytes
    ]

dwmapi = ctypes.windll.dwmapi
info = _DWM_TIMING_INFO()
info.cbSize = 292

# 1. Take a baseline snapshot
if dwmapi.DwmGetCompositionTimingInfo(None, ctypes.byref(info)) == 0:
    start_presents = info.cDXPresent
    start_refresh = info.cRefresh
    start_time = time.perf_counter()
else:
    print("Failed to get initial timing info")
    exit(1)

# 2. Wait exactly 1 second
time.sleep(1.0)

# 3. Take a second snapshot
if dwmapi.DwmGetCompositionTimingInfo(None, ctypes.byref(info)) == 0:
    end_presents = info.cDXPresent
    end_refresh = info.cRefresh
    end_time = time.perf_counter()
    
    # 4. Calculate actual frames rendered per second
    elapsed_time = end_time - start_time
    total_frames = end_presents - start_presents
    game_fps = total_frames / elapsed_time
    
    refresh_frames = end_refresh - start_refresh
    refresh_fps = refresh_frames / elapsed_time
    
    print(f"Elapsed Time: {elapsed_time:.4f}s")
    print(f"Total Frames (Rendered): {total_frames}")
    print(f"Actual Game FPS: {round(game_fps, 1)}")
    print(f"Monitor Refresh FPS: {round(refresh_fps, 1)}")
    print(f"Monitor Refresh Rate: {info.rateRefreshNumerator / info.rateRefreshDenominator if info.rateRefreshDenominator > 0 else 0}")
else:
    print("Failed to get second timing info")
