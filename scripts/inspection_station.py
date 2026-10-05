"""Visual inspection gate and camera; no camera inference or data generation."""
from pxr import Gf, UsdGeom
from conveyor import cube, cylinder, FONT
from splice_tracker import STATION_POSITION, STRAIGHT


def create_station(stage, phase=1):
    x = STATION_POSITION - STRAIGHT / 2
    orange = (.95, .52, .07)
    for i, y in enumerate((-.95, .95)):
        cube(stage, f'/World/Station/Post_{i}', (x, y, 1.4), (.15, .15, 2.8), orange)
        cube(stage, f'/World/Station/Foot_{i}', (x, y, .06), (.5, .45, .12), orange)
    cube(stage, '/World/Station/Crossbar', (x, 0, 2.8), (.18, 2.05, .16), orange)
    # Four compact, color-coded demonstration devices under the gate crossbar.
    devices = {
        'CAMERA': (x - .62, 2.49),
        'MFL': (x - .19, 2.18),
        'LASER': (x + .25, 2.40),
        'ENCODER': (x + .66, 1.56),
    }
    cube(stage, '/World/Station/CameraHousing', (x - .62, 0, 2.60), (.35, .34, .22), (.17, .23, .3))
    cylinder(stage, '/World/Station/Lens', (x - .62, 0, 2.45), .085, .12, (.08, .5, .75), axis='Z')
    camera = UsdGeom.Camera.Define(stage, '/World/Station/InspectionCamera')
    camera.AddTranslateOp().Set((x - .62, 0, 2.4))  # Visual only; no RTX sensor.
    camera.CreateFocalLengthAttr(18)
    camera.CreateClippingRangeAttr((.05, 20))
    # MFL head: a purple U-shaped yoke with two magnetic shoe primitives.
    cube(stage, '/World/Station/MFLHead', (x - .19, 0, 2.18), (.38, .33, .15), (.43, .23, .70))
    for side_name, side in (('Left', -1), ('Right', 1)):
        cube(stage, f'/World/Station/MFLPole_{side_name}', (x - .19, side * .20, 1.92), (.16, .14, .38), (.57, .4, .82))
        cube(stage, f'/World/Station/MFLPoleTip_{side_name}', (x - .19, side * .20, 1.715), (.19, .16, .045), (.92, .62, .95))
    # Downward profile head and a slim red guide line on the belt.
    cube(stage, '/World/Station/LaserHead', (x + .25, 0, 2.40), (.25, .28, .20), (.16, .43, .54))
    beam = cube(stage, '/World/Station/LaserBeam', (x + .25, 0, 1.548), (.018, .98, .008), (.30, .04, .04))
    beam_flash = cube(stage, '/World/Station/LaserFlash', (x + .25, 0, 1.553), (.045, .98, .008), (1.0, .08, .14))
    beam_flash.GetVisibilityAttr().Set(UsdGeom.Tokens.invisible)
    # Small side wheel and support represent a shaft encoder.
    cube(stage, '/World/Station/EncoderBracket', (x + .66, -.73, 1.73), (.11, .12, .43), STEEL_COLOR)
    cylinder(stage, '/World/Station/EncoderWheel', (x + .66, -.78, 1.53), .16, .09, (.95, .68, .12), axis='X')
    cube(stage, '/World/Station/EncoderSpoke', (x + .66, -.832, 1.53), (.022, .015, .23), (.12, .15, .18))
    # Dark nameplates face the existing presentation camera, toward -Y.
    for name, (device_x, z) in devices.items():
        cube(stage, f'/World/Station/Plate_{name}', (device_x, -1.055, z), (.54, .045, .16), (.045, .07, .10))
        label_mesh(stage, f'/World/Station/Label_{name}', name, device_x, -1.083, z - .052)
    # Thin green line denotes the fixed encoder-based inspection plane.
    scan_line = cube(stage, '/World/Station/DetectionLine', (x, 0, 1.527), (.055, 1.04, .006), (.15, .95, .45))
    scan_flash = cube(stage, '/World/Station/ScanFlash', (x, 0, 1.535), (.15, 1.04, .012), (1.0, .86, .15))
    scan_flash.GetVisibilityAttr().Set(UsdGeom.Tokens.invisible)
    if phase >= 2:
        add_phase2_hardware(stage, x)
    return beam.GetPrim(), beam_flash.GetPrim(), scan_line.GetPrim(), scan_flash.GetPrim()


def label_mesh(stage, path, text, center_x, y, bottom_z, cell=.014):
    """Small, flat 3x5 block lettering sized to fit the sensor nameplates."""
    points, indices = [], []
    total_columns = len(text) * 4 - 1
    for char_index, char in enumerate(text):
        for row, line in enumerate(FONT[char]):
            for col, on in enumerate(line):
                if on != '1':
                    continue
                x = center_x + (char_index * 4 + col - (total_columns - 1) / 2) * cell
                z = bottom_z + (4 - row) * cell
                start = len(points)
                points.extend([(x, y, z), (x + cell * .88, y, z),
                               (x + cell * .88, y, z + cell * .88), (x, y, z + cell * .88)])
                indices.extend(range(start, start + 4))
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr(points)
    mesh.CreateFaceVertexCountsAttr([4] * (len(points) // 4))
    mesh.CreateFaceVertexIndicesAttr(indices)
    mesh.CreateSubdivisionSchemeAttr('none')
    mesh.CreateDoubleSidedAttr(True)
    mesh.CreateDisplayColorAttr([(.93, .96, 1.0)])


STEEL_COLOR = (.18, .25, .30)


def add_phase2_hardware(stage, x):
    """Local primitive additions only. Existing camera reused, with no render product."""
    cube(stage, '/World/Station/SensorMountRail', (x - .2, 0, 2.75), (1.1, .12, .09), STEEL_COLOR)
    cube(stage, '/World/Station/HeadSupport', (x, .56, 2.14), (.09, .09, 1.2), STEEL_COLOR)
    cube(stage, '/World/Station/MFL24Bridge', (x, 0, 1.65), (.22, 1.04, .10), (.34, .18, .58))
    for index in range(24):
        y = -.46 + index * .92 / 23
        cube(stage, f'/World/Station/MFL24/MFL{index + 1:02d}', (x + .08, y, 1.583),
             (.075, .027, .025), (.64, .44, .85))
    stage.GetPrimAtPath('/World/Station/Plate_MFL').GetAttribute('xformOp:scale').Set(Gf.Vec3f(.92, .045, .19))
    stage.RemovePrim('/World/Station/Label_MFL')
    label_mesh(stage, '/World/Station/Label_MFL', 'MFL 24-CH', x - .19, -1.083, 2.13, cell=.023)
    cube(stage, '/World/Station/TensionMount', (x + .95, -.7, 1.0), (.4, .15, .12), STEEL_COLOR)
    cube(stage, '/World/Station/TensionCell', (x + .95, -.79, 1.12), (.27, .18, .20), (.1, .6, .47))
    cylinder(stage, '/World/Station/TensionPin', (x + .95, -.9, 1.12), .065, .09, (.7, .77, .8))
    cube(stage, '/World/Station/Plate_Tension', (x + .95, -1.055, .87), (.65, .045, .16), (.045, .07, .10))
    label_mesh(stage, '/World/Station/Label_Tension', 'TENSION', x + .95, -1.083, .82, cell=.019)
    camera = UsdGeom.Camera(stage.GetPrimAtPath('/World/Station/InspectionCamera'))
    camera.ClearXformOpOrder()
    matrix = Gf.Matrix4d().SetLookAt(Gf.Vec3d(x - .62, 0, 2.4), Gf.Vec3d(x, 0, 1.5), Gf.Vec3d(0, 1, 0))
    camera.AddTransformOp().Set(matrix.GetInverse())
