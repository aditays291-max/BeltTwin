# Contributing to BeltTwin

Keep changes small, explainable and reproducible. Run
`python -B -S scripts/run_tests.py` on Windows before proposing a change.

## Invariants

- Never replace the original files in `data/baseline/`.
- Preserve every earlier raw history record and health snapshot.
- Keep all 24 MFL channels and correct splice/encoder associations.
- Reuse the anomaly detector and degradation scenario rather than creating
  competing formulas or hard-coded per-level health classifications.
- Keep sensor observations explicitly synthetic until hardware validation exists.
- Keep rendering lightweight; perform analysis only at inspection events.
- Never modify the Isaac Sim installation or add dependencies casually.

## Commits and evidence

Use accurate messages describing the change, such as
`fix: validate inspection identity before persistence` or
`test: cover missing history in health scoring`.
Do not backdate commits, invent benchmark results or present planned work as
implemented. The initial repository commits import an existing local prototype;
they are not a reconstruction of its earlier development chronology.

## Verification levels

The GitHub Actions job tests deterministic Python logic. Live rendering,
performance and visual HUD verification require the separately installed Isaac
Sim runtime and compatible GPU. Report these checks separately.

Raw runtime logs are local outputs. Recorded acceptance JSON files provide the
published evidence; the workstation audit scripts additionally expect their
original local run logs. Launching another scene appends a new demonstration run.
