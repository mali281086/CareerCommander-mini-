import json

with open("data/cache.json", "r", encoding="utf-8") as f:
    cache = json.load(f)

print(f"Total cached items: {len(cache)}")
na_items = 0
for k, v in cache.items():
    if "error" not in v and "ats_report" not in v:
        print(f"\n--- N/A Cache Entry: {k} ---")
        print(json.dumps(v, indent=2))
        na_items += 1
        
print(f"\nTotal N/A items: {na_items}")
