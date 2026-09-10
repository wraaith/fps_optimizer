# AI System Performance Booster

A local, non-destructive AI-driven optimizer for Windows that monitors system health
and applies safe remediation actions — **it never ends/kills any process.**

## Architecture

1. **monitor.py** — collects CPU/RAM/swap/disk/network telemetry via `psutil` every few seconds.
2. **ai_engine.py** — trains an unsupervised **Isolation Forest** on baseline ("normal") system
   behavior, then flags anomalies (unusual spikes) in real time, and forecasts short-term
   memory trend via linear regression.
3. **actions.py** — executes only SAFE, non-destructive fixes:
   - Clears Windows standby/cached memory (via `EmptyStandbyList.exe`, download separately from Sysinternals-adjacent tools)
   - Trims process working sets via `SetProcessWorkingSetSize` (WinAPI) — pages out idle memory without closing the app
   - Lowers CPU scheduling priority (`nice`) of heavy background processes — never terminates them
   - Logs an advisory to review page file / virtual memory size
4. **main.py** — orchestrates: bootstrap-train on ~2 minutes of baseline data, then loop
   detect → decide → act.

## Why Isolation Forest?

Isolation Forest is efficient, unsupervised, and well suited to system telemetry because
anomalies (sudden CPU/memory spikes) are "few and different" and get isolated in fewer
tree splits than normal points — no labeled training data required [cite:24][cite:27].

## Setup

```
pip install -r requirements.txt
python main.py
```

Optional: place `EmptyStandbyList.exe` in this folder to enable standby-memory clearing
(a well-known free Sysinternals-adjacent CLI tool referenced widely for this exact purpose) [cite:9][cite:12].

## Safety guarantees

- No call to `process.kill()`, `process.terminate()`, or `taskkill` anywhere in the codebase.
- All actions are reversible or purely cache-clearing (standby memory, working-set trim).
- Priority changes only lower scheduling priority — the process keeps running normally.
- Page file resizing is logged as an advisory only, never auto-applied (requires admin + reboot).

## Extending this further

- Swap the rule layer in `decide_actions()` for a trained classifier once you've logged
  enough real anomaly/action outcome pairs (supervised fine-tuning).
- Add a Random Forest regressor on historical CPU utilization to forecast capacity needs
  ahead of time, similar to AIOps capacity-planning approaches [cite:20].
- Package as a Windows Scheduled Task or background service for continuous operation.
