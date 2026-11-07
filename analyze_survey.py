import csv
import json
import math
import sys
from pathlib import Path
from statistics import mean


project = Path(__file__).resolve().parent
logs = project / "logs"
# Optional command-line argument selects a specific run timestamp.
if len(sys.argv) > 1:
    run_id = sys.argv[1]
else:
    recordings = sorted(logs.glob("measured_flight_*.csv"))
    if not recordings:
        raise SystemExit("Run survey_measured.py first to create a labelled recording.")
    run_id = recordings[-1].stem.removeprefix("measured_flight_")

flight_path = logs / f"measured_flight_{run_id}.csv"
plan_path = logs / f"measured_plan_{run_id}.csv"
result_path = logs / f"measured_result_{run_id}.json"
for path in (flight_path, plan_path, result_path):
    if not path.exists():
        raise SystemExit(f"Missing file: {path}. Wait until the flight script finishes.")

with flight_path.open(newline="", encoding="utf-8-sig") as file:
    flight = list(csv.DictReader(file))
with plan_path.open(newline="", encoding="utf-8-sig") as file:
    plan_rows = list(csv.DictReader(file))
if len(flight) < 2 or len(plan_rows) < 2:
    raise SystemExit("Too few measurements or plan points.")
result = json.loads(result_path.read_text())
plan = {int(row["point"]): row for row in plan_rows}
origin_lat = float(plan_rows[0]["origin_lat_deg"])
origin_lon = float(plan_rows[0]["origin_lon_deg"])
radius = 6_378_137.0
longitude_scale = radius * math.cos(math.radians(origin_lat))
errors = []
altitude_errors = []
per_pass = {}
times = [float(row["autopilot_time_s"]) for row in flight]
if any(b < a for a, b in zip(times, times[1:])):
    raise SystemExit("Autopilot time reset within this recording.")

for row in flight:
    if row["phase"] != "SURVEY_PASS":
        continue
    destination = int(row["destination"])
    start, end = plan[destination - 1], plan[destination]
    start_n, start_e = float(start["north_m"]), float(start["east_m"])
    delta_n = float(end["north_m"]) - start_n
    delta_e = float(end["east_m"]) - start_e
    length_squared = delta_n ** 2 + delta_e ** 2
    if length_squared == 0:
        continue
    north = math.radians(float(row["latitude_deg"]) - origin_lat) * radius
    east = math.radians(float(row["longitude_deg"]) - origin_lon) * longitude_scale
    progress = ((north - start_n) * delta_n + (east - start_e) * delta_e) / length_squared
    # Explicitly analyze only the middle 80% of each straight survey pass.
    if not 0.1 <= progress <= 0.9:
        continue
    error = abs(delta_n * (east - start_e) - delta_e * (north - start_n)) / math.sqrt(length_squared)
    altitude_error = abs(float(row["relative_altitude_m"]) - float(end["target_altitude_m"]))
    errors.append(error)
    altitude_errors.append(altitude_error)
    per_pass.setdefault(destination, []).append(error)

if not errors:
    raise SystemExit("No samples in the middle 80% of survey passes. Check the labelled recording.")

expected_passes = [int(row["point"]) for row in plan_rows[1:-1]
                   if abs(float(row["east_m"]) - float(plan[int(row["point"]) - 1]["east_m"])) < 0.000001]
missing_passes = sorted(set(expected_passes) - set(per_pass))
last = flight[-1]
final_n = math.radians(float(last["latitude_deg"]) - origin_lat) * radius
final_e = math.radians(float(last["longitude_deg"]) - origin_lon) * longitude_scale
lines = [
    f"Run: {run_id}",
    f"Flight sequence completed: {result['completed']}",
    f"Recorded samples: {len(flight)}",
    f"Recording duration (includes setup and landing): {times[-1] - times[0]:.1f} s",
    "Error metrics below use the middle 80% of each labelled straight survey pass.",
    f"Passes represented: {len(per_pass)} of {len(expected_passes)}",
    f"Missing pass destination IDs: {missing_passes}",
    f"Samples used for errors: {len(errors)}",
    f"Mean absolute cross-track error: {mean(errors):.3f} m",
    f"Cross-track RMSE: {math.sqrt(mean(value ** 2 for value in errors)):.3f} m",
    f"Maximum sampled cross-track error: {max(errors):.3f} m",
    f"Mean absolute altitude error: {mean(altitude_errors):.3f} m",
    f"Maximum sampled altitude error: {max(altitude_errors):.3f} m",
    f"Final recorded horizontal offset from origin: {math.hypot(final_n, final_e):.3f} m",
    "",
    "Per-pass sample counts and maximum sampled cross-track error:",
]
for destination, values in sorted(per_pass.items()):
    lines.append(f"Destination {destination}: {len(values)} samples, max {max(values):.3f} m")
lines.extend(["", "Limits: simulated telemetry, approximately 2 Hz. Phase labels reflect script state at reception.",
              "Turn overshoot, connectors and return are excluded from the error metrics. Unsampled peaks may be missed.",
              "These metrics measure tracking, not map accuracy or image quality."])
report = "\n".join(lines)
report_folder = project / "reports"
report_folder.mkdir(exist_ok=True)
report_path = report_folder / f"survey_metrics_{run_id}.txt"
report_path.write_text(report, encoding="utf-8")
print(report)
print(f"\nReport saved to: {report_path}")
