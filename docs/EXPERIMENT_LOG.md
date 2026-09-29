# Additional estimator experiments

The active 5.2 estimator remains receiver-initialized, using the expanded window-weighted speed prior and speed-update-only propagation. Selection uses the unchanged 18 development windows and below-10% threshold.

| Experiment | Passes | Mean endpoint error | Median drift |
|---|---:|---:|---:|
| Active receiver-initialized model | 6/18 | 55.271 m | 17.181% |
| GNSS-anchored temporal speed-change forest | 5/18 | 83.673 m | 20.295% |
| Pre-outage confidence-weighted speed changes | 6/18 | 74.247 m | 19.844% |

Neither candidate was promoted. The temporal forest was trained on 114,232 examples from 52 training recordings whose speed units passed the training-data consistency gate. It uses current/anchor IMU features, elapsed outage time and the last known speed; receiver values inside the scored outage are not model inputs. Full results are in reports/temporal and reports/speed-confidence. Their presence is experiment history, not evidence that they improve the deployed system.

Independent reserved smartphone recordings were not scored or used to tune these experiments. The drift target remains unresolved. Reliable mount calibration, better velocity-change observation and independent reference measurements remain necessary; model changes should continue to be accepted only after measured validation.
