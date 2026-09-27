"""验证用户提供的新智谱 key：chat / embedding 两条链路。"""

import sys

sys.path.insert(0, "src")

from manual_qa.config import LLMConfig
from manual_qa.llm import EmbeddingClient, LLMClient

KEY = "REDACTED_ZHIPU_KEY_CODING"
BASE = "https://open.bigmodel.cn/api/paas/v4"

llm = LLMClient(LLMConfig(base_url=BASE, api_key=KEY, model="glm-4.7"))
try:
    r = llm.chat([{"role": "user", "content": "回复两个字：可用"}])
    print("chat OK:", r[:20])
except Exception as ex:
    print("chat FAIL:", str(ex)[:120])

emb = EmbeddingClient(LLMConfig(base_url=BASE, api_key=KEY, model="embedding-3"))
try:
    v = emb.embed(["寄存器地址配置方法", "SPI flash 初始化"])
    print("embedding OK: dim", len(v[0]), "count", len(v))
except Exception as ex:
    print("embedding FAIL:", str(ex)[:120])
