# Validation record — KinematiX

Validated locally on 29 September 2026.

## Software checks

- Python: 13 navigation/API regression tests pass, including header-invariant recording identity.
- TypeScript type checking and Vite production build pass.
- JavaScript checks pass: propagation, shock gating, deterministic simulation, blackout/recovery, map distance/heading/ambiguity gates, and Python/JavaScript model parity.
- Browser: local simulation starts/pauses; blackout control changes mode; measured replay renders through the API; saved reports are accessible.
- Responsive browser check: 390 px requested viewport, 375 px content width with no horizontal page overflow; desktop layout checked at 1440 px.
- Edge stepping microbenchmark: 10,000 × 0.005 s updates took 0.150 s on this desktop (0.015 ms/update average). This is not target-device certification.

## Measured dataset suite

3/15 runs below 10% endpoint drift. All passing runs are on a training recording. No independent-drive accuracy claim is established.

| Recording | Split | Outage | Drift | Endpoint error |
|---|---|---:|---:|---:|
| S-S1.csv | development holdout | 10 s | 16.067% | 12.516 m |
| S-S1.csv | development holdout | 30 s | 14.425% | 43.635 m |
| S-S1.csv | development holdout | 60 s | 22.504% | 139.868 m |
| S-S1.csv | development holdout | 10 s | 44.785% | 37.059 m |
| S-S1.csv | development holdout | 30 s | 70.867% | 111.741 m |
| S-S1.csv | development holdout | 60 s | 61.967% | 307.364 m |
| S-S1.csv | development holdout | 10 s | 21.675% | 6.538 m |
| S-S1.csv | development holdout | 30 s | 39.530% | 15.677 m |
| S-S1.csv | development holdout | 60 s | 39.072% | 78.984 m |
| S-M.csv | training recording | 10 s | 493.788% | 15.518 m |
| S-M.csv | training recording | 30 s | 220.000% | 62.628 m |
| S-M.csv | training recording | 60 s | 103.502% | 156.367 m |
| S-Vw4.csv | training recording | 10 s | 2.704% | 8.135 m |
| S-Vw4.csv | training recording | 30 s | 3.135% | 29.245 m |
| S-Vw4.csv | training recording | 60 s | 2.590% | 49.183 m |

S-Vw1 was downloaded from the official Git LFS media endpoint for a post-development test. Its latitude and longitude are constant across all 20,476 rows. The source paper identifies it as a stationary sensor-bias recording. Its exclusion from moving-drive scoring is preserved; a stationary bias check is included in the dataset audit.

Sparse GPS updates, GPS noise, and interpolated reference positions limit the precision of these scores. S-S1 was excluded from model fitting but used during algorithm development. Results must not be advertised as blind final validation.

## Speed model

- Export size: 268,846 bytes.
- S-S1 development-holdout speed MAE: 3.726 m/s; RMSE: 5.075 m/s.
- Constant training-mean baseline MAE: 7.807 m/s.
- Labels derive from GNSS displacement/time because supplied speed units disagree with coordinates.

## Not verified

- Android APK compilation: no JDK/Android SDK installed on this machine. CI workflow and source updated; no APK is claimed.
- Physical Android device, remount recovery, multi-level parking, magnetometer fusion, calibrated uncertainty coverage, battery consumption and long background operation.
- HMM road-graph matching, lane-level accuracy and robust performance on unseen vehicles.

See `backend/reports/benchmark_summary.json` for complete provenance, trajectories and limits.

See [the dataset audit](DATASET_AUDIT.md) for the latest data-quality findings.
