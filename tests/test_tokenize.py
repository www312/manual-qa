"""单元测试：混合分词器的保形行为。"""

import sys

sys.path.insert(0, "src")

from manual_qa.retrieval import _tokenize


def test_register_name_kept_whole() -> None:
    toks = _tokenize("RCC_APB1ENR 的地址偏移")
    assert "rcc_apb1enr" in toks, toks


def test_api_name_kept_whole() -> None:
    toks = _tokenize("调用 esp_light_sleep_start() 进入休眠")
    assert "esp_light_sleep_start" in toks, toks


def test_plain_english_words() -> None:
    toks = _tokenize("The DAC channel is selected")
    assert "channel" in toks and "selected" in toks


def test_chinese_segmented() -> None:
    toks = _tokenize("低功耗模式的进入方式")
    assert any("低功耗" in t for t in toks)


def test_mixed_query() -> None:
    toks = _tokenize("GPIOx_AFRL 寄存器 alternate function")
    assert "gpiox_afrl" in toks and "alternate" in toks
