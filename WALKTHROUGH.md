# Desktop verification and video walkthrough

## Before recording

1. Follow the README installation steps and run `python main.py`.
2. Resize the desktop window so the full control panel, telemetry, graph, and map fit. A 1440×900 or larger desktop is convenient.
3. Wait for the offshore OpenStreetMap tiles to load in the Marine navigation panel. If the map says it is unavailable, check the internet connection and wait for its 30-second retry interval. Ensure tiles are actually visible before recording. Check the offshore coordinates, north arrow, launch range rings, metre scale, vehicle depth/heading label and attribution. Move the ROV more than 1 m to see its real simulated track; do not describe the rings as bathymetry or a geofence.
4. Confirm that the application opens disarmed, with Manual mode selected and zero displayed thrust.
5. Arm in Manual mode. Hold W, D, F and E separately; check that position, depth and heading respond. Release each control. Check Q, A, R and S for the opposite direction.
6. Click Disarm while moving. Verify that every displayed thrust component becomes exactly zero. Brief coasting is expected.
7. Rearm. Leave Manual idle for more than one second; check the idle/zero-thrust status. Hold a movement button, move focus to another application, and confirm input clears.
8. Select Depth Hold, set 8 m, and allow time for depth to approach 8 m. Check the dashed target line and response trace. Disarm and verify zero thrust.
9. Arm in Heading Hold and set 120°. Confirm the heading approaches the target. Test 359° then 1° to see a short turn across north.
10. Test CSV recording. Save to a writable file, run several seconds, stop, and open it in a spreadsheet. Check headers and changing telemetry values.
11. Press Escape and confirm disarm. Check both map zoom buttons. Close and relaunch once to check a clean startup.

These are manual verification steps to perform locally; they were not executed in the generation environment.

## Record the requested interface walkthrough

Use your desktop recorder and capture the **application window only**, as requested by the PDF. A 60–90 second recording is sufficient unless the recruiter specifies otherwise.

| Time | Show | Suggested explanation |
| --- | --- | --- |
| 0–15 s | Full ABYSS dashboard | “This is a native Qt desktop ground station for a simulated underwater vehicle.” |
| 15–30 s | Armed state, mode and telemetry cards | “The dashboard displays armed state, mode, depth, heading or yaw, roll, pitch, and battery voltage.” |
| 30–45 s | Arm/Disarm, mode selector and target inputs | “The operator can choose Manual, Depth Hold or Heading Hold, and set the corresponding target.” |
| 45–60 s | Live depth graph | “The depth history shows measured depth against time; Depth Hold adds a target reference.” |
| 60–75 s | OpenStreetMap and location footer | “The embedded map follows the position estimated from simulated motion.” |
| 75–90 s | Full window, end disarmed | “Keyboard controls, response delay, drag, and safety logic are implemented separately from the interface.” |

Movement, hold convergence and watchdog behavior do not need to be demonstrated in the video. The PDF explicitly says this is an interface walkthrough; prepare to explain the implementation at interview.

## Be ready to explain

- Why Python/PySide6 was chosen and how it remains a native desktop application.
- Why the simulation and interface are separate files.
- How requested thrust differs from actual thruster output and vehicle velocity.
- Why disarming bypasses thruster lag but does not instantly stop existing velocity.
- How the one-second Manual watchdog works and why hold modes continue automatically.
- Why PD control uses both target error and velocity.
- How heading wrapping handles turns across north.
- Why network downloads are asynchronous and telemetry refresh runs slower than physics.
- Why the map position is simulated rather than GPS, and what happens offline.
- Which parts are approximations: neutral buoyancy, simplified roll/pitch, battery drain and local coordinate conversion.
- How to change a gain, timer interval, launch location or visual style.
- How Codex assisted and which checks you personally completed.

## Submission checklist

- [ ] Application launches from the documented setup commands.
- [ ] All nine simulation tests pass locally.
- [ ] Dashboard and controls have been checked on a real desktop.
- [ ] OSM tiles and visible attribution appear in the video.
- [ ] Video shows all required telemetry and controls.
- [ ] README includes accurate AI tool disclosure.
- [ ] You can explain and modify every submitted source file.
- [ ] Source and recording are included; virtual environment and caches are excluded.
