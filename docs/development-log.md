# BeltTwin â€” Phase 1

Standalone Isaac Sim 6.1 prototype using only local primitive geometry. Tested
against `6.1.0-rc.26+release.49347.2d230af4.gl` and bundled Python 3.12.13.

## Launch (PowerShell)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\BeltTwin\scripts\run_isaac.ps1 -Script phase1_scene.py
```

The default run demonstrates 65 simulated seconds (over two belt circuits), then
calls `SimulationApp.close()`. Close the application window to finish early.
Startup and shader compilation are additional time. Initial cold compilation
took about five minutes; subsequent smoke startup took about ten seconds.

Shorter or longer runs:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\BeltTwin\scripts\run_isaac.ps1 -Script phase1_scene.py --seconds 90
```

Smoke test:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\BeltTwin\scripts\run_isaac.ps1 -Script phase1_smoke_test.py
```

Encoder tests (no application startup):

```powershell
& 'C:\Isaac Sim\kit\python\python.exe' -B -S C:\BeltTwin\scripts\test_splice_tracker.py
```

The launcher configures the bundled environment and invokes its `python.exe`
directly. It deliberately avoids `python.bat`, which can copy an executable into
the installation. Python bytecode writes are disabled; Kit's portable runtime,
logs and caches are directed into `C:\BeltTwin\data\runtime`. No packages are
installed and extension registry downloads are disabled.

## What Phase 1 demonstrates

- 18 m overall length, 1 m belt width, steel frame and 16 idler rollers.
- Two drums, a top run and return run; animated tread marks follow a closed
  racetrack and drum spokes turn with the belt.
- Five equally spaced colored splice markers, S01â€“S05, with mesh lettering.
  Splices circulate onto the underside, so all five are not on the top at once.
- Orange inspection gate at 14.2 m along the top run (world X = 5.5 m), with
  labeled visual Camera, MFL shoe, Laser head and Encoder wheel representations.
- A semi-transparent, high-contrast viewport HUD with system status, encoder,
  splice status rows and an inspection event card that returns to awaiting mode
  after 2.5 simulation seconds.
- A brief red laser guide and amber station-line flash during each detection;
  the splice marker also brightens and widens while its event is displayed.
- 1280Ã—720 render target and initial window size, single GPU, real-time RTX
  lighting, no external scene assets or textures.

Motion is **kinematic animation**, not a deformable belt/contact simulation.
The encoder uses a fixed 1/30 s simulation step and 1.2 m/s speed. Rendering may
take longer than a simulation step on a busy machine; detection remains tied
to simulation distance. Displayed encoder resolution is 100 ticks/m (10 mm per tick); identification uses
the underlying unquantized distance. Startup has a known zero reference.

Detection uses unwrapped encoder crossings, not vision. It emits exactly one
event per splice centre crossing, even when an update crosses several splices
or loops. `Position: 14.2 m` is the fixed station coordinate. The event card
shows a local station scale of 100 ticks/m (1,420 ticks); the live HUD and CSV
`encoder_m` field show total accumulated belt travel. The station indicator
uses a finite overlap zone.

The device bodies and their names are visual indicators only: there is no camera
image processing, magnetic/MFL model, profile/tension
sensing, health model, historical-inspection database or digital-twin dashboard.
The CSV is only the current run's diagnostic event log.

## Phase 1 files and outputs

| File | Purpose |
|---|---|
| `scripts/phase1_smoke_test.py` | New stage, one cube, 150 updates, shutdown |
| `scripts/phase1_scene.py` | Phase 1 entry point; shared scene runner |
| `scripts/conveyor.py` | Primitive frame, belt, rollers and splice geometry |
| `scripts/splice_tracker.py` | Closed-loop position and deterministic crossings |
| `scripts/inspection_station.py` | Gate and visual inspection camera |
| `scripts/app_config.py` | Lightweight SimulationApp configuration |
| `scripts/run_isaac.ps1` | Bundled Python launcher |
| `scripts/test_splice_tracker.py` | Standard-library tracker tests |
| `project/belttwin.kit` | Minimal local application experience |
| `project/phase1_conveyor.usda` | Exported initial scene; animation requires script |
| `data/phase1_inspections.csv` | Inspection events, overwritten per run |
| `data/phase1_summary.json` | Completion and detection summary, overwritten per run |
| `screenshots/phase1_*.png` | Actual viewport captures, overwritten per run |

Viewport file captures contain only the rendered scene. Additional `phase*_hud_*.png` captures include the native HUD, captured directly from the application window.

## Known startup notes

The initial minimal configuration missed `omni.kit.usd.layers`; this was fixed
locally. A camera helper unavailable in this build was replaced by a native USD
camera. Full extension teardown triggered a Windows access violation in an early
attempt; the working configuration uses SimulationApp's default fast shutdown,
after closing output streams and the stage. Success requires the printed pass
marker and process exit code 0, not merely an opened window.

Non-blocking messages can mention the integrated AMD GPU being skipped,
MaterialX being unavailable, and the disabled crash reporter. The scene uses
the NVIDIA GPU and simple display colors, with no MaterialX assets.

## Original Phase 1 verification

Smoke: 150 updates, `SMOKE_TEST_PASSED`, process exit 0.
Polished Phase 1: 1,080/1,080 frames over 36 simulated seconds; 5 inspections,
covering each of S01â€“S05 once; all event records carried 1,420 calibrated
station ticks; process exit 0. The update loop averaged 23.8 FPS over the run,
excluding startup. Event-card timing was 2.5 simulation seconds. Four viewport
captures (start, first event, middle, end) were visually inspected. The scene
contains 227 prims, including hidden scan/highlight overlays. Startup warnings
were limited to the disabled crash reporter, unavailable-but-unused MaterialX,
and Isaac Sim skipping the integrated AMD GPU in favor of the NVIDIA GPU. The
final run had no USD Fabric, traceback, or error-level log warnings.


## Phase 2 — synchronized synthetic multi-sensor inspection

Launch from PowerShell (65 simulated seconds by default):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\BeltTwin\scripts\run_isaac.ps1 -Script phase2_scene.py
```

Exact acceptance-run command, issued from `C:\BeltTwin`:

```powershell
& .\scripts\run_isaac.ps1 phase2_scene.py --seconds 36 *> data/phase2_run.log
```

The existing conveyor, movement, camera composition and encoder crossing logic
are reused. `scene_runner.py` owns the shared scene lifecycle; `phase1_hud.py`
retains the original Phase 1 presentation. Phase 2 adds only 33 prims (260 total),
including the 24 sensing elements near the belt and a tension-sensor indicator.
The existing inspection camera is aimed at the station and has no render product.

### Data contract and presentation

- One encoder crossing creates one record with a unique `INS-0001`-style ID.
  Camera, MFL, profile and tension each carry that same inspection ID, splice ID
  and exact encoder-crossing simulation time. Render-frame delays do not change
  the recorded crossing position/time.
- Camera score is 0.95; tension score is 0.96. MFL01–MFL24 are deterministic,
  small sinusoidal values about 0.025 in arbitrary normalized units, bounded by
  0.017–0.033. The 16-sample profile has a maximum absolute deviation near
  0.027 mm. All statuses are synthetic NORMAL observations, not diagnostic
  decisions or a learned health model.
- Station position is 14.2 m. `encoder_ticks=1420` preserves the Phase 1 local
  station coordinate at 100 ticks/m. `encoder.travel_m` and `travel_ticks`
  separately record cumulative belt travel at the crossing. The live encoder
  readout shows cumulative travel. These references intentionally differ.
- Sensor statuses cycle READY -> SCANNING (0.6 simulation seconds) -> COMPLETE,
  then return to READY 2.5 simulation seconds after detection. The encoder shows
  ACTIVE / TRACKING / COMPLETE. At lower rendering rates, wall-clock duration
  stretches with simulation time.
- The 24 bars update only when an inspection completes and retain the latest
  completed scan, clearly identified by inspection/splice ID. The fixed chart
  scale is 0–0.05. The splice highlight and station flash reuse Phase 1 geometry.
- Completed records append once to `InspectionSession.inspection_history`.
  This list exists only while the application runs; it resets on every launch.
  Full records print to the console. The acceptance command captures console
  output for test evidence; the application does not save a history database,
  JSON record archive or fingerprints. Its summary file contains metrics only.

### Phase 2 files

| File | Purpose |
|---|---|
| `scripts/phase2_scene.py` | Separate Phase 2 launcher |
| `scripts/scene_runner.py` | Shared stage, animation, event lifecycle, captures and shutdown |
| `scripts/phase1_hud.py` | Extracted original Phase 1 overlay |
| `scripts/phase2_hud.py` | Sensor statuses, inspection card, counter and 24 bars |
| `scripts/camera_sensor.py` | Healthy synthetic camera observation |
| `scripts/mfl_sensor.py` | Deterministic MFL01–MFL24 signals |
| `scripts/profile_sensor.py` | Small profile deviation and 16 samples |
| `scripts/tension_sensor.py` | Healthy synthetic tension observation |
| `scripts/inspection_event.py` | Record assembly, synchronization validation and in-memory history |
| `scripts/test_inspection_event.py` | Multi-loop, shape, synchronization and lifecycle checks |
| `project/phase2_conveyor.usda` | Initial Phase 2 stage; use the launcher for animation/HUD |
| `data/phase2_summary.json` | Latest run's validation metrics |
| `data/phase2_run.log` | Captured acceptance-run console output |
| `screenshots/phase2_hud_*.png` | Start, scanning, complete, ready and end UI captures |

Run the pure-Python checks without starting Isaac Sim:

```powershell
& 'C:\Isaac Sim\kit\python\python.exe' -B -S C:\BeltTwin\scripts\test_inspection_event.py
& 'C:\Isaac Sim\kit\python\python.exe' -B -S C:\BeltTwin\scripts\test_splice_tracker.py
```

### Verified Phase 2 acceptance run

- Successful launch and exit code 0; 1,080/1,080 updates, 36 simulated seconds.
- Five completed records, zero pending: S02, S01, S05, S04, S03 in geometric
  crossing order. All five IDs were checked against belt position.
- Exactly 24 numeric MFL values per record; all four observations synchronized
  to the same inspection/splice/time; all healthy bounds validated.
- Six READY transitions, five SCANNING and five COMPLETE transitions.
- Approximately 25.7 update FPS over 42.06 wall-clock seconds, excluding startup
  and final capture flushing. The application targets 30 FPS.
- HUD and 24 bars checked in application-window captures. Station geometry,
  readable MFL 24-CH label, moving splices and the scan indicator are present.
- Six standard-library tests passed: three sensor/session tests and three
  existing encoder tests, including skipped updates and repeated belt loops.
- Final run had no errors or traceback. Non-blocking startup warnings: disabled
  crash reporter, unused MaterialX unavailable, and integrated AMD GPU skipped.
  Initial UI integration errors were corrected before this acceptance run.
- No packages installed, no installation source/configuration files edited,
  and no Phase 3 functionality added.

Phase 1 regression after the shared-runner extraction also passed: 1,080 frames,
all five splice IDs, 227 prims, approximately 25.6 FPS, exit code 0. The native
Phase 1 HUD was checked in its application capture. Evidence is in
`data/phase1_regression.log` and `data/phase1_summary.json`.


## Phase 3 — create and remember healthy fingerprints

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\BeltTwin\scripts\run_isaac.ps1 -Script phase3_scene.py --seconds 65
```

This uses the same conveyor, station, sensors and view as Phase 2 (260 prims).
The first completed valid healthy observation for each splice becomes its
fingerprint in `data/baseline/S01.json` through `S05.json`. Source inspection ID,
position, station ticks, cumulative encoder information, camera, all 24 MFL
channels, the profile samples/deviation and tension are copied from that record.
The existing Phase 2 healthy synthetic-data validation is reused.

The store loads existing files at startup and never replaces them. Later scans
report `EXISTS / BASELINE PRESERVED`. Sensor readings in an existing baseline
are never updated by a new scan. Returned data and source records cannot mutate
the store through shared lists or dictionaries. A fully written temporary file
is published using a create-only hard link on the project's NTFS volume; another
writer's existing baseline wins. An invalid existing baseline causes a clear
load error while preserving that file, rather than silently replacing it.

The sensor panel remains available. A compact lower panel shows all five
baseline statuses and the active splice's stored details. The existing 24-bar
chart shows the selected inspection's stored healthy MFL fingerprint, labelled
with its splice and source inspection. It does not calculate differences or
combine sensors into a health score. `HEALTHY` describes the source synthetic
observation. Inspection history remains in memory; only the five fingerprints
are persistently stored. Inspection IDs remain local to each run, as in Phase 2;
a baseline retains its original source ID and simulation timestamp.

First-run creation order follows encoder crossings: S02, S01, S05, S04, S03.
A 65-second demonstration observes each splice twice. Once baselines exist,
subsequent launches demonstrate loading and preservation, not recreation.

### Phase 3 files

- `scripts/phase3_scene.py`: Phase 3 entry point.
- `scripts/digital_fingerprint.py`: typed fingerprint schema, deep-copy construction and validation.
- `scripts/fingerprint_store.py`: create-once JSON publication and startup loading.
- `scripts/phase3_hud.py`: baseline status/details and reuse of the Phase 2 chart.
- `scripts/test_digital_fingerprint.py`: completeness, restart, immutability,
  invalid-input, independent-store and copy-isolation tests.
- `data/baseline/S01.json`–`S05.json`: actual healthy per-splice fingerprints.
- `project/phase3_conveyor.usda`: initial scene; launch Python for motion and HUD.
- `data/phase3_run.log`, `data/phase3_restart.log`: captured live-run evidence.
- `data/phase3_acceptance.json`: acceptance results and restart integrity checks.
- `screenshots/phase3_hud_*.png`: application-only UI captures.
- `screenshots/phase3_first_run/`: retained first-run creation captures.

Run every standard-library test with the bundled interpreter:

```powershell
& 'C:\Isaac Sim\kit\python\python.exe' -B -S -m unittest discover -s C:\BeltTwin\scripts -p 'test_*.py' -v
```

The intentionally different S03 observation in the immutability test is test
input only. It proves preservation; no anomaly logic is implemented. Tests use
and clean temporary directories beneath `C:\BeltTwin\data`, never the real
baseline directory. Phase 1 and Phase 2 launch commands remain unchanged.


### Phase 3 acceptance results

All acceptance criteria passed. First launch: 65 simulated seconds, 1,950
frames, 10 inspections, five fingerprints created and five preserved, 25.74 FPS.
Restart: all five loaded, five more inspections, zero replacements, 25.81 FPS.
SHA-256 hashes and file modification times remained unchanged for all five files.
Each saved fingerprint also matched the sensor values from its first completed
inspection in the first-run console log. S03's source was INS-0005.

The independent Phase 2 and Phase 1 GUI regression runs each completed 36
simulated seconds and all five splice detections, with exit code 0. Their native
HUDs were visually checked. All 12 standard-library tests passed. All four GUI
runs exited successfully with no error-level messages or tracebacks. Only the
known startup warnings appeared: unavailable crash reporter, unused MaterialX,
and skipped integrated AMD GPU. No dependencies were installed, no Isaac Sim
installation files were edited, and no Phase 4 functionality was implemented.

Exact GUI acceptance commands, from `C:\BeltTwin`:

```powershell
& .\scripts\run_isaac.ps1 phase3_scene.py --seconds 65 *> data/phase3_run.log
& .\scripts\run_isaac.ps1 phase3_scene.py --seconds 36 *> data/phase3_restart.log
& .\scripts\run_isaac.ps1 phase2_scene.py --seconds 36 *> data/phase3_phase2_regression.log
& .\scripts\run_isaac.ps1 phase1_scene.py --seconds 36 *> data/phase3_phase1_regression.log
```

First-run captures are retained under `screenshots/phase3_first_run/`, including
`phase3_hud_baseline_created_1.png`, `phase3_hud_baseline_created_5.png`,
`phase3_hud_baseline_preserved.png` and `phase3_hud_end.png`. The restart captures
include `screenshots/phase3_hud_start.png` (five loaded before any new inspection)
and `screenshots/phase3_hud_baseline_preserved.png`. Render-only counterparts
without `_hud_` are also generated. `data/phase3_acceptance.json` contains the
full metrics and integrity results; `data/phase3_tests.log` records test output.


## Phase 4 — longitudinal inspection memory

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\BeltTwin\scripts\run_isaac.ps1 -Script phase4_scene.py --seconds 125
```

The default Phase 4 duration is 125 simulated seconds, enough for four completed
inspections per splice. It reuses the Phase 3 scene and sensor generators, with
260 prims and no new sensors, cameras, downloaded assets or dependencies.

### History data and persistence

`data/history/S01.json` through `S05.json` each hold a versioned document with
`splice_id`, `inspection_count` and an ordered `inspections` array. Every
completed observation retains the full Phase 2 record, including all 24 raw MFL
values, channel names, profile samples, camera, tension, encoder and source
simulation time. Metadata adds:

- `inspection_sequence`: contiguous sequence starting at 1 independently for
  each splice. Baselines are separate and are not counted as Phase 4 observations.
- `run_sequence`: deterministic application-run ordinal inferred from persisted
  history; no wall-clock timestamps are used.
- `timestamp_s`: ordered history time. At restart, the origin advances to the
  last persisted crossing time, then adds the new run's exact local crossing time.
  `timestamp_offset_s` records this origin and `simulation_time_s` retains the
  original run-local time, also used by the synchronized sensor observations.
  Unobserved trailing frames and real-world downtime are not added to this clock.
- `baseline_splice_id`: a reference to the separate Phase 3 fingerprint.
- `mfl.channel_count`: 24, alongside the existing raw channel array.

Phase 4 inspection IDs continue after the highest ID found in persisted history
or baseline source IDs. The existing Phase 1–3 launchers retain their run-local
ID behavior. Pre-Phase-4 diagnostic logs are not imported as history, and no
past observations are invented. Completed records alone are appended.

Storage is append-only at the record level. A completion writes one updated
per-splice JSON container through a temporary file, flushes it, then atomically
replaces that history container. All previous observation dictionaries are
retained unchanged. Nothing writes to the baseline directory through this
history module. There are no record update/delete APIs. No files are rewritten
per animation frame. A Windows writer lock prevents simultaneous Phase 4
instances from losing each other's updates. Closing or terminating the process
releases the lock; the tiny `.writer.lock` file can remain on disk.

Invalid, mixed-splice, duplicate or out-of-order history fails validation rather
than being silently discarded or replaced. An interrupted/failed publication
leaves the previously committed JSON intact. Prototype JSON files are tiny;
this implementation rewrites one growing per-splice container per completion,
so it is intended for demonstration-scale history rather than unlimited data.

### History controls

The Phase 2 live inspection card remains at the left. Its counter is labelled
`RUN INSPECTIONS` to distinguish it from persisted per-splice totals.

- **History** shows the selected splice's stored observations and raw camera
  score trend. The table follows the selected observation, showing up to four
  nearby records; the trend shows the latest eight sequence numbers on a fixed
  0–1 scale. The entire history remains available on disk and through navigation.
- **S01–S05** selects a physical splice and turns automatic following off.
- **< Scan / Scan >** navigates its full persisted history. The existing 24-bar
  MFL chart displays that exact stored observation, labelled with inspection ID,
  sequence and timestamp. No channels are discarded or collapsed into a score.
- **Baseline** displays the immutable Phase 3 fingerprint and its original MFL
  values. This switches the view; no difference or anomaly is calculated.
- **Live: ON/OFF** resumes or pauses following the splice currently inspected.

The history panel shows counts for every splice, first/latest inspection IDs,
storage availability and the separate healthy baseline status. Chart colors are
fixed presentation colors. No anomaly, health scoring, degradation, alerting,
machine learning or Phase 5 functionality is implemented.

### Phase 4 files and tests

New code: `scripts/phase4_scene.py`, `inspection_history.py`, `history_store.py`,
`phase4_hud.py`, and `test_inspection_history.py`. The shared scene runner adds
the Phase 4 completion hook. `InspectionSession` accepts an optional inspection
ID offset, with its old behavior unchanged by default.

```powershell
& 'C:\Isaac Sim\kit\python\python.exe' -B -S -m unittest discover -s C:\BeltTwin\scripts -p 'test_*.py' -v
```

Nine history tests cover restart ordering and every sensor field, independent
per-splice sequences, mixed crossing order and unequal counts, copy isolation,
duplicate/out-of-order rejection, invalid input, atomic publication failure,
writer locking, corrupt-file preservation, and baseline hashes/modification
times. Tests use temporary directories inside `C:\BeltTwin\data` and do not
modify the demonstration baselines or history.

The optional `--verify-history-ui` flag exercises the same selection/navigation
methods used by the buttons after the run, checks chart identity, and captures
the latest S03 scan, a previous scan, and the separate S03 baseline. It does not
add observations or alter stored data. Normal users can omit the flag.


### Phase 4 acceptance results

All listed functional acceptance criteria passed. The initial 125-second run
completed 3,750 frames and appended 20 records (four per splice). Restart loaded
all 20 and appended five more, leaving five per splice and 25 total records.
All previous observation dictionaries remained identical. Every persisted record
matched its logged completed-history record, including all 24 MFL values and
all other sensor fields. Per-splice sequences are 1–5; inspection IDs continue
from INS-0006 through INS-0030 without duplication. Baseline SHA-256 hashes and
modification times remained unchanged for all five splice files.

All 21 automated tests passed. The Phase 1, 2 and 3 GUI regression runs each
completed all five splice inspections and exited with code 0. Phase 3 loaded
and preserved all five fingerprints. Both Phase 4 runs also passed the three
history UI checks (latest scan, previous scan and separate baseline). Captures
were visually checked for the table, persisted counts, trend, MFL chart and
baseline details.

Measured Phase 4 performance was 23.01 FPS initially and 20.58 FPS on restart,
excluding startup and final UI checks. The current Phase 1/2/3 control runs were
20.89/21.01/21.09 FPS respectively. The historical approximately 25 FPS was not
reproduced in this session; Phase 4's restart result was close to these controls.
No error-level messages or tracebacks occurred. Only the known startup warnings
appeared: disabled crash reporter, unused MaterialX, and skipped integrated AMD
GPU. No packages were installed, no Isaac Sim installation files were edited,
and Phase 5 was not started.

Exact acceptance commands, from `C:\BeltTwin`:

```powershell
& .\scripts\run_isaac.ps1 phase4_scene.py --seconds 125 --verify-history-ui *> data/phase4_run.log
& .\scripts\run_isaac.ps1 phase4_scene.py --seconds 36 --verify-history-ui *> data/phase4_restart.log
& .\scripts\run_isaac.ps1 phase3_scene.py --seconds 36 *> data/phase4_phase3_regression.log
& .\scripts\run_isaac.ps1 phase2_scene.py --seconds 36 *> data/phase4_phase2_regression.log
& .\scripts\run_isaac.ps1 phase1_scene.py --seconds 36 *> data/phase4_phase1_regression.log
```

Evidence: `data/phase4_acceptance.json`, `data/phase4_tests.log`, the run logs
above, and `project/phase4_conveyor.usda`. The first run's screenshots are retained
in `screenshots/phase4_first_run/`. Restart screenshots include
`phase4_hud_start.png`, `phase4_hud_history_latest.png`,
`phase4_hud_history_previous.png` and `phase4_hud_history_baseline.png` beneath
`screenshots/`. The initial history snapshot and baseline integrity snapshot are
retained in `data/phase4_history_before_restart.json` and
`data/phase4_baseline_before.json` for acceptance evidence. New normal launches
continue appending to the existing history.


## Phase 5 — compare with the original healthy fingerprint

```powershell
Set-Location C:\BeltTwin
& .\scripts\run_isaac.ps1 phase5_scene.py --seconds 36 *> data/phase5_run.log
```

Phase 5 reads the SAME splice's original Phase 3 healthy fingerprint and compares
one completed current observation against it. History provides context and stores
the new raw observation; it is never substituted for the baseline. The detector
is deterministic arithmetic, not AI/ML or electromagnetic simulation. Its output
is anomaly severity only, not a health score or maintenance recommendation.

### Fixed scenario

`phase5_config.py` centralizes scenario and comparison constants. The default is
`--scenario degradation --degradation-level 1`. `--scenario healthy` keeps all
five sensor generators unchanged. Levels from 0 to 1 scale a fixed perturbation;
they do not increase with time or inspection sequence.

Only S03 changes: add 0.035, 0.060, 0.080, 0.060, 0.035 to MFL09–MFL13 respectively;
reduce camera by 0.10 and tension by 0.06; add a small localized profile bump
(peaking at 0.060 mm) to samples 6–10 (zero-based). Profile deviation is recomputed
from the full 16-sample array. All other channels retain the generated readings.
These are controlled synthetic proxy changes, not calibrated physical damage.
The same inputs always give the same result. The pre-existing healthy generator
can vary with inspection index; the added perturbation never progresses.

### Transparent formula

Let `clip(x) = min(1, max(0, x))`, `b` be the 24 baseline MFL values, and `c` the
24 current values. Both vectors must contain exactly 24 finite numbers.

```text
mfl_scale = max(2 * RMS(b), 0.020)
mfl_deviation = clip(RMS(c - b) / mfl_scale)
camera_deviation = clip((baseline_camera - current_camera) / 0.20)
profile_deviation = clip((current_profile_mm - baseline_profile_mm) / 0.10)
tension_deviation = clip((baseline_tension - current_tension) / 0.20)

anomaly_score = clip(
    0.50 * mfl_deviation +
    0.20 * camera_deviation +
    0.20 * profile_deviation +
    0.10 * tension_deviation
)
```

The MFL RMS ratio is dimensionless and scale-invariant above the zero-signal
floor. The factor of two keeps ordinary Phase 2 low-amplitude pattern variation
from dominating the score. Camera/profile/tension spans explicitly convert their
different units to comparable 0–1 deviations. These spans are demonstration
calibrations, not inferred thresholds from history. Improvements in camera or
tension, or reduced profile error, contribute zero rather than negative anomaly.

Severity boundaries are exact: `[0,0.20)` NORMAL; `[0.20,0.40)` WATCH;
`[0.40,0.70)` WARNING; `[0.70,1]` CRITICAL.

The 24 plotted channel deviations are `clip(abs(c[i]-b[i])/mfl_scale)`. Channels
at or above 0.35 are listed in `affected_channels` and highlighted. This is a
separate channel-display threshold, not the overall severity classification.
`mfl_max_channel_index` is one-based; `mfl_max_channel_deviation` retains the raw
absolute difference in original MFL signal units, without clipping. Results also
retain each sensor deviation, weights, weighted contributions, baseline source,
inspection identity and existing sequence/timestamp metadata.

### Architecture and data integrity

New code: `scripts/phase5_scene.py`, `phase5_hud.py`, `phase5_config.py`,
`sensor_scenario.py`, `anomaly_detector.py`, and `test_anomaly_detector.py`.

The existing inspection session accepts an optional record transform. Default
Phase 1–4 generation and its strict healthy-value tests remain unchanged. Phase 5
adds a versioned `synthetic_scenario` metadata field to newly generated records.
The history validator recognizes that extension and validates structure, finite
values, units, encoder identity and synchronized sensor metadata without imposing
the earlier healthy-only fixture bounds. Untagged old records retain their old
validation. Changed sensor observations carry `SYNTHETIC_CHANGE`; the Phase 5
sensor card labels raw values OBSERVED rather than incorrectly marking them NORMAL.

Phase 5 opens `FingerprintStore` in enforced read-only mode and requires all five
existing fingerprints. Its scene never calls `remember()` or creates a baseline.
Completed new observations append through the unchanged atomic HistoryStore write
path. Old records are preserved. Anomaly results are separate run/acceptance
artifacts (`data/phase5_results.json`, `phase5_summary.json`, `phase5_acceptance.json`),
not inserted into old inspection records or used to redefine fingerprints. These
artifacts describe the latest verification run; they are not a new anomaly-history
database. Full raw sensor vectors remain in the appended inspection history.

### Presentation and verification

The Phase 4 history/baseline controls remain available. **Compare / Live** returns
to the comparison view. Selecting S01–S05 shows each splice's latest completed
comparison. The MFL chart shows all 24 normalized differences and highlights the
measured affected channels. The compact panel shows original baseline values,
current values, score/severity, and each deviation multiplied by its weight.
No maintenance instruction or future-phase health engine is present.

The scene automatically captures S03 at inspection completion for
`screenshots/phase5_hud_anomaly.png`, followed by detailed comparison and healthy
splice views at `phase5_hud_mfl_deviation.png` and `phase5_hud_healthy_splices.png`.
Anomaly calculations run once per completed inspection, never per render frame.
Geometry stays at 260 prims; no cameras, RTX sensors, textures or packages were
added. The accepted performance reference is approximately 21 FPS.

Run all tests with the bundled interpreter:

```powershell
& 'C:\Isaac Sim\kit\python\python.exe' -B -S -m unittest discover -s C:\BeltTwin\scripts -p 'test_*.py' -v
```

The 16 new tests cover low healthy scores, fixed S03 changes, unchanged healthy
splices, 24-channel validation on both sides, channel localization independent of
splice name, individual sensor contributions, weights, exact severity boundaries,
determinism, same-splice checks, scale invariance, finite inputs, read-only
fingerprints, and old-history preservation through degraded-record persistence.
The original 21 tests remain unchanged and are included in the 37-test suite.


### Phase 5 acceptance results

Acceptance passed. Final scene: 1,080/1,080 frames, five completed comparisons,
all five splice IDs, 260 prims, clean exit code 0, approximately 20.80 FPS against
the accepted ~21 FPS reference. S01/S02/S04/S05 scored approximately 0.064 and
remained NORMAL. S03 (INS-0040, source fingerprint INS-0005) scored 0.534409 and
classified WARNING. All results were recomputed independently from the persisted
current observation and original baseline, with identical results.

S03 deviations: MFL 0.588419, camera 0.500000, profile 0.551000, tension 0.300000.
Their weighted contributions were 0.294209, 0.100000, 0.110200, 0.030000. Camera
changed 0.95 -> 0.85, profile 0.0269 -> 0.0820 mm, tension 0.96 -> 0.90. Affected
MFL channels were MFL09–MFL13; the largest raw difference was 0.0886 at MFL11.
The score follows these measurements and does not test whether the ID is S03.

All 37 automated tests passed (16 new plus the unchanged 21). Fresh Phase 1,
Phase 2, Phase 3 and Phase 4 GUI regressions each completed five detections with
exit code 0. The Phase 4 regression reloaded the extended raw observations and
passed its latest/previous/baseline browser checks. All baseline SHA-256 hashes
and modification times matched their pre-Phase-5 values. All 25 original history
records remained identical. There are now 40 records, eight per splice: five
new observations from initial validation, five from the final demonstration,
and five intentional additions from the Phase 4 regression. No old record was
rewritten with an anomaly result. Full 24-channel arrays survive persistence.

No error-level messages or tracebacks occurred. Known startup warnings remain:
disabled crash reporter, unused MaterialX and skipped integrated AMD GPU. No
packages were installed or Isaac Sim installation files edited. No progressive
degradation, health engine, maintenance recommendation or Phase 6 was added.

Acceptance evidence: `data/phase5_acceptance.json` contains scores, contributions,
baseline before/after hashes and modification times, history counts/integrity,
all regression metrics and the actual S03 baseline/current sensor values.
`data/phase5_tests.log` contains the 37-test result. Final launch and regression
commands, from `C:\BeltTwin`:

```powershell
& .\scripts\run_isaac.ps1 phase5_scene.py --seconds 36 *> data/phase5_run.log
& .\scripts\run_isaac.ps1 phase4_scene.py --seconds 36 --verify-history-ui *> data/phase5_phase4_regression.log
& .\scripts\run_isaac.ps1 phase3_scene.py --seconds 36 *> data/phase5_phase3_regression.log
& .\scripts\run_isaac.ps1 phase2_scene.py --seconds 36 *> data/phase5_phase2_regression.log
& .\scripts\run_isaac.ps1 phase1_scene.py --seconds 36 *> data/phase5_phase1_regression.log
```

The initial validation is retained in `data/phase5_initial_run.log` and
`data/phase5_initial_summary.json`. Phase 5 screenshots include the active S03
hero (`screenshots/phase5_hud_anomaly.png`), detailed channel deviations
(`screenshots/phase5_hud_mfl_deviation.png`) and healthy splice comparison
(`screenshots/phase5_hud_healthy_splices.png`). The exported initial USD stage is
`project/phase5_conveyor.usda`; launch the Python entry point for live behavior.


## Phase 6 — progressive degradation

Phase 6 runs six controlled S03 inspections through the unchanged Phase 5
`compare_inspection` function. It stops at a measured deterioration trend; no
health score, prediction, maintenance recommendation, AI agent or Phase 7 is included.

`degradation_scenario.py` changes observations only. The six stages HEALTHY,
EARLY, DEVELOPING, MODERATE, ADVANCED and SEVERE use amplitudes
`0, 0.25, 0.55, 0.90, 1.25, 1.60`. S03 numerical sensor values are anchored to
its original healthy fingerprint, eliminating inspection-index variation in this
controlled experiment. Current inspection IDs, time, splice identity and encoder
fields remain those of the actual conveyor passage. Other splices retain the
unchanged healthy generator and are not anchored or degraded.

The Phase 5 localized MFL09–MFL13 bump is multiplied by the amplitude; the other
19 channels retain their baseline values. Camera falls by `0.10 * amplitude`,
tension falls by `0.06 * amplitude`, and the 16 joint profile samples rise by
`0.06 mm * amplitude`. This preserves their shape and raises the measured maximum
monotonically. These are synthetic demonstration values, not calibrated defect
sizes or an electromagnetic model. No severity is assigned by the scenario.
The existing Phase 5 normalization, 50/20/20/10 weights and severity thresholds
remain unchanged.

Each run starts at level 0. Only an S03 inspection advances its level; after
level 5, subsequent S03 scans hold SEVERE. Restarting the demonstration restarts
the scenario, not the history or baseline. History sequence numbers and IDs
continue across runs. The trend therefore groups points by run and must not be
interpreted as continuous degradation across demonstration restarts.

Original healthy fingerprints are opened read-only. Every completed scan appends
to the existing Phase 4 history, with versioned scenario metadata on S03 records.
Untagged healthy and existing Phase 5 records retain their validation contracts.
`data/degradation/run_NNNN.json` stores compact detector-result references with
inspection ID, persistent sequence/time, level, stage, score, severity, deviations
and affected channels; raw sensor observations remain in `data/history/`.
Existing trend files are never replaced. `data/phase6_summary.json` describes the
latest run. An early close saves completed observations but is not acceptance.

The native HUD retains the original-baseline/current comparison and history
browser. Its six-bar S03 trend uses actual detector scores on a fixed 0–1 scale,
with real history sequence numbers and severity colors. “S03 trend” selects the
target; “24-channel deviation” reveals the existing MFL difference chart. Baseline
and History controls remain available. Sensor changes and trend updates occur
only at inspection events, never in the render loop. Geometry remains lightweight.

Launch from PowerShell and leave the window open until it exits automatically:

```powershell
Set-Location C:\BeltTwin
& .\scripts\run_isaac.ps1 phase6_scene.py --seconds 187 *> data/phase6_run.log
```

187 simulated seconds includes six S03 passages (about 183 seconds to the last
passage plus scan completion). At roughly 21 rendered FPS the wall-clock run is
longer because the existing loop advances by 1/30 simulated second per frame.
Use the Python launcher for motion and inspection behavior; the exported
`project/phase6_conveyor.usda` is only the initial stage.

Tests use only the bundled interpreter:

```powershell
& 'C:\Isaac Sim\kit\python\python.exe' -B -S -m unittest discover -s scripts -p 'test_*.py' -v *> data/phase6_tests.log
```

The 16 new tests cover original healthy values, deterministic input-preserving
changes, unchanged non-target splices, 24 channels, localized strict MFL growth,
strict camera/profile/tension and score progression, measured severity progression,
ID/encoder preservation, validation, saturation and run restart, independence
from global inspection index, persisted history reload and compact trend references,
and actual baseline SHA-256/mtime and old-history integrity. The original 37 tests
are unchanged.

Requested presentation images are `screenshots/phase6_hud_progression.png`
(active S03 passage), `screenshots/phase6_hud_trend.png`, and
`screenshots/phase6_hud_s03_degradation.png` (final comparison and trend).

### Phase 6 acceptance results

Acceptance passed: 53 tests (37 existing unchanged, 16 new), six S03 levels,
30 completed inspections, all five splice IDs, 5,610/5,610 frames, and clean exit.
Measured Phase 6 performance: 20.73 FPS against the accepted ~21 FPS reference.
The 260-prim exported stage is byte-for-byte identical to Phase 5.

| Level | Stage | Inspection | Sequence | Score | Severity | MFL | Camera | Profile | Tension |
|---|---|---|---:|---:|---|---:|---:|---:|---:|
| 0 | HEALTHY | INS-0055 | 10 | 0.000000 | NORMAL | 0.000000 | 0.000 | 0.000 | 0.000 |
| 1 | EARLY | INS-0060 | 11 | 0.126139 | NORMAL | 0.127278 | 0.125 | 0.150 | 0.075 |
| 2 | DEVELOPING | INS-0065 | 12 | 0.277505 | WATCH | 0.280011 | 0.275 | 0.330 | 0.165 |
| 3 | MODERATE | INS-0070 | 13 | 0.454100 | WARNING | 0.458199 | 0.450 | 0.540 | 0.270 |
| 4 | ADVANCED | INS-0075 | 14 | 0.630694 | WARNING | 0.636388 | 0.625 | 0.750 | 0.375 |
| 5 | SEVERE | INS-0080 | 15 | 0.807288 | CRITICAL | 0.814576 | 0.800 | 0.960 | 0.480 |

All four normalized sensor deviations and the score strictly increased.
Level 0 has no affected channels; level 1 identifies MFL11; levels 2–5 identify
MFL09–MFL13. MFL11 has the largest difference at every nonzero level.
S01/S02/S04/S05 each completed six NORMAL inspections, with scores below 0.083.
All saved anomaly results were recomputed from persisted observations against
the original fingerprints and matched exactly.

| Live regression | Detections | FPS | Result |
|---|---:|---:|---|
| Phase 1 | 5 | 21.02 | PASS |
| Phase 2 | 5 | 20.96 | PASS |
| Phase 3 | 5 | 20.97 | PASS |
| Phase 4 | 5 | 21.03 | PASS |
| Phase 5 | 5 | 20.92 | PASS |

Phase 4 also passed latest/previous/baseline history-browser checks.
All five baseline SHA-256 hashes and nanosecond modification times are unchanged.
All 40 pre-Phase-6 history records remain identical. The final history has 85
records, 17 per splice. The 45 intentional appends are five from an early-ended
initial run, 30 from the full acceptance run, five from Phase 4 regression and
five from Phase 5 regression. The initial run ended at 34.83 simulated seconds;
it was preserved and was not used as the six-level acceptance demonstration.
Full 24-channel MFL, other sensor values, splice IDs and encoder associations
passed reload validation. Later regression scans are separate from the Phase 6
run-7 trend; the latest raw history scan need not be that trend’s final point.

Acceptance evidence: `data/phase6_acceptance.json`, `data/phase6_summary.json`,
`data/phase6_tests.log`, and `data/degradation/run_0007.json`. The original
integrity snapshot is `data/phase6_before.json`; the early run is retained in
`data/phase6_initial_run.log`, `data/phase6_initial_summary.json`, and
`data/degradation/run_0006.json`. `scripts/verify_phase6.py` checks these recorded
acceptance runs and writes the report. It is tied to this pre-change snapshot;
launching another demonstration appends a new history run and trend artifact.

Known warnings remain: unavailable crash reporter, unused MaterialX extension,
and skipped integrated AMD GPU. One initial Phase 3 regression reported an RTX
shader-cache startup error and Hydra initialization warnings even though its
inspections finished. That attempt was rejected for acceptance and retained as
`data/phase6_phase3_first_attempt.log`. The unchanged Phase 3 command was rerun
successfully, with rendered screenshot verification and no error-level messages.
The accepted Phase 6 run and accepted Phase 1–5 regressions have no error-level
messages or Python tracebacks. No packages were installed and no Isaac Sim
installation files were edited.

Exact live regression commands (each from `C:\BeltTwin`):

```powershell
& .\scripts\run_isaac.ps1 phase1_scene.py --seconds 36 *> data/phase6_phase1_regression.log
& .\scripts\run_isaac.ps1 phase2_scene.py --seconds 36 *> data/phase6_phase2_regression.log
& .\scripts\run_isaac.ps1 phase3_scene.py --seconds 36 *> data/phase6_phase3_regression.log
& .\scripts\run_isaac.ps1 phase4_scene.py --seconds 36 --verify-history-ui *> data/phase6_phase4_regression.log
& .\scripts\run_isaac.ps1 phase5_scene.py --seconds 36 *> data/phase6_phase5_regression.log
```

Phase 6 complete. Phase 7 not started.


## Phase 7 — sensor fusion and splice health

Phase 7 adds an explainable health layer after the existing anomaly detector.
The chain is unchanged Phase 6 `degradation_scenario.py` -> synchronized current
inspection -> immutable original fingerprint comparison (`anomaly_detector.py`)
-> actual same-splice anomaly history -> `health_engine.py` -> health score/state.
It does not predict remaining life, recommend maintenance, use ML/LLMs, create
work orders or begin Phase 8.

### Current condition and history fusion

The Phase 5 detector still owns MFL/camera/profile/tension normalization and the
50/20/20/10 sensor weights. Health consumes its score and exposes its individual
deviations and weighted contributions without independently rescoring sensors.

Let `A` be the current anomaly score and `W` contain the current observation plus
up to four earlier anomaly observations of the SAME splice. Prior anomalies are
recomputed from actual persisted raw inspections using the original healthy
fingerprint. This occurs only on an inspection event. Let `m = mean(W)` and
`s = median(adjacent anomaly differences in W)`.

Direction requires at least three observations and two corroborating changes:

- DEGRADING: `s >= 0.04` and at least two differences are `>= 0.04`.
- IMPROVING: `s <= -0.04` and at least two differences are `<= -0.04`.
- STABLE: otherwise, including insufficient history (explicitly explained).

These are changes per inspection, not rates used for lifetime prediction.
The median and corroboration rule prevent one isolated jump from activating the
additional deterioration penalty. A single unusual scan still affects current
condition and the window mean. Small ordinary healthy variation stays STABLE.

```
clip(x) = min(1, max(0, x))
persistence = mean(W)
penalty = 0.50 * clip(s / 0.20) if direction == DEGRADING else 0
trend_score = clip(persistence + penalty)
historical_trend_health = 1 - trend_score
health_score = 100 * clip(0.70 * (1 - A) + 0.30 * historical_trend_health)
```

`trend_score` is a degradation measure: higher means worse. The window mean
captures persistent abnormality; the bounded penalty captures corroborated
rising anomaly. These explicit constants are demonstration calibration, not
physical failure probabilities. Improving observations can retain a history
penalty until earlier abnormal observations leave the window. With no prior
history, the window contains the current scan alone, so health reduces to
`100 * (1 - A)`. One prior observation supports persistence but not direction.

The existing Phase 6 scenario deliberately restarts at level 0 on every launch.
Therefore health windows are partitioned by `run_sequence` as well as splice ID.
Earlier runs remain fully preserved but are not joined into a false recovery or
degradation trend across that deliberate scenario reset. For a continuous run,
the rolling window naturally spans repeated inspections. Current and previous
observations must reference the same original baseline; it is never the latest
history record. Baseline files remain read-only.

### Health states and evidence

| Health score | Health state |
|---|---|
| 90–100 | HEALTHY |
| 75–<90 | STABLE |
| 50–<75 | DEGRADING |
| 25–<50 | AT RISK |
| 0–<25 | CRITICAL |

Health states are separate from Phase 5 anomaly severities
NORMAL/WATCH/WARNING/CRITICAL. No state is assigned from a degradation level.
`health_engine.py` returns the four sensor deviations/contributions, current
anomaly/severity, trend mean/median/penalty/direction, source inspection IDs,
fusion weights, health-point contributions, health score/state and explanation.
Explanations report actual strongest sensor contribution, evidence sufficiency,
direction and calculated health. No text-generation model is used.

`data_confidence = 0.70 + 0.30 * min(prior_observations, 4) / 4` for validated
complete current evidence. Missing/invalid current evidence, including an
incomplete 24-channel MFL result, is rejected. The value progresses from 70% to
100% as history fills. It is an evidence-completeness rubric, **not statistical
confidence, a probability of safety or AI confidence**.

### Storage and presentation

Each health snapshot is saved once as `data/health/INS-xxxx.json` using exclusive
creation; an existing health file cannot be overwritten. These compact derived
records reference the raw inspection and original fingerprint, without copying
full sensor vectors. Completed raw observations still append through the Phase 4
history store. No old raw record or baseline is modified by health calculations.
The Phase 6 compact degradation artifact is also retained for each run.

`phase7_hud.py` shows the actual S03 health scores falling while their corresponding
anomaly scores rise. It displays health state, trend direction, four sensor
deviations, historical degradation, completeness confidence and the baseline ->
scan -> anomaly -> history -> health chain. The explanation is available on the
fusion-summary tooltip. Baseline, History and Compare views remain accessible;
Health / Live returns to health display. The health graph always identifies S03,
while the comparison panel follows the active splice. Updates occur only when
inspection results arrive, not every render frame.

Launch the full six-level demonstration and leave the window open until it exits:

```powershell
Set-Location C:\BeltTwin
& .\scripts\run_isaac.ps1 phase7_scene.py --seconds 187 *> data/phase7_run.log
```

187 simulated seconds includes six S03 passages; wall-clock duration is longer
at the accepted ~21 FPS because the existing loop advances 1/30 simulated second
per frame. No additional geometry, cameras, RTX sensors, textures or packages
are needed. `project/phase7_conveyor.usda` is the initial stage; the Python entry
point supplies live motion, inspection and health behavior.

```powershell
& 'C:\Isaac Sim\kit\python\python.exe' -B -S -m unittest discover -s scripts -p 'test_*.py' -v *> data/phase7_tests.log
```

The 23 Phase 7 tests cover healthy/severe states, strict progression, meaningful
historical penalties, stable healthy splices, score bounds, exact health/direction
thresholds, isolated jumps, missing/single/full history, completeness confidence,
24-channel requirements, determinism, actual-evidence explanations, documented
fusion and sensor evidence, invalid history mixing/order, persisted-history
adapter and restart scope, baseline hashes/mtimes, old history, and unchanged
Phase 5/6 detector/scenario source. The accepted Phase 6 persisted observations
also reproduce the same health progression. The previous 53 tests are unchanged.

Requested screenshots: `screenshots/phase7_hud_health.png`,
`screenshots/phase7_hud_health_trend.png`, and
`screenshots/phase7_hud_sensor_fusion.png`.

### Phase 7 acceptance results

Acceptance passed: 76 tests (53 unchanged existing tests and 23 Phase 7 tests).
All live Phase 1–6 regressions passed without error-level messages; Phase 6
completed the full six-level progression and Phase 4 passed history navigation.
Phase 7 completed 30 inspections at 23.78 FPS, against the accepted ~21 FPS reference.
Geometry remains byte-identical to Phase 6 (260 prims).

| Level | Inspection | Anomaly | Health | State | Historical degradation | Direction |
|---|---|---:|---:|---|---:|---|
| 0 | INS-0125 | 0.000000 | 100.000 | HEALTHY | 0.000000 | STABLE |
| 1 | INS-0130 | 0.126139 | 89.278 | STABLE | 0.063069 | STABLE |
| 2 | INS-0135 | 0.277505 | 66.132 | DEGRADING | 0.481430 | DEGRADING |
| 3 | INS-0140 | 0.454100 | 50.427 | DEGRADING | 0.592852 | DEGRADING |
| 4 | INS-0145 | 0.630694 | 34.622 | AT RISK | 0.707638 | DEGRADING |
| 5 | INS-0150 | 0.807288 | 16.471 | CRITICAL | 0.900631 | DEGRADING |

Final S03 sensor evidence: MFL 0.814576, camera 0.800, profile 0.960,
tension 0.480. Data confidence is 100% evidence completeness.
All four other splices finish HEALTHY with STABLE trends, at approximately
98.64 health. Saved health results were recomputed identically from raw
history and original fingerprints.

All five baseline SHA-256 hashes and modification times are unchanged.
All 85 pre-Phase-7 history records are identical. There are now 185 raw
records (37 per splice): 30 initial validation scans, 30 visible acceptance
scans, five Phase 4 regression scans, five Phase 5 regression scans and
30 Phase 6 regression scans were intentionally appended. Sixty separate
health snapshots preserve both Phase 7 runs. No old health snapshot was
overwritten. The first Phase 7 run completed while minimized for much of
its duration and is excluded from rendering-performance acceptance.

Evidence: `data/phase7_acceptance.json`, `data/phase7_tests.log`,
`data/phase7_summary.json`, `data/phase7_before.json`, and `data/health/`.
The initial run remains in `data/phase7_initial_run.log` and its summary.
Verification script: `scripts/verify_phase7.py` (recorded-run audit).

Known nonblocking warnings: unavailable crash reporter, unused MaterialX,
and skipped integrated AMD GPU. No packages were installed and no Isaac
Sim installation files were edited. No Phase 8 functionality was added.

Phase 7 complete. Phase 8 not started.
