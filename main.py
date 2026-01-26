#!/usr/bin/env python3
"""QA Data Pipeline CLI.

Usage:
    python main.py input.xlsx --output-dir ./output
    python main.py input.xlsx --range 4-1 5-2
    python main.py input.xlsx --no-autofill
"""

import argparse
import sys
import json
from pathlib import Path
from datetime import datetime

from src.pipeline import Pipeline, PipelineConfig, PipelineResult
from src.config import config, reload_config
from src import log


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="QA Data Pipeline - Automated validation for regulatory data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s data/input.xlsx
  %(prog)s data/input.xlsx --output-dir ./results
  %(prog)s data/input.xlsx --range 4-1 5-2
  %(prog)s data/input.xlsx --no-autofill --json
        """
    )
    
    # Required
    parser.add_argument(
        "input_file",
        help="Input Excel file path"
    )
    
    # Output options
    parser.add_argument(
        "-o", "--output-dir",
        default="output",
        help="Output directory (default: output)"
    )
    parser.add_argument(
        "--format",
        choices=["xlsx", "csv"],
        default="xlsx",
        help="Output format (default: xlsx)"
    )
    
    # Pipeline stages
    parser.add_argument(
        "--no-standardize",
        action="store_true",
        help="Skip label standardization"
    )
    parser.add_argument(
        "--no-autofill",
        action="store_true",
        help="Skip auto-fill from AI data"
    )
    parser.add_argument(
        "--no-flag",
        action="store_true",
        help="Skip flag generation"
    )
    
    # Filtering
    parser.add_argument(
        "--range",
        nargs=2,
        metavar=("START", "END"),
        help="Filter by item range (e.g., --range 4-1 5-2)"
    )
    
    # Config
    parser.add_argument(
        "-c", "--config",
        help="Path to config file"
    )
    
    # Output format
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Quiet output (errors only)"
    )
    parser.add_argument(
        "--save-intermediate",
        action="store_true",
        help="Save intermediate files"
    )
    
    return parser.parse_args()


def print_banner():
    """Print banner."""
    print("""
+-------------------------------------------+
|       QA Data Pipeline v0.2.0             |
|  Automated Validation for Regulatory Data |
+-------------------------------------------+
    """)


def print_result(result: PipelineResult, as_json: bool = False):
    """Print pipeline result."""
    if as_json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return
    
    print("\n" + "=" * 50)
    print("PIPELINE RESULT")
    print("=" * 50)
    
    status = "SUCCESS" if result.success else "FAILED"
    print(f"Status: {status}")
    print(f"Duration: {result.total_duration_ms:.2f}ms")
    print(f"Start: {result.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"End: {result.end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    print("\n--- Stages ---")
    for stage in result.stages:
        status_icon = "[OK]" if stage.success else "[FAIL]"
        print(f"  {status_icon} {stage.name}: {stage.output_rows} rows ({stage.duration_ms}ms)")
        if stage.error:
            print(f"      Error: {stage.error}")
    
    print("\n--- Stats ---")
    for key, value in result.final_stats.items():
        print(f"  {key}: {value}")
    
    print("\n--- Output Files ---")
    for path in result.output_files:
        print(f"  {path}")
    
    print("=" * 50)


def main():
    """Main entry point."""
    args = parse_args()
    
    # Setup logging
    if args.quiet:
        logger = log.init(level=log.ERROR)
    elif args.verbose:
        logger = log.init(level=log.DEBUG)
    else:
        logger = log.init(level=log.INFO)
    
    # Print banner unless quiet
    if not args.quiet and not args.json:
        print_banner()
    
    # Load config if specified
    if args.config:
        reload_config(args.config)
    
    # Validate input file
    input_path = Path(args.input_file)
    if not input_path.exists():
        logger.error(f"Input file not found: {args.input_file}")
        sys.exit(1)
    
    if not input_path.suffix.lower() in [".xlsx", ".xls"]:
        logger.error(f"Input must be Excel file (.xlsx or .xls)")
        sys.exit(1)
    
    # Build pipeline config
    pipeline_config = PipelineConfig(
        input_file=str(input_path),
        output_dir=args.output_dir,
        run_standardize=not args.no_standardize,
        run_autofill=not args.no_autofill,
        run_flag=not args.no_flag,
        item_range_start=args.range[0] if args.range else None,
        item_range_end=args.range[1] if args.range else None,
        save_intermediate=args.save_intermediate,
        export_format=args.format,
    )
    
    # Log config
    if args.verbose:
        logger.info("Pipeline configuration", 
                   input=str(input_path),
                   output_dir=args.output_dir,
                   range=args.range)
    
    # Create and run pipeline
    pipeline = Pipeline(pipeline_config)
    
    # Add progress callbacks
    if not args.quiet and not args.json:
        def on_start(name: str):
            print(f"  Running: {name}...", end="", flush=True)
        
        def on_end(stage):
            status = "done" if stage.success else "FAILED"
            print(f" {status} ({stage.output_rows} rows, {stage.duration_ms}ms)")
        
        pipeline.on_stage_start(on_start).on_stage_end(on_end)
        print("Starting pipeline...")
    
    # Run
    result = pipeline.run()
    
    # Output result
    print_result(result, as_json=args.json)
    
    # Exit code
    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
