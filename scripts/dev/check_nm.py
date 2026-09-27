"""检查 frontend node_modules 实际状态。"""

import os

nm = "/Users/wengzitao/manual-qa/frontend/node_modules"
if not os.path.isdir(nm):
    print("node_modules MISSING")
else:
    entries = os.listdir(nm)
    print(f"node_modules entries: {len(entries)}")
    for probe in ["vite", "vue-tsc", "element-plus", ".bin", "typescript"]:
        print(f"  {probe}: {'OK' if os.path.exists(os.path.join(nm, probe)) else 'MISSING'}")
    binp = os.path.join(nm, ".bin")
    if os.path.isdir(binp):
        print(f".bin contents: {sorted(os.listdir(binp))[:15]}")
