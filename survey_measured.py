import math
import json
import csv
import time
from datetime import datetime
from pathlib import Path

from pymavlink import mavutil


TARGET_HEIGHT = 10
HOVER_SECONDS = 10

SYSTEM_ID = 1
COMPONENT_ID = 1

GUIDED_MODE = 4
LAND_MODE = 9

# Load the survey destinations before connecting or starting flight.
plan_path = Path(__file__).resolve().parent / "plans" / "survey_plan.csv"
survey_destinations = []

with plan_path.open("r", newline="", encoding="utf-8-sig") as plan_file:
    reader = csv.DictReader(plan_file)

    for row in reader:
        north = float(row["north_m"])
        east = float(row["east_m"])

        if not math.isfinite(north) or not math.isfinite(east):
            raise SystemExit("The plan contains an invalid coordinate.")

        survey_destinations.append((north, east))

if len(survey_destinations) < 2:
    raise SystemExit("The survey plan needs at least two points.")

if survey_destinations[0] != (0.0, 0.0):
    raise SystemExit("This exercise expects the first point to be (0, 0).")

print(f"Loaded {len(survey_destinations)} points from {plan_path.name}")

connection = mavutil.mavlink_connection(
    "udpin:127.0.0.1:14600",
    source_system=245,
    source_component=191,
)

# Create a separate recording for this automated flight.
project_folder = Path(__file__).resolve().parent
log_folder = project_folder / "logs"
log_folder.mkdir(exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
log_path = log_folder / f"measured_flight_{timestamp}.csv"

csv_file = log_path.open("x", newline="", encoding="utf-8")
writer = csv.writer(csv_file)

writer.writerow([
    "received_at",
    "autopilot_time_s",
    "latitude_deg",
    "longitude_deg",
    "relative_altitude_m",
    "sea_level_altitude_m",
    "phase",
    "destination",
])
csv_file.flush()

print(f"Recording this flight to:\n{log_path}")

# Send a command with up to seven parameters.
def send_command(command, *parameters):
    values = list(parameters)
    values.extend([0] * (7 - len(values)))

    connection.mav.command_long_send(
        SYSTEM_ID,
        COMPONENT_ID,
        command,
        0,
        *values,
    )


# Read autopilot messages and save every position update we receive.
def receive_message(message_type, timeout):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        message = connection.recv_match(
            blocking=True,
            timeout=1,
        )

        if message is None:
            continue

        if (
            message.get_srcSystem() != SYSTEM_ID
            or message.get_srcComponent() != COMPONENT_ID
        ):
            continue

        if message.get_type() == "GLOBAL_POSITION_INT":
            writer.writerow([
                datetime.now().astimezone().isoformat(
                    timespec="milliseconds"
                ),
                message.time_boot_ms / 1000,
                message.lat / 10_000_000,
                message.lon / 10_000_000,
                message.relative_alt / 1000,
                message.alt / 1000,
                phase,
                active_destination,
            ])
            csv_file.flush()

        if message.get_type() == message_type:
            return message

    raise TimeoutError(f"No {message_type} received.")


# Wait for a heartbeat confirming a particular state.
def wait_for_state(description, condition, timeout=15):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        heartbeat = receive_message("HEARTBEAT", 3)

        if condition(heartbeat):
            print(description)
            return

    raise TimeoutError(f"Not confirmed: {description}")


def is_armed(heartbeat):
    return bool(
        heartbeat.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED
    )


def set_mode(mode):
    send_command(
        mavutil.mavlink.MAV_CMD_DO_SET_MODE,
        mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
        mode,
    )

def fly_to_offset(north_m, east_m, origin_lat, origin_lon):
    # Approximate Earth as a sphere for this small local exercise.
    earth_radius = 6_378_137.0
    origin_lat_rad = math.radians(origin_lat)

    target_lat = origin_lat + math.degrees(north_m / earth_radius)
    target_lon = origin_lon + math.degrees(
        east_m / (earth_radius * math.cos(origin_lat_rad))
    )

    print(f"Flying to North={north_m} m, East={east_m} m")

    connection.mav.set_position_target_global_int_send(
        0,
        SYSTEM_ID,
        COMPONENT_ID,
        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
        3576,
        round(target_lat * 10_000_000),
        round(target_lon * 10_000_000),
        TARGET_HEIGHT,
        0, 0, 0,
        0, 0, 0,
        0, 0,
    )

    deadline = time.monotonic() + 60
    consecutive_arrivals = 0

    while time.monotonic() < deadline:
        heartbeat = receive_message("HEARTBEAT", 3)

        if not is_armed(heartbeat) or heartbeat.custom_mode != GUIDED_MODE:
            raise RuntimeError("Vehicle left the expected Guided flight state.")

        position = receive_message("GLOBAL_POSITION_INT", 3)

        current_lat = position.lat / 10_000_000
        current_lon = position.lon / 10_000_000
        altitude = position.relative_alt / 1000

        north_error = math.radians(target_lat - current_lat) * earth_radius
        east_error = (
            math.radians(target_lon - current_lon)
            * earth_radius
            * math.cos(origin_lat_rad)
        )

        distance = math.hypot(north_error, east_error)
        altitude_error = abs(altitude - TARGET_HEIGHT)

        print(
            f"Distance remaining: {distance:.2f} m | "
            f"Altitude: {altitude:.2f} m"
        )

        if distance <= 1.0 and altitude_error <= 0.5:
            consecutive_arrivals += 1
        else:
            consecutive_arrivals = 0

        if consecutive_arrivals >= 3:
            print("Destination reached.")
            return

    raise TimeoutError("Destination was not reached within 60 seconds.")

flight_started = False
phase = "SETUP"
active_destination = 0
completed = False

try:
    print("Connecting to the simulated autopilot...")
    heartbeat = receive_message("HEARTBEAT", 20)

    if is_armed(heartbeat):
        raise RuntimeError("Start this exercise with the simulator disarmed.")

    print("Requesting Guided mode...")
    set_mode(GUIDED_MODE)
    wait_for_state(
        "Guided mode confirmed.",
        lambda heartbeat: heartbeat.custom_mode == GUIDED_MODE,
    )

    # Request altitude updates twice per second.
    send_command(
        mavutil.mavlink.MAV_CMD_SET_MESSAGE_INTERVAL,
        mavutil.mavlink.MAVLINK_MSG_ID_GLOBAL_POSITION_INT,
        500_000,
    )

    # Confirm position telemetry is available before arming.
    position = receive_message("GLOBAL_POSITION_INT", 5)
    print(f"Initial relative altitude: {position.relative_alt / 1000:.2f} m")

    # Capture the origin before arming and preserve the exact plan for plotting.
    origin_lat = position.lat / 10_000_000
    origin_lon = position.lon / 10_000_000
    print(f"Survey origin: {origin_lat:.7f}, {origin_lon:.7f}")

    executed_plan_path = log_folder / f"measured_plan_{timestamp}.csv"
    with executed_plan_path.open("x", newline="", encoding="utf-8") as plan_file:
        plan_writer = csv.writer(plan_file)
        plan_writer.writerow([
            "point", "north_m", "east_m", "origin_lat_deg",
            "origin_lon_deg", "target_altitude_m",
        ])

        complete_route = survey_destinations + [(0.0, 0.0)]
        for point_number, (north, east) in enumerate(complete_route):
            plan_writer.writerow([
                point_number, north, east, origin_lat, origin_lon, TARGET_HEIGHT,
            ])

    print(f"Plan for this flight saved to: {executed_plan_path}")

    phase = "ARMING"
    print("Requesting arming...")
    flight_started = True
    send_command(mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 1)
    wait_for_state("Arming confirmed.", is_armed)

    phase = "TAKEOFF"
    print(f"Requesting takeoff to {TARGET_HEIGHT} m...")
    send_command(
        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        0, 0, 0, 0, 0, 0, TARGET_HEIGHT,
    )

    climb_deadline = time.monotonic() + 60

    while time.monotonic() < climb_deadline:
        position = receive_message("GLOBAL_POSITION_INT", 5)
        altitude = position.relative_alt / 1000
        print(f"Climbing: {altitude:.2f} m")

        if altitude >= TARGET_HEIGHT - 0.5:
            print("Reached the target altitude band.")
            break
    else:
        raise TimeoutError("Target altitude was not reached within 60 seconds.")

    phase = "HOVER"
    print(f"Hovering for {HOVER_SECONDS} seconds...")
    hover_deadline = time.monotonic() + HOVER_SECONDS

    while time.monotonic() < hover_deadline:
        heartbeat = receive_message("HEARTBEAT", 3)

        if not is_armed(heartbeat) or heartbeat.custom_mode != GUIDED_MODE:
            raise RuntimeError("The vehicle left the expected Guided flight state.")

        position = receive_message("GLOBAL_POSITION_INT", 3)
        print(f"Hover altitude: {position.relative_alt / 1000:.2f} m")


    print("Starting the survey route...")

    for point_number, (north_m, east_m) in enumerate(
        survey_destinations[1:],
        start=1,
    ):
        active_destination = point_number
        previous_north, previous_east = survey_destinations[point_number - 1]
        phase = "SURVEY_PASS" if abs(east_m - previous_east) < 0.000001 else "CONNECTOR"
        print(f"Survey point {point_number} of {len(survey_destinations) - 1}")
        fly_to_offset(north_m, east_m, origin_lat, origin_lon)

    phase = "RETURN"
    active_destination = len(survey_destinations)
    print("Survey passes completed. Returning to the starting point...")
    fly_to_offset(0, 0, origin_lat, origin_lon)

    print("Return completed. Preparing to land.")

    phase = "LANDING"
    print("Requesting landing...")
    set_mode(LAND_MODE)
    wait_for_state(
        "Land mode confirmed.",
        lambda heartbeat: heartbeat.custom_mode == LAND_MODE,
    )

    wait_for_state(
        "Landing complete: autopilot is disarmed.",
        lambda heartbeat: not is_armed(heartbeat),
        timeout=90,
    )

    flight_started = False
    completed = True
    print("SUCCESS: survey route, return and landing completed.")

except (Exception, KeyboardInterrupt) as error:
    print(f"\nSequence stopped: {error}")

    if flight_started:
        phase = "RECOVERY"
        print("Requesting Land mode for recovery...")

        try:
            set_mode(LAND_MODE)
            wait_for_state(
                "Recovery complete: autopilot is disarmed.",
                lambda heartbeat: not is_armed(heartbeat),
                timeout=90,
            )
        except (Exception, KeyboardInterrupt):
            print("Recovery could not be confirmed.")
            print("Select LAND in Mission Planner and monitor the simulator.")

finally:
    csv_file.close()
    connection.close()
    result_path = log_folder / f"measured_result_{timestamp}.json"
    result_path.write_text(json.dumps({"completed": completed}, indent=2), encoding="utf-8")
    print(f"Flight recording saved to:\n{log_path}")