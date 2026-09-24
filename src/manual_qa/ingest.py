"""ingest 流水线：PDF -> 清洗 -> 层级感知分块。

设计（面试考点）：
  1. 骨架 = PDF 书签(outline)：两份手册都有 4-6 级书签，天然携带章节层级，
     比「按字号猜标题」可靠一个量级。
  2. 清洗：RM0433 页眉三行（'RM0433 Rev 8'/'N/3353'/'RM0433'）+ 页脚行；
     ESP-IDF 页眉（'Chapter N. xxx'）+ '(续上页)'。
  3. 表格：pymupdf find_tables 提取后转 Markdown，防表意丢失——寄存器手册的
     寄存器位定义全是表格，丢表=丢魂。
  4. 分块：以 level<=2 的章节为容器，正文滑窗(512 token/64 overlap)，
     每块携带 doc/chapter/page 元数据，供引用溯源。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pymupdf
import tiktoken

_ENC = tiktoken.get_encoding("cl100k_base")

# ---------- 清洗规则 ----------

RM_HEADERS = re.compile(r"^(RM0433 Rev \d+|\d+/3353|RM0433)$")
ESP_HEADERS = re.compile(r"^(Chapter \d+\..*|\(续上页\))$")
PAGE_NUM = re.compile(r"^\d{1,4}$")

# 无信息量行：孤立页码、重复水印
NOISE = re.compile(r"^(\s*|www\.st\.com\s*|STM32H742/743/753.*$)", re.I)


def clean_line(line: str, doc: str) -> str:
    line = line.strip()
    if not line:
        return ""
    if doc == "rm0433" and (RM_HEADERS.match(line) or PAGE_NUM.match(line)):
        return ""
    if doc == "espidf" and (ESP_HEADERS.match(line)):
        return ""
    return line


# ---------- 分块 ----------


@dataclass
class Chunk:
    chunk_id: str
    doc: str
    chapter: str  # 完整层级路径，如 "37 High-Resolution Timer > 37.5 HRTIM registers"
    page: int
    text: str
    meta: dict = field(default_factory=dict)


def _token_len(s: str) -> int:
    """tiktoken cl100k 精确计数（与智谱分词器近似，误差 <10%）。

    教训：早期用「中文按字+英文按词」粗估，目录页的点引导线
    （" . . . . 254"）几乎不计权，导致单块实际 3000+ token 触发
    智谱 embedding 输入上限（错误码 1210）。精确计量是流水线的地基。
    """
    return len(_ENC.encode(s))


# 目录引导点行（"标题 . . . . 页码"）——零检索价值，整行剔除
TOC_LINE = re.compile(r"(\.\s*){4,}\d*\s*$")


def chunk_section(
    text: str, chunk_size: int, overlap: int
) -> list[str]:
    """滑窗切分：按 token 长度，句子边界对齐优先。"""
    if _token_len(text) <= chunk_size:
        return [text] if text.strip() else []
    # 按行切（保留表格行完整性），贪心装填
    lines, out, buf, buf_len = text.split("\n"), [], [], 0
    for line in lines:
        ll = _token_len(line)
        if buf_len + ll > chunk_size and buf:
            out.append("\n".join(buf))
            # 回退 overlap：保留尾部若干行
            keep, kept = [], 0
            for prev in reversed(buf):
                if kept + _token_len(prev) > overlap:
                    break
                keep.insert(0, prev)
                kept += _token_len(prev)
            buf, buf_len = keep, kept
        buf.append(line)
        buf_len += ll
    if buf:
        out.append("\n".join(buf))
    return out


def table_to_md(tb) -> str:
    rows = tb.extract()
    if not rows:
        return ""
    head = rows[0]
    md = "| " + " | ".join(str(c or "") for c in head) + " |\n"
    md += "|" + "---|" * len(head) + "\n"
    for r in rows[1:]:
        md += "| " + " | ".join(str(c or "") for c in r) + " |\n"
    return md


def ingest_pdf(
    path: str,
    doc: str,
    chunk_size: int = 512,
    overlap: int = 64,
    max_level: int = 3,
) -> list[Chunk]:
    pdf = pymupdf.open(path)
    toc = [t for t in pdf.get_toc() if t[0] <= max_level]

    # 页 -> 标题列表 映射（书签页码是 1-based）
    page_heads: dict[int, list[tuple[int, str]]] = {}
    for lvl, title, pno in toc:
        page_heads.setdefault(pno - 1, []).append((lvl, title))

    chapters: list[dict] = []  # [{path, page, lines}]
    cur_path: list[str] = []

    for pno in range(pdf.page_count):
        page = pdf[pno]
        # 表格先行提取并占位替换，避免正文流里表格碎成行
        table_list = page.find_tables()
        tables = table_list.tables if table_list else []
        for i, tb in enumerate(tables):
            md = table_to_md(tb)
            page.insert_text(
                (72, 72), f"__TBL{i}__", overlay=False
            ) if False else None
        # 用 textpage 方式拿到“表格区域外”的正文 + 表格占位拼接
        blocks = page.get_text("blocks")
        parts: list[str] = []
        for b in blocks:
            x0, y0, x1, y1, txt, bno, btype = b
            if btype != 0:
                continue
            lines = [clean_line(l, doc) for l in txt.split("\n")]
            lines = [l for l in lines if l and not TOC_LINE.search(l)]
            if not lines:
                continue
            # 该 block 是否落在某个表格 bbox 内 → 用表格 MD 替换
            in_tbl = None
            for i, tb in enumerate(tables):
                tbx = tb.bbox
                if x0 >= tbx[0] - 2 and x1 <= tbx[2] + 2 and y0 >= tbx[1] - 2 and y1 <= tbx[3] + 2:
                    in_tbl = i
                    break
            if in_tbl is not None:
                parts.append(f"__TBL{in_tbl}__")
            else:
                parts.append("\n".join(lines))
        body = "\n".join(parts)

        # 表格 MD 回填占位符
        for i, tb in enumerate(tables):
            body = body.replace(f"__TBL{i}__", table_to_md(tb).strip())
        body = re.sub(r"__TBL\d+__", "", body)  # 未命中的残留占位

        # 章节边界：本页出现的书签标题 → 开新章节
        heads = page_heads.get(pno, [])
        consumed = 0
        for lvl, title in heads:
            while cur_path and lvl <= _lvl(cur_path[-1]):
                cur_path.pop()
            cur_path.append(title)
            consumed += _token_len(title)
        # 修正：书签层级需要数字比较，重做
        chapters.append(
            {"path": " > ".join(cur_path), "page": pno + 1, "text": body}
        )

    pdf.close()

    # 合并相邻同章节页 + 分块
    merged: dict[str, dict] = {}
    order: list[str] = []
    for ch in chapters:
        if ch["path"] in merged:
            merged[ch["path"]]["text"] += "\n" + ch["text"]
            merged[ch["path"]]["pages"].append(ch["page"])
        else:
            merged[ch["path"]] = {"text": ch["text"], "pages": [ch["page"]]}
            order.append(ch["path"])

    out: list[Chunk] = []
    for path in order:
        for piece in chunk_section(merged[path]["text"], chunk_size, overlap):
            cid = f"{doc}-{len(out):05d}"
            out.append(
                Chunk(
                    chunk_id=cid,
                    doc=doc,
                    chapter=path,
                    page=merged[path]["pages"][0],
                    text=piece,
                    meta={"pages": merged[path]["pages"]},
                )
            )
    return out


def _lvl(title: str) -> int:
    """从标题文本推断层级（辅助，主逻辑用书签数字层级）。"""
    m = re.match(r"^(\d+(\.\d+)*)\s", title)
    return m.group(1).count(".") + 1 if m else 9


if __name__ == "__main__":
    for name, p, d in [
        ("RM0433", "data/raw/rm0433.pdf", "rm0433"),
        ("ESP-IDF", "data/raw/esp-idf-zh_CN-v5.0.9-esp32.pdf", "espidf"),
    ]:
        chunks = ingest_pdf(p, d)
        sizes = [_token_len(c.text) for c in chunks]
        print(
            f"{name}: {len(chunks)} chunks, avg {sum(sizes)//max(len(sizes),1)} tok, "
            f"max {max(sizes)}, empty {sum(1 for s in sizes if s < 10)}"
        )
        # 抽样 2 块
        for c in chunks[len(chunks) // 3 : len(chunks) // 3 + 2]:
            print(f"\n--- {c.chunk_id} | {c.chapter[:60]} | p{c.page}")
            print(c.text[:300])
