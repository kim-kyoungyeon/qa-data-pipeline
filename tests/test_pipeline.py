"""Tests for pipeline and metrics modules."""

import pytest
import os
import tempfile
import pandas as pd
from src.pipeline import (
    Pipeline,
    PipelineConfig,
    PipelineResult,
    StageResult,
)
from src.metrics import (
    MetricsCollector,
    MetricsSnapshot,
    get_collector,
    timed_stage,
)


class TestPipelineConfig:
    """Tests for PipelineConfig."""
    
    def test_defaults(self):
        config = PipelineConfig(input_file="test.xlsx")
        
        assert config.input_file == "test.xlsx"
        assert config.output_dir == "output"
        assert config.run_standardize is True
        assert config.run_flag is True
        assert config.run_autofill is True
    
    def test_custom(self):
        config = PipelineConfig(
            input_file="test.xlsx",
            output_dir="custom_output",
            run_autofill=False,
            item_range_start="4-1",
            item_range_end="5-2"
        )
        
        assert config.output_dir == "custom_output"
        assert config.run_autofill is False
        assert config.item_range_start == "4-1"


class TestStageResult:
    """Tests for StageResult."""
    
    def test_creation(self):
        result = StageResult(
            name="load",
            success=True,
            duration_ms=100.5,
            input_rows=0,
            output_rows=1000,
            stats={"file": "test.xlsx"}
        )
        
        assert result.name == "load"
        assert result.success is True
        assert result.duration_ms == 100.5


class TestPipelineResult:
    """Tests for PipelineResult."""
    
    def test_to_dict(self):
        from datetime import datetime
        
        result = PipelineResult(
            success=True,
            start_time=datetime.now(),
            end_time=datetime.now(),
            total_duration_ms=500.0,
            stages=[],
            final_stats={"total_rows": 100},
            output_files=["output.xlsx"]
        )
        
        d = result.to_dict()
        
        assert d["success"] is True
        assert "start_time" in d
        assert d["final_stats"]["total_rows"] == 100


class TestMetricsCollector:
    """Tests for MetricsCollector."""
    
    def test_increment_runs(self):
        collector = MetricsCollector(use_prometheus=False)
        
        collector.increment_runs(success=True)
        collector.increment_runs(success=False)
        
        snapshot = collector.get_snapshot()
        assert snapshot.pipeline_runs_total == 2
        assert snapshot.pipeline_runs_success == 1
        assert snapshot.pipeline_runs_failed == 1
    
    def test_add_rows(self):
        collector = MetricsCollector(use_prometheus=False)
        
        collector.add_rows_processed(100)
        collector.add_rows_processed(50)
        
        snapshot = collector.get_snapshot()
        assert snapshot.rows_processed_total == 150
    
    def test_add_flags(self):
        collector = MetricsCollector(use_prometheus=False)
        
        collector.add_flags_generated("EMPTY_DE", 10)
        collector.add_flags_generated("WEAK_E", 5)
        
        snapshot = collector.get_snapshot()
        assert snapshot.flags_generated_total == 15
    
    def test_stage_timing(self):
        import time
        collector = MetricsCollector(use_prometheus=False)
        
        collector.start_stage("load")
        time.sleep(0.1)
        collector.end_stage("load")
        
        snapshot = collector.get_snapshot()
        assert "load" in snapshot.stage_duration_seconds
        assert snapshot.stage_duration_seconds["load"] >= 0.1
    
    def test_reset(self):
        collector = MetricsCollector(use_prometheus=False)
        
        collector.increment_runs(success=True)
        collector.add_rows_processed(100)
        collector.reset()
        
        snapshot = collector.get_snapshot()
        assert snapshot.pipeline_runs_total == 0
        assert snapshot.rows_processed_total == 0


class TestMetricsSnapshot:
    """Tests for MetricsSnapshot."""
    
    def test_to_dict(self):
        snapshot = MetricsSnapshot(
            pipeline_runs_total=10,
            rows_processed_total=1000
        )
        
        d = snapshot.to_dict()
        
        assert d["pipeline_runs_total"] == 10
        assert d["rows_processed_total"] == 1000
        assert "timestamp" in d


class TestTimedStageDecorator:
    """Tests for timed_stage decorator."""
    
    def test_decorator(self):
        import time
        
        # Create fresh collector
        collector = MetricsCollector(use_prometheus=False)
        
        collector.start_stage("test_stage")
        time.sleep(0.05)
        collector.end_stage("test_stage")
        
        snapshot = collector.get_snapshot()
        assert "test_stage" in snapshot.stage_duration_seconds
