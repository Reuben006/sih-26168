# KinematiX 5.2 — receiver initialization correction

The replay adapter now retains receiver speed and bearing. Before each outage, the evaluator checks speed scale against previous displacement intervals and validates bearing convention against previous path headings. Valid receiver measurements initialize velocity and heading at the actual cutoff instead of using stale interval averages. Gyro projection and bias are fitted jointly against pre-outage receiver heading changes. If validation fails, the existing displacement-based initialization remains the fallback.

No receiver speed, bearing, position or reference label from inside the blackout enters the estimator. The leakage regression now poisons all of those post-cutoff fields and confirms identical estimated trajectories.

## Same windows, same threshold

| Suite | Before | After |
|---|---:|---:|
| Expanded development validation | 4/18 passes | 6/18 passes |
| Validation mean endpoint error | 76.984 m | 55.271 m |
| Validation median endpoint drift | 21.222% | 17.181% |
| Legacy suite | 3/15 passes | 4/15 passes |

All failures remain in the app. The <10% target and outage windows were unchanged. The original suite includes training recordings and development recordings; it is not an independent test. These improvements were developed using validation, and no new untouched-test claim is made. Some individual windows regress. The acceleration-fitting experiment was rejected and reverted because it worsened results.

The fix concerns dataset replay initialization. Android already receives speed in m/s and bearing from Android Location; its live EKF uses those to initialize. Better replay numbers do not establish better physical-phone accuracy. The learned model, live EKF, and experimental speed-only propagation remain the 5.2 versions.

Version name stays 5.2 as requested; internal build code is 16. The result is still below the requested reliability target and must not be submitted as a demonstrated all-scenario or lane-level solution.
