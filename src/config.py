"""Configuration loader for QA Data Pipeline.

This module provides typed access to configuration values loaded from YAML.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import yaml


@dataclass
class ColumnConfig:
    """Column name mappings."""
    city: str = "도시명"
    item: str = "항목명"
    grade: str = "등급"
    status: str = "이상유무 및 수정값"
    content: str = "조항내용"
    grade_data: str = "등급판단 데이터"
    ai_law: str = "법령명"
    ai_content: str = "조항내용.1"
    reason: str = "이유"
    is_metro: str = "광역데이터여부"
    json_data: str = "json"


@dataclass
class ValidationConfig:
    """Validation rules."""
    min_content_length: int = 40
    min_ai_content_length: int = 30
    min_status_length: int = 10


@dataclass
class PatternConfig:
    """Pattern configuration for standardization."""
    keywords: List[str] = field(default_factory=list)
    description: str = ""
    priority: int = 99


@dataclass
class FlagConfig:
    """Flag type configuration."""
    code: str = ""
    description: str = ""
    severity: str = "info"  # critical, high, medium, low, warning, info


@dataclass
class PathConfig:
    """File path configuration."""
    input_dir: str = "data/input"
    output_dir: str = "data/output"
    sample_dir: str = "sample_data"
    log_dir: str = "logs"


@dataclass 
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "json"
    file: str = "logs/pipeline.log"
    max_size_mb: int = 10
    backup_count: int = 5


@dataclass
class MetricsConfig:
    """Metrics configuration."""
    enabled: bool = True
    port: int = 8000
    endpoint: str = "/metrics"


class Config:
    """Main configuration class with typed access."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Load configuration from YAML file.
        
        Args:
            config_path: Path to config file. If None, uses default.
        """
        self._raw: Dict[str, Any] = {}
        self._load(config_path)
        
        # Parsed configs
        self.columns = ColumnConfig()
        self.validation = ValidationConfig()
        self.paths = PathConfig()
        self.logging = LoggingConfig()
        self.metrics = MetricsConfig()
        self.patterns: Dict[str, PatternConfig] = {}
        self.flags: Dict[str, FlagConfig] = {}
        
        self._parse()
    
    def _load(self, config_path: Optional[str] = None):
        """Load raw YAML config."""
        if config_path is None:
            # Find config relative to this file or in common locations
            possible_paths = [
                Path(__file__).parent.parent / "config" / "config.yaml",
                Path("config/config.yaml"),
                Path("config.yaml"),
            ]
            for path in possible_paths:
                if path.exists():
                    config_path = str(path)
                    break
        
        if config_path and Path(config_path).exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                self._raw = yaml.safe_load(f) or {}
    
    def _parse(self):
        """Parse raw config into typed objects."""
        # Columns
        if "columns" in self._raw:
            cols = self._raw["columns"]
            self.columns = ColumnConfig(
                city=cols.get("city", self.columns.city),
                item=cols.get("item", self.columns.item),
                grade=cols.get("grade", self.columns.grade),
                status=cols.get("status", self.columns.status),
                content=cols.get("content", self.columns.content),
                grade_data=cols.get("grade_data", self.columns.grade_data),
                ai_law=cols.get("ai_law", self.columns.ai_law),
                ai_content=cols.get("ai_content", self.columns.ai_content),
                reason=cols.get("reason", self.columns.reason),
                is_metro=cols.get("is_metro", self.columns.is_metro),
                json_data=cols.get("json_data", self.columns.json_data),
            )
        
        # Validation
        if "validation" in self._raw:
            val = self._raw["validation"]
            self.validation = ValidationConfig(
                min_content_length=val.get("min_content_length", 40),
                min_ai_content_length=val.get("min_ai_content_length", 30),
                min_status_length=val.get("min_status_length", 10),
            )
        
        # Paths
        if "paths" in self._raw:
            p = self._raw["paths"]
            self.paths = PathConfig(
                input_dir=p.get("input_dir", "data/input"),
                output_dir=p.get("output_dir", "data/output"),
                sample_dir=p.get("sample_dir", "sample_data"),
                log_dir=p.get("log_dir", "logs"),
            )
        
        # Logging
        if "logging" in self._raw:
            log = self._raw["logging"]
            self.logging = LoggingConfig(
                level=log.get("level", "INFO"),
                format=log.get("format", "json"),
                file=log.get("file", "logs/pipeline.log"),
                max_size_mb=log.get("max_size_mb", 10),
                backup_count=log.get("backup_count", 5),
            )
        
        # Metrics
        if "metrics" in self._raw:
            met = self._raw["metrics"]
            self.metrics = MetricsConfig(
                enabled=met.get("enabled", True),
                port=met.get("port", 8000),
                endpoint=met.get("endpoint", "/metrics"),
            )
        
        # Standardization patterns
        if "standardization" in self._raw and "patterns" in self._raw["standardization"]:
            for name, pat in self._raw["standardization"]["patterns"].items():
                self.patterns[name] = PatternConfig(
                    keywords=pat.get("keywords", []),
                    description=pat.get("description", ""),
                    priority=pat.get("priority", 99),
                )
        
        # Flags
        if "flags" in self._raw:
            for name, flag in self._raw["flags"].items():
                self.flags[name] = FlagConfig(
                    code=flag.get("code", name),
                    description=flag.get("description", ""),
                    severity=flag.get("severity", "info"),
                )
    
    # Convenience properties for backward compatibility
    @property
    def min_content_length(self) -> int:
        return self.validation.min_content_length
    
    @property
    def min_ai_content_length(self) -> int:
        return self.validation.min_ai_content_length
    
    @property
    def ok_patterns(self) -> List[str]:
        """Get OK status patterns."""
        if "OK" in self.patterns:
            return self.patterns["OK"].keywords
        return ["이상없음", "이상 없음", "해당없음", "정상"]
    
    def get_pattern_keywords(self, pattern_name: str) -> List[str]:
        """Get keywords for a pattern."""
        if pattern_name in self.patterns:
            return self.patterns[pattern_name].keywords
        return []
    
    def get_flag_severity(self, flag_name: str) -> str:
        """Get severity for a flag."""
        if flag_name in self.flags:
            return self.flags[flag_name].severity
        return "info"


# Global config instance
config = Config()


def reload_config(config_path: Optional[str] = None) -> Config:
    """Reload configuration from file.
    
    Args:
        config_path: Optional path to config file
        
    Returns:
        New Config instance
    """
    global config
    config = Config(config_path)
    return config
