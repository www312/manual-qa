"""验证充值后的新 key：embedding + chat。"""

import sys

sys.path.insert(0, "src")

from openai import OpenAI

KEY = "REDACTED_ZHIPU_KEY"
c = OpenAI(base_url="https://open.bigmodel.cn/api/paas/v4", api_key=KEY)

r = c.embeddings.create(model="embedding-3", input=["寄存器地址配置方法", "SPI flash 初始化"])
print("embedding-3: OK dim", len(r.data[0].embedding), "count", len(r.data))

r = c.chat.completions.create(model="glm-4.7", messages=[{"role": "user", "content": "回复两个字：可用"}])
print("glm-4.7 chat OK:", (r.choices[0].message.content or "")[:20])
