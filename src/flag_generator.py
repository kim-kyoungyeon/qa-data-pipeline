"""Flag generator for QA validation.

This module provides comprehensive flag generation for QA validation,
detecting various types of data quality issues in regulatory data.

Flag Types:
    - EMPTY_DE: Both D and E columns are empty (completely unreviewed)
    - WEAK_E: E column content is too short (insufficient evidence)
    - AMBIG: Ambiguous cases requiring manual review
    - ATTACH: Attachment/appendix reference requiring manual check
    - LAW_FIX: Regulation text changes needed
    - NUM_FIX: Numeric value changes needed
    - AI_FILLED: Content was auto-filled from AI extraction
    - OK: Verified as correct
    - ETC: Other cases
"""

import re
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
import pandas as pd

from .config import config


class FlagType(Enum):
    """Enumeration of all possible flag types."""
    EMPTY_DE = "EMPTY_DE(완전미검수)"
    WEAK_E = "WEAK_E(근거부족)"
    AMBIG = "AMBIG(애매케이스)"
    ATTACH = "ATTACH(별표/첨부)"
    LAW_FIX = "LAW_FIX(조항변경)"
    NUM_FIX = "NUM_FIX(수치변경)"
    AI_FILLED = "AI_FILLED(AI복붙)"
    OK = "OK(이상없음)"
    ETC = "ETC(기타)"
    
    @property
    def needs_review(self) -> bool:
        """Check if this flag type requires manual review."""
        return self in (
            FlagType.EMPTY_DE,
            FlagType.WEAK_E,
            FlagType.AMBIG,
            FlagType.ATTACH,
        )
    
    @property
    def priority(self) -> int:
        """Get priority for sorting (lower = higher priority)."""
        priority_map = {
            FlagType.EMPTY_DE: 1,
            FlagType.WEAK_E: 2,
            FlagType.ATTACH: 3,
            FlagType.AMBIG: 4,
            FlagType.LAW_FIX: 5,
            FlagType.NUM_FIX: 6,
            FlagType.AI_FILLED: 7,
            FlagType.OK: 8,
            FlagType.ETC: 9,
        }
        return priority_map.get(self, 99)


@dataclass
class FlagResult:
    """Result of flag generation for a single row."""
    row_index: int
    city: str
    item: str
    item_id: Optional[str]
    status_d: str
    content_e: str
    flags: List[FlagType] = field(default_factory=list)
    confidence: float = 1.0
    
    @property
    def content_e_preview(self) -> str:
        """Get truncated preview of E column."""
        return self.content_e[:160].replace("\n", " ")
    
    @property
    def flag_names(self) -> List[str]:
        """Get list of flag value strings."""
        return [f.value for f in self.flags]
    
    @property
    def flag_string(self) -> str:
        """Get comma-separated flag string."""
        return ", ".join(self.flag_names)
    
    @property
    def needs_review(self) -> bool:
        """Check if this result needs manual review."""
        return any(f.needs_review for f in self.flags) or self.confidence < 0.8
    
    @property
    def primary_flag(self) -> Optional[FlagType]:
        """Get the highest priority flag."""
        if not self.flags:
            return None
        return min(self.flags, key=lambda f: f.priority)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for DataFrame."""
        return {
            "row_index": self.row_index,
            "city": self.city,
            "item": self.item,
            "item_id": self.item_id,
            "status_d": self.status_d,
            "content_e_preview": self.content_e_preview,
            "content_e_length": len(self.content_e),
            "flags": self.flag_string,
            "flag_count": len(self.flags),
            "primary_flag": self.primary_flag.value if self.primary_flag else "",
            "confidence": self.confidence,
            "needs_review": self.needs_review,
        }


# Keyword patterns for flag detection
PATTERNS: Dict[FlagType, List[str]] = {
    FlagType.OK: [
        "이상없음", "이상 없음", "해당없음", "해당 없음",
        "조례없음", "조례 없음", "법령없음", "법령 없음",
        "문제없음", "정상", "확인완료", "검토완료"
    ],
    FlagType.AMBIG: [
        "애매", "불충분", "여러개", "값이 없", "못찾",
        "불명확", "확인요", "검토필요", "재확인", "확인 필요"
    ],
    FlagType.ATTACH: [
        "별표", "이미지", "첨부", "파일", "그림", "표 참조", "붙임", "별지"
    ],
    FlagType.LAW_FIX: [
        "조항변경", "조례변경", "근거변경", "법령변경", "법률개정"
    ],
    FlagType.NUM_FIX: [
        "수치변경", "값변경", "금액변경", "거리변경",
        "단위변경", "비율변경"
    ],
    FlagType.AI_FILLED: [
        "ai조항복붙", "ai 조항 복붙", "자동복사", "ai추출", "ai 복붙"
    ],
}

# Regex patterns for numeric changes (e.g., "12->16", "100 → 200")
NUMERIC_CHANGE_PATTERN = re.compile(r'\d+\s*[-→>]+\s*\d+')


def sanitize(value: Any) -> str:
    """Clean and convert value to string.
    
    Args:
        value: Any input value
        
    Returns:
        Cleaned string with whitespace trimmed
    """
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def normalize_text(text: str) -> str:
    """Normalize text for pattern matching.
    
    Args:
        text: Input text
        
    Returns:
        Lowercase text with extra whitespace removed
    """
    text = sanitize(text).lower()
    text = re.sub(r'\s+', ' ', text)
    return text


def extract_item_id(item_text: str) -> Optional[str]:
    """Extract item ID like '4-9' from '4-9 자동이체 감면금액'.
    
    Args:
        item_text: Item name string
        
    Returns:
        Item ID or None
    """
    m = re.match(r"^\s*(\d+\-\d+)", sanitize(item_text))
    return m.group(1) if m else None


def check_pattern(text: str, patterns: List[str]) -> bool:
    """Check if any pattern exists in text.
    
    Args:
        text: Text to search in (should be normalized)
        patterns: List of patterns to search for
        
    Returns:
        True if any pattern found
    """
    text_lower = text.lower()
    return any(p.lower() in text_lower for p in patterns)


def is_ok_status(status_text: str) -> bool:
    """Check if status indicates 'OK/No issues'.
    
    Args:
        status_text: D column value
        
    Returns:
        True if status is OK
    """
    return check_pattern(status_text, PATTERNS[FlagType.OK])


def detect_flags(status: str, content: str) -> Tuple[List[FlagType], float]:
    """Detect all applicable flags for given D and E values.
    
    Args:
        status: D column (이상유무 및 수정값)
        content: E column (조항내용)
        
    Returns:
        Tuple of (list of flags, confidence score 0.0-1.0)
    """
    d = sanitize(status)
    e = sanitize(content)
    combined = f"{d} {e}"
    
    flags: List[FlagType] = []
    confidence = 1.0
    
    # Get min content length from config
    min_content_len = config.validation.min_content_length
    
    # Priority 1: Empty check (highest priority)
    if d == "" and e == "":
        return [FlagType.EMPTY_DE], 1.0
    
    # Priority 2: Weak content
    if d == "" and len(e) < min_content_len:
        return [FlagType.WEAK_E], 0.9
    
    # Priority 3: OK status - return early
    if check_pattern(d, PATTERNS[FlagType.OK]):
        return [FlagType.OK], 1.0
    
    # Priority 4: AI filled
    if check_pattern(combined, PATTERNS[FlagType.AI_FILLED]):
        flags.append(FlagType.AI_FILLED)
        confidence = min(confidence, 0.85)
    
    # Priority 5: Attachment (needs manual review)
    if check_pattern(combined, PATTERNS[FlagType.ATTACH]):
        flags.append(FlagType.ATTACH)
        confidence = min(confidence, 0.7)
    
    # Priority 6: Law/regulation changes
    if check_pattern(combined, PATTERNS[FlagType.LAW_FIX]):
        flags.append(FlagType.LAW_FIX)
        confidence = min(confidence, 0.8)
    
    # Priority 7: Numeric changes (keyword or regex)
    if check_pattern(combined, PATTERNS[FlagType.NUM_FIX]) or NUMERIC_CHANGE_PATTERN.search(d):
        flags.append(FlagType.NUM_FIX)
        confidence = min(confidence, 0.8)
    
    # Priority 8: Ambiguous cases
    if check_pattern(combined, PATTERNS[FlagType.AMBIG]):
        flags.append(FlagType.AMBIG)
        confidence = min(confidence, 0.6)
    
    # If no specific flags but has content
    if not flags:
        if d and len(d) > 5:
            flags.append(FlagType.ETC)
            confidence = 0.5
        elif e and len(e) >= min_content_len:
            # Has sufficient content but no D value - likely OK but uncertain
            flags.append(FlagType.ETC)
            confidence = 0.7
    
    return flags, confidence


def generate_flags(status: str, content: str) -> List[str]:
    """Generate validation flags (simplified interface).
    
    Args:
        status: D column (이상유무 및 수정값)
        content: E column (조항내용)
        
    Returns:
        List of flag strings (excludes OK)
    """
    flags, _ = detect_flags(status, content)
    # Filter out OK for backward compatibility
    return [f.value for f in flags if f != FlagType.OK]


def canonicalize_label(status: str, content: str = "") -> str:
    """Canonicalize D column to standard label.
    
    Args:
        status: D column value
        content: E column value (optional)
        
    Returns:
        Standard label string
    """
    flags, _ = detect_flags(status, content)
    if flags:
        return flags[0].name
    return FlagType.ETC.name


def process_row(idx: int, row: pd.Series) -> Optional[FlagResult]:
    """Process a single row and generate flag result.
    
    Args:
        idx: Row index
        row: DataFrame row
        
    Returns:
        FlagResult if flags detected (excluding OK), None otherwise
    """
    col_d = config.columns.status
    col_e = config.columns.content
    col_city = config.columns.city
    col_item = config.columns.item
    
    d = sanitize(row.get(col_d, ""))
    e = sanitize(row.get(col_e, ""))
    item = sanitize(row.get(col_item, ""))
    
    flags, confidence = detect_flags(d, e)
    
    # Skip OK rows - they don't need attention
    if flags == [FlagType.OK]:
        return None
    
    return FlagResult(
        row_index=idx,
        city=sanitize(row.get(col_city, "")),
        item=item,
        item_id=extract_item_id(item),
        status_d=d,
        content_e=e,
        flags=flags,
        confidence=confidence,
    )


def process_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Process entire dataframe and generate flags.
    
    Args:
        df: Input dataframe with D and E columns
        
    Returns:
        DataFrame with flagged rows only
    """
    flagged_rows = []
    
    for idx, row in df.iterrows():
        result = process_row(idx, row)
        if result:
            flagged_rows.append(result.to_dict())
    
    return pd.DataFrame(flagged_rows)


def get_flag_statistics(df: pd.DataFrame) -> Dict[str, Any]:
    """Get comprehensive statistics of flags.
    
    Args:
        df: Input dataframe (original, not flagged)
        
    Returns:
        Dictionary with flag statistics
    """
    col_d = config.columns.status
    col_e = config.columns.content
    
    stats = {
        "total_rows": len(df),
        "flag_counts": {f.name: 0 for f in FlagType},
        "needs_review": 0,
        "confidence_avg": 0.0,
        "confidence_low": 0,  # confidence < 0.8
    }
    
    confidence_sum = 0.0
    processed = 0
    
    for _, row in df.iterrows():
        d = sanitize(row.get(col_d, ""))
        e = sanitize(row.get(col_e, ""))
        flags, confidence = detect_flags(d, e)
        
        for flag in flags:
            stats["flag_counts"][flag.name] += 1
        
        if any(f.needs_review for f in flags):
            stats["needs_review"] += 1
        
        if confidence < 0.8:
            stats["confidence_low"] += 1
        
        confidence_sum += confidence
        processed += 1
    
    if processed > 0:
        stats["confidence_avg"] = round(confidence_sum / processed, 3)
    
    # Sort flag counts by value descending
    stats["flag_counts"] = dict(
        sorted(stats["flag_counts"].items(), key=lambda x: -x[1])
    )
    
    return stats


def filter_by_flag(df: pd.DataFrame, flag_type: FlagType) -> pd.DataFrame:
    """Filter dataframe to rows with specific flag.
    
    Args:
        df: Flagged dataframe from process_dataframe()
        flag_type: Flag type to filter by
        
    Returns:
        Filtered dataframe
    """
    if "flags" not in df.columns:
        return pd.DataFrame()
    
    # Use regex=False to avoid interpreting parentheses as groups
    mask = df["flags"].str.contains(flag_type.value, case=False, na=False, regex=False)
    return df[mask].copy()


def get_review_queue(df: pd.DataFrame) -> pd.DataFrame:
    """Get rows that need manual review, sorted by priority.
    
    Args:
        df: Flagged dataframe from process_dataframe()
        
    Returns:
        Sorted dataframe of items needing review
    """
    if "needs_review" not in df.columns:
        return pd.DataFrame()
    
    review_df = df[df["needs_review"] == True].copy()
    
    # Sort by flag count (desc), then confidence (asc)
    if len(review_df) > 0:
        review_df = review_df.sort_values(
            ["flag_count", "confidence"],
            ascending=[False, True]
        )
    
    return review_df
