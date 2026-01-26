"""Prometheus metrics for QA Data Pipeline.

This module provides metrics collection for monitoring pipeline execution,
including counters, gauges, and histograms for various operations.
"""

import time
from typing import Optional, Dict, Any, Callable
from functools import wraps
from dataclasses import dataclass, field
from datetime import datetime

try:
    from prometheus_client import (
        Counter,
        Gauge,
        Histogram,
        CollectorRegistry,
        generate_latest,
        push_to_gateway,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


@dataclass
class MetricsSnapshot:
    """Snapshot of current metric values."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    pipeline_runs_total: int = 0
    pipeline_runs_success: int = 0
    pipeline_runs_failed: int = 0
    rows_processed_total: int = 0
    flags_generated_total: int = 0
    stage_duration_seconds: Dict[str, float] = field(default_factory=dict)
    current_stage: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "pipeline_runs_total": self.pipeline_runs_total,
            "pipeline_runs_success": self.pipeline_runs_success,
            "pipeline_runs_failed": self.pipeline_runs_failed,
            "rows_processed_total": self.rows_processed_total,
            "flags_generated_total": self.flags_generated_total,
            "stage_duration_seconds": self.stage_duration_seconds,
            "current_stage": self.current_stage,
        }


class MetricsCollector:
    """Collector for pipeline metrics."""
    
    def __init__(self, use_prometheus: bool = True):
        """Initialize metrics collector."""
        self.use_prometheus = use_prometheus and PROMETHEUS_AVAILABLE
        self._registry = CollectorRegistry() if self.use_prometheus else None
        
        # Internal counters
        self._counters: Dict[str, int] = {
            "pipeline_runs_total": 0,
            "pipeline_runs_success": 0,
            "pipeline_runs_failed": 0,
            "rows_processed_total": 0,
            "flags_generated_total": 0,
        }
        self._stage_durations: Dict[str, float] = {}
        self._current_stage: str = ""
        self._stage_start_time: Optional[float] = None
        
        if self.use_prometheus:
            self._init_prometheus()
    
    def _init_prometheus(self):
        """Initialize Prometheus metrics."""
        self._prom_runs = Counter(
            "qa_pipeline_runs_total", "Total pipeline runs",
            ["status"], registry=self._registry
        )
        self._prom_rows = Counter(
            "qa_pipeline_rows_total", "Total rows processed",
            registry=self._registry
        )
        self._prom_flags = Counter(
            "qa_pipeline_flags_total", "Total flags generated",
            ["flag_type"], registry=self._registry
        )
        self._prom_stage_duration = Histogram(
            "qa_pipeline_stage_seconds", "Stage duration",
            ["stage"], buckets=[0.1, 0.5, 1, 5, 10, 30, 60],
            registry=self._registry
        )
        self._prom_current_stage = Gauge(
            "qa_pipeline_current_stage", "Current stage",
            registry=self._registry
        )
    
    def increment_runs(self, success: bool = True):
        """Increment pipeline run counter."""
        self._counters["pipeline_runs_total"] += 1
        key = "pipeline_runs_success" if success else "pipeline_runs_failed"
        self._counters[key] += 1
        
        if self.use_prometheus:
            self._prom_runs.labels(status="success" if success else "failed").inc()
    
    def add_rows_processed(self, count: int):
        """Add to rows processed counter."""
        self._counters["rows_processed_total"] += count
        if self.use_prometheus:
            self._prom_rows.inc(count)
    
    def add_flags_generated(self, flag_type: str, count: int = 1):
        """Add to flags generated counter."""
        self._counters["flags_generated_total"] += count
        if self.use_prometheus:
            self._prom_flags.labels(flag_type=flag_type).inc(count)
    
    def start_stage(self, stage_name: str):
        """Mark start of a pipeline stage."""
        self._current_stage = stage_name
        self._stage_start_time = time.time()
        
        if self.use_prometheus:
            stage_map = {"load": 1, "filter": 2, "standardize": 3,
                        "autofill": 4, "flag": 5, "export": 6}
            self._prom_current_stage.set(stage_map.get(stage_name, 0))
    
    def end_stage(self, stage_name: str):
        """Mark end of a pipeline stage."""
        if self._stage_start_time:
            duration = time.time() - self._stage_start_time
            self._stage_durations[stage_name] = duration
            
            if self.use_prometheus:
                self._prom_stage_duration.labels(stage=stage_name).observe(duration)
        
        self._stage_start_time = None
    
    def get_snapshot(self) -> MetricsSnapshot:
        """Get current metrics snapshot."""
        return MetricsSnapshot(
            pipeline_runs_total=self._counters["pipeline_runs_total"],
            pipeline_runs_success=self._counters["pipeline_runs_success"],
            pipeline_runs_failed=self._counters["pipeline_runs_failed"],
            rows_processed_total=self._counters["rows_processed_total"],
            flags_generated_total=self._counters["flags_generated_total"],
            stage_duration_seconds=dict(self._stage_durations),
            current_stage=self._current_stage,
        )
    
    def reset(self):
        """Reset all metrics."""
        for key in self._counters:
            self._counters[key] = 0
        self._stage_durations.clear()
        self._current_stage = ""
    
    def export_prometheus(self) -> Optional[bytes]:
        """Export metrics in Prometheus format."""
        if self.use_prometheus and self._registry:
            return generate_latest(self._registry)
        return None


# Default collector
_collector: Optional[MetricsCollector] = None


def get_collector(use_prometheus: bool = True) -> MetricsCollector:
    """Get or create metrics collector."""
    global _collector
    if _collector is None:
        _collector = MetricsCollector(use_prometheus)
    return _collector


def timed_stage(stage_name: str):
    """Decorator to time a pipeline stage."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            collector = get_collector()
            collector.start_stage(stage_name)
            try:
                return func(*args, **kwargs)
            finally:
                collector.end_stage(stage_name)
        return wrapper
    return decorator


# Convenience functions
def increment_runs(success: bool = True):
    get_collector().increment_runs(success)

def add_rows_processed(count: int):
    get_collector().add_rows_processed(count)

def add_flags_generated(flag_type: str, count: int = 1):
    get_collector().add_flags_generated(flag_type, count)

def start_stage(stage_name: str):
    get_collector().start_stage(stage_name)

def end_stage(stage_name: str):
    get_collector().end_stage(stage_name)

def get_snapshot() -> MetricsSnapshot:
    return get_collector().get_snapshot()
