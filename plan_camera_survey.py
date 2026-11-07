import csv
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


# Illustrative camera and flat-field assumptions for a planning exercise.
FIELD_LENGTH_M = 30.0
FIELD_WIDTH_M = 20.0
HEIGHT_ABOVE_GROUND_M = 10.0
CROSS_TRACK_FOV_DEG = 60.0
ALONG_TRACK_FOV_DEG = 45.0
SIDE_OVERLAP = 0.70
FRONT_OVERLAP = 0.80

if min(FIELD_LENGTH_M, FIELD_WIDTH_M, HEIGHT_ABOVE_GROUND_M) <= 0:
    raise SystemExit("Field dimensions and height must be positive.")
if not all(0 < fov < 180 for fov in (CROSS_TRACK_FOV_DEG, ALONG_TRACK_FOV_DEG)):
    raise SystemExit("Field of view must be between 0 and 180 degrees.")
if not all(0 <= overlap < 1 for overlap in (SIDE_OVERLAP, FRONT_OVERLAP)):
    raise SystemExit("Overlap fractions must be at least 0 and less than 1.")

footprint_width = 2 * HEIGHT_ABOVE_GROUND_M * math.tan(math.radians(CROSS_TRACK_FOV_DEG / 2))
footprint_length = 2 * HEIGHT_ABOVE_GROUND_M * math.tan(math.radians(ALONG_TRACK_FOV_DEG / 2))
lane_spacing = footprint_width * (1 - SIDE_OVERLAP)
photo_spacing = footprint_length * (1 - FRONT_OVERLAP)

# Include both field edges. The final gap can be shorter than the requested spacing.
lane_count = math.ceil(FIELD_WIDTH_M / lane_spacing) + 1
photos_per_lane = math.ceil(FIELD_LENGTH_M / photo_spacing) + 1
if lane_count * photos_per_lane > 10000:
    raise SystemExit("This preview is limited to 10,000 planned photos. Review the inputs.")

lanes = [min(index * lane_spacing, FIELD_WIDTH_M) for index in range(lane_count)]
photo_norths = [min(index * photo_spacing, FIELD_LENGTH_M) for index in range(photos_per_lane)]
route = []
photos = []

for lane_index, east in enumerate(lanes):
    norths = photo_norths if lane_index % 2 == 0 else list(reversed(photo_norths))
    route.extend([(norths[0], east), (norths[-1], east)])
    for north in norths:
        photos.append((lane_index + 1, north, east))

output_folder = Path(__file__).resolve().parent / "plans" / "camera_preview"
output_folder.mkdir(parents=True, exist_ok=True)

with (output_folder / "survey_plan.csv").open("w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(["point", "north_m", "east_m"])
    for index, (north, east) in enumerate(route):
        writer.writerow([index, north, east])

with (output_folder / "planned_photos.csv").open("w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)
    writer.writerow(["photo", "lane", "north_m", "east_m"])
    for index, (lane, north, east) in enumerate(photos, start=1):
        writer.writerow([index, lane, north, east])

settings = {
    "field_length_m": FIELD_LENGTH_M,
    "field_width_m": FIELD_WIDTH_M,
    "height_above_ground_m": HEIGHT_ABOVE_GROUND_M,
    "cross_track_fov_deg": CROSS_TRACK_FOV_DEG,
    "along_track_fov_deg": ALONG_TRACK_FOV_DEG,
    "side_overlap": SIDE_OVERLAP,
    "front_overlap": FRONT_OVERLAP,
    "footprint_width_m": footprint_width,
    "footprint_length_m": footprint_length,
    "lane_spacing_m": lane_spacing,
    "photo_spacing_m": photo_spacing,
    "assumptions": "Flat ground, nadir camera, footprint axes aligned east/north; ideal geometry only. Photos along passes only; return leg excluded.",
}
(output_folder / "camera_settings.json").write_text(json.dumps(settings, indent=2), encoding="utf-8")

figure, axes = plt.subplots(figsize=(9, 9))
for index, (_, north, east) in enumerate(photos):
    axes.add_patch(Rectangle(
        (east - footprint_width / 2, north - footprint_length / 2),
        footprint_width, footprint_length,
        facecolor="cornflowerblue", edgecolor="royalblue", alpha=0.045,
        label="Ideal photo footprints" if index == 0 else None,
    ))
axes.plot([east for north, east in route], [north for north, east in route],
          color="darkorange", linewidth=1.5, label="Planned route")
axes.scatter([east for lane, north, east in photos], [north for lane, north, east in photos],
             s=8, color="royalblue", label="Planned photo centres")
axes.plot([0, FIELD_WIDTH_M, FIELD_WIDTH_M, 0, 0], [0, 0, FIELD_LENGTH_M, FIELD_LENGTH_M, 0],
          color="black", linestyle="--", linewidth=2, label="Field boundary")
axes.set_title("Camera-based survey preview\nExample camera, flat ground, 10 m height")
axes.set_xlabel("East from starting point (m)")
axes.set_ylabel("North from starting point (m)")
axes.set_aspect("equal", adjustable="box")
axes.grid(True, alpha=0.2)
axes.legend(loc="upper center", bbox_to_anchor=(0.5, -0.09), ncol=2)
figure.tight_layout()
figure.savefig(output_folder / "camera_coverage.png", dpi=150)

print(f"One photo footprint: {footprint_width:.2f} m east-west x {footprint_length:.2f} m north-south")
print(f"Maximum lane spacing: {lane_spacing:.2f} m")
print(f"Maximum photo spacing along a pass: {photo_spacing:.2f} m")
print(f"Survey lanes: {lane_count}")
print(f"Planned photos: {len(photos)}")
print("Photo centres include the field edges; footprints extend beyond those edges.")
print("These are planned capture locations. No images have been captured.")
print(f"Preview and plan files saved in: {output_folder}")
plt.show()
