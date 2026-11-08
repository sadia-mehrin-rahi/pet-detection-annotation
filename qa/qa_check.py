import json, sys, re, statistics
from collections import Counter

data = json.load(open(sys.argv[1]))

def iou(a, b):
    ax2, ay2 = a["x"] + a["width"], a["y"] + a["height"]
    bx2, by2 = b["x"] + b["width"], b["y"] + b["height"]
    iw = max(0, min(ax2, bx2) - max(a["x"], b["x"]))
    ih = max(0, min(ay2, by2) - max(a["y"], b["y"]))
    inter = iw * ih
    union = a["width"] * a["height"] + b["width"] * b["height"] - inter
    return inter / union if union else 0

flags = []
label_counts = Counter()
boxes_total = 0
multi = []
lead_times = []
no_annot = []
cancelled = []
updated_after = 0
img_class = Counter()

for t in data:
    fname = re.sub(r"^[0-9a-f]{8}-", "", t["file_upload"])
    expected = "cat" if fname[0].isupper() else "dog"
    img_class[expected] += 1
    anns = [a for a in t["annotations"] if not a.get("was_cancelled")]
    if any(a.get("was_cancelled") for a in t["annotations"]):
        cancelled.append(fname)
    if not anns:
        no_annot.append(fname)
        continue
    a = anns[-1]
    if a["updated_at"][:19] != a["created_at"][:19]:
        updated_after += 1
    lt = a.get("lead_time")
    if lt is not None:
        lead_times.append((lt, fname))
    boxes = [r for r in a["result"] if r["type"] == "rectanglelabels"]
    boxes_total += len(boxes)
    if not boxes:
        flags.append((fname, "Missing box", "No bounding box on this image"))
        continue
    if len(boxes) > 1:
        multi.append((fname, len(boxes)))
    for r in boxes:
        v = r["value"]
        lab = v["rectanglelabels"][0] if v["rectanglelabels"] else "(none)"
        label_counts[lab] += 1
        if lab != expected:
            flags.append((fname, "Wrong label", f"Labeled '{lab}', filename says '{expected}'"))
        area = v["width"] * v["height"] / 100  # % of image
        if area < 2:
            flags.append((fname, "Suspicious box", f"Very small box ({area:.1f}% of image)"))
        if area > 97:
            flags.append((fname, "Suspicious box", f"Box covers {area:.0f}% of image, check if too loose"))
        if v["x"] < -0.5 or v["y"] < -0.5 or v["x"] + v["width"] > 100.5 or v["y"] + v["height"] > 100.5:
            flags.append((fname, "Out of bounds", "Box extends beyond image edge"))
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            s = iou(boxes[i]["value"], boxes[j]["value"])
            if s > 0.7:
                flags.append((fname, "Duplicate box", f"Two boxes overlap {s:.0%}, possible duplicate"))

lts = sorted(x[0] for x in lead_times)
med = statistics.median(lts)
fast = [(lt, f) for lt, f in lead_times if lt < 5]
slow = [(lt, f) for lt, f in lead_times if lt > 600]
active = [lt for lt in lts if lt <= 600]

print("TASKS", len(data), "img classes", dict(img_class))
print("BOXES", boxes_total, dict(label_counts))
print("MULTI", len(multi), multi)
print("NO_ANNOT", no_annot, "CANCELLED", cancelled)
print("UPDATED_AFTER_CREATE", updated_after)
print("LEAD median %.1f mean %.1f min %.1f max %.1f total_min %.1f" % (med, statistics.mean(lts), lts[0], lts[-1], sum(lts) / 60))
print("ACTIVE(<=600s) n=%d total_min %.1f mean %.1f -> %.0f img/hr" % (len(active), sum(active) / 60, statistics.mean(active), 3600 / statistics.mean(active)))
print("FAST<5s", len(fast), sorted(fast)[:20])
print("SLOW>600s", slow)
print("FLAGS", len(flags))
for f in flags:
    print(" ", f)
ct = sorted(a["created_at"] for t in data for a in t["annotations"])
print("FIRST", ct[0], "LAST", ct[-1])
