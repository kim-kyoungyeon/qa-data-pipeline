"""Standardize D column labels.

This module normalizes D column values to standard labels,
handling variations in spacing, typos, and different expressions
for the same meaning.
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pandas as pd

from .config import config
from .flag_generator import FlagType, sanitize, PATTERNS


@dataclass
class StandardizeResult:
    """Result of label standardization."""
    original: str
    standardized: str
    flag_type: FlagType
    changed: bool
    
    def to_dict(self) -> Dict:
        return {
            "original": self.original,
            "standardized": self.standardized,
            "flag_type": self.flag_type.name,
            "changed": self.changed,
        }


# Standard label mappings (original variations -> canonical form)
LABEL_MAPPINGS: Dict[str, str] = {
    # OK variations
    "이상 없음": "이상없음",
    "해당 없음": "해당없음",
    "조례 없음": "조례없음",
    "법령 없음": "법령없음",
    "문제 없음": "문제없음",
    "정상": "이상없음",
    "확인완료": "이상없음",
    "ok": "이상없음",
    "OK": "이상없음",
    
    # AI filled variations
    "AI 조항 복붙": "AI조항복붙",
    "ai 조항 복붙": "AI조항복붙",
    "AI조항 복붙": "AI조항복붙",
    "자동복사": "AI조항복붙",
    "ai추출": "AI조항복붙",
    
    # Attachment variations
    "별표 참조": "별표확인",
    "표 참조": "별표확인",
    "첨부 확인": "별표확인",
    "첨부확인": "별표확인",
    "이미지 확인": "별표확인",
    
    # Change variations
    "수치 변경": "수치변경",
    "값 변경": "수치변경",
    "조항 변경": "조항변경",
    "조례 변경": "조항변경",
    
    # Ambiguous variations
    "확인 필요": "확인요",
    "검토 필요": "확인요",
    "재확인": "확인요",
    "확인필요": "확인요",
    "검토필요": "확인요",
}


def normalize_spacing(text: str) -> str:
    """Normalize spacing in text.
    
    Args:
        text: Input text
        
    Returns:
        Text with normalized spacing
    """
    # Remove multiple spaces
    text = re.sub(r'\s+', ' ', text)
    # Trim
    text = text.strip()
    return text


def standardize_label(label: str) -> StandardizeResult:
    """Standardize a single D column label.
    
    Args:
        label: Original D column value
        
    Returns:
        StandardizeResult with standardized label
    """
    original = sanitize(label)
    
    if not original:
        return StandardizeResult(
            original=original,
            standardized="",
            flag_type=FlagType.EMPTY_DE,
            changed=False,
        )
    
    # Step 1: Normalize spacing
    normalized = normalize_spacing(original)
    
    # Step 2: Check direct mappings
    normalized_lower = normalized.lower()
    for pattern, replacement in LABEL_MAPPINGS.items():
        if pattern.lower() == normalized_lower:
            return StandardizeResult(
                original=original,
                standardized=replacement,
                flag_type=_get_flag_type(replacement),
                changed=(original != replacement),
            )
    
    # Step 3: Check pattern-based detection
    for flag_type, patterns in PATTERNS.items():
        for pattern in patterns:
            if pattern.lower() in normalized_lower:
                standardized = _get_canonical_form(flag_type, normalized)
                return StandardizeResult(
                    original=original,
                    standardized=standardized,
                    flag_type=flag_type,
                    changed=(original != standardized),
                )
    
    # Step 4: Check for numeric change pattern (e.g., "12->16")
    if re.search(r'\d+\s*[-→>]+\s*\d+', normalized):
        return StandardizeResult(
            original=original,
            standardized=normalized,
            flag_type=FlagType.NUM_FIX,
            changed=False,
        )
    
    # Default: ETC
    return StandardizeResult(
        original=original,
        standardized=normalized,
        flag_type=FlagType.ETC,
        changed=(original != normalized),
    )


def _get_flag_type(label: str) -> FlagType:
    """Get FlagType from standardized label."""
    label_lower = label.lower()
    
    if "이상없음" in label_lower or "해당없음" in label_lower:
        return FlagType.OK
    elif "ai" in label_lower and "복붙" in label_lower:
        return FlagType.AI_FILLED
    elif "별표" in label_lower or "첨부" in label_lower:
        return FlagType.ATTACH
    elif "수치변경" in label_lower:
        return FlagType.NUM_FIX
    elif "조항변경" in label_lower:
        return FlagType.LAW_FIX
    elif "확인" in label_lower or "애매" in label_lower:
        return FlagType.AMBIG
    else:
        return FlagType.ETC


def _get_canonical_form(flag_type: FlagType, original: str) -> str:
    """Get canonical form for a flag type."""
    canonical_map = {
        FlagType.OK: "이상없음",
        FlagType.AI_FILLED: "AI조항복붙",
        FlagType.ATTACH: "별표확인",
        FlagType.NUM_FIX: original,  # Keep original for numeric changes
        FlagType.LAW_FIX: "조항변경",
        FlagType.AMBIG: "확인요",
        FlagType.ETC: original,
    }
    return canonical_map.get(flag_type, original)


def standardize_dataframe(
    df: pd.DataFrame,
    inplace: bool = False
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Standardize D column labels in entire dataframe.
    
    Args:
        df: Input dataframe
        inplace: If True, modify original dataframe
        
    Returns:
        Tuple of (standardized dataframe, statistics dict)
    """
    col_d = config.columns.status
    
    result_df = df if inplace else df.copy()
    
    stats = {
        "total": len(df),
        "changed": 0,
        "flag_distribution": {f.name: 0 for f in FlagType},
    }
    
    standardized_values = []
    
    for idx, row in result_df.iterrows():
        original = sanitize(row.get(col_d, ""))
        result = standardize_label(original)
        
        standardized_values.append(result.standardized)
        stats["flag_distribution"][result.flag_type.name] += 1
        
        if result.changed:
            stats["changed"] += 1
    
    result_df[col_d] = standardized_values
    
    # Sort flag distribution by count
    stats["flag_distribution"] = dict(
        sorted(stats["flag_distribution"].items(), key=lambda x: -x[1])
    )
    
    return result_df, stats


def get_label_variations(df: pd.DataFrame) -> Dict[str, List[str]]:
    """Get all variations of D column labels grouped by standard form.
    
    Args:
        df: Input dataframe
        
    Returns:
        Dictionary mapping standard label to list of variations found
    """
    col_d = config.columns.status
    
    variations: Dict[str, List[str]] = {}
    
    for _, row in df.iterrows():
        original = sanitize(row.get(col_d, ""))
        if not original:
            continue
        
        result = standardize_label(original)
        
        if result.standardized not in variations:
            variations[result.standardized] = []
        
        if original not in variations[result.standardized]:
            variations[result.standardized].append(original)
    
    return variations


def filter_by_item_range(
    df: pd.DataFrame,
    start: str = "1-1",
    end: str = "9-9"
) -> pd.DataFrame:
    """Filter dataframe by item ID range.
    
    Args:
        df: Input dataframe
        start: Start item ID (e.g., "4-1")
        end: End item ID (e.g., "5-2")
        
    Returns:
        Filtered dataframe
    """
    col_item = config.columns.item
    
    def parse_item_id(item_id: str) -> Tuple[int, int]:
        """Parse item ID to tuple of integers."""
        match = re.match(r"(\d+)-(\d+)", item_id)
        if match:
            return (int(match.group(1)), int(match.group(2)))
        return (0, 0)
    
    def in_range(item_text: str) -> bool:
        """Check if item is in range."""
        match = re.match(r"^\s*(\d+-\d+)", sanitize(item_text))
        if not match:
            return False
        
        item_id = match.group(1)
        item_tuple = parse_item_id(item_id)
        start_tuple = parse_item_id(start)
        end_tuple = parse_item_id(end)
        
        return start_tuple <= item_tuple <= end_tuple
    
    mask = df[col_item].apply(in_range)
    return df[mask].copy()
