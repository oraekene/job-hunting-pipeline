"""Extract Wellfound job cards from fetched HTML (2026-08-24)."""
import re, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
html = open(os.path.join(HERE, "wellfound.html"), encoding="utf-8").read()
print("bytes:", len(html))

# pattern A: /jobs/{id}-{slug} occurrences
links = re.findall(r"/jobs/(\d+)-([a-z0-9\-]+)", html)
seen, uniq = set(), []
for i, s in links:
    if (i, s) not in seen:
        seen.add((i, s)); uniq.append((i, s))
print("job link matches unique:", len(uniq))
for i, s in uniq[:15]:
    print("  ", i, s)

# pattern B: embedded state markers
markers = ["__NEXT_DATA__", "apolloState", "jobAt", "slug", "window.__"]
for m in markers:
    print(f"marker {m!r}: {html.count(m)}")

# pattern C: title/meta pairs like yesterday's .wellfound_matches.json
pairs = []
for m in re.finditer(r'"title":\s*"([^"]{4,120})"[^}]*?"meta":\s*"((?:[^"\\]|\\.){0,400})"', html):
    pairs.append({"title": m.group(1), "meta": m.group(2)})
print("title/meta pairs:", len(pairs))
for p in pairs[:8]:
    print("  ", json.dumps(p)[:220])

json.dump({"links": [{"id": i, "slug": s} for i, s in uniq], "pairs": pairs},
          open(os.path.join(HERE, "wellfound_extract.json"), "w"))
