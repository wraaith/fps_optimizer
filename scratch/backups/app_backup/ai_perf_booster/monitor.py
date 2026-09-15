"""
AI System Performance Booster - Monitoring & Data Collection Module
Collects real-time system metrics using psutil.
Optimized for minimal overhead on low-end hardware.
No processes are ever terminated by this module.
"""
import psutil
import time
from datetime import datetime

FIELDS = [
    "timestamp", "cpu_percent", "mem_percent", "mem_available_mb",
    "swap_percent", "disk_read_mb", "disk_write_mb",
    "net_sent_mb", "net_recv_mb"
]

def sample_system_metrics(prev_disk=None, prev_net=None):
    # Non-blocking CPU query based on OS tick delta (0ms delay)
    cpu = psutil.cpu_percent(interval=None)
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    disk = psutil.disk_io_counters()
    net = psutil.net_io_counters()

    disk_read_mb = disk_write_mb = net_sent_mb = net_recv_mb = 0.0
    if prev_disk is not None and disk is not None:
        disk_read_mb = max(0.0, (disk.read_bytes - prev_disk.read_bytes) / (1024**2))
        disk_write_mb = max(0.0, (disk.write_bytes - prev_disk.write_bytes) / (1024**2))
    if prev_net is not None and net is not None:
        net_sent_mb = max(0.0, (net.bytes_sent - prev_net.bytes_sent) / (1024**2))
        net_recv_mb = max(0.0, (net.bytes_recv - prev_net.bytes_recv) / (1024**2))

    row = {
        "timestamp": datetime.now().isoformat(),
        "cpu_percent": cpu,
        "mem_percent": vm.percent,
        "mem_available_mb": vm.available / (1024**2),
        "swap_percent": swap.percent,
        "disk_read_mb": round(disk_read_mb, 3),
        "disk_write_mb": round(disk_write_mb, 3),
        "net_sent_mb": round(net_sent_mb, 3),
        "net_recv_mb": round(net_recv_mb, 3),
    }
    return row, disk, net

def top_memory_processes(n=10):
    procs = []
    for p in psutil.process_iter(['pid', 'name', 'memory_info', 'cpu_percent', 'nice']):
        try:
            mem_info = p.info.get('memory_info')
            if not mem_info:
                continue
            mem_mb = mem_info.rss / (1024**2)
            procs.append({
                "pid": p.info['pid'],
                "name": p.info['name'],
                "mem_mb": round(mem_mb, 2),
                "cpu_percent": p.info.get('cpu_percent', 0) or 0,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, Exception):
            continue
    procs.sort(key=lambda x: x["mem_mb"], reverse=True)
    return procs[:n]

