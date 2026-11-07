import csv
import math
from pathlib import Path

import matplotlib.pyplot as plt


# These two files belong to the same completed simulated survey.
RUN_ID = "20261108_023126_613096"
project_folder = Path(__file__).resolve().parent
flight_path = project_folder / "logs" / f"survey_flight_{RUN_ID}.csv"
plan_path = project_folder / "logs" / f"survey_plan_used_{RUN_ID}.csv"

for path in (flight_path, plan_path):
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

with plan_path.open(newline="", encoding="utf-8-sig") as plan_file:
    plan = list(csv.DictReader(plan_file))

with flight_path.open(newline="", encoding="utf-8-sig") as flight_file:
    flight = list(csv.DictReader(flight_file))

if len(plan) < 3 or len(flight) < 2:
    raise SystemExit("The plan or flight recording has too few rows to plot.")

origin_lat = float(plan[0]["origin_lat_deg"])
origin_lon = float(plan[0]["origin_lon_deg"])
target_altitude = float(plan[0]["target_altitude_m"])
earth_radius = 6_378_137.0

planned_north = [float(row["north_m"]) for row in plan]
planned_east = [float(row["east_m"]) for row in plan]

recorded_north = []
recorded_east = []
altitudes = []
elapsed_seconds = []
start_time = float(flight[0]["autopilot_time_s"])

for row in flight:
    latitude = float(row["latitude_deg"])
    longitude = float(row["longitude_deg"])

    north = math.radians(latitude - origin_lat) * earth_radius
    east = (
        math.radians(longitude - origin_lon)
        * earth_radius
        * math.cos(math.radians(origin_lat))
    )

    recorded_north.append(north)
    recorded_east.append(east)
    altitudes.append(float(row["relative_altitude_m"]))
    elapsed_seconds.append(float(row["autopilot_time_s"]) - start_time)

if any(later < earlier for earlier, later in zip(elapsed_seconds, elapsed_seconds[1:])):
    raise SystemExit("Autopilot time moved backwards. Check for a simulator restart in this recording.")

figure, (route_axes, altitude_axes) = plt.subplots(1, 2, figsize=(13, 6))

# The final plan row is the return to the origin.
route_axes.plot(
    planned_east[:-1], planned_north[:-1],
    color="darkorange", linestyle="--", linewidth=2.5,
    label="Planned survey passes",
)
route_axes.plot(
    planned_east[-2:], planned_north[-2:],
    color="purple", linestyle=":", linewidth=2.5,
    label="Planned return",
)
route_axes.plot(
    recorded_east, recorded_north,
    color="royalblue", linewidth=1.3, label="Recorded flight",
)
route_axes.scatter(0, 0, color="green", s=65, zorder=5, label="Plan origin")
route_axes.scatter(
    recorded_east[-1], recorded_north[-1],
    color="red", marker="x", s=65, zorder=6,
    label="Final recorded position",
)
route_axes.set_title("Survey route and return")
route_axes.set_xlabel("East from saved origin (m)")
route_axes.set_ylabel("North from saved origin (m)")
route_axes.set_aspect("equal", adjustable="box")
route_axes.margins(0.12)
route_axes.grid(True, alpha=0.3)
route_axes.legend(fontsize=8, loc="best")

altitude_axes.plot(elapsed_seconds, altitudes, color="royalblue", label="Recorded altitude")
altitude_axes.axhline(
    target_altitude, color="darkorange", linestyle="--",
    label=f"Target during flight ({target_altitude:g} m)",
)
altitude_axes.set_title("Altitude throughout the recording")
altitude_axes.set_xlabel("Time since recording began (s)")
altitude_axes.set_ylabel("Altitude relative to home (m)")
altitude_axes.grid(True, alpha=0.3)
altitude_axes.legend(fontsize=8)

figure.suptitle("Simulated survey - planned and recorded flight")
figure.tight_layout()

plots_folder = project_folder / "plots"
plots_folder.mkdir(exist_ok=True)
image_path = plots_folder / f"survey_comparison_{RUN_ID}.png"
figure.savefig(image_path, dpi=150)

final_offset = math.hypot(recorded_north[-1], recorded_east[-1])
print(f"Recorded measurements: {len(flight)}")
print(f"Recording duration: {elapsed_seconds[-1]:.1f} s")
print(f"Maximum recorded altitude: {max(altitudes):.3f} m")
print(f"Final horizontal distance from saved origin: {final_offset:.2f} m")
print("Final distance describes the last recorded position, not whole-route tracking error.")
print(f"Graph saved to: {image_path}")

plt.show()
