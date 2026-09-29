# Dataset and calibration audit

ORIGIN X · Team 134028 · KinematiX

## Findings

1. **Sampling is approximately 10 Hz.** Elapsed-time increments agree with the date column. S-M resets its elapsed clock at zero-based source row 44,226; the current adapter retains the longest continuous segment. This is not a 100 Hz recording.
2. **Coordinate changes occur about every nine seconds in the three driving files.** The paper specifies nominal 1 Hz GNSS. Coordinate-change cadence is not proof of actual receiver update cadence, especially when stationary. Interpolating these coordinates cannot establish lane-level accuracy.
3. **The speed-unit inconsistency is supported by the data, but not resolved by documentation.** For moving intervals, displacement/time divided by the raw speed value is close to one. The column header and paper say km/h. We retain GNSS-displacement labels and do not silently reinterpret all speed columns as m/s.
4. **S-Vw1 is intentionally stationary.** Table A4-1 of the source paper identifies it as a sensor-bias recording. It is useful for stationary calibration tests, but distance-normalized drift is undefined for a zero-distance drive. The earlier description of this file as unusable/defective was too broad.
5. **S-S1 data rows match the official file byte-for-byte.** The checksum difference comes entirely from a header encoding change. Known-drive classification now includes a versioned numeric-stream fingerprint, preventing renamed/re-encoded known data from being labelled unseen.
6. **AI corrections are helpful but not consistently best.** In the fixed 15-window audit, AI-on improves endpoint error over AI-off in 11 runs and over constant-speed + calibrated gyro in 9 runs. This does not mean those runs meet the SIH target.
7. **Mount calibration is still provisional.** Fitted gyro-projection vectors are not a validated physical rotation matrix; sensor axes must be verified before transferring the model to arbitrary phone mounts. The current estimated forward axis and fixed speed residual can become unreliable through stops and turns.

## Recording checks

| Recording | IMU interval | Clock resets | Coordinate-change interval | Displacement/raw-speed ratio |
|---|---:|---:|---:|---:|
| S-M.csv | 0.100 s | 1 | 9.0 | 0.9945295211563917 |
| S-S1.csv | 0.100 s | 0 | 9.0 | 0.9659475784124019 |
| S-Vw4.csv | 0.100 s | 0 | 9.0 | 0.9984732613041756 |
| S-Vw1.csv | 0.100 s | 0 | None | None |

## Controlled estimator comparison

| Recording | Outage start | Duration | AI-on endpoint | AI-off endpoint | Constant-speed endpoint |
|---|---:|---:|---:|---:|---:|
| S-S1.csv | 1045.1s | 10s | 12.52m | 77.60m | 71.91m |
| S-S1.csv | 1045.1s | 30s | 43.63m | 295.35m | 281.88m |
| S-S1.csv | 1045.1s | 60s | 139.87m | 597.48m | 570.37m |
| S-S1.csv | 1817.1s | 10s | 37.06m | 7.16m | 14.70m |
| S-S1.csv | 1817.1s | 30s | 111.74m | 333.35m | 72.34m |
| S-S1.csv | 1817.1s | 60s | 307.36m | 1435.10m | 190.77m |
| S-S1.csv | 3371.1s | 10s | 6.54m | 54.23m | 19.08m |
| S-S1.csv | 3371.1s | 30s | 15.68m | 152.24m | 106.31m |
| S-S1.csv | 3371.1s | 60s | 78.98m | 260.45m | 170.02m |
| S-M.csv | 1843.9s | 10s | 15.52m | 23.01m | 23.01m |
| S-M.csv | 1843.9s | 30s | 62.63m | 49.98m | 49.98m |
| S-M.csv | 1843.9s | 60s | 156.37m | 6.15m | 6.16m |
| S-Vw4.csv | 4429.0s | 10s | 8.13m | 8.18m | 2.51m |
| S-Vw4.csv | 4429.0s | 30s | 29.25m | 29.16m | 37.74m |
| S-Vw4.csv | 4429.0s | 60s | 49.18m | 88.07m | 79.86m |

## Next implementation priorities

- Validate the gyro/body-frame mapping using controlled known rotations and synchronized vehicle-reference recordings. Do not tune it against final test trajectories.
- Estimate stationary bias from an initial calibration interval and validate residuals on the remainder. S-Vw1 is reserved for this purpose.
- Replace the fixed speed residual and weakly observed forward-axis estimate with confidence-weighted corrections. Evaluate improvements on development recordings before freezing a new model.
- Obtain a moving, never-used final test recording and higher-rate reference before making independent-drive or lane-level claims.

## Reproduce

From `backend`: `python audit_dataset.py --archive <IO-VNBD-master-directory>`.

The audit writes `reports/dataset_audit.json`. It performs no model fitting or hyperparameter search. Existing 15-run accuracy scores are unchanged.

[Primary dataset paper](https://pure.coventry.ac.uk/ws/portalfiles/portal/40741559/Binder8.pdf): sampling and units in Sections 2.2/Table 5; stationary S-Vw1 in Table A4-1.
