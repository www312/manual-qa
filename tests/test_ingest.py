"""单元测试：ingest 清洗/分块逻辑（不打 API，秒级）。"""

import sys

sys.path.insert(0, "src")

from manual_qa.ingest import (
    TOC_LINE,
    _token_len,
    chunk_section,
    clean_line,
)


def test_clean_line_rm_headers() -> None:
    assert clean_line("RM0433 Rev 8", "rm0433") == ""
    assert clean_line("123/3353", "rm0433") == ""
    assert clean_line("RM0433", "rm0433") == ""
    assert clean_line("42", "rm0433") == ""
    assert clean_line("The DAC channel 1 is selected.", "rm0433") != ""


def test_clean_line_esp_headers() -> None:
    assert clean_line("Chapter 2. API 参考", "espidf") == ""
    assert clean_line("(续上页)", "espidf") == ""
    assert clean_line("正常正文行", "espidf") != ""


def test_toc_line_filter() -> None:
    dotline = "PWR main features  . . . . . . . . . . . . 254"
    assert TOC_LINE.search(dotline)
    assert not TOC_LINE.search("Set the OTR bit to enable")


def test_token_len_matches_tiktoken() -> None:
    # cl100k 对该串实计 5 tokens（实测值，非猜）
    assert _token_len("hello world foo bar baz") == 5


def test_chunk_section_small() -> None:
    out = chunk_section("short text", 512, 64)
    assert out == ["short text"]


def test_chunk_section_splits_and_overlaps() -> None:
    lines = [f"line {i} " + "x" * 20 for i in range(200)]
    text = "\n".join(lines)
    out = chunk_section(text, 512, 64)
    assert len(out) > 1
    for piece in out:
        assert _token_len(piece) <= 600  # 允许单行超限的少量裕量
    # overlap：相邻块应有尾部/头部共享行
    assert any(l in out[1] for l in out[0].split("\n")[-3:])
