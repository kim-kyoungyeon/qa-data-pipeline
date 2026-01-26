"""Tests for standardize module."""

import pytest
import pandas as pd
from src.standardize import (
    standardize_label,
    standardize_dataframe,
    filter_by_item_range,
    normalize_spacing,
)
from src.flag_generator import FlagType


class TestNormalizeSpacing:
    """Tests for normalize_spacing function."""
    
    def test_multiple_spaces(self):
        assert normalize_spacing("hello   world") == "hello world"
    
    def test_trim(self):
        assert normalize_spacing("  hello  ") == "hello"
    
    def test_normal(self):
        assert normalize_spacing("hello") == "hello"


class TestStandardizeLabel:
    """Tests for standardize_label function."""
    
    def test_ok_variations(self):
        result = standardize_label("이상 없음")
        assert result.standardized == "이상없음"
        assert result.flag_type == FlagType.OK
        assert result.changed is True
    
    def test_already_standard(self):
        result = standardize_label("이상없음")
        assert result.standardized == "이상없음"
        assert result.changed is False
    
    def test_ai_filled(self):
        result = standardize_label("AI 조항 복붙")
        assert result.standardized == "AI조항복붙"
        assert result.flag_type == FlagType.AI_FILLED
    
    def test_empty(self):
        result = standardize_label("")
        assert result.standardized == ""
        assert result.flag_type == FlagType.EMPTY_DE
    
    def test_numeric_change(self):
        result = standardize_label("12->16")
        assert result.flag_type == FlagType.NUM_FIX


class TestStandardizeDataframe:
    """Tests for standardize_dataframe function."""
    
    def test_standardize(self):
        df = pd.DataFrame({
            "도시명": ["서울", "부산"],
            "항목명": ["1-1", "1-2"],
            "이상유무 및 수정값": ["이상 없음", "확인 필요"],
            "조항내용": ["내용1", "내용2"]
        })
        
        result_df, stats = standardize_dataframe(df)
        
        assert stats["total"] == 2
        assert stats["changed"] >= 0
        assert "flag_distribution" in stats
    
    def test_inplace(self):
        df = pd.DataFrame({
            "도시명": ["서울"],
            "항목명": ["1-1"],
            "이상유무 및 수정값": ["이상 없음"],
            "조항내용": ["내용"]
        })
        
        result_df, _ = standardize_dataframe(df, inplace=True)
        # Should modify original
        assert result_df is df


class TestFilterByItemRange:
    """Tests for filter_by_item_range function."""
    
    def test_filter_range(self):
        df = pd.DataFrame({
            "도시명": ["서울", "서울", "서울", "서울"],
            "항목명": ["1-1 경사도", "4-1 대부료", "5-2 납부", "9-1 태양광"],
            "이상유무 및 수정값": ["", "", "", ""],
            "조항내용": ["", "", "", ""]
        })
        
        result = filter_by_item_range(df, "4-1", "5-2")
        
        assert len(result) == 2
        assert "4-1" in result.iloc[0]["항목명"]
        assert "5-2" in result.iloc[1]["항목명"]
    
    def test_empty_result(self):
        df = pd.DataFrame({
            "도시명": ["서울"],
            "항목명": ["1-1 경사도"],
            "이상유무 및 수정값": [""],
            "조항내용": [""]
        })
        
        result = filter_by_item_range(df, "9-1", "9-9")
        assert len(result) == 0
