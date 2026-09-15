"""
Diagnostics Engine for Network Stabilizer.
Bounded, cancellable, on-demand diagnostic probes computing:
Average, Median, 95th-percentile, Maximum, Adjacent-Difference Jitter, Loss %, and Timeout count.
"""

import re
import time
import math
import socket
import urllib.request
import subprocess
import threading
from typing import Dict, List, Any, Optional, Callable, Tuple

from network_stabilizer.constants import (
    DEFAULT_PROBE_COUNT,
    DETAILED_PROBE_COUNT,
    PROBE_TIMEOUT_SEC,
    REGEX_IPV4,
    REGEX_HOSTNAME,
    BUFFERBLOAT_GRADES,
    NETWORK_DIAGNOSES,
    RENDER_DIAGNOSES,
    TERM_BUFFERBLOAT_DISCLAIMER
)


class DiagnosticsEngine:
    """
    On-demand, bounded diagnostic engine. Zero continuous background activity.
    """
    def __init__(self):
        self._cached_gateway: Optional[str] = None
        self._active_cancel_event: Optional[threading.Event] = None
        self._active_proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    def request_cancellation(self):
        """Signal immediate cancellation to any running diagnostic probe or bufferbloat test."""
        with self._lock:
            if self._active_cancel_event:
                self._active_cancel_event.set()
            if self._active_proc:
                try:
                    self._active_proc.terminate()
                except Exception:
                    pass

    # ── Target Validation ───────────────────────────────────────────────

    @staticmethod
    def validate_target(target: Optional[str]) -> Tuple[bool, str]:
        """
        Validates target host/IP.
        Rejects:
        - empty input
        - leading/trailing whitespace
        - internal whitespace
        - control characters
        - shell metacharacters
        - length > 255
        - invalid IP or invalid hostname
        Returns (is_valid: bool, error_message: str)
        """
        if target is None or target == "":
            return False, "Target cannot be empty."

        if target != target.strip():
            return False, "Target contains leading or trailing whitespace."

        if any(c.isspace() for c in target):
            return False, "Target cannot contain internal whitespace."

        if any(ord(c) < 32 or ord(c) == 127 for c in target):
            return False, "Target contains invalid control characters."

        # Reject any shell metacharacters for defense in depth
        metachars = set('&|;`$<>(){}[]^"\'*?!')
        if any(c in metachars for c in target):
            return False, "Target contains illegal characters."

        if len(target) > 255:
            return False, "Target exceeds maximum length of 255 characters."

        # Check for valid IPv4 or valid RFC 1123 hostname
        if REGEX_IPV4.match(target):
            return True, ""

        if REGEX_HOSTNAME.match(target):
            return True, ""

        return False, "Target is not a valid IPv4 address or hostname."

    # ── Gateway Discovery ───────────────────────────────────────────────

    def get_default_gateway(self) -> str:
        """Query default gateway IPv4 without persistent polling."""
        if self._cached_gateway:
            return self._cached_gateway

        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            cmd = ["powershell", "-NoProfile", "-Command",
                   "(Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | "
                   "Sort-Object RouteMetric | Select-Object -First 1).NextHop"]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5, creationflags=no_window)
            gw = proc.stdout.strip()
            if gw and gw != "0.0.0.0" and REGEX_IPV4.match(gw):
                self._cached_gateway = gw
                return gw
        except Exception:
            pass

        try:
            res = subprocess.run(["ipconfig"], capture_output=True, text=True, timeout=5, creationflags=no_window)
            for line in res.stdout.splitlines():
                if "Default Gateway" in line and ":" in line:
                    candidate = line.split(":")[1].strip()
                    if candidate and not candidate.startswith("fe80") and REGEX_IPV4.match(candidate):
                        self._cached_gateway = candidate
                        return candidate
        except Exception:
            pass

        return "192.168.1.1"

    # ── Bounded Ping Probing ───────────────────────────────────────────

    def ping_target_bounded(
        self,
        host: str,
        probe_count: int = DEFAULT_PROBE_COUNT,
        timeout_sec: float = PROBE_TIMEOUT_SEC,
        cancel_event: Optional[threading.Event] = None
    ) -> Dict[str, Any]:
        """
        Executes bounded probes against host.
        Calculates:
        - Average latency
        - Median latency
        - 95th-percentile latency
        - Maximum latency
        - Adjacent-Difference Jitter (mean absolute diff between consecutive successful samples)
        - Packet loss percentage
        - Timeout count
        """
        is_valid, err = self.validate_target(host)
        if not is_valid:
            return {
                "target": host,
                "error": err,
                "samples_count": 0,
                "avg_ms": 0.0,
                "median_ms": 0.0,
                "p95_ms": 0.0,
                "max_ms": 0.0,
                "adjacent_jitter_ms": 0.0,
                "loss_pct": 100.0,
                "timeout_count": probe_count,
                "status": f"Invalid Target: {err}"
            }

        probe_count = max(1, min(probe_count, 100))
        timeout_ms = int(timeout_sec * 1000)
        no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        samples = []
        timeouts = 0

        # Execute single probes sequentially so we can check cancel_event at safe points
        for i in range(probe_count):
            if cancel_event and cancel_event.is_set():
                break

            cmd = ["ping", "-n", "1", "-w", str(timeout_ms), host]
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=no_window)
                with self._lock:
                    self._active_proc = proc

                stdout, _ = proc.communicate(timeout=timeout_sec + 1.0)
                with self._lock:
                    self._active_proc = None

                # Parse RTT from ping output
                # Matches: "time=23ms" or "time<1ms"
                m = re.search(r"time(?:=|<)(\d+)\s*ms", stdout, re.IGNORECASE)
                if m:
                    ms_val = max(1.0, float(m.group(1))) if "<" not in stdout else 0.5
                    samples.append(ms_val)
                else:
                    timeouts += 1
            except subprocess.TimeoutExpired:
                proc.kill()
                timeouts += 1
            except Exception:
                timeouts += 1

            # Brief pause between probes to avoid network flooding
            if i < probe_count - 1 and cancel_event and not cancel_event.is_set():
                cancel_event.wait(0.05)

        total_probes = len(samples) + timeouts
        loss_pct = round((timeouts / total_probes) * 100.0, 1) if total_probes > 0 else 100.0

        if samples:
            sorted_samples = sorted(samples)
            n = len(sorted_samples)

            # Average
            avg_ms = round(sum(sorted_samples) / n, 1)

            # Median (50th percentile)
            if n % 2 == 1:
                median_ms = round(sorted_samples[n // 2], 1)
            else:
                median_ms = round((sorted_samples[n // 2 - 1] + sorted_samples[n // 2]) / 2.0, 1)

            # 95th Percentile
            p95_idx = min(n - 1, math.ceil(0.95 * n) - 1)
            p95_ms = round(sorted_samples[p95_idx], 1)

            # Maximum
            max_ms = round(sorted_samples[-1], 1)

            # Adjacent-Difference Jitter: mean absolute difference between consecutive successful samples
            if n > 1:
                diffs = [abs(samples[j + 1] - samples[j]) for j in range(len(samples) - 1)]
                adjacent_jitter_ms = round(sum(diffs) / len(diffs), 2)
            else:
                adjacent_jitter_ms = 0.0

            status = "OK" if loss_pct == 0 else f"{loss_pct}% Loss"
        else:
            avg_ms = 0.0
            median_ms = 0.0
            p95_ms = 0.0
            max_ms = 0.0
            adjacent_jitter_ms = 0.0
            status = "Unreachable / Timed Out"

        return {
            "target": host,
            "samples_count": len(samples),
            "total_probes": total_probes,
            "avg_ms": avg_ms,
            "median_ms": median_ms,
            "p95_ms": p95_ms,
            "max_ms": max_ms,
            "adjacent_jitter_ms": adjacent_jitter_ms,
            "loss_pct": loss_pct,
            "timeout_count": timeouts,
            "status": status,
            "cancelled": bool(cancel_event and cancel_event.is_set())
        }

    def ping_host(self, host: str, count: int = 4, timeout_ms: int = 1000) -> Dict[str, Any]:
        """
        Bounded on-demand ping compatible with test suites and live monitor.
        """
        res = self.ping_target_bounded(host, probe_count=count)
        res["sent"] = res.get("total_probes", count)
        res["received"] = res.get("samples_count", 0)
        res["samples"] = [res.get("avg_ms", 0.0)] if res["received"] > 0 else []
        return res

    # ── Full Diagnostic Probe ─────────────────────────────────────────

    def run_full_diagnostic(
        self,
        custom_game_host: Optional[str] = None,
        probe_count: int = DEFAULT_PROBE_COUNT,
        cancel_event: Optional[threading.Event] = None
    ) -> Dict[str, Any]:
        """
        Runs bounded tests across Gateway, 1.1.1.1, 8.8.8.8, and optional sanitized custom host.
        Distinguishes Network Stutter root cause vs Render Stutter root cause.
        """
        with self._lock:
            self._active_cancel_event = cancel_event

        gateway = self.get_default_gateway()

        # Sanitize and validate custom host
        clean_custom = None
        if custom_game_host and custom_game_host.strip():
            c = custom_game_host.strip()
            is_valid, _ = self.validate_target(c)
            if is_valid:
                clean_custom = c

        targets = [
            {"id": "gateway", "label": f"Gateway ({gateway})", "host": gateway},
            {"id": "cloudflare", "label": "Cloudflare (1.1.1.1)", "host": "1.1.1.1"},
            {"id": "google", "label": "Google (8.8.8.8)", "host": "8.8.8.8"},
        ]
        if clean_custom:
            targets.append({"id": "custom", "label": f"Custom Target ({clean_custom})", "host": clean_custom})

        results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "probe_count": probe_count,
            "targets": {},
            "network_diagnosis": NETWORK_DIAGNOSES["NO_NETWORK_INSTABILITY"],
            "render_diagnosis": RENDER_DIAGNOSES["INSUFFICIENT_RENDER_DATA"],
            "summary_text": "",
            "cancelled": False
        }

        for t in targets:
            if cancel_event and cancel_event.is_set():
                results["cancelled"] = True
                break
            t_res = self.ping_target_bounded(t["host"], probe_count=probe_count, cancel_event=cancel_event)
            t_res["label"] = t["label"]
            results["targets"][t["id"]] = t_res

        # Evaluate root cause from collected summaries
        gw_data = results["targets"].get("gateway", {})
        cf_data = results["targets"].get("cloudflare", {})

        gw_loss = gw_data.get("loss_pct", 0.0)
        gw_jitter = gw_data.get("adjacent_jitter_ms", 0.0)
        cf_loss = cf_data.get("loss_pct", 0.0)
        cf_jitter = cf_data.get("adjacent_jitter_ms", 0.0)

        if gw_loss > 0 or gw_jitter > 3.5:
            results["network_diagnosis"] = NETWORK_DIAGNOSES["LOCAL_LAN_INSTABILITY"]
            results["summary_text"] = "High jitter or packet loss to local router. Check Wi-Fi interference or Ethernet cable."
        elif cf_loss > 1.0:
            results["network_diagnosis"] = NETWORK_DIAGNOSES["PACKET_LOSS_DETECTED"]
            results["summary_text"] = "Packet loss observed on Internet route. Flush DNS and inspect ISP link."
        elif cf_jitter > 12.0:
            results["network_diagnosis"] = NETWORK_DIAGNOSES["EXTERNAL_ROUTE_INSTABILITY"]
            results["summary_text"] = "High WAN jitter observed on Internet route."
        else:
            results["network_diagnosis"] = NETWORK_DIAGNOSES["NO_NETWORK_INSTABILITY"]
            results["summary_text"] = "Network latency and jitter are stable. Micro-stutters may be caused by render frame-time spikes."
            results["render_diagnosis"] = RENDER_DIAGNOSES["FRAME_TIME_SPIKES"]

        with self._lock:
            self._active_cancel_event = None

        return results

    # ── Controlled Bounded Bufferbloat Test ────────────────────────────

    def run_controlled_bufferbloat_test(
        self,
        cancel_event: Optional[threading.Event] = None,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Controlled loaded-latency test:
        1. Bounded idle baseline (10 probes to 1.1.1.1)
        2. Generates bounded load (Cloudflare CDN 10MB chunk, max 8-10s duration)
        3. Measures 10 probes during traffic load
        4. Compares: Idle Median vs Loaded Median vs Delta
        5. Grades delta using application-defined guidance threshold.
        """
        with self._lock:
            self._active_cancel_event = cancel_event

        def _notify(m: str):
            if progress_callback:
                progress_callback(m)

        _notify("Measuring baseline idle median latency (10 probes)...")
        idle_res = self.ping_target_bounded("1.1.1.1", probe_count=10, timeout_sec=0.8, cancel_event=cancel_event)
        if cancel_event and cancel_event.is_set():
            return {"cancelled": True}

        idle_median = idle_res.get("median_ms", 20.0)
        if idle_median <= 0:
            idle_median = 20.0

        _notify(f"Idle median: {idle_median}ms. Initializing bounded traffic load (max 8s)...")

        # Bounded controlled download from Cloudflare CDN speed probe
        test_url = "https://speed.cloudflare.com/__down?bytes=10000000"
        stop_worker = threading.Event()

        def _download_worker():
            try:
                req = urllib.request.Request(test_url, headers={"User-Agent": "FPSOptimizer-Probe/1.0"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    while not stop_worker.is_set():
                        chunk = resp.read(64 * 1024)
                        if not chunk:
                            break
            except Exception:
                pass

        load_t = threading.Thread(target=_download_worker, daemon=True)
        load_t.start()

        # Brief ramp up
        time.sleep(1.0)
        _notify("Measuring latency under load (10 probes)...")

        loaded_res = self.ping_target_bounded("1.1.1.1", probe_count=10, timeout_sec=0.8, cancel_event=cancel_event)

        # Stop download worker immediately
        stop_worker.set()
        with self._lock:
            self._active_cancel_event = None

        if cancel_event and cancel_event.is_set():
            return {"cancelled": True}

        loaded_median = loaded_res.get("median_ms", idle_median)
        if loaded_median <= 0:
            loaded_median = idle_median

        delta_ms = max(0.0, round(loaded_median - idle_median, 1))

        # Assign grade with application-defined guidance threshold
        grade_info = None
        for g in BUFFERBLOAT_GRADES:
            if g["min_delta"] <= delta_ms < g["max_delta"]:
                grade_info = g
                break
        if not grade_info:
            grade_info = BUFFERBLOAT_GRADES[-1]

        _notify("Bufferbloat test complete.")

        return {
            "idle_median_ms": idle_median,
            "loaded_median_ms": loaded_median,
            "delta_ms": delta_ms,
            "grade": grade_info["grade"],
            "rating": grade_info["rating"],
            "color": grade_info["color"],
            "summary": grade_info["summary"],
            "disclaimer": TERM_BUFFERBLOAT_DISCLAIMER,
            "cancelled": False
        }
