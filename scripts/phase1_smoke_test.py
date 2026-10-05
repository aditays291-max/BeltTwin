"""Launch a separate Isaac Sim window, render one cube, and close."""
import time
import traceback
from app_config import launch

app = launch()
exit_code = 0
try:
    import omni.usd
    from pxr import Gf, UsdGeom, UsdLux
    from omni.kit.viewport.utility import get_active_viewport

    omni.usd.get_context().new_stage()
    stage = omni.usd.get_context().get_stage()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    cube = UsdGeom.Cube.Define(stage, '/World/Cube')
    cube.CreateSizeAttr(1.0)
    cube.CreateDisplayColorAttr([(0.1, 0.6, 0.9)])
    UsdLux.DomeLight.Define(stage, '/World/Light').CreateIntensityAttr(700)
    camera = UsdGeom.Camera.Define(stage, '/World/View')
    matrix = Gf.Matrix4d().SetLookAt(Gf.Vec3d(4, 4, 3), Gf.Vec3d(0, 0, 0), Gf.Vec3d(0, 0, 1))
    camera.AddTransformOp().Set(matrix.GetInverse())
    get_active_viewport().camera_path = '/World/View'
    for frame in range(150):
        if not app.is_running():
            raise RuntimeError('Application closed before smoke test completed')
        app.update()
        time.sleep(1 / 30)
    assert stage.GetPrimAtPath('/World/Cube').IsValid()
    print('SMOKE_TEST_PASSED: new stage, cube, 150 updates', flush=True)
except BaseException:
    traceback.print_exc()
    exit_code = 1
finally:
    print(f'SMOKE_TEST_CLOSING: exit_code={exit_code}', flush=True)
    app.close(wait_for_replicator=False, exit_code=exit_code)
