"""vec: tuple vectors, 3x3 matrices, Blender-exact Euler rotations. Owner: core. Standard library only.

Vectors are 3-tuples of floats; matrices are 3-tuples of 3-tuples (row major).
Euler order is 'XYZ' everywhere: R = Rz(rz) Ry(ry) Rx(rx), matching Blender
rotation_mode 'XYZ' with rotation_euler = (rx, ry, rz). Angles in radians.
"""
import math

IDENTITY = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def add(a, b):
    """-> a + b."""
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    """-> a - b."""
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, s):
    """-> a * scalar s."""
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a, b):
    """-> a . b."""
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    """-> a x b."""
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a):
    """-> |a|."""
    return math.sqrt(dot(a, a))


def norm(a):
    """-> a / |a|, or (0, 0, 0) when |a| < 1e-12."""
    n = length(a)
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-12 else (0.0, 0.0, 0.0)


def lerp3(a, b, u):
    """-> a + (b - a) u per component."""
    return (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u)


def mat_vec(m, v):
    """-> m v."""
    return tuple(m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] for i in range(3))


def mat_mul(a, b):
    """-> a b."""
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3))


def mat_t(m):
    """-> transpose (the inverse of a rotation)."""
    return tuple(tuple(m[j][i] for j in range(3)) for i in range(3))


def rot_x(a):
    """-> rotation about X by a."""
    c, s = math.cos(a), math.sin(a)
    return ((1.0, 0.0, 0.0), (0.0, c, -s), (0.0, s, c))


def rot_y(a):
    """-> rotation about Y by a."""
    c, s = math.cos(a), math.sin(a)
    return ((c, 0.0, s), (0.0, 1.0, 0.0), (-s, 0.0, c))


def rot_z(a):
    """-> rotation about Z by a."""
    c, s = math.cos(a), math.sin(a)
    return ((c, -s, 0.0), (s, c, 0.0), (0.0, 0.0, 1.0))


def rot_xyz(rx, ry, rz):
    """Blender 'XYZ': -> Rz Ry Rx."""
    return mat_mul(rot_z(rz), mat_mul(rot_y(ry), rot_x(rx)))


def euler_xyz(m):
    """Rotation matrix -> (rx, ry, rz) with rot_xyz(rx, ry, rz) == m (one solution, ry in [-pi/2, pi/2]).

    At gimbal lock (|m[2][0]| == 1) rx is set to 0 and rz carries the rest.
    """
    sy = -m[2][0]
    sy = 1.0 if sy > 1.0 else -1.0 if sy < -1.0 else sy
    ry = math.asin(sy)
    if abs(sy) < 1.0 - 1e-12:
        rx = math.atan2(m[2][1], m[2][2])
        rz = math.atan2(m[1][0], m[0][0])
    else:
        rx = 0.0
        rz = math.atan2(-m[0][1], m[1][1])
    return (rx, ry, rz)


def transform(R, T, p):
    """-> R p + T."""
    return add(mat_vec(R, p), T)


def compose(R1, T1, R2, T2):
    """Parent (R1, T1) then child (R2, T2) -> (R1 R2, R1 T2 + T1)."""
    return mat_mul(R1, R2), add(mat_vec(R1, T2), T1)


def _cross2(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def hull2d(pts):
    """[(x, y)] -> convex hull, counter-clockwise, monotone chain.

    Collinear boundary points are dropped. Fewer than 3 distinct points give
    the distinct points as they are.
    """
    pts = sorted(set(tuple(p) for p in pts))
    if len(pts) < 3:
        return pts
    lo, up = [], []
    for p in pts:
        while len(lo) >= 2 and _cross2(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(up) >= 2 and _cross2(up[-2], up[-1], p) <= 0:
            up.pop()
        up.append(p)
    return lo[:-1] + up[:-1]


def in_hull2d(pt, hull):
    """True when pt lies inside the convex hull (either winding), boundary included."""
    n = len(hull)
    if n < 3:
        return False
    signs = [_cross2(hull[k], hull[(k + 1) % n], pt) for k in range(n)]
    return all(s >= 0 for s in signs) or all(s <= 0 for s in signs)
