"""Data merger for applying flagged results back to original."""

import pandas as pd
from typing import Tuple, Dict, Any, List
from .config import config
from .flag_generator import sanitize


def merge_flagged_to_original(
    original_df: pd.DataFrame,
    flagged_df: pd.DataFrame,
    d_col_in_flagged: str = "status_d",
    e_col_in_flagged: str = "content_e_preview"
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Merge flagged/edited data back to original dataframe.
    
    Args:
        original_df: Original dataframe
        flagged_df: Flagged dataframe with edits
        d_col_in_flagged: Column name for D in flagged df
        e_col_in_flagged: Column name for E in flagged df
    
    Returns:
        Tuple of (merged dataframe, stats dict)
    """
    col_d = config.columns.status
    col_e = config.columns.content
    
    result = original_df.copy()
    
    stats = {
        "total_flagged": len(flagged_df),
        "d_updated": 0,
        "e_updated": 0,
        "skipped": 0,
    }
    
    for _, row in flagged_df.iterrows():
        idx = int(row["row_index"])
        
        # Bounds check
        if idx not in result.index:
            stats["skipped"] += 1
            continue
        
        new_d = sanitize(row.get(d_col_in_flagged, ""))
        new_e = sanitize(row.get(e_col_in_flagged, ""))
        
        # Only update if new value is non-empty
        if new_d and col_d in result.columns:
            result.at[idx, col_d] = new_d
            stats["d_updated"] += 1
        
        if new_e and col_e in result.columns:
            result.at[idx, col_e] = new_e
            stats["e_updated"] += 1
    
    return result, stats


def find_overwritten_rows(
    original_df: pd.DataFrame,
    final_df: pd.DataFrame,
    min_orig_len: int = None
) -> pd.DataFrame:
    """
    Find rows where original content was overwritten with shorter content.
    
    Args:
        original_df: Original dataframe
        final_df: Final/processed dataframe
        min_orig_len: Minimum original length to consider
    
    Returns:
        DataFrame with overwritten rows
    """
    if min_orig_len is None:
        min_orig_len = config.validation.min_status_length
    
    col_d = config.columns.status
    col_e = config.columns.content
    col_city = config.columns.city
    col_item = config.columns.item
    
    def make_key(row):
        return f"{sanitize(row.get(col_city, ''))}|{sanitize(row.get(col_item, ''))}"
    
    original_df = original_df.copy()
    final_df = final_df.copy()
    
    original_df["_key"] = original_df.apply(make_key, axis=1)
    final_df["_key"] = final_df.apply(make_key, axis=1)
    
    orig_data = {
        row["_key"]: {
            "d": sanitize(row.get(col_d, "")),
            "e": sanitize(row.get(col_e, ""))
        }
        for _, row in original_df.iterrows()
    }
    
    final_data = {
        row["_key"]: {
            "d": sanitize(row.get(col_d, "")),
            "e": sanitize(row.get(col_e, ""))
        }
        for _, row in final_df.iterrows()
    }
    
    overwritten = []
    
    for key, orig in orig_data.items():
        final = final_data.get(key, {"d": "", "e": ""})
        
        # Original D was substantial and got shortened
        if (len(orig["d"]) >= min_orig_len and 
            orig["d"] != final["d"] and 
            len(final["d"]) < len(orig["d"])):
            
            parts = key.split("|", 1)
            city = parts[0] if len(parts) > 0 else ""
            item = parts[1] if len(parts) > 1 else ""
            
            overwritten.append({
                "city": city,
                "item": item,
                "original_d": orig["d"],
                "final_d": final["d"],
                "d_length_change": len(final["d"]) - len(orig["d"]),
                "original_e": orig["e"][:100],
                "final_e": final["e"][:100],
            })
    
    return pd.DataFrame(overwritten)


def compare_dataframes(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    key_cols: List[str] = None
) -> Dict[str, Any]:
    """
    Compare two dataframes and return differences.
    
    Args:
        df1: First dataframe (e.g., original)
        df2: Second dataframe (e.g., processed)
        key_cols: Columns to use as key for matching
        
    Returns:
        Dictionary with comparison stats
    """
    if key_cols is None:
        key_cols = [config.columns.city, config.columns.item]
    
    col_d = config.columns.status
    col_e = config.columns.content
    
    stats = {
        "df1_rows": len(df1),
        "df2_rows": len(df2),
        "d_changed": 0,
        "e_changed": 0,
        "d_added": 0,
        "e_added": 0,
    }
    
    # Create key-based lookup
    def make_key(row):
        return "|".join(sanitize(row.get(c, "")) for c in key_cols)
    
    df1_data = {make_key(row): row for _, row in df1.iterrows()}
    df2_data = {make_key(row): row for _, row in df2.iterrows()}
    
    for key, row2 in df2_data.items():
        row1 = df1_data.get(key)
        
        if row1 is None:
            continue
        
        d1 = sanitize(row1.get(col_d, ""))
        d2 = sanitize(row2.get(col_d, ""))
        e1 = sanitize(row1.get(col_e, ""))
        e2 = sanitize(row2.get(col_e, ""))
        
        if d1 != d2:
            if d1 == "" and d2 != "":
                stats["d_added"] += 1
            else:
                stats["d_changed"] += 1
        
        if e1 != e2:
            if e1 == "" and e2 != "":
                stats["e_added"] += 1
            else:
                stats["e_changed"] += 1
    
    return stats
