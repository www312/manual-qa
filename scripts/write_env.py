"""把充值后的 key 写入 .env（test_paid_key.py 已验证 embedding+chat 全通）。"""

import re

p = "/Users/wengzitao/manual-qa/.env"
s = open(p).read()
s = re.sub(r"LLM_API_KEY=.*", "LLM_API_KEY=REDACTED_ZHIPU_KEY", s)
s = re.sub(r"EMBED_API_KEY=.*", "EMBED_API_KEY=REDACTED_ZHIPU_KEY", s)
open(p, "w").write(s)
print("key updated in .env")
