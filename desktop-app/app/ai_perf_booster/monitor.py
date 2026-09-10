"""
AI System Performance Booster - Monitoring & Data Collection Module
Collects real-time system + per-process metrics using psutil.
No processes are ever terminated by this module.
"""
import psutil
import time
import csv
import os
from datetime import datetime

METRICS_FILE = os.path.join(os.path.dirname(__file__), "metrics_log.csv")

FIELDS = [
    "timestamp", "cpu_percent", "mem_percent", "mem_available_mb",
    "swap_percent", "disk_read_mb", "disk_write_mb",
    "net_sent_mb", "net_recv_mb", "num_processes", "num_threads"
]

def init_log():
    if not os.path.exists(METRICS_FILE):
        with open(METRICS_FILE, "w", newline="") as f:
            csv.writer(f).writerow(FIELDS)

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
        "num_processes": 0,
        "num_threads": 0,
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

def run_monitor(duration_sec=60, interval_sec=3):
    init_log()
    prev_disk = psutil.disk_io_counters()
    prev_net = psutil.net_io_counters()
    rows = []
    start = time.time()
    while time.time() - start < duration_sec:
        row, prev_disk, prev_net = sample_system_metrics(prev_disk, prev_net)
        rows.append(row)
        with open(METRICS_FILE, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writerow(row)
        time.sleep(interval_sec)
    return rows

if __name__ == "__main__":
    run_monitor(duration_sec=60, interval_sec=3)
