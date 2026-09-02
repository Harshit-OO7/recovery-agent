"""
Demo Clock Time-Compression Module.

WHY THIS EXISTS:
Production recovery policies operate across real-world timescales (24h cooldowns,
overnight quiet hours, 48h salary cycle alignments). During an interactive demo or video,
waiting 24 hours is impossible.

The DemoClock compresses time durations by `DEMO_TIME_MULTIPLIER` (e.g. 28800x, turning
24 hours into 3 seconds).
CRITICAL RULE: The API and audit trail MUST report BOTH the real configured policy duration
and the compressed demo duration, ensuring complete transparency for hackathon evaluation.
"""

import time
from typing import Any, Dict, Optional

from app.config import settings


class DemoClock:
    """
    Clock engine that translates real-world policy durations into compressed demonstration time.
    """

    def __init__(self, multiplier: Optional[float] = None):
        self._multiplier = multiplier

    @property
    def multiplier(self) -> float:
        if self._multiplier is not None:
            return self._multiplier
        return getattr(settings, "DEMO_TIME_MULTIPLIER", 1.0)

    @multiplier.setter
    def multiplier(self, value: float) -> None:
        self._multiplier = max(1.0, value)

    def compress_duration(self, real_seconds: float) -> float:
        """
        Converts real duration in seconds to compressed simulation seconds.
        E.g., 86,400s (24h) / 28800 = 3.0s.
        """
        mult = self.multiplier
        if mult <= 0:
            return 0.0
        return real_seconds / mult

    def sleep_compressed(self, real_seconds: float, max_sleep_cap: float = 3.0) -> float:
        """
        Sleeps for the compressed duration, capped by max_sleep_cap.
        Returns the actual wall-clock seconds slept.
        """
        compressed = self.compress_duration(real_seconds)
        sleep_time = min(compressed, max_sleep_cap)
        if sleep_time > 0.005:
            time.sleep(sleep_time)
        return sleep_time

    def format_time_audit(self, real_seconds: float) -> Dict[str, Any]:
        """
        Produces a dual-duration audit payload showing real policy values alongside demo-compressed values.
        """
        compressed_sec = self.compress_duration(real_seconds)
        return {
            "real_duration_seconds": int(real_seconds),
            "real_duration_hours": round(real_seconds / 3600.0, 2),
            "real_duration_days": round(real_seconds / 86400.0, 2),
            "compressed_duration_seconds": round(compressed_sec, 3),
            "demo_time_multiplier": self.multiplier,
            "is_time_compressed": self.multiplier > 1.0,
        }


demo_clock = DemoClock()
