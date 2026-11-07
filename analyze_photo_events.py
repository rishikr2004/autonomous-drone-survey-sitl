"""Report simulated capture decisions. This does not assess real imagery."""
import csv
import json
import statistics
from pathlib import Path

root = Path(__file__).resolve().parent
files = list((root / "logs").glob("photo_result_*.json"))
if not files:
    raise SystemExit("Run survey_photo_events.py first.")
result_path = max(files, key=lambda p: p.stat().st_mtime)
run = result_path.stem.removeprefix("photo_result_")
result = json.loads(result_path.read_text(encoding="utf-8"))
settings = result["camera_settings"]

def read_csv(name):
    with (root / "logs" / f"{name}_{run}.csv").open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

events = read_csv("photo_events")
flight = read_csv("photo_flight")
plan = read_csv("photo_plan")
lines = [f"Run: {run}", f"Flight sequence completed: {result['completed']}",
         f"Simulated photo events: {len(events)}",
         f"Requested spacing: {settings['photo_spacing_m']:.3f} m",
         "No images were captured; these are software event records."]
intervals = [float(b["autopilot_time_s"]) - float(a["autopilot_time_s"])
             for a, b in zip(flight, flight[1:])]
intervals = [dt for dt in intervals if dt > 0]
if intervals:
    lines.append(f"Median telemetry interval: {statistics.median(intervals):.3f} s (approximately {1 / statistics.median(intervals):.1f} Hz)")
all_gaps = []
# The final plan point is the return home, so exclude it.
for i in range(1, len(plan) - 1):
    a, b = plan[i - 1], plan[i]
    if abs(float(b["east_m"]) - float(a["east_m"])) > 1e-6:
        continue
    progress = [float(e["along_track_m"]) for e in events if int(e["destination"]) == i]
    length = abs(float(b["north_m"]) - float(a["north_m"]))
    gaps = [y - x for x, y in zip(progress, progress[1:])]
    all_gaps.extend(gaps)
    lines.append(f"Pass ending at destination {i}: {len(progress)} events")
    if progress:
        lines.append(f"  First event: {progress[0]:.3f} m into pass; last event: {length - progress[-1]:.3f} m before end")
    if gaps:
        lines.append(f"  Spacing min/mean/max: {min(gaps):.3f} / {statistics.mean(gaps):.3f} / {max(gaps):.3f} m")
if all_gaps:
    worst_gap = max(all_gaps)
    ideal_overlap = max(0, 1 - worst_gap / settings["footprint_length_m"])
    lines.extend([f"Largest observed along-pass spacing: {worst_gap:.3f} m",
                  f"Smallest estimated forward overlap between consecutive events: {ideal_overlap:.1%}"])
lines.extend(["", "Interpretation:",
              "Distance is checked at received position updates. Events can be farther apart than requested.",
              "The first eligible sample starts each pass; endpoints are not forced captures.",
              "Event counts need not equal the planned preview count.",
              "Overlap assumes the preview's fixed footprint, flat ground and camera alignment.",
              "It does not account for yaw, tilt, exposure latency, image quality or map accuracy.",
              "Phase labels reflect script state when telemetry is received."])
report = "\n".join(lines)
print(report)
folder = root / "reports"
folder.mkdir(exist_ok=True)
path = folder / f"photo_report_{run}.txt"
path.write_text(report + "\n", encoding="utf-8")
print(f"Report saved to: {path}")
