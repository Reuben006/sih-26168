# Technical notes

## Units and coordinates

Python state: `[east_m, north_m, forward_speed_mps, heading_rad, gyro_bias_radps]`. Heading is counter-clockwise from east. Phone GNSS bearing is converted from clockwise-from-north. Latitude/longitude are converted to a local tangent approximation; metres are never added to latitude degrees.

The planar model enforces vehicle-frame no-sideways/no-vertical motion. It is not a complete 3D strapdown INS and is not appropriate for all motorcycle lean or multi-level parking scenarios without extension. The EKF uses Joseph covariance updates, angle-wrapped innovations, shock suppression, speed gating, and a GNSS residual gate. Its uncertainty is not empirically calibrated coverage.

## IO-VNBD adapter

- Requires actual smartphone sensor columns; vehicle-only CSVs and Git LFS pointers are rejected.
- Reads the stated millisecond timestamps and chooses the longest finite, monotonic segment without gaps over one second. Reports retain source/processed counts; additional segments are not silently joined.
- Uses causal previous-sample resampling on a 10 Hz grid.
- Gyro columns are initially ordered roll/pitch/yaw as x/y/z; pre-outage GNSS segment turns fit an effective gyro projection for replay. This calibration is dataset-specific, not proof of arbitrary mount recovery.
- Supplied GNSS coordinates typically change every nine seconds, despite 10 Hz IMU samples. The stated speed unit is inconsistent with coordinate displacement. Speed labels are therefore derived from GNSS displacement/time, not assumed from that column.
- Reference positions are interpolated **for training labels and scoring only**. The estimator starts just after an actual GNSS fix. Initial position, speed, heading and residual calibration use only fixes at or before that time.
- The speed model receives only causal IMU windows. Outage propagation receives no GNSS position or speed. Its learned speed correction is anchored by the latest pre-outage speed residual.
- The baseline keeps the last available speed and integrates the same calibrated yaw rate. It is an explicit baseline, not artificially degraded “raw INS”.
- Endpoint drift is endpoint error divided by integrated reference-path distance. Tiny travelled distances can yield very large percentages; there is no minimum-distance clamp to make scores look better.

## Model

ExtraTrees: 24 trees, depth at most 8, at least 12 examples per leaf. Two-second windows at 10 Hz; mean, standard deviation, RMS and absolute maximum of horizontal acceleration magnitude, vertical acceleration, projected yaw rate and gyro magnitude. Gravity removal precedes feature extraction. All 16 features have identical implementations in Python and JavaScript.

S-M and S-Vw4 fit the model. S-S1 is a **development holdout**: excluded from fitting, but inspected while improving calibration and evaluation. S-Vw1 is a stationary bias recording, not a moving final test. It is excluded only from distance-normalized drive evaluation and audited separately. The fixed outage protocol is documented in the measured JSON. No passing windows are cherry-picked for the summary.

The old pickle is retained only as a historical tracked artifact. No active path loads it. JSON export avoids executable pickle deserialization and reduces runtime dependencies. The phone's sampling and sensor-frame conventions can differ from IO-VNBD; transfer accuracy is unverified.

## Offline map matching

GeoJSON LineString/MultiLineString roads are converted relative to a phone GNSS origin. Candidate projections require distance <20 m and heading disagreement <0.65 rad. Ambiguous distinct candidates are rejected. This is a nearest-segment prototype, not HMM route inference; it ignores one-way restrictions, connectivity and floor level. The marker is a separate overlay and does not feed reference-based scoring.

## External edge contract

Run `python edge_runner.py --speed 10 --heading 0` in the backend directory and provide one JSON object per line on stdin:

```json
{"timestamp":0.0,"yaw_rate":0.01,"forward_acc":0.1}
{"timestamp":0.005,"yaw_rate":0.01,"forward_acc":0.1}
{"timestamp":0.010,"yaw_rate":0.01,"forward_acc":0.1,"gnss":{"east":0.1,"north":0.0,"speed":10,"heading":0,"accuracy":3}}
```

The first timestamp establishes the clock. Inputs require calibration into the vehicle frame. Output is JSONL with position, speed, mode and uncertainty. Missing GNSS is represented by omitting `gnss`. Do not insert reference positions during a blackout.

## Mobile lifecycle and security

Sensor collection is user-initiated and activity-bound. Sensor callbacks are sampled into 10 Hz packets, JSON-encoded and dispatched to the local WebView; a local JSON forest supplies learned speed. No telemetry is uploaded. External links open outside the bridge-enabled WebView. Runtime precise-location permission and sensor availability are checked. Capture stops on pause/destroy. Background use and device timing remain unverified.

## Evaluation API

- `GET /api/health`, `GET /api/model`
- `GET /api/evaluation/preset?preset_id=held_out&duration=30` (also mixed, motorway, test)
- `POST /api/evaluation/upload` — smartphone CSV, at most 80 MB
- `WS /ws/telemetry` — independent synthetic session for each client; JSON actions `outage`, `reset`, `shock`

Uploads use randomized temporary names and cleanup on success/failure. Missing datasets produce errors instead of fabricated scores. The API binds to localhost by default; public hosting would require authentication, rate limiting, and a deployment review.

See [the dataset audit](DATASET_AUDIT.md) for the latest data-quality findings.


## On-device EKF (version 5.0, build 13)
The Android WebView executes the five-state EKF locally in frontend/src/engine.ts. Kotlin supplies IMU and GNSS; no server is required for live fusion. The orange trajectory is the EKF output (including learned speed updates when available), not a separately fabricated curve. Python and JavaScript share state/covariance propagation, Joseph updates, innovation gates and three-fix recovery. Real GNSS accuracy is passed into the phone filter.

Validation: scripts/test-ekf.cjs compares all states, covariance entries and modes over 500 Python-generated steps, with maximum state difference 1.65e-12. This includes an outage, rejected position outlier, shock and recovery. The core engine matches; dataset calibration and phone calibration remain distinct, and the benchmark is still 3/15 passing. No improved field accuracy is claimed.
