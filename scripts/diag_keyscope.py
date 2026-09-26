"""区分：key 无效 vs 账户额度耗尽 vs 该 key 绑定的套餐范围。"""

import sys

sys.path.insert(0, "src")

from openai import OpenAI

KEY = "REDACTED_ZHIPU_KEY_CODING"
c = OpenAI(base_url="https://open.bigmodel.cn/api/paas/v4", api_key=KEY)

# 1) 故意错 key 对照：若错 key 返回 401 而新 key 返回 429，说明新 key 本身有效
bad = OpenAI(base_url="https://open.bigmodel.cn/api/paas/v4", api_key="badkey.123")
try:
    bad.chat.completions.create(model="glm-4.7", messages=[{"role": "user", "content": "hi"}])
except Exception as ex:
    print("错key对照组:", str(ex)[:100])

# 2) flash 模型（coding plan 通常先支持 flash 档）
for m in ["glm-5.3-flash", "glm-4.7-flash", "glm-5.3"]:
    try:
        r = c.chat.completions.create(model=m, messages=[{"role": "user", "content": "hi"}])
        print(f"{m}: OK")
        break
    except Exception as ex:
        print(f"{m}: {str(ex)[:90]}")
