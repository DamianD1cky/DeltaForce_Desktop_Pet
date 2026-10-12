"""Build native pixel animation atlases from the approved Red Wolf study.

The character is posed with a 3D skeleton projected orthographically onto the
front view. Bones keep their length, elbows and knees are hinges, shoulders
and hips are ball joints, and planted feet are solved with two-bone IK. Key
poses are interpolated in joint space, so limbs travel on arcs instead of
straight lines; per-joint delays and rotational springs add the
proximal-to-distal lag and settle of a real body.

Every body part reuses the original pixels. Parts close to their drawn pose
move by whole pixels; rotated parts are sampled RotSprite-style from an 8x
Scale2x copy, with angles quantized to one pixel of travel at the bone tip.
Identical neighbouring frames merge into longer frames on the 20 ms grid, and
atlas cells are cropped to each clip's bounds.
Runtime only selects complete frames; it never rotates/scales the character or
mirrors the cannon. Python 3.12+, Pillow and NumPy (scripts/requirements-art.txt).
"""
from bisect import bisect_right
from pathlib import Path
import hashlib
import json
import math
import os

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "asset/sprites/redwolf-gilded-rose"
src = Image.open(OUT / "redwolf-idle-front.png").convert("RGBA")
C = json.loads((OUT / "sprite.json").read_text())["palette"]
SIZE = (320, 320)
BASE = (64, 22)
FRAME_MS = 20
SIDES = ("right", "left")


def rnd(v):
    return math.floor(v + .5)


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def smooth(t):
    t = max(0, min(1, t))
    return t * t * (3 - 2 * t)


def wrap(a):
    return (a + math.pi) % math.tau - math.pi


# ------------------------------------------------------------------ cut-outs

def shape_mask(points):
    mask = Image.new("L", src.size)
    ImageDraw.Draw(mask).polygon(points, fill=255)
    part = src.copy()
    part.putalpha(ImageChops.multiply(src.getchannel("A"), mask))
    return part


parts = {
    "head": shape_mask([(68, 10), (126, 10), (126, 59), (108, 61),
                       (108, 67), (82, 67), (77, 59), (68, 58)]),
    "torso": shape_mask([(77, 63), (111, 62), (125, 68), (126, 42),
                        (129, 42), (131, 78), (121, 82), (117, 108),
                        (120, 138), (127, 139), (126, 166), (111, 170),
                        (69, 168), (56, 169), (57, 140), (64, 122),
                        (66, 93), (62, 76), (69, 65)]),
    "right_upper": shape_mask([(53, 68), (62, 67), (69, 71), (68, 83),
                              (64, 99), (56, 123), (53, 132), (38, 132),
                              (38, 111), (42, 88)]),
    "right_lower": shape_mask([(38, 130), (53, 129), (56, 147), (52, 162),
                              (48, 164), (38, 163), (35, 155)]),
    "left_upper": shape_mask([(120, 67), (134, 71), (146, 90), (151, 115),
                             (149, 133), (136, 135), (129, 122), (120, 102),
                             (117, 90)]),
    "left_lower": shape_mask([(133, 132), (147, 131), (153, 159), (145, 166),
                             (135, 156)]),
    "right_leg": shape_mask([(57, 169), (89, 169), (91, 180), (87, 203),
                            (86, 224), (82, 248), (83, 257), (79, 267),
                            (71, 274), (49, 274), (50, 260), (55, 245)]),
    "left_leg": shape_mask([(94, 169), (125, 167), (129, 251), (130, 274),
                           (103, 276), (96, 265), (99, 240), (94, 216),
                           (92, 190)]),
}


def part_slice(name, top, bottom):
    layer = parts[name].copy()
    mask = Image.new("L", src.size)
    ImageDraw.Draw(mask).rectangle((0, top, 191, bottom), fill=255)
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
    return layer


# --------------------------------------------------------- pixel sampling

def pack(rgba):
    return np.ascontiguousarray(rgba, dtype=np.uint8).view(np.uint32)[..., 0]


def unpack(packed):
    packed = np.ascontiguousarray(packed)
    return packed.view(np.uint8).reshape(*packed.shape, 4)


def scale2x(a):
    """EPX/Scale2x on packed RGBA; keeps the palette and single-pixel lines."""
    p = np.pad(a, 1)
    up, right, left, down = p[:-2, 1:-1], p[1:-1, 2:], p[1:-1, :-2], p[2:, 1:-1]
    out = np.empty((a.shape[0] * 2, a.shape[1] * 2), a.dtype)
    out[0::2, 0::2] = np.where((left == up) & (left != down) & (up != right), up, a)
    out[0::2, 1::2] = np.where((up == right) & (up != left) & (right != down), right, a)
    out[1::2, 0::2] = np.where((down == left) & (down != right) & (left != up), left, a)
    out[1::2, 1::2] = np.where((right == down) & (right != up) & (down != left), down, a)
    return out


class Piece:
    """Original pixels of one part at rest, plus an 8x copy for rotation."""

    def __init__(self, image, origin=BASE):
        box = image.getbbox()
        self.x0, self.y0 = origin[0] + box[0], origin[1] + box[1]
        self.pixels = np.asarray(image.crop(box), dtype=np.uint8).copy()
        big = pack(self.pixels)
        for _ in range(3):
            big = scale2x(big)
        self.big = unpack(big)
        self.cache = {}

    def turned(self, pivot, axis, angle, scale):
        """Rotate about the rest pivot and stretch along the rest axis."""
        key = (pivot, axis, angle, scale)
        if key in self.cache:
            return self.cache[key]
        ca, sa = math.cos(angle), math.sin(angle)
        ax, ay = axis
        h, w = self.pixels.shape[:2]
        corners = np.array([[self.x0, self.y0], [self.x0 + w, self.y0],
                            [self.x0, self.y0 + h], [self.x0 + w, self.y0 + h]],
                           float) - pivot
        along = corners @ axis
        corners = corners + np.outer(along * (scale - 1), axis)
        moved = corners @ np.array([[ca, sa], [-sa, ca]])
        lo = np.floor(moved.min(0)).astype(int) - 1
        hi = np.ceil(moved.max(0)).astype(int) + 1
        gx, gy = np.meshgrid(np.arange(lo[0], hi[0]) + .5, np.arange(lo[1], hi[1]) + .5)
        qx, qy = gx * ca + gy * sa, -gx * sa + gy * ca
        along = (qx * ax + qy * ay) * (1 / scale - 1)
        sx = (qx + along * ax + pivot[0] - self.x0) * 8
        sy = (qy + along * ay + pivot[1] - self.y0) * 8
        ix, iy = np.floor(sx).astype(int), np.floor(sy).astype(int)
        ok = (ix >= 0) & (iy >= 0) & (ix < self.big.shape[1]) & (iy < self.big.shape[0])
        out = np.zeros(gx.shape + (4,), np.uint8)
        out[ok] = self.big[iy[ok], ix[ok]]
        ys, xs = np.nonzero(out[..., 3])
        if len(xs):
            out = out[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
            hit = (out, (int(lo[0] + xs.min()), int(lo[1] + ys.min())))
        else:
            hit = (out[:0, :0], (0, 0))
        self.cache[key] = hit
        return hit


def blit(canvas, pixels, x, y):
    h, w = pixels.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(canvas.shape[1], x + w), min(canvas.shape[0], y + h)
    if x0 >= x1 or y0 >= y1:
        return
    sub = pixels[y0 - y:y1 - y, x0 - x:x1 - x]
    mask = sub[..., 3] > 0
    canvas[y0:y1, x0:x1][mask] = sub[mask]


def place(canvas, piece, a_rest, b_rest, a, b):
    """Map a part's rest joints onto posed joints, on the integer pixel grid."""
    rx, ry = b_rest[0] - a_rest[0], b_rest[1] - a_rest[1]
    rest_len = math.hypot(rx, ry)
    # Whole-pixel joints decide the pose, so sub-pixel drift cannot flicker a part.
    anchor = (rnd(a[0]), rnd(a[1]))
    cx = rx + rnd(b[0]) - rnd(b_rest[0]) - anchor[0] + rnd(a_rest[0])
    cy = ry + rnd(b[1]) - rnd(b_rest[1]) - anchor[1] + rnd(a_rest[1])
    if math.hypot(cx, cy) < 1:
        cx, cy = b[0] - a[0], b[1] - a[1]
    cur_len = math.hypot(cx, cy)
    angle = wrap(math.atan2(cy, cx) - math.atan2(ry, rx))
    if abs(angle) * rest_len < .75 and abs(cur_len - rest_len) < 1.5:
        blit(canvas, piece.pixels, piece.x0 + anchor[0] - rnd(a_rest[0]),
             piece.y0 + anchor[1] - rnd(a_rest[1]))
        return
    # One pixel of tip travel per step: slow turns stay stable instead of shimmering.
    step = 1 / rest_len
    angle = round(angle / step) * step
    scale = max(2, rnd(cur_len)) / rest_len
    pixels, (ox, oy) = piece.turned(tuple(a_rest), (rx / rest_len, ry / rest_len), angle, scale)
    blit(canvas, pixels, anchor[0] + ox, anchor[1] + oy)


pieces = {
    "pelvis": part_slice("torso", 138, 170),
    "waist": part_slice("torso", 122, 143),
    "ribs": part_slice("torso", 108, 127),
    "chest": part_slice("torso", 42, 115),
    "neck": part_slice("head", 58, 67),
    "skull": part_slice("head", 10, 61),
}
for side in SIDES:
    for name, top, bottom in (("thigh", 167, 216), ("shin", 207, 251),
                              ("boot", 246, 263), ("toe", 258, 276)):
        pieces[f"{side}_{name}"] = part_slice(f"{side}_leg", top, bottom)
    pieces[f"{side}_shoulder"] = part_slice(f"{side}_upper", 67, 98)
    pieces[f"{side}_upper"] = part_slice(f"{side}_upper", 91, 135)
    pieces[f"{side}_lower"] = parts[f"{side}_lower"]
pieces = {name: Piece(image) for name, image in pieces.items()}


# ------------------------------------------------------------------ skeleton
# Screen axes: x right, y down, z toward the viewer. The character faces +z,
# so anatomical right is screen left.

REST2 = {
    "hip": (158, 188), "waist": (158, 162), "chest": (158, 134),
    "neck": (158, 92), "jaw": (158, 80), "crown": (158, 42),
    "right_hip": (137, 192), "right_knee": (136, 233),
    "right_ankle": (132, 270), "right_toe": (126, 293),
    "left_hip": (172, 192), "left_knee": (173, 233),
    "left_ankle": (176, 270), "left_toe": (180, 293),
    "right_shoulder": (124, 100), "right_elbow": (111, 153),
    "right_wrist": (106, 182), "right_hand": (101, 193),
    "left_shoulder": (190, 100), "left_elbow": (204, 158),
    "left_wrist": (209, 184), "left_hand": (212, 197),
}
PARENT = {"waist": "hip", "chest": "waist", "neck": "chest", "jaw": "neck", "crown": "jaw"}
for side in SIDES:
    PARENT.update({f"{side}_hip": "hip", f"{side}_knee": f"{side}_hip",
                   f"{side}_ankle": f"{side}_knee", f"{side}_toe": f"{side}_ankle",
                   f"{side}_shoulder": "chest", f"{side}_elbow": f"{side}_shoulder",
                   f"{side}_wrist": f"{side}_elbow", f"{side}_hand": f"{side}_wrist"})
X, Y, Z = np.eye(3)


def v3(p, z=0.0):
    return np.array([p[0], p[1], z], float)


def unit(v):
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-9 else np.zeros(3)


def rot(axis, angle):
    """Rotation matrix (right-handed in screen space: +z turns x toward y)."""
    x, y, z = unit(np.asarray(axis, float))
    c, s = math.cos(angle), math.sin(angle)
    t = 1 - c
    return np.array([[t * x * x + c, t * x * y - s * z, t * x * z + s * y],
                     [t * x * y + s * z, t * y * y + c, t * y * z - s * x],
                     [t * x * z - s * y, t * y * z + s * x, t * z * z + c]])


def euler(rx=0.0, ry=0.0, rz=0.0):
    """Degrees: twist about y, then flexion about x, then side bend about z."""
    return rot(Z, math.radians(rz)) @ rot(X, math.radians(rx)) @ rot(Y, math.radians(ry))


OFFSET = {j: v3(REST2[j]) - v3(REST2[p]) for j, p in PARENT.items()}

# The drawn forearm hangs slightly toward the viewer: a relaxed elbow is bent
# about 27 degrees, so a sideways forearm shows its full 33 px length.
FOREARM = 33.0
ARM = {}
for side in SIDES:
    yb = unit(OFFSET[f"{side}_elbow"])
    xb = unit(X - yb[0] * yb)          # elbow hinge axis; +angle flexes forward
    zb = np.cross(xb, yb)
    f2 = OFFSET[f"{side}_wrist"][:2]
    f_rest = unit(np.array([f2[0], f2[1], math.sqrt(FOREARM ** 2 - f2 @ f2)]))
    phi = math.atan2(f_rest @ zb, f_rest @ yb)
    d0 = rot(xb, -phi) @ f_rest
    OFFSET[f"{side}_wrist"] = d0 * FOREARM
    OFFSET[f"{side}_hand"] = rot(xb, -phi) @ OFFSET[f"{side}_hand"]
    ARM[side] = {"yb": yb, "xb": xb, "zb": zb, "d0": d0, "phi": math.degrees(phi),
                 "upper": float(np.linalg.norm(OFFSET[f"{side}_elbow"]))}

# Legs are 0.4% longer than drawn so the standing knee is soft, never locked.
LEG = {}
for side in SIDES:
    hip, knee, ankle = (v3(REST2[f"{side}_{j}"]) for j in ("hip", "knee", "ankle"))
    u = unit(ankle - hip)
    n = np.cross(Z, u)
    splay = float((knee - hip) @ n)
    LEG[side] = {"thigh": float(np.linalg.norm(knee - hip)) * 1.004,
                 "shin": float(np.linalg.norm(ankle - knee)) * 1.004,
                 "splay": abs(splay), "hint": tuple((n * math.copysign(1, splay))[:2])}


def upper_local(side, sa, sb, psi):
    """Swing (sa forward, sb about the view axis) then twist about the bone."""
    A = ARM[side]
    sv = math.radians(sa) * A["xb"] + math.radians(sb) * A["zb"]
    angle = float(np.linalg.norm(sv))
    swing = rot(sv, angle) if angle > 1e-9 else np.eye(3)
    return rot(swing @ A["yb"], math.radians(psi)) @ swing


def swing_direction(side, sa, sb):
    """Upper-arm direction in the arm's rest frame for a swing."""
    A = ARM[side]
    u = upper_local(side, sa, sb, 0) @ A["yb"]
    return [float(u @ A["xb"]), float(u @ A["yb"]), float(u @ A["zb"])]


def direction_swing(side, d):
    """Minimal swing that points the upper arm along d (inverse of above)."""
    A = ARM[side]
    u = unit(d[0] * A["xb"] + d[1] * A["yb"] + d[2] * A["zb"])
    axis = np.cross(A["yb"], u)
    angle = math.atan2(float(np.linalg.norm(axis)), float(A["yb"] @ u))
    if angle < 1e-9:
        return 0.0, 0.0
    sv = unit(axis) * angle
    return math.degrees(sv @ A["xb"]), math.degrees(sv @ A["zb"])


def solve_leg(side, hip, target, hint, inplane):
    """Two-bone IK. Standing (inplane=0) the knee keeps its drawn splay and
    folds toward the viewer; inplane=1 bends it in the picture plane toward
    `hint` (squat splay, side-on slide). Blending keeps the knee continuous."""
    G = LEG[side]
    L1, L2 = G["thigh"], G["shin"]
    d = target - hip
    dist = float(np.linalg.norm(d))
    u = d / dist
    dist = min(max(dist, abs(L1 - L2) + 1e-3), L1 + L2 - 1e-3)
    a = (L1 * L1 - L2 * L2 + dist * dist) / (2 * dist)
    h = math.sqrt(max(0.0, L1 * L1 - a * a))
    n = unit(np.cross(Z, u))
    drawn = n if n[0] * G["hint"][0] + n[1] * G["hint"][1] >= 0 else -n
    bent = n if n[0] * hint[0] + n[1] * hint[1] >= 0 else -n
    lateral = (1 - inplane) * min(h, G["splay"]) * drawn + inplane * h * bent
    out = math.sqrt(max(0.0, h * h - float(lateral @ lateral)))
    knee = hip + a * u + lateral + out * unit(Z - (Z @ u) * u)
    return knee, hip + u * dist


REST_CH = {
    "pelvis.x": 0, "pelvis.y": 0, "pelvis.z": 0,
    "pelvis.rx": 0, "pelvis.ry": 0, "pelvis.rz": 0,
    "breath": 0, "neck.len": 1, "head.level": .55,
}
for j in ("waist", "chest", "neck", "head"):
    REST_CH.update({f"{j}.rx": 0, f"{j}.ry": 0, f"{j}.rz": 0})
for side in SIDES:
    k = side[0]
    REST_CH.update({f"{k}.elev": 0, f"{k}.prot": 0, f"{k}.sa": 0, f"{k}.sb": 0,
                    f"{k}.psi": 0, f"{k}.phi": ARM[side]["phi"],
                    f"{k}.wflex": 0, f"{k}.wdev": 0,
                    f"{k}.ax": REST2[f"{side}_ankle"][0], f"{k}.ay": REST2[f"{side}_ankle"][1],
                    f"{k}.az": 0, f"{k}.kx": -1 if side == "right" else 1, f"{k}.ky": 0,
                    f"{k}.inplane": 0, f"{k}.foot": 0})


class Springs:
    """Rotational springs on in-plane bone angles: inertia lag and settle."""

    def __init__(self, params, fade=None):
        self.params, self.state, self.fade = params, {}, fade

    def apply(self, joint, world, bone, t):
        if joint not in self.params:
            return world
        v = world @ bone
        ratio = math.hypot(v[0], v[1]) / float(np.linalg.norm(bone))
        if ratio < .05:
            return world
        target = math.atan2(v[1], v[0])
        x, vel = self.state.get(joint, (target, 0.0))
        target = x + wrap(target - x)
        freq, zeta = self.params[joint]
        w = math.tau * freq
        h = FRAME_MS / 1000 / 10
        for _ in range(10):
            vel += (w * w * (target - x) - 2 * zeta * w * vel) * h
            x += vel * h
        self.state[joint] = (x, vel)
        # A bone pointing at the viewer has an unstable picture angle: its
        # offset fades out instead of snapping off.
        delta = max(-.35, min(.35, x - target)) * smooth((ratio - .2) / .3)
        if self.fade:
            delta *= self.fade(t)
        return rot(Z, delta) @ world


def fk(ch, springs=None, t=0):
    """Joint world positions (3D) and rotations for one set of channels."""
    P, W = {}, {}
    breath = ch["breath"]
    W["hip"] = euler(ch["pelvis.rx"], ch["pelvis.ry"], ch["pelvis.rz"])
    P["hip"] = v3(REST2["hip"]) + (ch["pelvis.x"], ch["pelvis.y"], ch["pelvis.z"])
    P["waist"] = P["hip"] + W["hip"] @ OFFSET["waist"]
    W["waist"] = W["hip"] @ euler(ch["waist.rx"], ch["waist.ry"], ch["waist.rz"])
    # Inhaling lifts and lengthens the rib cage a little.
    P["chest"] = P["waist"] + W["waist"] @ OFFSET["chest"] * (1 + .012 * breath)
    W["chest"] = W["waist"] @ euler(ch["chest.rx"], ch["chest.ry"], ch["chest.rz"])
    P["neck"] = P["chest"] + W["chest"] @ OFFSET["neck"] * (1 + .024 * breath)
    W["neck"] = W["chest"] @ euler(ch["neck.rx"], ch["neck.ry"], ch["neck.rz"])
    P["jaw"] = P["neck"] + W["neck"] @ OFFSET["jaw"] * ch["neck.len"]
    # The head partly cancels inherited lean so the gaze stays level.
    up = W["neck"] @ OFFSET["crown"]
    lean = wrap(math.atan2(up[1], up[0]) + math.pi / 2)
    W["jaw"] = rot(Z, -ch["head.level"] * lean) @ W["neck"] @ euler(
        ch["head.rx"], ch["head.ry"], ch["head.rz"])
    if springs:
        W["jaw"] = springs.apply("jaw", W["jaw"], OFFSET["crown"], t)
    P["crown"] = P["jaw"] + W["jaw"] @ OFFSET["crown"]
    for side in SIDES:
        k, sign = side[0], (1 if side == "right" else -1)
        A = ARM[side]
        sh, el, wr, hd = (f"{side}_{j}" for j in ("shoulder", "elbow", "wrist", "hand"))
        clav = rot(Z, math.radians(sign * (ch[f"{k}.elev"] + 1.6 * breath))) @ rot(
            Y, math.radians(sign * ch[f"{k}.prot"]))
        P[sh] = P["chest"] + W["chest"] @ clav @ OFFSET[sh]
        W[sh] = W["chest"] @ upper_local(side, ch[f"{k}.sa"], ch[f"{k}.sb"], ch[f"{k}.psi"])
        if springs:
            W[sh] = springs.apply(sh, W[sh], OFFSET[el], t)
        P[el] = P[sh] + W[sh] @ OFFSET[el]
        W[el] = W[sh] @ rot(A["xb"], math.radians(ch[f"{k}.phi"]))
        P[wr] = P[el] + W[el] @ OFFSET[wr]
        W[wr] = W[el] @ rot(A["xb"], math.radians(ch[f"{k}.wflex"])) @ rot(
            A["zb"], math.radians(sign * ch[f"{k}.wdev"]))
        if springs:
            W[wr] = springs.apply(wr, W[wr], OFFSET[hd], t)
        P[hd] = P[wr] + W[wr] @ OFFSET[hd]
        hj, kn, an, to = (f"{side}_{j}" for j in ("hip", "knee", "ankle", "toe"))
        P[hj] = P["hip"] + W["hip"] @ OFFSET[hj]
        target = np.array([ch[f"{k}.ax"], ch[f"{k}.ay"], ch[f"{k}.az"]])
        P[kn], P[an] = solve_leg(
            side, P[hj], target, (ch[f"{k}.kx"], ch[f"{k}.ky"]), ch[f"{k}.inplane"])
        P[to] = P[an] + rot(Z, math.radians(ch[f"{k}.foot"])) @ OFFSET[to]
    return P, W


def solve_arm(side, shoulder, thorax, wrist, pole):
    """Wrist target + elbow pole (screen space) -> hinge-correct arm channels."""
    A = ARM[side]
    L1, L2 = A["upper"], FOREARM
    d = np.asarray(wrist, float) - shoulder
    dist = float(np.linalg.norm(d))
    u = d / dist
    dist = min(max(dist, abs(L1 - L2) + 1e-3), L1 + L2 - 1e-3)
    a = (L1 * L1 - L2 * L2 + dist * dist) / (2 * dist)
    h = math.sqrt(max(0.0, L1 * L1 - a * a))
    p = np.asarray(pole, float)
    v = unit(p - (p @ u) * u)
    elbow = shoulder + a * u + h * v
    ul = thorax.T @ unit(elbow - shoulder)
    fl = thorax.T @ unit(shoulder + u * dist - elbow)
    target = math.acos(max(-1, min(1, ul @ fl)))

    def bend(phi):
        return math.acos(max(-1, min(1, A["yb"] @ (rot(A["xb"], phi) @ A["d0"]))))

    lo, hi = 0.0, math.radians(165)
    for _ in range(48):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if bend(mid) < target else (lo, mid)
    phi = (lo + hi) / 2
    axis = np.cross(A["yb"], ul)
    swing_angle = math.atan2(float(np.linalg.norm(axis)), float(A["yb"] @ ul))
    swing = rot(axis, swing_angle) if swing_angle > 1e-9 else np.eye(3)
    sv = unit(axis) * swing_angle
    predicted = swing @ rot(A["xb"], phi) @ A["d0"]
    a1, a2 = unit(predicted - (predicted @ ul) * ul), unit(fl - (fl @ ul) * ul)
    psi = math.atan2(float(np.cross(a1, a2) @ ul), float(a1 @ a2))
    return {"sa": math.degrees(sv @ A["xb"]), "sb": math.degrees(sv @ A["zb"]),
            "psi": math.degrees(psi), "phi": math.degrees(phi)}


def pose(**spec):
    """Author a key pose. Angles in degrees; positions in canvas pixels.

    pelvis=dict(x,y,z,rx,ry,rz); waist/chest/neck/head=dict(rx,ry,rz)
    arm_r/arm_l=dict(wrist=(x,y,z), pole=(x,y,z) or elbow=(x,y,z))
      or dict(flex, abd, twist, elbow=degrees)
      plus optional hand=(flex, deviation)
    leg_r/leg_l=dict(ankle=(x,y,z), knee=(x,y), inplane, foot)
    clav_r/clav_l=(elevation, protraction); breath, neck_len, head_level
    """
    ch = dict(REST_CH)
    for j in ("pelvis", "waist", "chest", "neck", "head"):
        for axis, value in spec.get(j, {}).items():
            ch[f"{j}.{axis}"] = value
    for name in ("breath", "neck_len", "head_level"):
        if name in spec:
            ch[name.replace("_", ".")] = spec[name]
    for side in SIDES:
        k, sign = side[0], (1 if side == "right" else -1)
        if f"clav_{k}" in spec:
            ch[f"{k}.elev"], ch[f"{k}.prot"] = spec[f"clav_{k}"]
        leg = spec.get(f"leg_{k}", {})
        if "ankle" in leg:
            ch[f"{k}.ax"], ch[f"{k}.ay"], ch[f"{k}.az"] = (*leg["ankle"], 0)[:3]
        if "knee" in leg:
            ch[f"{k}.kx"], ch[f"{k}.ky"] = leg["knee"]
        for name in ("inplane", "foot"):
            if name in leg:
                ch[f"{k}.{name}"] = leg[name]
    P, W = fk(ch)
    for side in SIDES:
        k, sign = side[0], (1 if side == "right" else -1)
        arm = spec.get(f"arm_{k}")
        if not arm:
            continue
        if "wrist" in arm:
            target = (*arm["wrist"], 0)[:3]
            pole = arm.get("pole", (-.3 * sign, .2, -1))
            if "elbow" in arm:
                pole = np.asarray(arm["elbow"], float) - P[f"{side}_shoulder"]
            solved = solve_arm(side, P[f"{side}_shoulder"], W["chest"], target, pole)
        else:
            solved = {"sa": arm.get("flex", 0), "sb": sign * arm.get("abd", 0),
                      "psi": -sign * arm.get("twist", 0),
                      "phi": arm.get("elbow", ARM[side]["phi"])}
        for name, value in solved.items():
            ch[f"{k}.{name}"] = value
        if "hand" in arm:
            ch[f"{k}.wflex"], ch[f"{k}.wdev"] = arm["hand"]
    return ch


REST_POSE = pose()


# ------------------------------------------------------------------- tracks

EASES = {
    "linear": lambda s: s,
    "in": lambda s: s * s,
    "out": lambda s: 1 - (1 - s) * (1 - s),
    "in3": lambda s: s * s * s,
    "out3": lambda s: 1 - (1 - s) ** 3,
    "inout": smooth,
}


class Track:
    """Monotone cubic per channel (continuous velocity, no overshoot), with
    optional per-segment easing for snaps and drops."""

    def __init__(self, keys):
        self.times = [t for t, _, _ in keys]
        self.values = [v for _, v, _ in keys]
        self.eases = [e for _, _, e in keys]

    def tangent(self, i):
        t, v = self.times, self.values
        if i == 0 or i == len(t) - 1:
            return 0.0
        d0 = (v[i] - v[i - 1]) / (t[i] - t[i - 1])
        d1 = (v[i + 1] - v[i]) / (t[i + 1] - t[i])
        return 2 * d0 * d1 / (d0 + d1) if d0 * d1 > 0 else 0.0

    def __call__(self, ms):
        t, v = self.times, self.values
        if ms <= t[0]:
            return v[0]
        if ms >= t[-1]:
            return v[-1]
        i = bisect_right(t, ms) - 1
        span = t[i + 1] - t[i]
        s = (ms - t[i]) / span
        ease = self.eases[i + 1]
        if ease:
            return v[i] + (v[i + 1] - v[i]) * EASES[ease](s)
        h00, h10 = 2 * s ** 3 - 3 * s * s + 1, s ** 3 - 2 * s * s + s
        h01, h11 = -2 * s ** 3 + 3 * s * s, s ** 3 - s * s
        return (h00 * v[i] + h10 * span * self.tangent(i)
                + h01 * v[i + 1] + h11 * span * self.tangent(i + 1))


DEFAULT_SPRINGS = {
    "right_shoulder": (4.2, .55), "left_shoulder": (3.4, .45),
    "right_wrist": (5.5, .5), "left_wrist": (5.0, .45),
}


class Clip:
    def __init__(self, name, label, ms, keyframe_ms, loop=False, **extra):
        self.name, self.label, self.ms, self.loop = name, label, ms, loop
        self.keyframe_ms, self.extra = keyframe_ms, extra
        self.keys, self.lag, self.layers = [], {}, []
        self.springs = dict(DEFAULT_SPRINGS)
        self.grip = {"right": lambda t: 1.0, "left": lambda t: 1.0}
        self.charged = lambda t: False
        self.draw = None          # draw(ctx) after the body: effects
        self.hold = {}            # hold[side](ctx) props drawn under that glove

    def key(self, t, channels, ease=None):
        self.keys.append((t, channels, ease))
        return self

    def compile(self):
        self.keys.sort(key=lambda k: k[0])
        self.tracks = {}
        if not self.keys:
            return
        rows = [dict(ch) for _, ch, _ in self.keys]
        for r in rows:
            # Shoulders interpolate the upper-arm direction (renormalised), close
            # to the shortest arc: a raised arm sweeps without drooping, and an arm
            # crossing the body passes near hanging instead of orbiting.
            for side in SIDES:
                k = side[0]
                r[f"{k}.ux"], r[f"{k}.uy"], r[f"{k}.uz"] = swing_direction(
                    side, r[f"{k}.sa"], r[f"{k}.sb"])
        names = [c for c in REST_CH if not c.endswith((".sa", ".sb"))]
        names += [f"{k}.{n}" for k in "rl" for n in ("ux", "uy", "uz")]
        self.tracks = {c: Track([(t, r[c], e) for (t, _, e), r in zip(self.keys, rows)])
                       for c in names}

    def channels(self, t):
        ch = dict(REST_CH)
        ease_in = smooth(t / 160)
        for c, track in self.tracks.items():
            # Positive lag trails the keys, negative lag leads them; both start
            # from the shared first pose.
            lag = next((ms for prefix, ms in self.lag.items() if c.startswith(prefix)), 0)
            ch[c] = track(t - lag * ease_in)
        for side in SIDES:
            k = side[0]
            if f"{k}.ux" in ch:
                d = [ch.pop(f"{k}.u{axis}") for axis in "xyz"]
                ch[f"{k}.sa"], ch[f"{k}.sb"] = direction_swing(side, d)
        for layer in self.layers:
            layer(t, ch)
        return ch


# ------------------------------------------------------------------ drawing

def derive(p):
    """2D helper joints between real joints, for the 22 drawn segments."""
    p = dict(p)
    x, y = lerp(p["waist"], p["chest"], .5)
    p["ribs"] = (x + (p["neck"][0] - p["hip"][0]) * .08, y)
    for side in SIDES:
        p[f"{side}_bicep"] = lerp(p[f"{side}_shoulder"], p[f"{side}_elbow"], .32)
        ankle, toe = p[f"{side}_ankle"], p[f"{side}_toe"]
        x, y = lerp(ankle, toe, .55)
        flex = (toe[0] - ankle[0] - (REST2[f"{side}_toe"][0] - REST2[f"{side}_ankle"][0])) * .08
        p[f"{side}_ball"] = (x, y - flex)
    return p


RIG_REST = derive(REST2)
LEG_SEGMENTS = (("thigh", "hip", "knee"), ("shin", "knee", "ankle"),
                ("boot", "ankle", "ball"), ("toe", "ball", "toe"))
TORSO_SEGMENTS = (("pelvis", "hip", "waist"), ("waist", "waist", "ribs"),
                  ("ribs", "ribs", "chest"), ("chest", "chest", "neck"),
                  ("neck", "neck", "jaw"), ("skull", "jaw", "crown"))


def heading(a, b):
    return math.atan2(b[1] - a[1], b[0] - a[0])


def glove_image(grip):
    # Two phalanges per finger, plus a thumb; the palm follows wrist rotation.
    hand = Image.new("RGBA", (40, 48))
    d = ImageDraw.Draw(hand)
    x, y = 20, 30
    d.polygon([(x - 8, y + 7), (x - 9, y - 4), (x - 5, y - 9), (x + 5, y - 8),
               (x + 9, y - 3), (x + 7, y + 7)], fill=C["carbon0"], outline=C["ink"])
    d.polygon([(x - 6, y - 5), (x + 3, y - 6), (x + 6, y - 1), (x + 3, y + 5),
               (x - 6, y + 3)], fill=C["carbon2"])
    for j in range(4):
        fx = x - 6 + j * 4
        # Curl each finger continuously; the little finger closes first.
        curl = max(0, min(1, grip * 1.25 - (3 - j) * .08))
        root = (fx, y - 3)
        knuckle = (fx + round(curl * 2), round(y - 9 + curl * 5))
        tip = (fx + round(curl * 3), round(y - 15 + abs(j - 1) * 2 + curl * 15))
        d.line([root, knuckle, tip], fill=C["carbon1"], width=3)
        d.point(knuckle, fill=C["edge"])
        if curl > .8:
            d.line((fx, y - 4, fx + 2, y - 4), fill=C["carbon3"], width=2)
    d.line((x + 7, y + 3, x + 2, y + 4), fill=C["edge"], width=2)
    return hand


GLOVES = {}


def glove(canvas, at, grip, wrist):
    grip = round(max(0, min(1, grip)) * 16) / 16
    if grip not in GLOVES:
        GLOVES[grip] = Piece(glove_image(grip), origin=(-20, -30))
    # Keep the readable front-facing fist, with bounded forearm follow-through.
    angle = max(-.75, min(.75, math.atan2(at[0] - wrist[0], at[1] - wrist[1]) * .45))
    place(canvas, GLOVES[grip], (0, 0), (0, -20), at,
          (at[0] + math.sin(angle) * 20, at[1] - math.cos(angle) * 20))


def cannon(frame, elbow, wrist, charged=False):
    """Arm-mounted device on anatomical RIGHT forearm (screen left)."""
    x, y = rnd(elbow[0]), rnd(elbow[1])
    tip = (rnd(wrist[0]), rnd(wrist[1]))
    length = max(8, rnd(math.hypot(tip[0] - x, tip[1] - y)))
    step = 1 / length
    angle = round(heading((x, y), tip) / step) * step
    ux, uy = math.cos(angle), math.sin(angle)
    nx, ny = -uy, ux

    def pt(t, n):
        width = 1.2 if charged else 1
        return (round(x + ux * t + nx * n * width), round(y + uy * t + ny * n * width))

    d = ImageDraw.Draw(frame)
    muzzle = length - 2
    d.polygon([pt(2, -10), pt(8, -13), pt(muzzle, -10), pt(muzzle + 4, -5),
               pt(muzzle + 4, 7), pt(6, 10), pt(1, 4)],
              fill=C["carbon0"], outline=C["ink"])
    d.polygon([pt(6, -9), pt(muzzle - 3, -7), pt(muzzle, 1), pt(8, 3)], fill=C["carbon2"])
    d.line([pt(6, -10), pt(muzzle - 4, -8)], fill=C["edge"])
    d.polygon([pt(5, 4), pt(muzzle - 7, 3), pt(muzzle - 6, 7), pt(7, 8)], fill=C["gold4"])
    d.line([pt(7, 5), pt(muzzle - 9, 4)], fill=C["gold6"])
    for t in (10, 16, 22):
        d.line([pt(t, -6), pt(t, 0)], fill=C["ink"], width=2)
    d.line([pt(muzzle + 3, -6), pt(muzzle + 3, 5)], fill=C["gold2"], width=3)
    d.line([pt(muzzle + 4, -3), pt(muzzle + 4, 2)],
           fill=C["gold7"] if charged else C["ink"], width=2)
    return pt(muzzle + 7, 0), (ux, uy)


class Frame:
    """Everything an effect needs: time, 2D joints, image and muzzle."""

    def __init__(self, t, p, image, muzzle, vector):
        self.t, self.p = t, p
        self.image, self.muzzle, self.vector = image, muzzle, vector


def render(clip, t, P, W):
    p = derive({j: (float(v[0]), float(v[1])) for j, v in P.items()})
    canvas = np.zeros((SIZE[1], SIZE[0], 4), np.uint8)

    def limb_depth(side, joints):
        return sum(float(P[f"{side}_{j}"][2]) for j in joints) / len(joints)

    for side in sorted(SIDES, key=lambda s: limb_depth(s, ("knee", "ankle"))):
        for name, a, b in LEG_SEGMENTS:
            a, b = f"{side}_{a}", f"{side}_{b}"
            place(canvas, pieces[f"{side}_{name}"], RIG_REST[a], RIG_REST[b], p[a], p[b])
    arms = sorted(SIDES, key=lambda s: (s == "right", limb_depth(s, ("elbow", "wrist"))))
    behind = [s for s in arms if limb_depth(s, ("elbow", "wrist", "hand")) < -14]
    muzzle = vector = None

    def draw_arm(side):
        nonlocal canvas, muzzle, vector
        sh, bi, el, wr, hd = (f"{side}_{j}" for j in ("shoulder", "bicep", "elbow", "wrist", "hand"))
        # The pauldron rides with the torso and only half follows the humerus.
        torso_turn = wrap(heading(p["chest"], p["neck"]) - heading(RIG_REST["chest"], RIG_REST["neck"]))
        reach = math.hypot(p[el][0] - p[sh][0], p[el][1] - p[sh][1]) / ARM[side]["upper"]
        arm_turn = wrap(heading(p[sh], p[el]) - heading(RIG_REST[sh], RIG_REST[el]) - torso_turn)
        pad = torso_turn + max(-.9, min(.9, arm_turn * .55 * min(1, reach * 1.4)))
        rest_pad = (RIG_REST[bi][0] - RIG_REST[sh][0], RIG_REST[bi][1] - RIG_REST[sh][1])
        cp, sp = math.cos(pad), math.sin(pad)
        pad_end = (p[sh][0] + rest_pad[0] * cp - rest_pad[1] * sp,
                   p[sh][1] + rest_pad[0] * sp + rest_pad[1] * cp)
        place(canvas, pieces[f"{side}_upper"], RIG_REST[bi], RIG_REST[el], p[bi], p[el])
        place(canvas, pieces[f"{side}_shoulder"], RIG_REST[sh], RIG_REST[bi], p[sh], pad_end)
        place(canvas, pieces[f"{side}_lower"], RIG_REST[el], RIG_REST[wr], p[el], p[wr])
        img = Image.fromarray(canvas)
        if side == "right":
            muzzle, vector = cannon(img, p[el], p[wr], clip.charged(t))
        d = ImageDraw.Draw(img)
        link = [(rnd(p[j][0]), rnd(p[j][1])) for j in (wr, hd)]
        d.line(link, fill=C["ink"], width=9)
        d.line(link, fill=C["carbon1"], width=5)
        if side in clip.hold:
            clip.hold[side](Frame(t, p, img, muzzle, vector), d)
        canvas = np.array(img)
        glove(canvas, p[hd], clip.grip[side](t), p[wr])

    for side in behind:
        draw_arm(side)
    for name, a, b in TORSO_SEGMENTS:
        place(canvas, pieces[name], RIG_REST[a], RIG_REST[b], p[a], p[b])
    for side in arms:
        if side not in behind:
            draw_arm(side)
    image = Image.fromarray(canvas)
    frame = Frame(t, p, image, muzzle, vector)
    if clip.draw:
        clip.draw(frame, ImageDraw.Draw(image))
    return frame


def simulate(clip):
    """Sample channels, run springs (two passes for loops), return per-frame FK."""
    clip.compile()
    times = list(range(0, clip.ms, FRAME_MS))
    # Spring offsets fade out where clips meet, so seams land exactly on the pose.
    if clip.loop:
        def fade(t):
            return smooth(t / 240) * (1 - smooth((t - (clip.ms - 260)) / 240))
    else:
        def fade(t):
            return 1 - smooth((t - (clip.ms - 260)) / 220)
    springs = Springs(clip.springs, fade)
    result = []
    for _ in range(2 if clip.loop else 1):
        result = []
        for t in times:
            ch = clip.channels(t)
            P, W = fk(ch, springs, t)
            result.append((t, ch, P, W))
    return result


# ------------------------------------------------------------------- effects

def rose(d, center, crushed=False):
    x, y = map(round, center)
    if crushed:
        d.polygon([(x - 7, y - 2), (x - 1, y - 5), (x + 6, y - 3), (x + 5, y + 2),
                   (x, y + 3), (x - 6, y + 1)], fill=C["gold5"], outline=C["gold2"])
        return
    d.line((x, y + 3, x - 1, y + 26), fill=C["gold3"], width=2)
    d.polygon([(x, y + 15), (x + 8, y + 9), (x + 5, y + 16)], fill=C["gold4"])
    d.polygon([(x - 1, y + 20), (x - 8, y + 14), (x - 6, y + 21)], fill=C["gold2"])
    d.polygon([(x - 11, y - 4), (x - 6, y - 10), (x + 3, y - 12), (x + 11, y - 6),
               (x + 12, y + 2), (x + 5, y + 9), (x - 5, y + 8), (x - 12, y + 2)],
              fill=C["gold3"], outline=C["gold0"])
    d.line([(x - 10, y - 3), (x - 5, y - 8), (x + 3, y - 10), (x + 8, y - 6)], fill=C["gold7"], width=2)
    d.polygon([(x - 6, y - 4), (x, y - 7), (x + 7, y - 3), (x + 5, y + 4), (x - 1, y + 6),
               (x - 7, y + 2)], fill=C["gold5"])
    d.line([(x - 7, y + 3), (x - 2, y + 7), (x + 6, y + 5), (x + 10, y)], fill=C["gold6"], width=2)
    d.polygon([(x - 4, y - 2), (x + 2, y - 4), (x + 5, y), (x + 1, y + 3), (x - 4, y + 1)],
              fill=C["gold1"])
    d.line([(x - 3, y - 2), (x + 1, y - 3), (x + 3, y - 1)], fill=C["gold7"])


def petals(d, center, phase):
    """Rose fragments on ballistic arcs: thrown outward, then falling and tumbling."""
    x, y = center
    for j in range(14):
        angle = j * math.tau / 14 + .24
        speed = 26 + (j % 4) * 8
        drag = 1 - math.exp(-phase * 2.6)
        px = round(x + math.cos(angle) * (10 + speed * drag))
        py = round(y + math.sin(angle) * (10 + speed * drag) * .8 + phase * phase * 30)
        size = max(1, 4 - int(phase * 3))
        if (j + int(phase * 18)) % 2:
            shape = [(px - size, py), (px, py - size - 1), (px + size + 1, py + 1), (px, py + size)]
        else:
            shape = [(px - size, py - 1), (px + size, py - size), (px + size - 1, py + 1), (px - 1, py + size)]
        d.polygon(shape, fill=C["gold6" if j % 3 else "gold3"])
        if phase < .4:
            d.line((px - 4, py + 2, px - 7, py + 4), fill=C["gold2"])


def shot_effect(d, muzzle, vector, phase):
    x, y = muzzle
    ux, uy = vector
    nx, ny = -uy, ux

    def p(t, n=0):
        return (round(x + ux * t + nx * n), round(y + uy * t + ny * n))

    if phase < .45:
        d.polygon([p(0, -8), p(17, -15), p(13, -6), p(35, -1), p(15, 6), p(20, 14), p(0, 8)],
                  fill=C["gold5"])
        d.polygon([p(0, -5), p(25, 0), p(0, 5)], fill=C["gold7"])
    elif phase < .7:
        d.polygon([p(2, -4), p(12, -6), p(18, 0), p(12, 6), p(2, 4)], fill=C["gold3"])
    t = 22 + phase * 30
    d.line([p(t - 20), p(t - 6)], fill=C["gold2"], width=6)
    d.polygon([p(t - 12, -6), p(t + 1, -6), p(t + 9, 0), p(t + 1, 6), p(t - 12, 6)],
              fill=C["gold5"], outline=C["gold3"])
    d.line([p(t - 9), p(t + 4)], fill=C["gold7"], width=3)
    for j in range(3):
        d.rectangle((*p(8 + phase * 5, -8 - j * 5), *p(8 + phase * 5, -8 - j * 5)), fill=C["gold5"])


def grenade(d, center, angle=0):
    x, y = center
    co, si = math.cos(angle), math.sin(angle)

    def p(a, b):
        return round(x + a * co - b * si), round(y + a * si + b * co)

    d.polygon([p(-5, -8), p(5, -8), p(6, 7), p(3, 10), p(-4, 9), p(-6, 5)],
              fill=C["void"], outline=C["edge"])
    d.line([p(-4, -3), p(4, -3)], fill=C["gold5"], width=3)
    d.line([p(-3, 5), p(4, 5)], fill=C["gold2"], width=2)
    d.line([p(-2, -9), p(4, -11), p(7, -6)], fill=C["gold4"], width=2)


def smoke_cloud(elapsed, origin):
    """Black billows with gold embers inside; ordered dissolve keeps pixel alpha."""
    cloud = Image.new("RGBA", SIZE)
    d = ImageDraw.Draw(cloud)
    grow = 1 - (1 - smooth(elapsed / 900)) ** 2
    fade = 1 - smooth((elapsed - 1300) / 900)
    if elapsed < 0 or fade <= 0:
        return cloud
    ox, oy = origin
    shades = ("#08090c", "#0e1014", "#14161b", "#1c1f25")
    for j in range(24):
        angle = j * 2.39996
        spread = (18 + j % 5 * 7) * grow
        # Billows rise and drift as they expand; inner ones churn slowly.
        x = ox + math.cos(angle) * spread - 20 * grow + math.sin(elapsed / 430 + j) * 3 * grow
        y = oy - 4 - grow * (28 + j % 4 * 13) + math.sin(angle) * spread * .55
        radius = (13 + j % 4 * 4) * (.18 + .82 * grow)
        points = []
        for k in range(14):
            a = k * math.tau / 14
            r = radius * (1 + .12 * math.sin(k * 2 + j + elapsed / 300))
            points.append((round(x + math.cos(a) * r), round(y + math.sin(a) * r)))
        d.polygon(points, fill=shades[j % 4])
        d.polygon([lerp((x, y), point, .7) for point in points], fill=shades[j % 2])
    for j in range(42):
        phase = (elapsed / 1700 + j * .618) % 1
        angle = j * 2.4 + elapsed / 950
        x = round(ox - 20 + math.cos(angle) * (10 + j % 6 * 7) * grow)
        y = round(oy - 6 - phase * 109 * grow)
        if 0 <= x < SIZE[0] and 0 <= y < SIZE[1] and cloud.getpixel((x, y))[3]:
            color = C["gold6" if (j + int(elapsed / 160)) % 5 == 0 else "gold3"]
            d.line((x, y, x + 1, y - 2 - j % 2), fill=color, width=1 + j % 2)
    if fade < 1:
        # Pixel-stable 4x4 ordered transparency avoids random frame-to-frame flicker.
        order = np.array(((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5)))
        pixels = np.array(cloud)
        ys, xs = np.indices(pixels.shape[:2])
        pixels[(order[ys % 4, xs % 4] + .5) / 16 > fade] = 0
        cloud = Image.fromarray(pixels)
    return cloud


# --------------------------------------------------------------------- clips

def breath_wave(t, period, inhale, exhale):
    """Active inhale, slower passive exhale, then a rest before the next breath."""
    t %= period
    if t < inhale:
        return smooth(t / inhale)
    if t < inhale + exhale:
        return 1 - smooth((t - inhale) / exhale)
    return 0.0


def mix(a, b, t, over=None):
    out = {c: a[c] + (b[c] - a[c]) * t for c in a}
    out.update(over or {})
    return out


def ramp(t, start, end):
    return smooth((t - start) / (end - start))


CLIPS = []

# Idle: two calm breaths (15 per minute) and one slow contrapposto weight
# shift per loop. Hips tilt one way, shoulders the other; feet stay planted.
idle = Clip("idle", "待机", 8000, 0, loop=True)


def idle_layer(t, ch):
    b = breath_wave(t, 4000, 1500, 1900) * (1 if t < 4000 else .8)
    s = math.sin(math.tau * t / 8000)
    ch["breath"] = b
    ch["pelvis.x"], ch["pelvis.rz"] = .9 * s, -.8 * s
    ch["waist.rz"], ch["chest.rz"] = 1.0 * s, .5 * s
    for k in "rl":
        ch[f"{k}.phi"] += 1.5 * b


idle.layers.append(idle_layer)
idle.springs = {"right_shoulder": (2.4, .5), "left_shoulder": (2.2, .5),
                "right_wrist": (3.2, .5), "left_wrist": (3.0, .5)}
CLIPS.append(idle)

# Rest: slumped shoulders, head sunk forward, slow deep breathing.
SLEEP = pose(pelvis={"y": 2.5}, waist={"rx": -2}, chest={"rx": -5, "rz": 1.2},
             neck={"rz": 2.5}, head={"rz": 4}, neck_len=.6, head_level=.35,
             clav_r=(-3.5, 5), clav_l=(-3.5, 5),
             arm_r={"flex": 3, "abd": -1.5, "elbow": 22},
             arm_l={"flex": 3, "abd": -1.5, "elbow": 30})
sleep = Clip("sleep", "休整", 5600, 0, loop=True)


def sleep_layer(t, ch):
    ch.update(SLEEP)
    b = breath_wave(t, 5600, 2200, 2700) * 1.3
    ch["breath"] = b
    ch["neck.len"] += .07 * b
    ch["pelvis.y"] -= .4 * b


def drowsy_marks(f, d):
    for j in range(2):
        # Glyphs step together every 80 ms, like hand-placed pixel effects.
        phase = (math.floor(f.t / 80) + j * 18) % 35 / 35
        x, y = round(198 + phase * 18), round(84 - phase * 31)
        size = 6 if j == 0 else 4
        d.line([(x, y), (x + size, y), (x, y + size), (x + size, y + size)],
               fill=C["gold4" if phase < .65 else "gold2"])


sleep.layers.append(sleep_layer)
sleep.draw = drowsy_marks
sleep.springs = {"right_wrist": (2.5, .5), "left_wrist": (2.5, .5)}
CLIPS.append(sleep)

# Dozing off: a long exhale, shoulders sink, the head drops, nods once, settles.
doze = Clip("doze", "入睡", 1300, 1280, transition=True)
doze.key(0, REST_POSE)
doze.key(420, mix(REST_POSE, SLEEP, .3, {"breath": .35}))
doze.key(800, mix(REST_POSE, SLEEP, 1.05, {"neck.len": .54}), ease="in")
doze.key(960, mix(REST_POSE, SLEEP, .82))
doze.key(1240, SLEEP)
doze.springs = {"right_wrist": (2.6, .45), "left_wrist": (2.6, .45),
                "right_shoulder": (2.2, .5), "left_shoulder": (2.2, .5)}
CLIPS.append(doze)

# Waking: the head snaps up, a stretching inhale lifts chest and shoulders,
# then the body exhales back into the ready stance.
STRETCH = pose(pelvis={"y": -.5}, chest={"rx": 4}, neck={"rx": 2}, breath=1,
               clav_r=(4, -3), clav_l=(4, -3),
               arm_r={"flex": -4, "abd": 7, "elbow": 14},
               arm_l={"flex": -4, "abd": 7, "elbow": 18})
wake = Clip("wake", "醒来", 1500, 1480, transition=True)
wake.key(0, SLEEP)
wake.key(170, mix(SLEEP, REST_POSE, .6, {"neck.len": .97}), ease="out")
wake.key(600, STRETCH)
wake.key(1000, mix(STRETCH, REST_POSE, .75, {"breath": .25}))
wake.key(1420, REST_POSE)
CLIPS.append(wake)

# Slide: load the legs, push off, drop the hips and lean back into the glide,
# brake with the lead heel, gather the feet under the hips, stand and settle.
SLIDE_MOVE = (400, 1320)
crouch = pose(pelvis={"x": -2, "y": 24, "rz": -4.6}, waist={"rz": 13}, chest={"rz": 4},
              neck={"rz": -3}, head={"rz": -2}, head_level=0,
              leg_r={"knee": (-1, 0), "inplane": .4}, leg_l={"knee": (1, 0), "inplane": .4},
              arm_r={"wrist": (90, 196, -10), "pole": (-.4, .3, -1)},
              arm_l={"wrist": (214, 204, -12), "pole": (.4, .3, -1)})
launch = pose(pelvis={"x": 12, "y": 24, "rz": 2}, waist={"rz": 4}, chest={"rz": 1},
              neck={"rz": -3}, head={"rz": -2}, head_level=0,
              leg_r={"ankle": (130, 274), "knee": (-1, .2), "inplane": 1, "foot": -30},
              leg_l={"ankle": (214, 256), "knee": (1, -1), "inplane": 1, "foot": -35},
              arm_r={"wrist": (140, 204, 22), "pole": (-.3, .5, -1)},
              arm_l={"wrist": (198, 220, -18), "pole": (.3, .4, -1)})
extend = pose(pelvis={"x": 3, "y": 58, "rz": -45}, waist={"rz": 1.5}, chest={"rz": 2.7},
              neck={"rz": 22}, head={"rz": 30}, head_level=0,
              leg_r={"ankle": (134, 282), "knee": (-.6, -1), "inplane": 1, "foot": -74},
              leg_l={"ankle": (243, 279), "knee": (0, -1), "inplane": 1, "foot": -49},
              arm_r={"wrist": (72, 272), "pole": (-1, -.2, 0)},
              arm_l={"wrist": (186, 239), "pole": (.2, -1, 0)})
glide = pose(pelvis={"x": 6, "y": 67, "rz": -57.5}, waist={"rz": 5.5}, chest={"rz": 3},
             neck={"rz": 26}, head={"rz": 38}, head_level=0,
             leg_r={"ankle": (136, 282), "knee": (-.6, -1), "inplane": 1, "foot": -76},
             leg_l={"ankle": (254, 281), "knee": (0, -1), "inplane": 1, "foot": -52},
             arm_r={"wrist": (78, 278), "pole": (-1, -.3, 0)},
             arm_l={"wrist": (183, 247), "pole": (.2, -1, 0)})
brake = pose(pelvis={"x": 4, "y": 63, "rz": -38}, waist={"rz": 1}, chest={"rz": 9},
             neck={"rz": 16}, head={"rz": 22}, head_level=0,
             leg_r={"ankle": (132, 282), "knee": (-.6, -1), "inplane": 1, "foot": -76},
             leg_l={"ankle": (245, 281), "knee": (0, -1), "inplane": 1, "foot": -40},
             arm_r={"wrist": (84, 269), "pole": (-1, -.2, 0)},
             arm_l={"wrist": (199, 244), "pole": (.2, -1, 0)})
gather = pose(pelvis={"x": -1, "y": 32, "rz": 4.4}, waist={"rz": 12}, chest={"rz": 0},
              neck={"rz": -5}, head={"rz": -3}, head_level=0,
              leg_r={"knee": (-1, 0), "inplane": .5},
              leg_l={"ankle": (196, 270), "knee": (1, -.3), "inplane": .7},
              arm_r={"wrist": (116, 206, 12), "pole": (-.3, .4, -1)},
              arm_l={"wrist": (222, 214, 6), "pole": (.4, .3, -1)})
settle = pose(pelvis={"y": 2}, waist={"rz": -1.5}, chest={"rz": -1},
              leg_l={"ankle": (180, 270)})
slide = Clip("slide", "滑铲", 2000, 640,
             movement={"start": SLIDE_MOVE[0], "end": SLIDE_MOVE[1], "distance": 150})
for t, k in ((0, REST_POSE), (220, crouch), (330, launch), (520, extend), (680, glide),
             (1080, glide), (1300, brake), (1520, gather), (1760, settle), (1900, REST_POSE)):
    slide.key(t, k)
slide.springs = {"right_shoulder": (3.5, .45), "left_shoulder": (3.5, .45),
                 "right_wrist": (4.5, .45), "left_wrist": (4.5, .45), "jaw": (5, .6)}


def slide_layer(t, ch):
    # Ground chatter enters at the hips and fades up the spine.
    if 600 < t < 1200:
        s = (t - 600) / 600
        bump = math.sin(s * math.tau * 2.5) * 1.6 * math.sin(s * math.pi)
        ch["pelvis.y"] += bump
        ch["waist.rz"] -= bump * .6
        ch["chest.rz"] -= bump * .3


def slide_dust(f, d):
    if not SLIDE_MOVE[0] <= f.t < 1500:
        return
    fade = 1 - smooth((f.t - 1180) / 300)
    for j in range(12):
        age = ((f.t - SLIDE_MOVE[0]) / 480 + j / 12) % 1
        x = round(110 - age * 76)
        y = round(291 - math.sin(age * math.pi) * (8 + j % 3 * 4))
        length = max(1, round((1 - age) * 9 * fade))
        if fade > .05:
            d.line((x, y, x + length, y), fill=C["gold2" if j % 3 == 0 else "cloth3"])


def slide_curve():
    """Window travel: a quick push-off, then friction decelerates to rest."""
    n = (SLIDE_MOVE[1] - SLIDE_MOVE[0]) // FRAME_MS
    speed = [smooth(i / n / .12) * (1 - i / n) for i in range(n + 1)]
    total, out = 0.0, [0.0]
    for a, b in zip(speed, speed[1:]):
        total += (a + b) / 2
        out.append(total)
    return [round(v / total, 4) for v in out]


slide.layers.append(slide_layer)
slide.draw = slide_dust
slide.extra["movement"]["samples"] = slide_curve()
CLIPS.append(slide)

# Rose: lift the flower beside the mask, admire, crush it in the fist; the
# burst kicks the hand open and the head flinches, then the arm lowers on an arc.
r_lift = pose(clav_r=(-1.5, 0), arm_r={"wrist": (108, 186, -6), "pole": (-.3, .2, -1)})
r_raise = pose(chest={"ry": -5, "rz": -1}, head={"rz": -1.5}, clav_r=(1, 3),
               arm_r={"wrist": (113, 122, 36), "pole": (-.35, 1, -.25), "hand": (-8, 0)})
r_admire = pose(chest={"ry": -6, "rz": -1}, head={"rz": -2}, breath=.7, clav_r=(1.5, 3),
                arm_r={"wrist": (114, 120, 38), "pole": (-.35, 1, -.25), "hand": (-10, 0)})
r_crush = pose(chest={"ry": -6, "rz": -1.5}, head={"rz": -2}, breath=.9, clav_r=(3, 5),
               arm_r={"wrist": (114, 116, 41), "pole": (-.35, 1, -.25), "hand": (-14, 0)})
r_burst = pose(chest={"ry": -3, "rz": .8}, neck={"rz": 1}, neck_len=1.05, breath=.4,
               clav_r=(1, 2), arm_r={"wrist": (104, 118, 34), "pole": (-.5, 1, -.25), "hand": (6, 0)})
r_open = pose(chest={"ry": -3}, clav_r=(0, 2), breath=.3,
              arm_r={"wrist": (106, 124, 32), "pole": (-.5, 1, -.25), "hand": (4, 0)})
r_lower = pose(arm_r={"wrist": (110, 162, 18), "pole": (-.4, .4, -1)})
rose_clip = Clip("rose", "捏爆金玫瑰", 2800, 1250)
for t, k, e in ((0, REST_POSE, None), (180, r_lift, None), (620, r_raise, None),
                (900, r_admire, None), (1160, r_crush, "in"), (1240, r_burst, "out"),
                (1700, r_open, None), (2120, r_lower, None), (2560, REST_POSE, None)):
    rose_clip.key(t, k, e)
rose_clip.lag = {"head.": 50, "neck.": 40}
rose_clip.springs = {"right_shoulder": (6, .6), "left_shoulder": (3, .45),
                     "right_wrist": (6, .45), "left_wrist": (4, .45)}


def rose_grip(t):
    if t < 620:
        return 1 - ramp(t, 120, 420) * .85
    if t < 1240:
        return .15 + .85 * ((t - 900) / 260) ** 2 if t > 900 else .15
    return 1 - ramp(t, 1240, 1320) * .6 + ramp(t, 1900, 2300) * .6


def rose_hold(f, d):
    if 180 <= f.t < 1250:
        hand = f.p["right_hand"]
        grip = rose_grip(f.t)
        rose(d, (hand[0], hand[1] - 15 + grip * 9), crushed=f.t >= 1160)


def rose_burst(f, d):
    if 1240 <= f.t < 2000:
        petals(d, rose_clip.burst_point, (f.t - 1240) / 760)


rose_clip.grip["right"] = rose_grip
rose_clip.hold["right"] = rose_hold
rose_clip.draw = rose_burst
CLIPS.append(rose_clip)

# Hand cannon: brace (hips shift away from the muzzle, knees soften), raise
# the forearm on an arc, then three shots. Each recoil kicks the forearm,
# reaches the chest ~30 ms later and the head last, then settles.
SHOTS = (560, 800, 1040)
c_load = pose(pelvis={"x": 1}, clav_r=(-2, -2),
              arm_r={"wrist": (109, 188, -8), "pole": (-.3, .2, -1)})
c_aim = pose(pelvis={"x": 2.5, "y": 1.5, "rz": .8}, waist={"rz": -1.5}, chest={"rz": -2.5, "ry": -4},
             clav_r=(1, 2), arm_r={"wrist": (86, 135, 40), "elbow": (118, 140, 40)},
             arm_l={"wrist": (214, 182, 6), "pole": (.4, .2, -1)})
# Recoil drives the muzzle up and the forearm back toward the shoulder.
c_kick = pose(pelvis={"x": 3, "y": 2, "rz": .8}, waist={"rz": -.5}, chest={"rz": -.5, "ry": -2},
              clav_r=(2.5, -2), arm_r={"wrist": (95, 125, 37), "elbow": (122, 137, 37)},
              arm_l={"wrist": (216, 180, 6), "pole": (.4, .2, -1)})
c_lower = pose(pelvis={"x": 1}, arm_r={"wrist": (104, 164, 24), "elbow": (114, 150, 10)})
cannon_clip = Clip("cannon", "右臂手炮", 2100, 860,
                   events=[{"type": "shot", "atMs": t} for t in SHOTS])
cannon_clip.key(0, REST_POSE).key(140, c_load).key(420, c_aim)
for start in SHOTS:
    cannon_clip.key(start, c_aim).key(start + 45, c_kick, "out").key(start + 230, c_aim)
cannon_clip.key(1500, c_lower).key(1900, REST_POSE)
cannon_clip.lag = {"chest.": 25, "waist.": 30, "pelvis.": 35, "neck.": 50, "head.": 60}
cannon_clip.springs = {"right_shoulder": (7, .55), "left_shoulder": (3, .4),
                       "right_wrist": (8, .5), "left_wrist": (4, .45), "jaw": (6, .5)}
cannon_clip.charged = lambda t: 420 <= t < 1300


def cannon_fire(f, d):
    for start in SHOTS:
        if start <= f.t < start + 120 and f.muzzle:
            origin, vector = cannon_clip.aim_muzzle
            shot_effect(d, origin, vector, (f.t - start) / 120)


cannon_clip.draw = cannon_fire
CLIPS.append(cannon_clip)

# Smoke grenade: reach to the belt, pull the pin with the left hand, cock the
# arm by the ear with weight on the back foot, then hips, chest, shoulder,
# elbow and wrist fire in sequence; release in front of the shoulder, follow
# through across the body, recover. The grenade flies, bounces, then smokes.
RELEASE, LAND, BOUNCE = 800, 1220, 1340
s_reach = pose(chest={"rx": -3}, head={"rz": -1}, neck_len=.96,
               arm_r={"wrist": (128, 168, 22), "pole": (-.7, .5, -.4)})
s_pull = pose(chest={"rx": -2},
              arm_r={"wrist": (128, 132, 26), "pole": (-.6, .7, -.4)},
              arm_l={"wrist": (142, 132, 28), "pole": (.6, .7, -.4)})
s_pin = pose(arm_r={"wrist": (122, 128, 22), "pole": (-.6, .7, -.4)},
             arm_l={"wrist": (190, 150, 18), "pole": (.6, .5, -.6)})
s_cock = pose(pelvis={"x": -3, "rz": 1}, waist={"rz": -2}, chest={"rz": -3, "ry": -14},
              clav_r=(3, -4), arm_r={"wrist": (98, 66, -12), "pole": (-1, .3, -.3)},
              arm_l={"wrist": (206, 140, 24), "pole": (.5, .6, -.5)})
s_whip = pose(pelvis={"x": 1.5}, waist={"rz": 1}, chest={"rz": 1, "ry": 4},
              clav_r=(3, 3), arm_r={"wrist": (122, 64, 48), "pole": (-.8, .5, -.3)},
              arm_l={"wrist": (212, 170, 4), "pole": (.5, .3, -1)})
s_release = pose(pelvis={"x": 3, "rz": -1}, waist={"rz": 2}, chest={"rz": 3, "ry": 14},
                 clav_r=(1, 7), arm_r={"wrist": (172, 99, 76), "pole": (-.2, 1, -.3)},
                 arm_l={"wrist": (214, 188, -10), "pole": (.5, .3, -1)})
s_follow = pose(pelvis={"x": 3, "y": 1.5}, waist={"rx": -2, "rz": 2}, chest={"rx": -5, "rz": 3, "ry": 18},
                clav_r=(-1, 6), arm_r={"wrist": (184, 166, 30), "pole": (-.2, .8, -.6)},
                arm_l={"wrist": (214, 192, -8), "pole": (.5, .3, -1)})
s_recover = pose(pelvis={"x": 1}, chest={"ry": 4},
                 arm_r={"wrist": (120, 186, 14), "pole": (-.3, .3, -1)})
smoke_clip = Clip("smoke", "投掷烟雾弹", 3600, 1500,
                  events=[{"type": "release", "atMs": RELEASE}, {"type": "smoke", "atMs": BOUNCE}])
for t, k in ((0, REST_POSE), (250, s_reach), (420, s_pull), (520, s_pin), (640, s_cock),
             (720, s_whip), (RELEASE, s_release), (1010, s_follow), (1420, s_recover),
             (1800, REST_POSE)):
    smoke_clip.key(t, k)
smoke_clip.lag = {"pelvis.": -70, "waist.": -50, "chest.": -30, "head.": 40, "neck.": 30}
# The throwing arm is muscle-driven by its keys; only passive parts get inertia.
smoke_clip.springs = {"left_shoulder": (3.2, .45), "right_wrist": (7, .5),
                      "left_wrist": (4, .45), "jaw": (5, .55)}


def smoke_layer(t, ch):
    # A recovery breath while the cloud spreads.
    if t > 1800:
        ch["breath"] = breath_wave(t - 1800, 1800, 700, 1000) * .8


def smoke_grip(t):
    if t < RELEASE:
        return 1 - ramp(t, 60, 220) * .55 + ramp(t, 230, 270) * .55
    return 1 - ramp(t, RELEASE, RELEASE + 50) * .8 + ramp(t, 1100, 1500) * .8


def smoke_left_grip(t):
    return 1 - ramp(t, 300, 400) * .5 + ramp(t, 410, 440) * .5


def smoke_hold(f, d):
    if 250 <= f.t < RELEASE:
        hand = f.p["right_hand"]
        grenade(d, (hand[0], hand[1] - 2), -.25)


def pin_hold(f, d):
    if 430 <= f.t < 1000:
        x, y = (round(v) for v in f.p["left_hand"])
        d.ellipse((x + 3, y - 12, x + 9, y - 6), outline=C["gold5"])
        d.line((x + 6, y - 6, x + 6, y - 2), fill=C["gold3"])


def grenade_flight(f, d):
    rx, ry = smoke_clip.release_point
    landing = (262, 286)
    if RELEASE <= f.t < LAND:
        s = (f.t - RELEASE) / (LAND - RELEASE)
        x = rx + (landing[0] - rx) * s
        y = ry + (landing[1] - ry) * s - 150 * s * (1 - s)
        grenade(d, (x, y), s * math.tau * 1.5)
    elif LAND <= f.t < BOUNCE:
        s = (f.t - LAND) / (BOUNCE - LAND)
        grenade(d, (landing[0] + 6 * s, landing[1] - 10 * s * (1 - s) * 4), math.pi * (1 + s))
    elif BOUNCE <= f.t < 1900:
        grenade(d, (landing[0] + 6, landing[1]), math.pi / 2)
    if f.t >= BOUNCE:
        f.image.alpha_composite(smoke_cloud(f.t - BOUNCE, (landing[0] + 4, landing[1] - 8)))


smoke_clip.layers.append(smoke_layer)
smoke_clip.grip["right"] = smoke_grip
smoke_clip.grip["left"] = smoke_left_grip
smoke_clip.hold["right"] = smoke_hold
smoke_clip.hold["left"] = pin_hold
smoke_clip.draw = grenade_flight
CLIPS.append(smoke_clip)


# ------------------------------------------------------------------- output

SIMS = {}


def build(clip):
    sim = SIMS[clip.name] = simulate(clip)
    # More than ~26 px between 20 ms frames reads as a teleport, not a motion.
    for joint in ("right_hand", "left_hand", "crown", "hip"):
        jump = max(float(np.linalg.norm((b[2][joint] - a[2][joint])[:2]))
                   for a, b in zip(sim, sim[1:]))
        assert jump <= 26, (clip.name, joint, round(jump, 1))

    def at(ms):
        return min(sim, key=lambda s: abs(s[0] - ms))

    if clip is cannon_clip:
        # Shells leave from the aimed muzzle even while the arm recoils.
        t, ch, P, W = at(SHOTS[0])
        aim = render(Clip("probe", "", 20, 0), t, P, W)
        clip.aim_muzzle = (aim.muzzle, aim.vector)
    if clip is smoke_clip:
        hand = at(RELEASE)[2]["right_hand"]
        clip.release_point = (float(hand[0]), float(hand[1]) - 2)
    if clip is rose_clip:
        hand = at(1240)[2]["right_hand"]
        clip.burst_point = (float(hand[0]), float(hand[1]) - 8)
    return [render(clip, t, P, W) for t, ch, P, W in sim]


def pack_timeline(images):
    """Merge identical neighbours into longer frames; reuse identical cells."""
    cells, durations, unique, index, last = [], [], [], {}, None
    for image in images:
        key = hashlib.sha1(image.tobytes()).digest()
        if key == last:
            durations[-1] += FRAME_MS
            continue
        if key not in index:
            index[key] = len(unique)
            unique.append(image)
        cells.append(index[key])
        durations.append(FRAME_MS)
        last = key
    return cells, durations, unique


def frame_at(durations, ms):
    end = 0
    for i, duration in enumerate(durations):
        end += duration
        if ms < end:
            return i
    return len(durations) - 1


def write(built):
    manifest = {"version": 2, "character": "redwolf", "skin": "蚀金玫瑰",
                "frameWidth": SIZE[0], "frameHeight": SIZE[1], "frameMs": FRAME_MS, "clips": {}}
    for clip, frames in built:
        images = [f.image for f in frames]
        boxes = []
        for i, image in enumerate(images):
            alpha = np.asarray(image.getchannel("A"))
            assert set(np.unique(alpha)) <= {0, 255}, (clip.name, i)
            box = image.getbbox()
            assert box and box[0] > 0 and box[1] > 0 and box[2] < SIZE[0] and box[3] < SIZE[1], \
                (clip.name, i, box)
            boxes.append(box)
        cells, durations, unique = pack_timeline(images)
        # Cells keep only the clip's union bounds: transparent margins cost decoded memory.
        x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
        x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
        w, h = x1 - x0, y1 - y0
        columns = max(1, min(len(unique), round(math.sqrt(len(unique) * h / w))))
        atlas = Image.new("RGBA", (columns * w, math.ceil(len(unique) / columns) * h))
        assert max(atlas.size) <= 8192, (clip.name, atlas.size)
        for i, image in enumerate(unique):
            atlas.alpha_composite(image.crop((x0, y0, x1, y1)), ((i % columns) * w, (i // columns) * h))
        atlas.save(OUT / f"{clip.name}-atlas.png", optimize=True)
        entry = {"label": clip.label, "file": f"{clip.name}-atlas.png", "columns": columns,
                 "cell": [x0, y0, w, h], "frameCount": len(durations), "durations": durations,
                 "cells": cells, "durationMs": sum(durations),
                 "keyframe": frame_at(durations, clip.keyframe_ms)}
        if clip.loop:
            entry["loop"] = True
        entry.update(clip.extra)
        manifest["clips"][clip.name] = entry
        # GIF review with a solid background only; runtime uses RGBA atlases.
        previews = []
        for cell in cells:
            bg = Image.new("RGB", SIZE, "#15191e")
            bg.paste(unique[cell], mask=unique[cell].getchannel("A"))
            previews.append(bg)
        previews[0].save(OUT / f"{clip.name}-preview.gif", save_all=True,
                         append_images=previews[1:], duration=durations, loop=0, disposal=2)
    (OUT / "animations.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def review_font(size):
    font_candidates = [
        os.environ.get("PIXEL_ART_FONT", ""),
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "C:/Windows/Fonts/msyh.ttc",
    ]
    font_path = next((p for p in font_candidates if p and Path(p).is_file()), None)
    if not font_path:
        raise RuntimeError("Set PIXEL_ART_FONT to a Chinese font to render the review sheets.")
    return ImageFont.truetype(font_path, size)


def review_sheet(built):
    """Contact sheet of windup, contact and recovery for each action."""
    font = review_font(20)
    moments = {"slide": (220, 330, 520, 900, 1300, 1560),
               "rose": (180, 620, 1160, 1300, 1700, 2120),
               "cannon": (140, 420, 605, 845, 1500, 1900),
               "smoke": (250, 520, 640, RELEASE, 1000, 1600)}
    by_name = {clip.name: frames for clip, frames in built}
    crop = (8, 16, 312, 304)
    w, h = crop[2] - crop[0], crop[3] - crop[1]
    sheet = Image.new("RGB", (w * 6, (h + 34) * len(moments)), "#10151b")
    d = ImageDraw.Draw(sheet)
    for row, (name, times) in enumerate(moments.items()):
        clip = next(c for c, _ in built if c.name == name)
        d.text((14, row * (h + 34) + 6), clip.label, font=font, fill="#dfc27b")
        for col, t in enumerate(times):
            image = by_name[name][t // FRAME_MS].image.crop(crop)
            sheet.paste(image, (col * w, row * (h + 34) + 34), image)
            d.text((col * w + w - 64, row * (h + 34) + 10), f"{t} ms", fill="#7d8891")
    sheet.save(OUT / "actions-review.png")


def motion_sheet(built, sims):
    """Joint paths, one dot per 20 ms: arcs show rotation about joints, dot
    spacing shows easing. Faint figures mark the first frame and keyframe."""
    trails = {"right_hand": "#e2231a", "right_elbow": "#f08c14", "left_hand": "#1e5ac8",
              "crown": "#14965a", "hip": "#8c28a0"}
    names = ("slide", "rose", "cannon", "smoke")
    scale = 2
    font = review_font(18)
    sheet = Image.new("RGB", (SIZE[0] * scale * 2, SIZE[1] * scale * 2), "#f4f4f0")
    for i, name in enumerate(names):
        clip, frames = next((c, f) for c, f in built if c.name == name)
        panel = Image.new("RGBA", SIZE, "#f4f4f0")
        for image, alpha in ((frames[0].image, 40), (frames[clip.keyframe_ms // FRAME_MS].image, 70)):
            ghost = image.copy()
            ghost.putalpha(ghost.getchannel("A").point(lambda a, k=alpha: a * k // 255))
            panel.alpha_composite(ghost)
        panel = panel.resize((SIZE[0] * scale, SIZE[1] * scale), Image.Resampling.NEAREST)
        d = ImageDraw.Draw(panel)
        for joint, color in trails.items():
            points = [(float(P[joint][0]) * scale, float(P[joint][1]) * scale) for _, _, P, _ in sims[name]]
            d.line(points, fill=color, width=1)
            for k, (x, y) in enumerate(points):
                r = 2.5 if k % 5 == 0 else 1.2
                d.ellipse((x - r, y - r, x + r, y + r), fill=color)
        d.text((12, 8), f"{clip.label}  {clip.ms} ms", font=font, fill="#111111")
        sheet.paste(panel, ((i % 2) * SIZE[0] * scale, (i // 2) * SIZE[1] * scale))
    sheet.save(OUT / "motion-review.png")


if __name__ == "__main__":
    built = [(clip, build(clip)) for clip in CLIPS]
    manifest = write(built)
    review_sheet(built)
    motion_sheet(built, SIMS)
    print(json.dumps({n: {"frames": v["frameCount"], "cells": max(v["cells"]) + 1,
                          "ms": v["durationMs"]} for n, v in manifest["clips"].items()}))
