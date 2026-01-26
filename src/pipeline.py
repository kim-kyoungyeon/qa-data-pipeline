"""Pipeline orchestrator for QA data validation.

This module orchestrates the entire QA pipeline, running all steps
in the correct order and managing data flow between stages.

Pipeline Stages:
    1. Load: Read input Excel file
    2. Standardize: Normalize D column labels
    3. Flag: Generate validation flags
    4. Autofill: Fill E from AI data (H column)
    5. Export: Save results
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
import pandas as pd

from .config import config as app_config
from .flag_generator import (
    process_dataframe as generate_flags,
    get_flag_statistics,
    FlagType,
)
from .standardize import standardize_dataframe, filter_by_item_range
from .autofill import autofill_from_ai
from .data_merger import merge_flagged_to_original, find_overwritten_rows


@dataclass
class PipelineConfig:
    """Configuration for pipeline execution."""
    input_file: str
    output_dir: str = "output"
    
    # Stage toggles
    run_standardize: bool = True
    run_flag: bool = True
    run_autofill: bool = True
    
    # Filters
    item_range_start: Optional[str] = None  # e.g., "4-1"
    item_range_end: Optional[str] = None    # e.g., "5-2"
    
    # Output options
    save_intermediate: bool = False
    export_format: str = "xlsx"  # xlsx or csv


@dataclass
class StageResult:
    """Result of a single pipeline stage."""
    name: str
    success: bool
    duration_ms: float
    input_rows: int
    output_rows: int
    stats: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class PipelineResult:
    """Result of entire pipeline execution."""
    success: bool
    start_time: datetime
    end_time: datetime
    total_duration_ms: float
    stages: List[StageResult] = field(default_factory=list)
    final_stats: Dict[str, Any] = field(default_factory=dict)
    output_files: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "total_duration_ms": self.total_duration_ms,
            "stages": [
                {
                    "name": s.name,
                    "success": s.success,
                    "duration_ms": s.duration_ms,
                    "input_rows": s.input_rows,
                    "output_rows": s.output_rows,
                    "stats": s.stats,
                    "error": s.error,
                }
                for s in self.stages
            ],
            "final_stats": self.final_stats,
            "output_files": self.output_files,
        }


class Pipeline:
    """Main pipeline orchestrator."""
    
    def __init__(self, cfg: PipelineConfig):
        """Initialize pipeline with configuration.
        
        Args:
            cfg: Pipeline configuration
        """
        self.cfg = cfg
        self.df: Optional[pd.DataFrame] = None
        self.flagged_df: Optional[pd.DataFrame] = None
        self.stages: List[StageResult] = []
        
        # Callbacks for progress reporting
        self._on_stage_start: Optional[Callable[[str], None]] = None
        self._on_stage_end: Optional[Callable[[StageResult], None]] = None
    
    def on_stage_start(self, callback: Callable[[str], None]) -> "Pipeline":
        """Set callback for stage start events."""
        self._on_stage_start = callback
        return self
    
    def on_stage_end(self, callback: Callable[[StageResult], None]) -> "Pipeline":
        """Set callback for stage end events."""
        self._on_stage_end = callback
        return self
    
    def _run_stage(
        self,
        name: str,
        func: Callable[[], Dict[str, Any]],
        input_rows: int
    ) -> StageResult:
        """Run a single pipeline stage with timing.
        
        Args:
            name: Stage name
            func: Function to execute
            input_rows: Number of input rows
            
        Returns:
            StageResult with timing and stats
        """
        if self._on_stage_start:
            self._on_stage_start(name)
        
        start = datetime.now()
        
        try:
            result = func()
            success = True
            error = None
        except Exception as e:
            result = {"output_rows": 0, "stats": {}}
            success = False
            error = str(e)
        
        end = datetime.now()
        duration_ms = (end - start).total_seconds() * 1000
        
        stage_result = StageResult(
            name=name,
            success=success,
            duration_ms=round(duration_ms, 2),
            input_rows=input_rows,
            output_rows=result.get("output_rows", 0),
            stats=result.get("stats", {}),
            error=error,
        )
        
        self.stages.append(stage_result)
        
        if self._on_stage_end:
            self._on_stage_end(stage_result)
        
        return stage_result
    
    def run(self) -> PipelineResult:
        """Execute the full pipeline.
        
        Returns:
            PipelineResult with all stage results
        """
        start_time = datetime.now()
        self.stages = []
        output_files = []
        
        # Ensure output directory exists
        os.makedirs(self.cfg.output_dir, exist_ok=True)
        
        # Stage 1: Load
        def load_stage():
            self.df = pd.read_excel(self.cfg.input_file)
            return {
                "output_rows": len(self.df),
                "stats": {
                    "columns": list(self.df.columns),
                    "file": self.cfg.input_file,
                }
            }
        
        load_result = self._run_stage("load", load_stage, 0)
        if not load_result.success:
            return self._finalize(start_time, False, output_files)
        
        current_rows = len(self.df)
        
        # Stage 1.5: Filter by item range (optional)
        if self.cfg.item_range_start and self.cfg.item_range_end:
            def filter_stage():
                self.df = filter_by_item_range(
                    self.df,
                    self.cfg.item_range_start,
                    self.cfg.item_range_end
                )
                return {
                    "output_rows": len(self.df),
                    "stats": {
                        "range": f"{self.cfg.item_range_start} ~ {self.cfg.item_range_end}"
                    }
                }
            
            filter_result = self._run_stage("filter", filter_stage, current_rows)
            if not filter_result.success:
                return self._finalize(start_time, False, output_files)
            current_rows = len(self.df)
        
        # Stage 2: Standardize
        if self.cfg.run_standardize:
            def standardize_stage():
                self.df, stats = standardize_dataframe(self.df)
                return {
                    "output_rows": len(self.df),
                    "stats": stats
                }
            
            std_result = self._run_stage("standardize", standardize_stage, current_rows)
            if not std_result.success:
                return self._finalize(start_time, False, output_files)
            
            if self.cfg.save_intermediate:
                path = self._save_df(self.df, "standardized")
                output_files.append(path)
        
        # Stage 3: Autofill
        if self.cfg.run_autofill:
            def autofill_stage():
                self.df, stats = autofill_from_ai(self.df)
                return {
                    "output_rows": len(self.df),
                    "stats": stats
                }
            
            auto_result = self._run_stage("autofill", autofill_stage, current_rows)
            if not auto_result.success:
                return self._finalize(start_time, False, output_files)
            
            if self.cfg.save_intermediate:
                path = self._save_df(self.df, "autofilled")
                output_files.append(path)
        
        # Stage 4: Flag
        if self.cfg.run_flag:
            def flag_stage():
                self.flagged_df = generate_flags(self.df)
                stats = get_flag_statistics(self.df)
                return {
                    "output_rows": len(self.flagged_df),
                    "stats": stats
                }
            
            flag_result = self._run_stage("flag", flag_stage, current_rows)
            if not flag_result.success:
                return self._finalize(start_time, False, output_files)
            
            # Always save flagged results
            path = self._save_df(self.flagged_df, "flagged")
            output_files.append(path)
        
        # Stage 5: Export final
        def export_stage():
            path = self._save_df(self.df, "final")
            output_files.append(path)
            return {
                "output_rows": len(self.df),
                "stats": {"output_file": path}
            }
        
        export_result = self._run_stage("export", export_stage, current_rows)
        
        return self._finalize(start_time, export_result.success, output_files)
    
    def _save_df(self, df: pd.DataFrame, suffix: str) -> str:
        """Save dataframe to file.
        
        Args:
            df: DataFrame to save
            suffix: Filename suffix
            
        Returns:
            Output file path
        """
        base_name = Path(self.cfg.input_file).stem
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if self.cfg.export_format == "csv":
            filename = f"{base_name}_{suffix}_{timestamp}.csv"
            path = os.path.join(self.cfg.output_dir, filename)
            df.to_csv(path, index=False, encoding="utf-8-sig")
        else:
            filename = f"{base_name}_{suffix}_{timestamp}.xlsx"
            path = os.path.join(self.cfg.output_dir, filename)
            df.to_excel(path, index=False)
        
        return path
    
    def _finalize(
        self,
        start_time: datetime,
        success: bool,
        output_files: List[str]
    ) -> PipelineResult:
        """Finalize pipeline execution.
        
        Args:
            start_time: Pipeline start time
            success: Overall success status
            output_files: List of output file paths
            
        Returns:
            PipelineResult
        """
        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds() * 1000
        
        # Compute final stats
        final_stats = {}
        if self.df is not None:
            final_stats["total_rows"] = len(self.df)
        if self.flagged_df is not None:
            final_stats["flagged_rows"] = len(self.flagged_df)
            final_stats["flagged_pct"] = round(
                len(self.flagged_df) / len(self.df) * 100, 2
            ) if self.df is not None and len(self.df) > 0 else 0
        
        return PipelineResult(
            success=success,
            start_time=start_time,
            end_time=end_time,
            total_duration_ms=round(total_duration, 2),
            stages=self.stages,
            final_stats=final_stats,
            output_files=output_files,
        )


def run_pipeline(
    input_file: str,
    output_dir: str = "output",
    item_range: Optional[tuple] = None,
    verbose: bool = True,
) -> PipelineResult:
    """Convenience function to run pipeline with default settings.
    
    Args:
        input_file: Input Excel file path
        output_dir: Output directory
        item_range: Optional (start, end) tuple for item filtering
        verbose: Print progress to console
        
    Returns:
        PipelineResult
    """
    cfg = PipelineConfig(
        input_file=input_file,
        output_dir=output_dir,
        item_range_start=item_range[0] if item_range else None,
        item_range_end=item_range[1] if item_range else None,
        save_intermediate=False,
    )
    
    pipeline = Pipeline(cfg)
    
    if verbose:
        def on_start(name: str):
            print(f"[STAGE] {name}...")
        
        def on_end(result: StageResult):
            status = "OK" if result.success else "FAIL"
            print(f"[{status}] {result.name}: {result.output_rows} rows ({result.duration_ms}ms)")
        
        pipeline.on_stage_start(on_start).on_stage_end(on_end)
    
    return pipeline.run()
