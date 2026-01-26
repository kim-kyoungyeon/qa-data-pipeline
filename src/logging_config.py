"""Logging configuration for QA Data Pipeline."""

import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Try to use structlog if available, otherwise fall back to standard logging
try:
    import structlog
    HAS_STRUCTLOG = True
except ImportError:
    HAS_STRUCTLOG = False


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    json_format: bool = False,
) -> logging.Logger:
    """
    Setup logging configuration.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional file path for log output
        json_format: Use JSON format for logs (useful for log aggregation)
    
    Returns:
        Configured logger instance
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Base format
    if json_format and HAS_STRUCTLOG:
        # Structlog JSON format
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        logger = structlog.get_logger("qa_pipeline")
    else:
        # Standard logging
        log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        date_format = "%Y-%m-%d %H:%M:%S"
        
        handlers = [logging.StreamHandler(sys.stdout)]
        
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
        
        logging.basicConfig(
            level=log_level,
            format=log_format,
            datefmt=date_format,
            handlers=handlers,
            force=True,
        )
        
        logger = logging.getLogger("qa_pipeline")
    
    return logger


def get_logger(name: str = "qa_pipeline") -> logging.Logger:
    """Get logger instance by name."""
    if HAS_STRUCTLOG:
        return structlog.get_logger(name)
    return logging.getLogger(name)


class LogContext:
    """Context manager for logging with timing."""
    
    def __init__(self, logger: logging.Logger, operation: str, **context):
        self.logger = logger
        self.operation = operation
        self.context = context
        self.start_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        self.logger.info(f"Starting: {self.operation}", extra=self.context)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).total_seconds()
        
        if exc_type:
            self.logger.error(
                f"Failed: {self.operation}",
                extra={**self.context, "duration_s": duration, "error": str(exc_val)}
            )
        else:
            self.logger.info(
                f"Completed: {self.operation}",
                extra={**self.context, "duration_s": duration}
            )
        
        return False  # Don't suppress exceptions
