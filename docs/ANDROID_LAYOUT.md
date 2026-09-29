# Android layout verification — ORIGIN X / 134028

The Android shell enters immersive fullscreen by default. The toolbar can exit or re-enter it; swiping from an edge temporarily reveals system bars.

A native FrameLayout applies system-bar, display-cutout, gesture, keyboard and rounded-corner insets before sizing the WebView. Insets update on rotation and fullscreen changes. The web interface also respects CSS safe-area variables for browsers. Text remains zoomable; touch targets are at least 44 px. Phones use top navigation in portrait and landscape instead of a fixed sidebar.

## Device acceptance checks

1. Build `KinematiX.apk` with the existing GitHub Actions workflow or a configured Android SDK/JDK machine.
2. Test portrait and both landscape rotations on a punch-hole/notch phone.
3. Verify ORIGIN X, Team ID 134028, all metric labels and the rightmost controls are visible.
4. Enter/exit fullscreen; swipe to reveal system bars and let them hide again.
5. Open the CSV chooser, cancel it, then confirm fullscreen and padding recover.
6. Enable larger system text and test with gesture navigation and three-button navigation.
7. If using an emulator, test developer-option simulated cutouts and a rounded-corner device profile.

Browser viewport checks do not prove native cutout behavior. APK compilation and signature verification passed on 29 September 2026 using JDK 17, Gradle 8.5 and SDK 34. Android lint completed with zero errors and four warnings (three dependency-update notices and a backup-rules notice). Physical-device verification remains pending; no device was connected.

Implementation follows Android's official [immersive-mode](https://developer.android.com/develop/ui/views/layout/immersive), [display-cutout](https://developer.android.com/develop/ui/views/layout/display-cutout) and [rounded-corner](https://developer.android.com/develop/ui/views/layout/insets/rounded-corners) guidance.

## Completed browser checks

- Portrait at 390 × 844: no horizontal page overflow; all buttons at least 44 px high.
- Landscape at 844 × 390 with simulated 44 px left, 24 px right, 28 px top and 24 px bottom safe areas: inspected controls and metrics stay inside the safe horizontal bounds.
- Browser fullscreen enters successfully and exposes an Exit fullscreen control.
- These simulated checks are separate from pending Android hardware verification.

## Local build

Run scripts/Build-Android.ps1 from PowerShell. The script uses the downloaded project-local JDK 17 and Gradle 8.5, builds the web assets, then runs assembleDebug and lintDebug.

Output: android/app/build/outputs/apk/debug/KinematiX.apk

Connect a phone with USB debugging enabled and authorize the computer on the phone before installation. Physical sensor and cutout behavior must still be checked on hardware.
