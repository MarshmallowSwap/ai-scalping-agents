import json
with open("tools_catalogue.json", "r", encoding="utf-8") as f:
    tools = json.load(f)
for t in tools:
    print(t["name"])
