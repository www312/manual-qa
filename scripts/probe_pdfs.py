"""P0 前置侦察：摸清两份 PDF 的内部结构，为解析器设计提供依据。

要看什么：
  1. PDF 书签(outline/TOC)是否可用 → 层级感知分块的骨架
  2. 页眉页脚的精确模式 → 清洗规则
  3. 表格数量与分布 → 表格→Markdown 的必要性和工作量
  4. 正文字体/字号分布 → 标题识别的辅助信号
"""

import pymupdf

for name, path in [("RM0433", "data/raw/rm0433.pdf"), ("ESP-IDF", "data/raw/esp-idf-zh_CN-v5.0.9-esp32.pdf")]:
    doc = pymupdf.open(path)
    print(f"\n{'='*60}\n{name}: {doc.page_count} pages")
    toc = doc.get_toc()
    print(f"bookmarks/TOC entries: {len(toc)}")
    if toc:
        print("first 8:", toc[:8])
        print("levels:", sorted({t[0] for t in toc}))

    # 抽 3 页看原文：一页正文、一页表格页、目录后第一页
    for pno in [50, 500, 1500]:
        page = doc[pno]
        text = page.get_text()
        lines = [l for l in text.split("\n") if l.strip()][:6]
        print(f"\n--- page {pno} first lines ---")
        for l in lines:
            print(repr(l[:80]))

    # 表格探测（抽 20 页）
    tbl = sum(len(doc[p].find_tables().tables) for p in range(100, 120))
    print(f"\ntables in sample pages 100-119: {tbl}")
    doc.close()
