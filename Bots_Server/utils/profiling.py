import os
import json
import time
import asyncio
from typing import Optional, Dict, Any

import psutil


class AsyncPhaseProfiler:
    """
    Async profiler that samples system metrics periodically and writes JSONL records.
    Also computes running statistics and flags simple anomalies (z > 3) after warmup.
    """

    def __init__(
        self,
        phase_name: str,
        out_dir: str = "logs/phase_profiles",
        sample_interval_seconds: float = 1.0,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.phase_name = phase_name
        self.out_dir = out_dir
        self.sample_interval_seconds = sample_interval_seconds
        self.extra_metadata = extra_metadata or {}

        self._running: bool = False
        self._task: Optional[asyncio.Task] = None
        self._start_monotonic: float = 0.0
        self._start_epoch: float = 0.0
        self._file_path: Optional[str] = None

        # Running stats (Welford) for cpu_percent and memory_percent
        self._n: int = 0
        self._mean_cpu: float = 0.0
        self._m2_cpu: float = 0.0
        self._mean_mem: float = 0.0
        self._m2_mem: float = 0.0
        self._max_cpu: float = 0.0
        self._max_mem: float = 0.0

    async def start(self) -> None:
        os.makedirs(self.out_dir, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        safe_phase = self.phase_name.replace(" ", "_")
        self._file_path = os.path.join(self.out_dir, f"{safe_phase}_{ts}.jsonl")
        self._running = True
        self._start_monotonic = time.monotonic()
        self._start_epoch = time.time()

        # Prime psutil cpu_percent to avoid first-call anomaly
        psutil.cpu_percent(interval=None)

        # Write header
        header = {
            "type": "phase_start",
            "phase": self.phase_name,
            "epoch": self._start_epoch,
            "metadata": self.extra_metadata,
        }
        self._append_json(header)

        self._task = asyncio.create_task(self._sample_loop())

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._task is not None:
            try:
                await self._task
            finally:
                self._task = None

        duration = time.monotonic() - self._start_monotonic
        summary = {
            "type": "phase_summary",
            "phase": self.phase_name,
            "epoch": time.time(),
            "duration_seconds": duration,
            "stats": {
                "cpu_percent": self._stats_dict(self._n, self._mean_cpu, self._m2_cpu, self._max_cpu),
                "memory_percent": self._stats_dict(self._n, self._mean_mem, self._m2_mem, self._max_mem),
            },
        }
        self._append_json(summary)

    async def _sample_loop(self) -> None:
        net_prev = psutil.net_io_counters()
        disk_prev = psutil.disk_io_counters() if hasattr(psutil, "disk_io_counters") else None

        while self._running:
            t_epoch = time.time()
            cpu = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory().percent
            load_avg = None
            try:
                load_avg = os.getloadavg()
            except Exception:
                load_avg = None

            net_now = psutil.net_io_counters()
            net_delta = {
                "bytes_sent": max(0, net_now.bytes_sent - net_prev.bytes_sent),
                "bytes_recv": max(0, net_now.bytes_recv - net_prev.bytes_recv),
                "packets_sent": max(0, net_now.packets_sent - net_prev.packets_sent),
                "packets_recv": max(0, net_now.packets_recv - net_prev.packets_recv),
            }
            net_prev = net_now

            disk_delta = None
            if disk_prev is not None:
                disk_now = psutil.disk_io_counters()
                disk_delta = {
                    "read_bytes": max(0, disk_now.read_bytes - disk_prev.read_bytes),
                    "write_bytes": max(0, disk_now.write_bytes - disk_prev.write_bytes),
                    "read_count": max(0, disk_now.read_count - disk_prev.read_count),
                    "write_count": max(0, disk_now.write_count - disk_prev.write_count),
                }
                disk_prev = disk_now

            # Update running stats
            self._update_running_stats(cpu, mem)

            record = {
                "type": "sample",
                "phase": self.phase_name,
                "epoch": t_epoch,
                "metrics": {
                    "cpu_percent": cpu,
                    "memory_percent": mem,
                    "load_avg": load_avg,
                    "net_delta": net_delta,
                    "disk_delta": disk_delta,
                },
            }
            self._append_json(record)

            # Simple anomaly detection after 10 samples
            if self._n >= 10:
                cpu_z = self._z_score(value=cpu, mean=self._mean_cpu, m2=self._m2_cpu, n=self._n)
                mem_z = self._z_score(value=mem, mean=self._mean_mem, m2=self._m2_mem, n=self._n)
                if cpu_z is not None and cpu_z > 3.0:
                    self._append_json({
                        "type": "anomaly",
                        "phase": self.phase_name,
                        "epoch": t_epoch,
                        "signal": "cpu_percent",
                        "z_score": cpu_z,
                        "value": cpu,
                    })
                if mem_z is not None and mem_z > 3.0:
                    self._append_json({
                        "type": "anomaly",
                        "phase": self.phase_name,
                        "epoch": t_epoch,
                        "signal": "memory_percent",
                        "z_score": mem_z,
                        "value": mem,
                    })

            await asyncio.sleep(self.sample_interval_seconds)

    def _update_running_stats(self, cpu: float, mem: float) -> None:
        self._n += 1

        # CPU
        delta_cpu = cpu - self._mean_cpu
        self._mean_cpu += delta_cpu / self._n
        delta2_cpu = cpu - self._mean_cpu
        self._m2_cpu += delta_cpu * delta2_cpu
        if cpu > self._max_cpu:
            self._max_cpu = cpu

        # Memory
        delta_mem = mem - self._mean_mem
        self._mean_mem += delta_mem / self._n
        delta2_mem = mem - self._mean_mem
        self._m2_mem += delta_mem * delta2_mem
        if mem > self._max_mem:
            self._max_mem = mem

    @staticmethod
    def _stats_dict(n: int, mean: float, m2: float, max_value: float) -> Dict[str, Any]:
        if n <= 1:
            variance = 0.0
            stddev = 0.0
        else:
            variance = m2 / (n - 1)
            stddev = variance ** 0.5
        return {
            "count": n,
            "mean": mean,
            "stddev": stddev,
            "max": max_value,
        }

    @staticmethod
    def _z_score(value: float, mean: float, m2: float, n: int) -> Optional[float]:
        if n <= 1:
            return None
        variance = m2 / (n - 1)
        if variance <= 1e-9:
            return None
        stddev = variance ** 0.5
        return (value - mean) / stddev

    def _append_json(self, obj: Dict[str, Any]) -> None:
        if not self._file_path:
            return
        try:
            with open(self._file_path, "a") as f:
                f.write(json.dumps(obj) + "\n")
        except Exception:
            # Swallow I/O errors to avoid impacting the main flow
            pass


