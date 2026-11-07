# Survey Simulation Results

## Scope and evidence

This summary records results from a Windows-based ArduCopter SITL survey application using Python and pymavlink. Values and run IDs were transcribed from terminal reports and screenshots produced during development. The raw logs have not been independently reprocessed for this document.

The mission covers a 30 m by 20 m rectangular field with seven survey passes at a 10 m home-relative altitude. Camera calculations assume flat ground, a downward-facing camera, and fixed east/north footprint axes. Photo events are software records, not images or confirmed physical exposures.

## 1. Tracking measurement

Run ID: `20261108_024444_549959`

| Measurement | Reported value |
|---|---:|
| Flight sequence completed | True |
| Recorded position samples | 278 |
| Recording duration, including setup and landing | 138.5 s |
| Survey passes represented | 7 of 7 |
| Samples included in error calculation | 56; eight per pass |
| Mean absolute cross-track error | 0.046 m |
| Cross-track RMSE | 0.054 m |
| Maximum sampled cross-track error | 0.095 m |
| Mean absolute altitude error | 0.007 m |
| Maximum sampled altitude error | 0.023 m |
| Final recorded horizontal offset from origin | 0.045 m |

Error metrics use the middle 80% of each labelled straight survey pass, at approximately 2 Hz telemetry. They exclude turn overshoot, connectors, takeoff, landing, and return. They measure simulated path tracking, not map accuracy. Unsampled peaks may be larger.

Evidence: `logs/measured_flight_20261108_024444_549959.csv` and `reports/survey_metrics_20261108_024444_549959.txt`, with the matching executed plan and result JSON.

## 2. Baseline photo-event spacing

Run ID: `20261108_025808_554458`

The baseline trigger used the nominal maximum spacing, approximately 1.657 m, as its threshold. Position updates could arrive after the threshold had been crossed.

| Measurement | Reported value |
|---|---:|
| Simulated photo events | 119 |
| Largest observed along-pass gap | 2.004 m |
| Minimum estimated forward overlap | 75.8% |
| Intended forward overlap | 80% |

The flight completed, but the measured event spacing did not meet the intended overlap requirement under the ideal camera model. The preview's planned photo count is not directly interchangeable with the event count: the preview includes endpoints, while the event generator does not force endpoint captures.

Evidence: `reports/photo_report_20261108_025808_554458.txt` and matching `logs/photo_*` files.

## 3. Improved trigger and repeatability

The improved trigger subtracts an experimental 0.40 m margin from the nominal 1.656854 m spacing limit. Its threshold is approximately 1.256854 m. Actual recorded gaps are still checked against the original planning limit, not against the shorter trigger threshold.

| Run | Run ID | Maximum gap | Minimum estimated overlap | Exceedances / checked intervals | Check |
|---|---|---:|---:|---:|---|
| 1 | `20261108_030711_020785` | 1.603 m | 80.7% | 0 / 147 | PASS |
| 2 | `20261108_031328_614112` | 1.625 m | 80.4% | 0 / 147 | PASS |
| 3 | `20261108_031733_046652` | 1.603 m | 80.7% | 0 / 147 | PASS |

All seven passes contained sufficient events for interval checks. Across the three runs, no observed interval exceeded the nominal spacing limit: **0 of 441**. The worst maximum gap across these runs was 1.625 m, approximately 0.032 m below the nominal limit.

These results demonstrate three successful repetitions under the tested settings. The small remaining margin and limited test set do not establish a guarantee under changed speed, delays, wind, or hardware conditions. The overlap estimate does not prove full field coverage or image quality.

Evidence: `reports/photo_report_<run ID>.txt`, with matching `logs/photo_flight_<run ID>.csv`, `photo_events_<run ID>.csv`, `photo_plan_<run ID>.csv`, and `photo_result_<run ID>.json`.

## 4. Keyboard-interruption recovery

Run ID: `20261108_032315_402825`

Procedure: start the improved survey script, wait until it is flying the first survey pass, and press Ctrl+C once while leaving the application and SITL running.

Observed outcome:

- The application stopped the normal sequence after 16 simulated photo events.
- It requested LAND for recovery.
- The terminal reported that the autopilot was disarmed.
- Flight and event logs were saved.
- The result JSON contained `"completed": false`, `"photo_events": 16`, and `"trigger_margin_m": 0.4`.

**Result: the handled keyboard-interruption test passed.** The interrupted survey was correctly retained as incomplete. Successful recovery is distinct from successful completion of the survey.

Evidence: terminal screenshot and `logs/photo_result_20261108_032315_402825.json`, plus matching flight and event CSVs. The JSON completion flag alone does not independently certify recovery; the disarm confirmation was observed in terminal output.

## Conclusions

The application demonstrated automated survey execution, timestamped telemetry logging, measurable path tracking, simulated capture decisions, an empirically improved capture-spacing rule, and a handled interruption with preserved records.

The strongest supported capture-spacing statement is: **three repeated SITL runs produced no spacing exceedances among 441 checked within-pass event intervals, under the fixed ideal camera assumptions.**

These tests do not establish real-world survey accuracy, real camera performance, general failsafe behaviour, or readiness for autonomous physical flight. Communication loss, sudden process termination, hardware operation, terrain variation, and real imagery remain outside the validated scope.
