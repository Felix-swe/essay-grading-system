import json
with open("essays.json", "r", encoding="utf-8") as f:
    data = json.load(f)
print(f"成功读取，共{len(data)}篇作文")
print(data[0]["text"])