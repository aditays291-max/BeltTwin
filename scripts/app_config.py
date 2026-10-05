"""Shared lightweight SimulationApp configuration; all runtime output stays local."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]


def launch(headless=False, phase=1):
    from isaacsim import SimulationApp

    runtime = ROOT / 'data' / 'runtime'
    runtime.mkdir(parents=True, exist_ok=True)
    isaac = Path(os.environ['ISAAC_PATH'])
    return SimulationApp({
        'headless': headless, 'width': 1280, 'height': 720,
        'window_width': 1280, 'window_height': 720,
        'renderer': 'RaytracedLighting', 'anti_aliasing': 1,
        'multi_gpu': False, 'limit_cpu_threads': 8,
        'fast_shutdown': True, 'enable_crashreporter': False,
        'extra_args': [
            f'--/app/window/title=BeltTwin | Phase {phase}',
            '--portable-root', str(runtime),
            '--ext-folder', str(isaac / 'extscache'),
            '--/app/settings/persistent=false',
            '--/app/exts/registryEnabled=false',
            '--/app/exts/registryExtensionDownloading=false',
            f'--/log/file={runtime / "kit.log"}',
        ],
    }, experience=str(ROOT / 'project' / 'belttwin.kit'))
