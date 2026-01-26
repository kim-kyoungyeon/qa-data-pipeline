"""Auto-fill E column from AI-extracted H column."""

import pandas as pd
from typing import Tuple, Dict, Any
from .config import config
from .flag_generator import sanitize


def autofill_from_ai(
    df: pd.DataFrame,
    min_e_len: int = None,
    min_h_len: int = None
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Auto-fill empty E column with AI-extracted H column data.
    
    Logic:
    - If E is empty/short AND H has sufficient content
    - Copy H to E (with G as prefix if available)
    - Mark D as "AI조항복붙" if D is empty
    
    Args:
        df: Input dataframe
        min_e_len: Minimum E length to consider as "needs filling"
        min_h_len: Minimum H length to consider as valid source
    
    Returns:
        Tuple of (modified dataframe, stats dict)
    """
    # Use config values if not specified
    if min_e_len is None:
        min_e_len = config.validation.min_content_length // 2  # Half of min
    if min_h_len is None:
        min_h_len = config.validation.min_ai_content_length
    
    col_d = config.columns.status
    col_e = config.columns.content
    col_h = config.columns.ai_content
    
    # Optional columns
    col_g = config.columns.ai_law
    
    df = df.copy()
    
    stats = {
        "total_rows": len(df),
        "filled": 0,
        "skipped_e_sufficient": 0,
        "skipped_h_insufficient": 0,
        "d_marked": 0,
        "with_law_prefix": 0,
    }
    
    # Check if columns exist
    has_g = col_g in df.columns
    has_h = col_h in df.columns
    
    if not has_h:
        stats["error"] = f"AI content column '{col_h}' not found"
        return df, stats
    
    for idx in df.index:
        d = sanitize(df.at[idx, col_d]) if col_d in df.columns else ""
        e = sanitize(df.at[idx, col_e]) if col_e in df.columns else ""
        g = sanitize(df.at[idx, col_g]) if has_g else ""
        h = sanitize(df.at[idx, col_h])
        
        # Skip if E already has sufficient content
        if len(e) >= min_e_len:
            stats["skipped_e_sufficient"] += 1
            continue
        
        # Skip if H doesn't have enough content
        if len(h) < min_h_len:
            stats["skipped_h_insufficient"] += 1
            continue
        
        # Build new E value
        if g and len(g) > 2:
            e_new = f"[{g}]\n{h}"
            stats["with_law_prefix"] += 1
        else:
            e_new = h
        
        df.at[idx, col_e] = e_new
        stats["filled"] += 1
        
        # Mark D if empty
        if d == "" and col_d in df.columns:
            df.at[idx, col_d] = "AI조항복붙"
            stats["d_marked"] += 1
    
    # Calculate fill rate
    stats["fill_rate"] = round(
        stats["filled"] / stats["total_rows"] * 100, 2
    ) if stats["total_rows"] > 0 else 0
    
    return df, stats


def check_autofill_candidates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Find rows that would be auto-filled (dry run).
    
    Args:
        df: Input dataframe
        
    Returns:
        DataFrame with candidate rows
    """
    min_e_len = config.validation.min_content_length // 2
    min_h_len = config.validation.min_ai_content_length
    
    col_e = config.columns.content
    col_h = config.columns.ai_content
    
    candidates = []
    
    for idx, row in df.iterrows():
        e = sanitize(row.get(col_e, ""))
        h = sanitize(row.get(col_h, ""))
        
        if len(e) < min_e_len and len(h) >= min_h_len:
            candidates.append({
                "row_index": idx,
                "e_length": len(e),
                "h_length": len(h),
                "e_preview": e[:50],
                "h_preview": h[:100],
            })
    
    return pd.DataFrame(candidates)
