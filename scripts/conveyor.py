"""Primitive conveyor geometry and kinematic belt animation (no rigid-body solver)."""
import math
from pxr import Gf, UsdGeom
from splice_tracker import STRAIGHT, RADIUS, LOOP_LENGTH, SPLICES, belt_pose

STEEL = (0.18, 0.25, 0.30)
BELT = (0.045, 0.06, 0.065)
COLORS = [(1.0, 0.45, 0.08), (0.12, 0.75, 0.95), (0.9, 0.75, 0.1),
          (0.55, 0.35, 0.95), (0.15, 0.85, 0.5)]
FONT = {
    ' ': ('000', '000', '000', '000', '000'),
    '-': ('000', '000', '111', '000', '000'),
    'H': ('101', '101', '111', '101', '101'),
    'I': ('111', '010', '010', '010', '111'),
    'T': ('111', '010', '010', '010', '010'),
    'S': ('111', '100', '111', '001', '111'),
    '0': ('111', '101', '101', '101', '111'),
    '1': ('010', '110', '010', '010', '111'),
    '2': ('111', '001', '111', '100', '111'),
    '3': ('111', '001', '111', '001', '111'),
    '4': ('101', '101', '111', '001', '001'),
    '5': ('111', '100', '111', '001', '111'),
    'A': ('111', '101', '111', '101', '101'),
    'C': ('111', '100', '100', '100', '111'),
    'D': ('110', '101', '101', '101', '110'),
    'E': ('111', '100', '110', '100', '111'),
    'F': ('111', '100', '110', '100', '100'),
    'L': ('100', '100', '100', '100', '111'),
    'M': ('101', '111', '111', '101', '101'),
    'N': ('101', '111', '111', '111', '101'),
    'O': ('111', '101', '101', '101', '111'),
    'R': ('110', '101', '110', '101', '101'),
}


def cube(stage, path, position, scale, color):
    obj = UsdGeom.Cube.Define(stage, path)
    obj.CreateSizeAttr(1)
    obj.AddTranslateOp().Set(Gf.Vec3d(*position))
    obj.AddScaleOp().Set(Gf.Vec3f(*scale))
    obj.CreateDisplayColorAttr([color])
    return obj


def cylinder(stage, path, position, radius, length, color, axis='Y'):
    obj = UsdGeom.Cylinder.Define(stage, path)
    obj.CreateAxisAttr(axis)
    obj.CreateRadiusAttr(radius)
    obj.CreateHeightAttr(length)
    obj.AddTranslateOp().Set(Gf.Vec3d(*position))
    obj.CreateDisplayColorAttr([color])
    return obj


def splice_text(stage, path, text):
    """A low-poly bitmap label authored as one mesh on top of each marker."""
    cell, points, indices = .038, [], []
    width = len(text) * 4 - 1
    for char_index, char in enumerate(text):
        for row, line in enumerate(FONT[char]):
            for col, on in enumerate(line):
                if on != '1':
                    continue
                x = (2 - row) * cell
                y = (char_index * 4 + col - (width - 1) / 2) * cell
                start = len(points)
                points.extend([(x, y, .023), (x + cell * .88, y, .023),
                               (x + cell * .88, y + cell * .88, .023), (x, y + cell * .88, .023)])
                indices.extend(range(start, start + 4))
    label = UsdGeom.Mesh.Define(stage, path)
    label.CreatePointsAttr(points)
    label.CreateFaceVertexCountsAttr([4] * (len(points) // 4))
    label.CreateFaceVertexIndicesAttr(indices)
    label.CreateSubdivisionSchemeAttr('none')
    label.CreateDoubleSidedAttr(True)
    label.CreateDisplayColorAttr([(.015, .02, .025)])
    return label


class Conveyor:
    def __init__(self, stage):
        self.moving = []
        self.roller_rotations = []
        self.splice_markers = {}
        self.splice_highlights = {}
        cube(stage, '/World/Conveyor/UpperBelt', (0, 0, 1.5), (STRAIGHT, 1, .025), BELT)
        cube(stage, '/World/Conveyor/ReturnBelt', (0, 0, .9), (STRAIGHT, 1, .025), BELT)
        for side in (-1, 1):
            cube(stage, f'/World/Frame/Rail_{side + 1}', (0, side * .65, 1.14), (18, .12, .17), STEEL)
        for i, x in enumerate((-8, -5, -2, 1, 4, 7)):
            for j, y in enumerate((-.65, .65)):
                cube(stage, f'/World/Frame/Leg_{i}_{j}', (x, y, .55), (.13, .13, 1.1), STEEL)
                cube(stage, f'/World/Frame/Foot_{i}_{j}', (x, y, .055), (.45, .36, .1), STEEL)
            cube(stage, f'/World/Frame/Brace_{i}', (x, 0, .55), (.12, 1.35, .12), STEEL)
        for i in range(16):
            x = -8.1 + i * 1.08
            cylinder(stage, f'/World/Rollers/Idler_{i}', (x, 0, 1.37), .115, 1.22, (.38, .43, .46))
        for i, x in enumerate((-STRAIGHT / 2, STRAIGHT / 2)):
            cylinder(stage, f'/World/Rollers/Drum_{i}', (x, 0, 1.2), RADIUS, 1.05, BELT)
            hub = UsdGeom.Xform.Define(stage, f'/World/Rollers/Hub_{i}')
            hub.AddTranslateOp().Set(Gf.Vec3d(x, -.59, 1.2))
            self.roller_rotations.append(hub.AddRotateYOp())
            cylinder(stage, f'{hub.GetPath()}/Cap', (0, 0, 0), .22, .08, (.6, .65, .7))
            cube(stage, f'{hub.GetPath()}/Spoke', (0, -.05, 0), (.36, .015, .045), (.95, .55, .1))
        for i, (name, offset) in enumerate(SPLICES.items()):
            path = f'/World/Splices/{name}'
            root = UsdGeom.Xform.Define(stage, path)
            root.GetPrim().SetCustomDataByKey('splice_id', name)
            translate, rotate = root.AddTranslateOp(), root.AddRotateYOp()
            cube(stage, path + '/Marker', (0, 0, .006), (.32, 1.02, .025), COLORS[i])
            highlight = cube(stage, path + '/ActiveHighlight', (0, 0, .022), (.42, 1.02, .005), (1.0, .92, .24))
            highlight.GetVisibilityAttr().Set(UsdGeom.Tokens.invisible)
            splice_text(stage, path + '/Label', name)
            self.splice_markers[name] = stage.GetPrimAtPath(path + '/Marker')
            self.splice_highlights[name] = stage.GetPrimAtPath(path + '/ActiveHighlight')
            self.moving.append((offset, translate, rotate))
        for i in range(48):
            path = f'/World/Treads/Tread_{i:02d}'
            root = UsdGeom.Xform.Define(stage, path)
            translate, rotate = root.AddTranslateOp(), root.AddRotateYOp()
            cube(stage, path + '/Stripe', (0, 0, .003), (.025, .93, .023), (.12, .15, .16))
            self.moving.append((i * LOOP_LENGTH / 48, translate, rotate))
        self.update(0)

    def update(self, distance):
        for offset, translate, rotate in self.moving:
            x, z, angle = belt_pose(offset + distance)
            translate.Set(Gf.Vec3d(x, 0, z))
            rotate.Set(angle)
        for rotate in self.roller_rotations:
            rotate.Set(math.degrees(distance / RADIUS) % 360)

    def highlight(self, splice):
        """Brighten the splice currently being demonstrated at the station."""
        for name, marker in self.splice_markers.items():
            marker.GetAttribute('xformOp:scale').Set(Gf.Vec3f(.32, 1.02, .025))
            imageable = UsdGeom.Imageable(self.splice_highlights[name])
            imageable.MakeVisible() if name == splice else imageable.MakeInvisible()
