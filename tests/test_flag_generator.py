"""Tests for flag generator module."""

import pytest
import pandas as pd
from src.flag_generator import (
    FlagType,
    FlagResult,
    sanitize,
    is_ok_status,
    detect_flags,
    generate_flags,
    process_dataframe,
    get_flag_statistics,
    filter_by_flag,
    extract_item_id,
)


class TestSanitize:
    """Tests for sanitize function."""
    
    def test_none_value(self):
        assert sanitize(None) == ""
    
    def test_nan_value(self):
        assert sanitize(float('nan')) == ""
    
    def test_string_with_whitespace(self):
        assert sanitize("  hello  ") == "hello"
    
    def test_number(self):
        assert sanitize(123) == "123"
    
    def test_empty_string(self):
        assert sanitize("") == ""


class TestExtractItemId:
    """Tests for extract_item_id function."""
    
    def test_normal_format(self):
        assert extract_item_id("4-9 자동이체 감면금액") == "4-9"
    
    def test_with_spaces(self):
        assert extract_item_id("  1-10 주차장설치기준") == "1-10"
    
    def test_no_match(self):
        assert extract_item_id("invalid") is None
    
    def test_empty(self):
        assert extract_item_id("") is None


class TestIsOkStatus:
    """Tests for is_ok_status function."""
    
    def test_ok_patterns(self):
        assert is_ok_status("이상없음") is True
        assert is_ok_status("이상 없음") is True
        assert is_ok_status("해당 없음") is True
        assert is_ok_status("조례없음") is True
        assert is_ok_status("정상") is True
    
    def test_not_ok(self):
        assert is_ok_status("확인요") is False
        assert is_ok_status("수치변경") is False
        assert is_ok_status("") is False
        assert is_ok_status("별표 확인") is False


class TestFlagType:
    """Tests for FlagType enum."""
    
    def test_needs_review(self):
        assert FlagType.EMPTY_DE.needs_review is True
        assert FlagType.WEAK_E.needs_review is True
        assert FlagType.AMBIG.needs_review is True
        assert FlagType.ATTACH.needs_review is True
        assert FlagType.OK.needs_review is False
        assert FlagType.NUM_FIX.needs_review is False
    
    def test_priority(self):
        assert FlagType.EMPTY_DE.priority < FlagType.OK.priority
        assert FlagType.WEAK_E.priority < FlagType.ETC.priority


class TestDetectFlags:
    """Tests for detect_flags function."""
    
    def test_empty_de(self):
        flags, confidence = detect_flags("", "")
        assert FlagType.EMPTY_DE in flags
        assert confidence == 1.0
    
    def test_weak_e(self):
        flags, confidence = detect_flags("", "짧은내용")
        assert FlagType.WEAK_E in flags
        assert confidence == 0.9
    
    def test_ok_status(self):
        flags, confidence = detect_flags("이상없음", "조례 제10조에 따라...")
        assert FlagType.OK in flags
        assert confidence == 1.0
    
    def test_ai_filled(self):
        flags, confidence = detect_flags("AI조항복붙", "조례 내용...")
        assert FlagType.AI_FILLED in flags
        assert confidence < 1.0
    
    def test_attachment(self):
        flags, confidence = detect_flags("별표 확인 필요", "")
        assert FlagType.ATTACH in flags
        assert confidence <= 0.7
    
    def test_numeric_change(self):
        flags, confidence = detect_flags("12->16", "높이제한 변경")
        assert FlagType.NUM_FIX in flags
    
    def test_law_fix(self):
        flags, confidence = detect_flags("조항변경", "내용...")
        assert FlagType.LAW_FIX in flags
    
    def test_ambiguous(self):
        flags, confidence = detect_flags("확인요", "")
        assert FlagType.AMBIG in flags
        assert confidence <= 0.6


class TestGenerateFlags:
    """Tests for generate_flags function."""
    
    def test_empty_returns_flag(self):
        flags = generate_flags("", "")
        assert "EMPTY_DE(완전미검수)" in flags
    
    def test_ok_returns_empty(self):
        flags = generate_flags("이상없음", "조례 내용...")
        assert flags == []
    
    def test_multiple_flags(self):
        flags = generate_flags("별표 확인요", "내용 애매함")
        assert len(flags) > 0


class TestFlagResult:
    """Tests for FlagResult dataclass."""
    
    def test_to_dict(self):
        result = FlagResult(
            row_index=0,
            city="서울",
            item="1-1 경사도",
            item_id="1-1",
            status_d="확인요",
            content_e="짧은내용",
            flags=[FlagType.AMBIG],
            confidence=0.6
        )
        d = result.to_dict()
        
        assert d["row_index"] == 0
        assert d["city"] == "서울"
        assert d["needs_review"] is True
    
    def test_primary_flag(self):
        result = FlagResult(
            row_index=0, city="", item="", item_id=None,
            status_d="", content_e="",
            flags=[FlagType.AMBIG, FlagType.ATTACH],
            confidence=0.5
        )
        # ATTACH has higher priority (lower number) than AMBIG
        assert result.primary_flag == FlagType.ATTACH


class TestProcessDataframe:
    """Tests for process_dataframe function."""
    
    def test_empty_df(self):
        df = pd.DataFrame({
            "도시명": [],
            "항목명": [],
            "이상유무 및 수정값": [],
            "조항내용": []
        })
        result = process_dataframe(df)
        assert len(result) == 0
    
    def test_with_flags(self):
        df = pd.DataFrame({
            "도시명": ["서울특별시", "부산광역시"],
            "항목명": ["1-1 경사도", "1-2 높이제한"],
            "이상유무 및 수정값": ["", "이상없음"],
            "조항내용": ["", "조례 제5조"]
        })
        result = process_dataframe(df)
        # First row should be flagged (empty)
        assert len(result) == 1
        assert result.iloc[0]["city"] == "서울특별시"
    
    def test_ok_rows_excluded(self):
        df = pd.DataFrame({
            "도시명": ["서울"],
            "항목명": ["1-1"],
            "이상유무 및 수정값": ["이상없음"],
            "조항내용": ["조례 제10조에 따른 충분한 내용입니다"]
        })
        result = process_dataframe(df)
        assert len(result) == 0


class TestGetFlagStatistics:
    """Tests for get_flag_statistics function."""
    
    def test_statistics(self):
        df = pd.DataFrame({
            "도시명": ["서울", "부산", "인천"],
            "항목명": ["1-1", "1-2", "1-3"],
            "이상유무 및 수정값": ["", "이상없음", "확인요"],
            "조항내용": ["", "조례 내용", ""]
        })
        stats = get_flag_statistics(df)
        
        assert "total_rows" in stats
        assert stats["total_rows"] == 3
        assert "flag_counts" in stats


class TestFilterByFlag:
    """Tests for filter_by_flag function."""
    
    def test_filter(self):
        df = pd.DataFrame({
            "flags": [
                "EMPTY_DE(완전미검수)",
                "OK(이상없음)",
                "AMBIG(애매케이스)"
            ],
            "city": ["서울", "부산", "인천"]
        })
        
        result = filter_by_flag(df, FlagType.EMPTY_DE)
        assert len(result) == 1
        assert result.iloc[0]["city"] == "서울"
