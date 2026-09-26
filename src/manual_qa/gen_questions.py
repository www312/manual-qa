"""P1 评测层 Step1：LLM 生成 QA 测试集。

设计（面试考点）：
  - 出题方式：从语料中按章节分层抽样 chunk 作为"种子"，让 LLM 只依据种子
    出题 + 给标准答案，避免 LLM 凭空编造（题必须可由语料回答）。
  - 分层：RM0433 按外设大类均衡、ESP-IDF 全抽；中英混合出题（中文问英文手册
    = 跨语言检索场景，是这个项目的差异化点）。
  - 金标准：记录 seed chunk_id → recall@k 直接按"是否命中种子块"计。
    （局限：正确答案可能出现在多个块——P1 后期用 LLM judge 补块级放宽。）
"""

import json
import random
import sys

sys.path.insert(0, "src")

from manual_qa.config import load_settings
from manual_qa.llm import LLMClient

random.seed(42)

chunks = [json.loads(l) for l in open("data/chunks_selected.jsonl")]
rm = [c for c in chunks if c["doc"] == "rm0433"]
esp = [c for c in chunks if c["doc"] == "espidf"]

# RM0433 按一级章节分层抽样（每章最多 3 题避免偏科）
by_ch: dict[str, list] = {}
for c in rm:
    top = c["chapter"].split(" > ")[0]
    # 只要正文章节（数字开头的寄存器/外设章）
    if top and top[0].isdigit():
        by_ch.setdefault(top, []).append(c)

seeds = []
for ch, lst in sorted(by_ch.items()):
    seeds.extend(random.sample(lst, min(3, len(lst))))
# ESP-IDF 抽 15
seeds.extend(random.sample(esp, 15))
print(f"chapters: {len(by_ch)}, rm seeds: {len(seeds)-15}, esp seeds: 15, total {len(seeds)}")

PROMPT = """你是嵌入式技术手册的考官。根据下面资料出一道【有唯一明确答案】的技术问题，
用于测试检索系统。

要求：
- 问题必须能且仅能由这段资料回答（不要出常识题）
- RM0433 资料：用中文提问（跨语言检索测试），问题里可以用寄存器/信号英文名
- ESP-IDF 资料：用中文提问
- 给出简洁的标准答案（不超过40字）
- 问题类型多样化：数值型（地址/频率/位宽）、条件型（什么情况下/前提）、步骤型（如何做）

资料出处：{chapter} (p{page})
资料内容：
{text}

严格按此 JSON 格式输出（不要其他内容）：
{{"question": "...", "answer": "...", "type": "数值|条件|步骤"}}"""


def main() -> None:
    s = load_settings()
    llm = LLMClient(s.llm)
    out_path = "data/qa_dataset_raw.jsonl"
    ok, fail = 0, 0
    with open(out_path, "w", encoding="utf-8") as f:
        for i, seed in enumerate(seeds):
            # 截种子到 1500 字省 token
            txt = seed["text"][:1500]
            prompt = PROMPT.format(
                chapter=seed["chapter"][:80], page=seed["page"], text=txt
            )
            try:
                raw = llm.chat([{"role": "user", "content": prompt}], temperature=0.7)
                raw = raw.strip()
                # 容错：剥 markdown 代码壳
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
                obj = json.loads(raw)
                obj["seed_chunk_id"] = seed["chunk_id"]
                obj["seed_chapter"] = seed["chapter"]
                obj["seed_page"] = seed["page"]
                obj["doc"] = seed["doc"]
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
                ok += 1
            except Exception as ex:
                fail += 1
                print(f"[{i}] FAIL: {str(ex)[:60]}")
            if (i + 1) % 20 == 0:
                print(f"{i+1}/{len(seeds)} done (ok={ok} fail={fail})")
    print(f"\nfinal: ok={ok} fail={fail} -> {out_path}")


if __name__ == "__main__":
    main()
