# Expanded IO-VNBD experiment — KinematiX 5.2

Downloaded all 72 synchronized smartphone CSVs (199,120,620 bytes) from the official IO-VNBD repository. Every file matched its Git LFS size and SHA-256. Files are in backend/app/datasets/expanded; source URLs and hashes are recorded in backend/reports/expanded_split.json.

## Split and exclusions

The split was frozen before fitting: drivers B/E train, A validation, D test. Related fragments stay in the same driver group. The adapter accepted 56 training recordings, six validation recordings and one driver-D recording. Nine files could not support the moving-drive loader; each exclusion is in reports/expanded/audit.json. No vehicle CAN/odometry features were used.

## Experiments and selection

Validation uses the same 35%-of-recording anchor and 10/30/60-second outages for every candidate (18 windows). Selection prefers more passing windows, breaking ties using lower median drift. All candidate artifacts are retained.

| Candidate | Validation passes | Median drift | Mean endpoint error |
|---|---:|---:|---:|
| Original two-drive model | 4/18 | 22.093% | 98.6295 m |
| Expanded, equal drive weight | 4/18 | 26.664% | 88.6849 m |
| Expanded, equal window weight | 3/18 | 20.5135% | 77.3732 m |
| Expanded drive weight, speed-update-only | 4/18 | 24.137% | 87.8954 m |
| Selected: expanded window weight, speed-update-only | 4/18 | 21.2215% | 76.9838 m |

The selected model has 32 depth-limited ExtraTrees. Speed-update-only propagation avoids integrating the provisional forward-axis acceleration; speed evolves through learned pseudo-measurements anchored at the last pre-outage GNSS speed. Gyro heading propagation and EKF updates remain active. This does not solve absolute-speed observability, changing mounts, or gyro bias.

## Test integrity and limits

The first expanded experiment selected the original model; its reserved-driver test passed 0/3 with median drift 64.86%. Further development used validation only. A later check of the selected candidate on that SAME driver produced 34.558%, 46.266%, and 49.164% drift: still 0/3. It is explicitly labelled a reused reserved-driver benchmark, not a fresh untouched test. A new external drive is needed for final independent confirmation.

The legacy suite remains 3/15 passing. Some legacy windows regress. The reduction in validation mean error is about 22%, but the pass count is unchanged and no lane-level claim is justified. The app includes every expanded validation result, the reused test results, and the legacy suite.

Build 5.2 includes this candidate for experimental comparison. The original model is preserved in reports/expanded/baseline_model.json. Model and core EKF parity checks and 13 Python tests pass. Neither these tests nor more CSVs certify road performance.

## Reproduction

Run backend/fetch_datasets.py --scope expanded, backend/train_expanded.py, backend/train_expanded_window_weighted.py and backend/compare_calibration.py in that order using backend/.venv. The first training script evaluates the reserved driver only after writing selection.json; subsequent model comparison uses validation only. Do not reinterpret reruns of the reserved driver as untouched testing.


## Full smartphone repository coverage

After the initial synchronized experiment, all 241 smartphone CSV paths in the repository were inventoried: 72 synchronized categorized, 72 synchronized uncategorized, and 97 unsynchronized. These resolve to 169 unique file hashes (563,418,528 bytes), all downloaded and checksum-verified in backend/app/datasets/repository-smartphone. The inventory maps each original path to its hash-named local file. File-hash deduplication is not proof of independent drives.

There are 25 additional recording names (S-A*, S-I, S-T*) not included in the synchronized experiment. They are reserved and have not been trained on or scored; session/driver provenance and timing must be audited first. Synchronized/unsynchronized variants of existing names must never be split across training and testing. Vehicle CSVs and repository ZIP archives were not downloaded as part of this smartphone expansion. This is complete smartphone CSV coverage, not a complete repository mirror.

Version 5.2 APK build and lint passed. Installation was attempted but the phone was disconnected; 5.2 is not verified as installed.
