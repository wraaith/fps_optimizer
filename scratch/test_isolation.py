import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'desktop-app', 'app'))

import services.system_scan as ss

steps = [
    ("cpu_name", ss._get_cpu_name),
    ("live_cpu_power", ss.get_live_cpu_power_wmi),
    ("gpus_reg", ss._get_gpus_from_registry),
    ("live_gpu_power", ss.get_live_gpu_power),
    ("gpu_info", ss._get_gpu_info),
    ("os_info", ss._get_os_info),
    ("full_scan", lambda: ss.run_system_scan(cached=False)),
]

for name, fn in steps:
    import subprocess
    code = f"""
import sys, os
sys.path.insert(0, os.path.join(r'{os.path.abspath("desktop-app/app")}'))
import services.system_scan as ss
res = ss.{fn.__name__ if hasattr(fn, '__name__') and fn.__name__ != '<lambda>' else 'run_system_scan(cached=False)'}()
"""
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    out = res.stdout + res.stderr
    if "IUnknown" in out or "exception" in out.lower():
        print(f"FAILED ON STEP: {name}")
        print(out)
    else:
        print(f"PASS: {name}")
