"""
AI System Performance Booster - Orchestrator
Continuously monitors -> AI detects anomalies/pressure -> executes SAFE actions.
Never ends/kills any process.
"""
import time
import pandas as pd
import os
from monitor import sample_system_metrics, init_log, METRICS_FILE, FIELDS
from ai_engine import PerformanceAI, decide_actions
from actions import execute
import csv

BOOTSTRAP_SAMPLES = 40   # ~ a few minutes of data before AI training
INTERVAL_SEC = 3
WHITELIST_APPS = ["python.exe", "code.exe", "explorer.exe", "chrome.exe"]

def bootstrap_and_train():
    init_log()
    ai = PerformanceAI(contamination=0.05)
    prev_disk = prev_net = None
    rows = []
    print(f"Collecting {BOOTSTRAP_SAMPLES} baseline samples to learn 'normal' behavior...")
    for i in range(BOOTSTRAP_SAMPLES):
        row, prev_disk, prev_net = sample_system_metrics(prev_disk, prev_net)
        rows.append(row)
        with open(METRICS_FILE, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writerow(row)
        time.sleep(INTERVAL_SEC)
    df = pd.DataFrame(rows)
    ai.train(df)
    print("AI model trained on baseline system behavior.")
    return ai, prev_disk, prev_net

def run_loop(ai, prev_disk, prev_net, iterations=20):
    for _ in range(iterations):
        row, prev_disk, prev_net = sample_system_metrics(prev_disk, prev_net)
        anomaly = ai.detect_anomaly(row)
        actions = decide_actions(row, anomaly)
        print(f"[{row['timestamp']}] mem={row['mem_percent']}% cpu={row['cpu_percent']}% "
              f"anomaly={anomaly['is_anomaly']} -> actions={actions}")
        if actions != ["NO_ACTION_NEEDED"]:
            results = execute(actions)
            print(f"  Executed: {results}")
        time.sleep(INTERVAL_SEC)

if __name__ == "__main__":
    ai, prev_disk, prev_net = bootstrap_and_train()
    run_loop(ai, prev_disk, prev_net, iterations=20)
