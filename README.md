# KinematiX

Smartphone inertial navigation and GNSS fusion prototype for **SIH 26168**, developed by **ORIGIN X · Team ID 134028**.

KinematiX combines phone IMU measurements, a learned speed prior and a five-state Extended Kalman Filter to maintain a trajectory during GNSS outages. Training runs on a desktop; live inference and navigation run locally in the Android app.

## Current evidence

The saved development validation suite passes **6/18** blackout windows. The legacy benchmark passes **4/15** and includes training recordings. These suites overlap and must not be combined into an independent pass rate. The below-10% drift requirement is **not consistently achieved**. Physical-phone drift accuracy remains unverified.

The default saved example is a selected passing development-validation run, not a measure of overall performance. All recorded results remain accessible in Evaluation.

## Architecture

```text
Phone accelerometer / gyro / gravity (50 Hz requested)
    -> latest sample forwarding (10 Hz)
    -> motion features + learned speed prior
                                      \
                                       -> five-state EKF -> trajectory + uncertainty
                                      /
GNSS (1 Hz requested) -> fix checks --

Desktop IO-VNBD CSV -> calibration -> Python EKF -> reference-only scoring
Desktop model training -> portable JSON forest -> Android inference
Offline road data -> optional display overlay
```

The EKF tracks east, north, speed, heading and gyro bias. Android navigation is scheduled at 10 Hz. Sensor frequencies are requests, not measured delivery guarantees. Map matching is currently a display overlay and does not correct the EKF. External-IMU 200 Hz operation is not validated.

## Desktop setup

From the project root, with Python and Node.js installed:

```powershell
python -m venv backend/.venv
./backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
cd frontend
npm ci
npm run dev
```

In another terminal, from the project root:

```powershell
./backend/.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Open the Vite address printed by `npm run dev`. Evaluation can connect to `http://127.0.0.1:8000` on the same computer. Desktop automatically checks the local backend; upload a CSV or run a preset directly once it is ready. The manual **Connect server** form appears only in Android.

## Android

The application ID and namespace are `com.originx.kinematix`; Kotlin source is under `android/app/src/main/java/com/originx/kinematix`. The current app version is 5.8.

Install JDK 17, Android SDK Platform 34 / Build Tools 34.0.0, and Gradle 8.5. The build helper accepts `-JavaPath`, `-GradlePath` and `-SdkPath` for local toolchain locations:

```powershell
./scripts/Build-Android.ps1
```

The generated APK is `android/app/build/outputs/apk/debug/KinematiX.apk`. This is a **local build output**, not a file to commit. Build outputs, datasets, virtual environments and local toolchains are ignored by Git.

Grant precise location permission and enable system Location. Start live capture outdoors and wait for a usable GNSS position, speed and heading. The live EKF and sensor display work without the Python server. Raw acceleration includes gravity; approximately 9.8 m/s² on a resting axis is expected. Small gyroscope noise at rest is normal. Capture is foreground-only.

## Connect Android to the desktop evaluation server

Saved examples and live navigation work offline. **Uploading a new CSV requires the Python backend on your laptop**; Python does not run inside the APK.

1. Connect the laptop and phone to the same trusted Wi-Fi network.
2. Start the backend from the project root:

   ```powershell
   ./backend/.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
   ```

3. Run `ipconfig` on the laptop. Find the IPv4 address of the active Wi-Fi adapter, for example `192.168.1.10`. If Windows Firewall prompts, allow Python on your private network. Do not expose this development server to the public internet.
4. In Android, open **Evaluation > Desktop evaluation server**. Enter `http://192.168.1.10:8000`, replacing the example with your laptop's address, and tap **Connect server**. Do not enter `127.0.0.1` or `0.0.0.0` on the phone.
5. After a successful connection check, **Upload CSV · backend required** becomes available. Select a supported IO-VNBD smartphone CSV. It is sent to that laptop for evaluation; the app displays the returned trajectory and metrics.

The address is saved locally. Reconnect after reopening the app. Editing the address disables upload until a new connection check succeeds. If the check fails, verify the backend, address, port, firewall and Wi-Fi client isolation settings. Guest networks may block communication between devices. Saved evaluations remain usable without a connection.

## Dataset and reproducibility

Raw datasets are not committed. The download script retrieves them when needed and verifies SHA-256 hashes and byte sizes against committed manifests:

```powershell
# Synchronized smartphone data used in the development experiments
./backend/.venv/Scripts/python.exe backend/fetch_datasets.py --scope expanded
# Optional full smartphone inventory, including unsynchronized variants
./backend/.venv/Scripts/python.exe backend/fetch_datasets.py --scope all
```

The synchronized collection contains 72 CSVs. The full smartphone inventory contains 241 repository paths resolving to 169 unique file hashes. Different hashes can still contain overlapping drives. This inventory does not include every vehicle file in the upstream repository. Vehicle CAN/odometry is not a model input.

The expanded split uses drivers B/E for training (56 usable recordings), driver A for development validation (6 recordings), and driver D as a reserved test recording. The driver-D recording has already been evaluated and is no longer an untouched blind test. Stationary or invalid recordings are excluded with documented reasons. S-Vw1 is a stationary calibration recording, unsuitable for moving-distance drift scoring.

During blackout replay, GNSS is withheld from the estimator and used afterward for reference scoring. Endpoint drift is endpoint position error divided by reference distance. Windows from the same drive are not independent trials. Calibration uses pre-outage observations. The current model is a portable JSON ExtraTrees speed prior; rejected experimental models are not the deployed model.

See [dataset audit](docs/DATASET_AUDIT.md), [expanded dataset](docs/EXPANDED_DATASET.md), [calibration](docs/V52_CALIBRATION.md), and [experiment log](docs/EXPERIMENT_LOG.md) for details and historical results.

## Checks

```powershell
./backend/.venv/Scripts/python.exe -m unittest discover -s backend/tests -q
./frontend/node_modules/.bin/tsc.cmd frontend/src/engine.ts --outDir .test-build --module commonjs --target es2022 --skipLibCheck
node scripts/test-engine.cjs
node scripts/test-ekf.cjs
```

The Android build helper also runs lint. Python/JavaScript EKF parity checks verify implementation consistency; they do not establish navigation accuracy.

## GitHub APK builds

GitHub Actions runs on pushes to `main` / `master` or manually via **Actions > Build Standalone Android APK > Run workflow**. Download the **KinematiX-debug** artifact from the completed run; its ZIP contains `KinematiX.apk`. The workflow bundles the UI, model and saved report, checks the package and signature, and runs Android lint. It does not publish a GitHub Release or commit the APK. A GitHub-hosted run has not yet been verified for this checkout.

These are debug builds. Release signing is not configured. CI and local debug signing keys can differ; a differently signed APK cannot update an installed copy. Export any sessions you need before uninstalling an existing app, and configure stable signing before distribution.

## Project layout

- `frontend/`: interface, portable model inference and on-device EKF.
- `android/`: native sensor/location bridge and packaged WebView app.
- `backend/`: training, dataset evaluation and Python navigation engine.
- `backend/reports/`: split manifests and experiment evidence.
- `scripts/`: build and verification helpers.
- `docs/`: technical notes, dataset audits and validation limits.

## Remaining work

Reliable below-10% drift across independent drives, real vehicle and mounting validation, on-device CSV replay, robust remount calibration, EKF-integrated road constraints, background operation and 200 Hz external-IMU validation remain open. No lane-level accuracy claim is made.

Dataset attribution: [IO-VNBD](https://github.com/onyekpeu/IO-VNBD). Follow the upstream dataset terms when using or redistributing recordings.

### App address versus API address

Open **http://localhost:5173/** or **http://127.0.0.1:5173/** for the interface. Port **8000** serves the evaluation API, not the interface; its root provides links to the app and API documentation. Restart Vite after configuration updates. `scripts/Start-KinematiX.ps1` starts both services. The development UI binds to all IPv4 interfaces so both local addresses work; use a trusted network.
