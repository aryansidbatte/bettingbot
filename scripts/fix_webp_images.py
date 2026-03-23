"""
Extract PNG URLs from horseimgurl.txt and update horses.json,
replacing all .webp paths with their correct .png equivalents.
"""

import json
import re
import os

ROOT = os.path.join(os.path.dirname(__file__), "..")
TXT_PATH = os.path.join(ROOT, "horseimgurl.txt")
JSON_PATH = os.path.join(ROOT, "data", "horses.json")

with open(TXT_PATH) as f:
    html = f.read()

with open(JSON_PATH) as f:
    data = json.load(f)

BASE_URL = data["base_url"]  # https://images.microcms-assets.io/assets/<id>

# Extract all unique PNG URLs that start with our base
all_urls = re.findall(r'https://[^\s"\'<>]+\.png', html)
png_urls = sorted(set(u for u in all_urls if u.startswith(BASE_URL)))
print(f"Found {len(png_urls)} unique PNG URLs")

# Strip base_url prefix to get relative paths (same format as stored in json)
png_paths = [u[len(BASE_URL) + 1:] for u in png_urls]  # +1 for the slash

# Build a lookup: normalized filename stem -> path
# e.g. "specialweek_list.png" -> stem "specialweek"
def normalize(s):
    """Lowercase, remove spaces/punctuation/accents for fuzzy matching."""
    s = s.lower()
    s = re.sub(r"[^a-z0-9]", "", s)
    return s

stem_to_path = {}
for path in png_paths:
    filename = path.split("/")[-1]          # e.g. "specialweek_list.png"
    stem = re.sub(r'_?(list|top|_\d+)', '', filename.replace(".png", ""))
    stem = normalize(stem)
    stem_to_path[stem] = path

# Match horse names to paths
updated = 0
unmatched = []

for horse_name, current_path in data["images"].items():
    if not current_path.endswith(".webp"):
        continue

    name_norm = normalize(horse_name)

    # Try exact stem match first
    matched_path = stem_to_path.get(name_norm)

    # If no exact match, try substring match
    if not matched_path:
        candidates = [path for stem, path in stem_to_path.items() if name_norm in stem or stem in name_norm]
        if len(candidates) == 1:
            matched_path = candidates[0]

    if matched_path:
        data["images"][horse_name] = matched_path
        print(f"  ✓ {horse_name}: {current_path} -> {matched_path}")
        updated += 1
    else:
        unmatched.append((horse_name, current_path, name_norm))

print(f"\nUpdated: {updated}")
if unmatched:
    print(f"Unmatched ({len(unmatched)}) — manual review needed:")
    for name, path, norm in unmatched:
        print(f"  ✗ {name!r} (norm={norm!r}): {path}")
    print("\nAll available stems:")
    for stem in sorted(stem_to_path):
        print(f"  {stem}: {stem_to_path[stem]}")
else:
    print("All webp entries replaced!")
    with open(JSON_PATH, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved {JSON_PATH}")
