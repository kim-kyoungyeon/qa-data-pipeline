"""Structured logging for QA Data Pipeline.

This module provides structured logging using Python's logging module
with JSON formatting support for production environments.
"""

import logging
import sys
import json
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path
from functools import wraps
import time


# Log levels
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add source location
        log_data["source"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


class PrettyFormatter(logging.Formatter):
    """Pretty formatter for console output."""
    
    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        color = self.COLORS.get(record.levelname, "")
        reset = self.RESET
        
        # Build base message
        timestamp = datetime.now().strftime("%H:%M:%S")
        level = record.levelname[:4]
        message = record.getMessage()
        
        formatted = f"{color}[{timestamp}] {level}{reset} {message}"
        
        # Add extra data if present
        if hasattr(record, "extra_data") and record.extra_data:
            extra_str = " ".join(f"{k}={v}" for k, v in record.extra_data.items())
            formatted += f" {color}({extra_str}){reset}"
        
        return formatted


class Logger:
    """Structured logger wrapper."""
    
    def __init__(self, name: str = "qa-pipeline"):
        """Initialize logger.
        
        Args:
            name: Logger name
        """
        self.name = name
        self._logger = logging.getLogger(name)
        self._context: Dict[str, Any] = {}
    
    def bind(self, **kwargs) -> "Logger":
        """Bind context data to logger.
        
        Args:
            **kwargs: Context key-value pairs
            
        Returns:
            New logger with bound context
        """
        new_logger = Logger(self.name)
        new_logger._logger = self._logger
        new_logger._context = {**self._context, **kwargs}
        return new_logger
    
    def _log(self, level: int, message: str, **kwargs):
        """Internal log method.
        
        Args:
            level: Log level
            message: Log message
            **kwargs: Additional data to log
        """
        extra_data = {**self._context, **kwargs}
        
        record = self._logger.makeRecord(
            self._logger.name,
            level,
            "(unknown)",
            0,
            message,
            (),
            None,
        )
        record.extra_data = extra_data
        
        self._logger.handle(record)
    
    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._log(DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs):
        """Log info message."""
        self._log(INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self._log(WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message."""
        self._log(ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self._log(CRITICAL, message, **kwargs)
    
    def exception(self, message: str, **kwargs):
        """Log exception with traceback."""
        self._logger.exception(message, extra={"extra_data": {**self._context, **kwargs}})


def setup_logging(
    level: int = INFO,
    json_format: bool = False,
    log_file: Optional[str] = None,
) -> Logger:
    """Setup logging configuration.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: Use JSON formatting for console output
        log_file: Optional file path for logging
        
    Returns:
        Configured Logger instance
    """
    logger = logging.getLogger("qa-pipeline")
    logger.setLevel(level)
    logger.handlers = []  # Clear existing handlers
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    if json_format:
        console_handler.setFormatter(JsonFormatter())
    else:
        console_handler.setFormatter(PrettyFormatter())
    
    logger.addHandler(console_handler)
    
    # File handler (always JSON format)
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(JsonFormatter())
        logger.addHandler(file_handler)
    
    return Logger("qa-pipeline")


def get_logger(name: str = "qa-pipeline") -> Logger:
    """Get logger instance.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    return Logger(name)


def log_duration(logger: Optional[Logger] = None):
    """Decorator to log function duration.
    
    Args:
        logger: Logger instance (uses default if None)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            log = logger or get_logger()
            start = time.time()
            
            log.debug(f"Starting {func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start) * 1000
                log.info(
                    f"Completed {func.__name__}",
                    duration_ms=round(duration_ms, 2)
                )
                return result
            except Exception as e:
                duration_ms = (time.time() - start) * 1000
                log.error(
                    f"Failed {func.__name__}",
                    duration_ms=round(duration_ms, 2),
                    error=str(e)
                )
                raise
        
        return wrapper
    return decorator


# Default logger instance
_default_logger: Optional[Logger] = None


def init(
    level: int = INFO,
    json_format: bool = False,
    log_file: Optional[str] = None
) -> Logger:
    """Initialize default logger.
    
    Args:
        level: Log level
        json_format: Use JSON format
        log_file: Optional log file path
        
    Returns:
        Logger instance
    """
    global _default_logger
    _default_logger = setup_logging(level, json_format, log_file)
    return _default_logger


def debug(message: str, **kwargs):
    """Log debug to default logger."""
    (_default_logger or get_logger()).debug(message, **kwargs)


def info(message: str, **kwargs):
    """Log info to default logger."""
    (_default_logger or get_logger()).info(message, **kwargs)


def warning(message: str, **kwargs):
    """Log warning to default logger."""
    (_default_logger or get_logger()).warning(message, **kwargs)


def error(message: str, **kwargs):
    """Log error to default logger."""
    (_default_logger or get_logger()).error(message, **kwargs)
