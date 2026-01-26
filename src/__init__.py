"""QA Data Pipeline - Automated QA validation for large-scale regulatory data.

This package provides tools for:
- Flag generation for data quality issues
- D column label standardization
- Auto-fill from AI-extracted data
- Data merging and diff detection
- Pipeline orchestration
- Logging and metrics collection
"""

from .config import config
from .flag_generator import (
    FlagType,
    FlagResult,
    generate_flags,
    detect_flags,
    process_dataframe,
    get_flag_statistics,
    is_ok_status,
    sanitize,
    filter_by_flag,
    get_review_queue,
)
from .standardize import (
    standardize_label,
    standardize_dataframe,
    filter_by_item_range,
    get_label_variations,
)
from .autofill import autofill_from_ai
from .data_merger import (
    merge_flagged_to_original,
    find_overwritten_rows,
)
from .pipeline import (
    Pipeline,
    PipelineConfig,
    PipelineResult,
    StageResult,
    run_pipeline,
)
from . import logging_utils as log
from . import metrics

__version__ = "0.2.0"
__all__ = [
    # Config
    "config",
    
    # Flag Generator
    "FlagType",
    "FlagResult",
    "generate_flags",
    "detect_flags",
    "process_dataframe",
    "get_flag_statistics",
    "is_ok_status",
    "sanitize",
    "filter_by_flag",
    "get_review_queue",
    
    # Standardize
    "standardize_label",
    "standardize_dataframe",
    "filter_by_item_range",
    "get_label_variations",
    
    # Autofill
    "autofill_from_ai",
    
    # Data Merger
    "merge_flagged_to_original",
    "find_overwritten_rows",
    
    # Pipeline
    "Pipeline",
    "PipelineConfig",
    "PipelineResult",
    "StageResult",
    "run_pipeline",
    
    # Logging & Metrics
    "log",
    "metrics",
]
