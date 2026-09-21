"""Reproducible pixel study of 红狼「蚀金玫瑰」, based on asset/pic.

Run with Python 3.9+ and Pillow 11.3.0. This is a static art study, not an
animation generator. All sprite coordinates are native integer pixels.
"""

from pathlib import Path
import json
import os
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "asset" / "sprites" / "redwolf-gilded-rose"
OUT.mkdir(parents=True, exist_ok=True)
SIZE = (192, 288)

# Separate cool cloth, neutral carbon, warm gold and silver ramps.
PALETTE = {
    "ink": "#0b0e14", "void": "#11151c", "black": "#181d25",
    "cloth0": "#1e242d", "cloth1": "#282f38", "cloth2": "#353d47",
    "cloth3": "#454e58", "cloth4": "#59626b",
    "carbon0": "#151b20", "carbon1": "#252c30",
    "carbon2": "#394247", "carbon3": "#505a5d", "edge": "#6b7576",
    "gold0": "#453623", "gold1": "#66502e", "gold2": "#89703e",
    "gold3": "#aa8b4c", "gold4": "#c6a760", "gold5": "#dfc27b",
    "gold6": "#efda97", "gold7": "#fff0b8",
    "silver0": "#555e67", "silver1": "#7d8891",
    "silver2": "#acb5b9", "silver3": "#d2d8d6", "silver4": "#f0f1e9",
    "red0": "#4a242b", "red1": "#793d43", "red2": "#ac6364",
    "sole0": "#1c1d21", "sole1": "#343639", "sole2": "#535552",
}

sprite = Image.new("RGBA", SIZE)
d = ImageDraw.Draw(sprite)


def poly(points, fill, outline=None):
    d.polygon(points, fill=PALETTE[fill], outline=PALETTE[outline] if outline else None)


def line(points, fill, width=1):
    d.line(points, fill=PALETTE[fill], width=width)


def box(coords, fill):
    d.rectangle(coords, fill=PALETTE[fill])


def ellipse(coords, fill, outline=None):
    d.ellipse(coords, fill=PALETTE[fill], outline=PALETTE[outline] if outline else None)


def stud(x, y):
    box((x, y, x + 2, y + 2), "void")
    box((x, y, x + 1, y + 1), "silver1")
    box((x, y, x, y), "silver3")


def carbon_plate(points):
    poly(points, "carbon1", "ink")
    line(points[:3], "carbon3")


def pouch(x, y, w, h):
    poly([(x, y), (x + w - 2, y), (x + w, y + 3),
          (x + w - 1, y + h), (x + 1, y + h + 1), (x - 1, y + h - 2)],
         "cloth0", "ink")
    box((x + 2, y + 3, x + w - 3, y + h - 2), "cloth1")
    poly([(x, y + 1), (x + w - 1, y + 1), (x + w - 1, y + 7),
          (x + 3, y + 8), (x, y + 5)], "cloth2")
    line([(x + 1, y + 1), (x + w - 2, y + 1)], "cloth3")
    line([(x + 1, y + 9), (x + 1, y + h - 2)], "cloth3")
    line([(x + 4, y + 11), (x + 4, y + h - 3)], "cloth2")
    box((x + w // 2, y + 5, x + w // 2 + 2, y + 6), "carbon0")
    line([(x + 2, y + h - 1), (x + w - 3, y + h - 1)], "carbon2")


# Backpack silhouette, right-side radio aerial and top grab handle.
poly([(62, 71), (75, 63), (116, 65), (134, 75), (133, 143),
      (122, 160), (66, 154), (57, 134), (56, 88)], "void", "ink")
poly([(59, 80), (65, 77), (63, 137), (58, 132)], "cloth2")
poly([(124, 78), (132, 82), (131, 138), (126, 143)], "black")
box((126, 42, 128, 98), "ink")
line([(127, 43), (127, 81)], "carbon3")
box((123, 89, 131, 125), "carbon0")
line([(124, 92), (130, 92)], "gold3")
line([(78, 66), (83, 62), (107, 62), (115, 67)], "gold3", 2)
line([(81, 65), (84, 63), (105, 63)], "gold6")

# Trouser silhouette. Slightly separated feet, no ground shadow in the asset.
poly([(72, 146), (113, 146), (119, 164), (119, 190),
      (117, 215), (121, 245), (113, 258), (102, 257), (98, 247),
      (95, 216), (92, 190), (89, 177), (86, 197), (83, 222),
      (82, 248), (70, 257), (62, 250), (64, 224), (65, 198),
      (65, 171)], "cloth0", "ink")
poly([(70, 163), (84, 163), (88, 178), (82, 209), (69, 211), (66, 197)],
     "cloth1")
poly([(73, 166), (82, 170), (82, 183), (77, 192), (70, 191)], "cloth2")
line([(70, 175), (75, 171), (81, 171)], "cloth3")
line([(68, 184), (76, 189), (81, 188)], "cloth2")
poly([(94, 165), (108, 164), (115, 180), (115, 201),
      (109, 215), (99, 204), (96, 183)], "cloth1")
poly([(97, 169), (103, 170), (111, 191), (109, 201), (103, 201)], "cloth2")
line([(94, 182), (98, 190), (99, 200)], "black")
line([(114, 178), (112, 191), (114, 199)], "black")
line([(70, 216), (78, 219), (78, 237)], "cloth2", 2)
line([(103, 216), (112, 223), (113, 239)], "cloth2", 2)

# Thigh straps and slim holsters, one to either side.
poly([(65, 175), (85, 180), (84, 186), (64, 181)], "carbon0", "ink")
line([(66, 176), (84, 181)], "carbon2")
poly([(95, 180), (118, 173), (118, 179), (97, 186)], "carbon0", "ink")
line([(98, 181), (116, 176)], "carbon2")
box((72, 178, 76, 183), "carbon2")
box((73, 179, 75, 182), "ink")

# Gold outer thigh rails, articulated hip joints.
poly([(64, 151), (69, 153), (67, 163), (62, 181), (63, 196),
      (60, 202), (58, 194), (58, 177), (61, 158)], "gold2", "ink")
poly([(63, 158), (66, 155), (64, 169), (61, 181), (61, 194),
      (59, 188), (60, 173)], "gold5")
line([(64, 156), (63, 165), (60, 179), (60, 187)], "gold7")
poly([(118, 150), (122, 154), (124, 179), (124, 193),
      (120, 202), (118, 198), (120, 180), (117, 165)], "gold2", "ink")
poly([(119, 154), (121, 158), (123, 180), (121, 194),
      (120, 188), (121, 177)], "gold5")
line([(119, 155), (120, 167), (122, 179)], "gold6")
ellipse((57, 149, 69, 161), "carbon0", "ink")
ellipse((60, 152, 66, 158), "edge")
ellipse((61, 153, 65, 157), "carbon2")
line([(62, 153), (62, 157)], "silver2")
ellipse((115, 149, 126, 161), "carbon0", "ink")
ellipse((118, 152, 123, 158), "carbon3")
stud(120, 153)

poly([(59, 142), (65, 141), (66, 166), (61, 171), (56, 168)], "carbon0", "ink")
box((59, 145, 62, 159), "carbon2")
line([(58, 146), (58, 164)], "edge")
poly([(117, 138), (125, 139), (127, 159), (123, 169), (117, 168)],
     "carbon0", "ink")
box((119, 144, 122, 159), "carbon2")
line([(122, 139), (124, 144), (124, 162)], "cloth3")

# Black knee carriers with chipped gold kneecaps.
poly([(65, 204), (71, 198), (82, 200), (86, 207), (82, 220),
      (67, 219), (63, 212)], "carbon0", "ink")
poly([(98, 204), (106, 199), (117, 202), (119, 211), (114, 221),
      (100, 219), (97, 211)], "carbon0", "ink")
for shift in (0, 33):
    poly([(68 + shift, 201), (79 + shift, 201), (81 + shift, 205),
          (78 + shift, 209), (80 + shift, 216), (75 + shift, 220),
          (68 + shift, 217), (70 + shift, 209), (66 + shift, 205)],
         "gold3", "gold1")
    poly([(69 + shift, 202), (77 + shift, 202), (78 + shift, 205),
          (74 + shift, 209), (76 + shift, 216), (70 + shift, 216),
          (72 + shift, 208)], "gold5")
    line([(70 + shift, 202), (75 + shift, 202)], "gold7")
    box((68 + shift, 204, 69 + shift, 205), "carbon1")
    box((77 + shift, 204, 78 + shift, 205), "carbon1")
    line([(73 + shift, 218), (76 + shift, 217)], "gold2")

# Lower-leg braces, rings, ankle cables.
poly([(60, 205), (64, 211), (63, 229), (60, 244), (62, 253),
      (56, 253), (56, 241), (59, 223)], "carbon0", "ink")
poly([(60, 218), (62, 213), (61, 231), (58, 244), (58, 251),
      (56, 246), (57, 236)], "gold4")
line([(60, 217), (60, 230), (57, 242)], "gold6")
poly([(120, 206), (124, 207), (124, 237), (128, 253),
      (122, 256), (119, 245), (120, 227)], "carbon0", "ink")
poly([(122, 216), (123, 216), (122, 236), (125, 248),
      (123, 251), (121, 241)], "gold4")
for x, y in [(59, 224), (59, 246), (122, 225), (123, 246)]:
    ellipse((x - 2, y - 2, x + 4, y + 4), "ink")
    ellipse((x, y, x + 2, y + 2), "carbon3")
    box((x, y, x, y), "silver2")

# Trousers bunch above high boots.
poly([(65, 221), (80, 225), (80, 239), (76, 245), (63, 242)], "cloth0")
poly([(66, 226), (77, 231), (79, 236), (68, 233)], "cloth2")
line([(66, 237), (72, 239), (78, 237)], "black")
poly([(100, 224), (114, 224), (117, 240), (110, 246), (102, 242)], "cloth0")
line([(102, 227), (111, 231), (114, 236)], "cloth2", 2)
line([(102, 237), (108, 240), (113, 240)], "black")

# Boots, separate toe boxes, soles and laces.
poly([(62, 241), (78, 242), (80, 256), (78, 267), (71, 272),
      (54, 272), (51, 268), (53, 262), (59, 255)], "carbon0", "ink")
poly([(102, 242), (116, 241), (119, 254), (126, 264), (126, 270),
      (121, 273), (105, 272), (100, 267), (100, 256)], "carbon0", "ink")
poly([(62, 245), (73, 245), (74, 258), (62, 262), (58, 260)], "cloth0")
poly([(104, 245), (113, 244), (114, 258), (121, 264), (106, 262)], "cloth0")
poly([(54, 264), (64, 261), (75, 262), (75, 266), (55, 267)], "cloth1")
poly([(103, 262), (114, 261), (124, 266), (121, 268), (105, 267)], "cloth1")
line([(56, 264), (67, 262), (72, 263)], "cloth2")
line([(108, 263), (116, 263), (121, 266)], "cloth2")
line([(52, 269), (56, 271), (70, 271), (76, 267)], "sole2")
line([(102, 268), (106, 271), (121, 271), (124, 269)], "sole2")
line([(54, 270), (70, 270)], "sole1")
line([(106, 270), (120, 270)], "sole1")
for y in range(247, 259, 3):
    line([(65, y), (71, y + 1)], "carbon2")
    line([(105, y + 1), (112, y)], "carbon2")
box((57, 250, 61, 253), "carbon2")
box((58, 250, 60, 251), "edge")
box((117, 250, 121, 253), "carbon2")

# Torso, tailored undersuit and side folds.
poly([(74, 66), (87, 61), (104, 61), (117, 67), (128, 78),
      (125, 103), (117, 125), (116, 150), (109, 161), (76, 161),
      (65, 152), (64, 123), (60, 92), (64, 77)], "cloth0", "ink")
poly([(75, 72), (85, 66), (104, 66), (116, 73), (119, 94),
      (115, 123), (113, 145), (75, 147), (66, 124), (66, 92)], "cloth1")
poly([(68, 104), (74, 109), (73, 143), (67, 139)], "cloth2")
line([(65, 132), (71, 136), (69, 147)], "cloth3")
line([(117, 125), (112, 139), (115, 144)], "black", 2)

# Neck cloth, silver shirt collar and muted gold tie.
poly([(81, 52), (109, 52), (111, 72), (100, 83), (82, 75), (78, 65)],
     "black", "ink")
poly([(84, 55), (107, 56), (105, 64), (92, 69), (82, 62)], "cloth1")
line([(84, 61), (95, 66), (105, 62)], "cloth2")
poly([(81, 67), (93, 76), (87, 85), (76, 72)], "silver0", "void")
poly([(82, 68), (92, 75), (86, 81)], "silver2")
poly([(96, 76), (108, 67), (112, 76), (103, 85)], "silver0", "void")
poly([(104, 73), (108, 70), (108, 79)], "silver1")
poly([(92, 75), (98, 75), (101, 80), (97, 84), (98, 92),
      (93, 96), (89, 90), (92, 83), (89, 80)], "gold3", "gold1")
line([(92, 77), (96, 76), (98, 79)], "gold6")
poly([(94, 84), (95, 84), (96, 91), (93, 92)], "gold5")

# Raised coat collar and diagonally folded lapels.
poly([(77, 63), (85, 74), (92, 91), (82, 91), (68, 71)], "carbon0", "ink")
line([(74, 65), (82, 77), (90, 89)], "cloth3", 2)
line([(74, 67), (82, 80)], "cloth4")
poly([(109, 63), (102, 78), (97, 91), (110, 89), (121, 69)], "carbon0", "ink")
line([(116, 66), (110, 77), (101, 89)], "carbon3", 2)

# Hanging arms with padded sleeves, bent left elbow and separate fingers.
poly([(63, 73), (55, 72), (46, 82), (43, 99), (39, 115),
      (37, 128), (41, 136), (37, 153), (33, 165), (36, 175),
      (44, 177), (53, 168), (55, 153), (60, 133), (58, 121),
      (66, 105), (73, 89)], "cloth0", "ink")
poly([(52, 83), (59, 78), (64, 88), (58, 101), (51, 115),
      (44, 119), (45, 100)], "cloth2")
poly([(52, 84), (57, 83), (60, 89), (55, 99), (50, 105), (47, 105)],
     "cloth3")
poly([(44, 111), (52, 117), (54, 128), (47, 133), (40, 129)], "cloth1")
line([(43, 116), (49, 119), (53, 118)], "cloth3")
line([(41, 123), (48, 126), (53, 125)], "black", 2)
poly([(40, 135), (48, 138), (50, 148), (46, 161), (37, 160)], "cloth2")
line([(38, 149), (43, 151), (48, 149)], "cloth3")

poly([(123, 73), (132, 76), (141, 90), (146, 109), (150, 125),
      (147, 138), (151, 155), (157, 167), (155, 178), (145, 180),
      (138, 170), (135, 153), (131, 135), (126, 119), (119, 103),
      (116, 86)], "cloth0", "ink")
poly([(127, 82), (133, 88), (139, 103), (141, 113), (137, 119),
      (132, 109), (124, 98)], "cloth2")
line([(134, 105), (139, 112), (138, 118)], "cloth3")
poly([(138, 118), (145, 118), (147, 128), (144, 136), (137, 132)],
     "cloth1")
line([(138, 123), (145, 126)], "cloth3")
line([(138, 129), (145, 132)], "black", 2)
poly([(137, 140), (144, 141), (148, 156), (146, 165), (139, 161)],
     "cloth1")
line([(142, 145), (146, 155)], "cloth2")

# Shoulder armor and small red unit patch.
carbon_plate([(52, 76), (60, 71), (72, 76), (68, 89), (58, 100), (47, 94)])
poly([(52, 81), (60, 77), (66, 80), (62, 88), (53, 91)], "cloth2")
line([(50, 94), (57, 96), (66, 89)], "carbon3")
carbon_plate([(121, 74), (131, 77), (140, 93), (130, 100), (119, 87)])
poly([(129, 87), (137, 93), (133, 101), (126, 98), (124, 92)],
     "red0", "ink")
line([(129, 89), (135, 94), (132, 98)], "red1")
line([(128, 93), (131, 95), (132, 92)], "silver1")

# Shoulder exoskeleton: disconnected outer rails leave visible air gaps.
for pts in [
    [(54, 69), (61, 69), (65, 73), (60, 81), (52, 85), (45, 99),
     (40, 100), (43, 88)],
    [(127, 70), (134, 75), (145, 91), (149, 101), (145, 104),
     (139, 92), (131, 85), (123, 78)],
]:
    carbon_plate(pts)
poly([(52, 75), (56, 72), (58, 75), (52, 82), (47, 92), (45, 94)], "carbon3")
poly([(131, 77), (136, 83), (142, 92), (141, 95), (134, 86)], "carbon2")
poly([(62, 68), (68, 71), (66, 78), (60, 79), (58, 74)], "gold4", "gold1")
poly([(62, 69), (66, 71), (63, 75), (60, 74)], "gold6")
box((63, 72, 65, 74), "void")
poly([(120, 68), (126, 71), (129, 77), (124, 81), (118, 76)], "gold3", "gold1")
line([(121, 70), (124, 72), (126, 76)], "gold6", 2)
box((120, 73, 122, 75), "void")
line([(41, 101), (43, 111), (48, 120)], "ink", 4)
line([(41, 101), (43, 110), (48, 118)], "carbon3", 2)
line([(147, 103), (149, 114), (144, 124)], "ink", 4)
line([(147, 103), (148, 113), (144, 122)], "carbon2", 2)
stud(47, 92)
stud(139, 91)
ellipse((43, 115, 51, 123), "carbon0", "ink")
ellipse((139, 119, 148, 127), "carbon0", "ink")
stud(46, 117)
stud(142, 121)

# Hard forearm gauntlets, gold inlays and wrist straps.
carbon_plate([(42, 130), (53, 132), (52, 148), (47, 160), (36, 156), (38, 143)])
poly([(41, 135), (48, 138), (46, 145), (48, 152), (43, 156),
      (38, 151)], "gold3", "gold1")
poly([(40, 136), (43, 140), (42, 149), (45, 152), (42, 153),
      (39, 149)], "gold6")
poly([(46, 133), (51, 135), (49, 145), (46, 145), (44, 141)], "carbon2")
stud(48, 135)
stud(39, 148)
line([(37, 159), (47, 162)], "gold3", 3)
line([(38, 159), (44, 161)], "gold5")
carbon_plate([(136, 133), (146, 133), (151, 155), (142, 163),
              (135, 153), (133, 143)])
poly([(144, 140), (148, 149), (146, 157), (139, 153),
      (138, 149), (142, 150)], "gold4", "gold1")
line([(145, 142), (147, 150), (145, 154)], "gold6")
line([(138, 136), (141, 140), (140, 146)], "carbon3", 2)
stud(138, 136)
stud(143, 153)
line([(142, 163), (151, 159)], "gold3", 3)
line([(144, 163), (150, 161)], "gold5")

# Gloves, four explicit fingertips rather than mitten shapes.
poly([(36, 164), (44, 165), (47, 170), (46, 176), (43, 180),
      (40, 180), (41, 171), (39, 177), (38, 183), (35, 183),
      (35, 174), (33, 181), (30, 180), (31, 170), (30, 175),
      (27, 173), (30, 164), (32, 160)], "carbon0", "ink")
poly([(32, 164), (39, 165), (42, 169), (39, 173), (31, 170)], "carbon2")
line([(33, 164), (38, 165), (40, 167)], "carbon3")
for x, y in [(30, 168), (34, 170), (38, 171), (43, 171)]:
    box((x, y, x + 1, y + 2), "edge")
line([(32, 176), (31, 179)], "carbon2")
line([(37, 176), (36, 181)], "carbon2")
poly([(143, 167), (152, 164), (157, 169), (161, 178), (159, 181),
      (156, 175), (159, 184), (156, 185), (151, 176), (154, 186),
      (151, 187), (146, 176), (148, 185), (145, 185), (142, 179),
      (139, 174), (139, 168)], "carbon0", "ink")
poly([(144, 168), (151, 167), (155, 172), (150, 177), (143, 173)], "carbon2")
line([(145, 169), (150, 168), (152, 170)], "carbon3")
for x, y in [(145, 174), (149, 174), (153, 172), (156, 172)]:
    box((x, y, x + 1, y + 2), "carbon3")

# Broad chest harness follows the original open, wing-shaped armor.
poly([(75, 79), (84, 85), (92, 91), (104, 86), (114, 79),
      (122, 91), (116, 118), (112, 129), (74, 129), (65, 110), (65, 91)],
     "carbon0", "ink")
poly([(69, 89), (79, 88), (85, 94), (82, 106), (69, 103)], "carbon2")
poly([(109, 89), (116, 88), (119, 93), (114, 105), (102, 106),
      (104, 94)], "carbon1")
poly([(74, 81), (76, 93), (84, 99), (89, 98), (86, 91), (82, 90),
      (80, 78)], "carbon1", "ink")
poly([(111, 80), (109, 93), (100, 99), (96, 97), (102, 89), (104, 89),
      (107, 77)], "carbon1", "ink")
line([(75, 82), (78, 91), (85, 96)], "carbon3")
line([(109, 83), (107, 92), (101, 96)], "carbon3")
poly([(67, 97), (78, 102), (88, 103), (88, 112), (77, 110), (68, 104)],
     "carbon1", "ink")
poly([(100, 103), (114, 101), (119, 95), (116, 105), (108, 111), (99, 111)],
     "carbon1", "ink")
line([(69, 98), (78, 104), (86, 104)], "carbon3")
line([(103, 104), (114, 103), (117, 100)], "carbon3")
poly([(90, 88), (97, 87), (101, 94), (98, 98), (97, 107),
      (92, 114), (87, 109), (85, 96)], "carbon1", "ink")
line([(91, 89), (88, 97), (90, 103)], "carbon3")
poly([(91, 104), (95, 103), (96, 108), (94, 111), (91, 109)], "ink")
line([(70, 95), (67, 97), (69, 103)], "gold5", 2)
line([(115, 94), (118, 96), (116, 101)], "gold4", 2)
for x, y in [(74, 83), (107, 83), (71, 98), (113, 97), (88, 94), (93, 107)]:
    stud(x, y)

# Backpack shoulder straps lie over the chest armor.
poly([(68, 67), (73, 66), (77, 78), (73, 92), (70, 125),
      (65, 125), (67, 91), (65, 79)], "cloth0", "ink")
line([(70, 70), (72, 79), (69, 108), (67, 121)], "cloth3", 2)
box((68, 99, 72, 105), "silver0")
box((69, 99, 71, 101), "silver2")
poly([(115, 65), (121, 67), (122, 81), (119, 98), (118, 124),
      (113, 124), (114, 96), (117, 80)], "cloth0", "ink")
line([(119, 70), (119, 82), (116, 110)], "cloth2", 2)
for y in (87, 93, 99, 105):
    line([(115, y), (119, y)], "carbon2")

# Gold chest bar, rose stem and leaves. Rose is offset like the reference.
poly([(72, 112), (91, 113), (99, 111), (116, 111), (111, 117),
      (99, 118), (93, 122), (83, 118), (76, 118)], "gold2", "gold0")
poly([(75, 113), (89, 115), (96, 114), (91, 118), (84, 117), (78, 116)],
     "gold6")
line([(73, 113), (88, 114)], "gold7")
poly([(96, 123), (89, 120), (90, 124), (97, 128)], "gold4", "gold1")
poly([(111, 116), (118, 111), (124, 113), (118, 118), (112, 120)],
     "gold4", "gold1")
line([(114, 116), (120, 113)], "gold6")

# Angular nested petal clusters, a dark center, light top edges.
poly([(98, 110), (103, 107), (109, 109), (114, 113), (115, 119),
      (112, 125), (107, 128), (99, 126), (95, 122), (94, 116)],
     "gold3", "gold0")
poly([(98, 112), (103, 108), (108, 111), (103, 112), (98, 116),
      (97, 122), (95, 118)], "gold6")
poly([(106, 110), (110, 111), (114, 116), (113, 121), (110, 124),
      (111, 117)], "gold5")
poly([(100, 122), (105, 125), (111, 123), (108, 126), (102, 126),
      (98, 123)], "gold6")
poly([(101, 113), (107, 112), (111, 116), (110, 122), (105, 124),
      (99, 121), (98, 116)], "gold2")
poly([(101, 113), (106, 113), (108, 115), (102, 115), (100, 118),
      (100, 120), (98, 117)], "gold7")
poly([(110, 116), (111, 119), (108, 122), (103, 122), (101, 120),
      (105, 121), (108, 120)], "gold5")
poly([(102, 115), (107, 115), (109, 118), (106, 121), (101, 119)],
     "carbon2")
line([(102, 116), (105, 115), (107, 116)], "carbon3")

# Ammunition carriers, gold retaining cords and subdued red tape.
for x, y, w in [(72, 122, 12), (87, 123, 12), (102, 127, 12)]:
    poly([(x + 1, y), (x + w - 2, y - 1), (x + w, y + 19),
          (x, y + 20)], "carbon0", "ink")
    line([(x + 3, y + 2), (x + w - 3, y + 1)], "carbon3")
    line([(x + 2, y + 1), (x + 1, y + 15)], "gold5")
    line([(x + 2, y + 1), (x + 6, y + 15)], "gold2")
box((102, 138, 113, 141), "red1")
line([(104, 139), (105, 140), (106, 139)], "red0")
line([(109, 139), (112, 139)], "red2")
for x, y in [(69, 136), (85, 137), (101, 139)]:
    pouch(x, y, 14, 22)
line([(104, 154), (108, 151), (112, 154), (109, 157)], "gold2")
line([(73, 153), (78, 153)], "carbon0")

# Belt, asymmetric buckles, straps and lower coat seams.
poly([(65, 158), (76, 159), (111, 161), (119, 157), (119, 166),
      (108, 168), (70, 166), (64, 165)], "carbon0", "ink")
line([(70, 160), (109, 163), (116, 161)], "carbon2")
box((85, 159, 99, 168), "carbon2")
box((87, 161, 97, 166), "ink")
box((89, 162, 95, 165), "carbon1")
line([(87, 160), (98, 160), (98, 166)], "edge")
box((102, 162, 107, 166), "carbon1")
box((74, 161, 79, 165), "carbon1")
poly([(82, 169), (97, 170), (106, 171), (104, 178),
      (93, 179), (84, 176)], "cloth0")
line([(85, 171), (98, 173)], "cloth2")
line([(92, 177), (95, 181)], "black")

# Head silhouette: swept silver hair, exposed skull mask and separate headset.
poly([(80, 18), (88, 12), (100, 11), (110, 15), (115, 22),
      (114, 40), (112, 56), (105, 63), (85, 62), (77, 55),
      (76, 39), (76, 25)], "black", "ink")

# Silver quiff: large connected clusters rather than photo noise.
poly([(79, 25), (80, 19), (86, 15), (94, 14), (98, 11), (106, 13),
      (112, 18), (114, 24), (111, 31), (106, 30), (105, 26),
      (85, 27), (79, 33), (77, 31)], "silver1", "ink")
poly([(80, 24), (85, 18), (93, 16), (99, 12), (104, 14),
      (101, 17), (91, 21), (87, 25), (81, 28)], "silver3")
poly([(89, 24), (94, 20), (103, 17), (106, 14), (110, 18),
      (108, 22), (101, 23), (97, 26)], "silver2")
poly([(98, 25), (103, 22), (110, 20), (113, 23), (112, 28),
      (107, 28), (107, 25), (103, 27)], "silver3")
line([(82, 21), (86, 18), (92, 17)], "silver4")
line([(87, 23), (92, 19), (100, 16), (102, 13)], "silver4")
line([(98, 23), (106, 20), (108, 17)], "silver4")
line([(91, 23), (95, 23), (100, 20)], "silver0")
line([(79, 25), (79, 31)], "silver2")
line([(110, 26), (111, 24)], "silver4")
poly([(78, 23), (82, 22), (81, 31), (79, 39), (76, 38)], "ink")
line([(78, 25), (78, 34)], "carbon3")
poly([(110, 19), (114, 23), (115, 40), (111, 39), (111, 28)], "ink")
line([(113, 27), (113, 34)], "carbon2")

# Warm metallic earcups, kept behind the mask.
poly([(75, 34), (79, 35), (82, 41), (81, 51), (77, 56),
      (71, 54), (69, 48), (70, 40)], "gold2", "ink")
poly([(73, 37), (76, 36), (78, 40), (78, 46), (74, 47),
      (76, 52), (72, 51), (71, 46)], "gold5")
line([(72, 39), (72, 44)], "gold7")
box((74, 46, 79, 49), "black")
box((73, 51, 77, 52), "carbon0")
stud(77, 40)
poly([(112, 35), (117, 35), (121, 41), (121, 50), (118, 56),
      (112, 55), (109, 48)], "gold1", "ink")
poly([(114, 37), (117, 38), (119, 43), (118, 49), (115, 52),
      (112, 50)], "gold3")
line([(115, 38), (117, 41), (117, 46)], "gold5")
box((113, 47, 116, 51), "black")
stud(114, 40)

# Gold skull mask. Dark eye sockets and vertical vent cuts are the key read.
poly([(84, 28), (91, 25), (102, 25), (109, 29), (111, 35),
      (109, 42), (110, 47), (105, 49), (104, 59),
      (100, 64), (91, 65), (85, 62), (83, 50), (79, 48),
      (78, 43), (80, 37), (80, 33)], "gold3", "gold1")
poly([(84, 30), (91, 27), (100, 27), (106, 29), (108, 33),
      (105, 36), (99, 36), (94, 35), (88, 36), (81, 36), (82, 32)], "gold5")
poly([(86, 29), (94, 27), (100, 28), (104, 30), (102, 33),
      (85, 34), (82, 35), (83, 32)], "gold6")
line([(87, 28), (94, 27), (99, 28)], "gold7")
poly([(108, 32), (109, 36), (106, 41), (109, 46),
      (104, 48), (101, 45), (104, 39)], "gold2")

# Brow planes and sockets, no cartoon glowing eyes.
poly([(81, 37), (85, 36), (91, 38), (91, 41), (87, 43),
      (81, 42), (80, 39)], "gold1")
poly([(82, 38), (86, 38), (90, 39), (88, 42), (83, 41)], "ink")
line([(83, 39), (87, 39)], "carbon2")
box((86, 39, 86, 39), "silver0")
poly([(98, 38), (103, 36), (107, 36), (108, 40),
      (105, 43), (99, 42), (97, 40)], "gold1")
poly([(99, 39), (105, 38), (106, 40), (104, 42), (99, 41)], "ink")
line([(101, 39), (104, 39)], "carbon1")
box((102, 39, 102, 39), "silver0")
line([(82, 36), (87, 36), (92, 38)], "gold4")
line([(97, 38), (104, 35)], "gold4")
poly([(93, 38), (95, 38), (98, 46), (94, 48),
      (90, 47), (90, 45)], "carbon0", "gold2")
line([(93, 39), (93, 43)], "ink")
poly([(81, 43), (86, 44), (89, 42), (88, 47), (85, 48),
      (81, 46)], "gold6")
poly([(99, 44), (103, 44), (106, 43), (107, 46), (102, 48),
      (98, 46)], "gold4")

# Long jaw plate and the four vertical vents.
poly([(87, 48), (92, 50), (99, 48), (104, 49), (103, 58),
      (99, 63), (91, 64), (87, 61), (85, 51)], "gold5")
poly([(87, 49), (89, 51), (90, 59), (93, 62), (91, 63),
      (87, 60)], "gold6")
poly([(101, 50), (103, 49), (102, 58), (99, 61), (97, 62),
      (98, 58)], "gold3")
line([(88, 51), (89, 57)], "gold1")
line([(92, 51), (92, 59)], "gold0")
line([(96, 51), (96, 59)], "gold0")
line([(100, 50), (99, 57)], "gold1")
line([(91, 63), (96, 64), (99, 62)], "gold4")
box((89, 51, 89, 53), "gold7")

# Microphone runs from the right cup across the jaw, ending below the cheek.
line([(117, 49), (122, 47), (125, 43)], "ink", 2)
line([(119, 49), (116, 55), (104, 57)], "ink", 2)
line([(117, 50), (115, 54), (105, 56)], "carbon3")
ellipse((101, 54, 108, 58), "ink")
line([(103, 54), (106, 54)], "carbon2")

# A few cloth stitches and abrasion pixels on mechanically meaningful edges.
for x, y in [(55, 84), (60, 83), (129, 86), (72, 173), (76, 174),
             (109, 191), (65, 228), (111, 234)]:
    box((x, y, x + 1, y), "cloth3")

sprite.save(OUT / "redwolf-idle-front.png")
sprite.resize((SIZE[0] * 4, SIZE[1] * 4), Image.Resampling.NEAREST).save(
    OUT / "redwolf-idle-front@4x.png"
)

colors = sorted({p[:3] for p in sprite.getdata() if p[3]}, key=lambda c: (sum(c), c))
alpha = sprite.getchannel("A")
assert set(alpha.getdata()) == {0, 255}, "Native sprite must have binary alpha."
assert len(colors) <= len(PALETTE), "Unexpected colors/antialiasing in native sprite."
assert alpha.getbbox() is not None

metadata = {
    "character": "红狼",
    "skin": "蚀金玫瑰",
    "status": "静态像素美术样稿 v1，待确认还原度",
    "canvas": list(SIZE),
    "frameCount": 1,
    "alpha": "binary",
    "paletteSize": len(colors),
    "bounds": list(alpha.getbbox()),
    "scale": "integer, nearest-neighbor",
    "sources": [f"../../pic/红狼-{n}.png" for n in range(1, 5)],
    "palette": PALETTE,
}
(OUT / "sprite.json").write_text(
    json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)

# Standalone review board. Typography is not baked into the sprite.
board = Image.new("RGB", (1400, 1040), "#10151b")
bd = ImageDraw.Draw(board)
font_candidates = [
    os.environ.get("PIXEL_ART_FONT", ""),
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/msyh.ttc",
]
font_path = next((p for p in font_candidates if p and Path(p).is_file()), None)
font_bold_path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"


def font(size, bold=False):
    file = font_bold_path if bold and Path(font_bold_path).is_file() else font_path
    if not file:
        raise RuntimeError("Set PIXEL_ART_FONT to a font supporting Chinese to render the review board.")
    return ImageFont.truetype(file, size)


bd.text((46, 28), "DELTA FORCE / PIXEL CHARACTER STUDY", fill="#a89366", font=font(17, True))
bd.text((44, 57), "红狼 · 蚀金玫瑰", fill="#efe9d9", font=font(38))
bd.text((46, 114), "静态立绘样稿 v1  /  正面站姿  /  参考图驱动的本地像素绘制",
        fill="#949da8", font=font(17))
bd.line((46, 156, 1354, 156), fill="#333d46")

# Whole sprite at 3×, with enough margin to judge the outline.
board.paste(sprite.resize((576, 864), Image.Resampling.NEAREST), (24, 169), sprite.resize(
    (576, 864), Image.Resampling.NEAREST
))
bd.text((57, 1008), "03×  /  NEAREST NEIGHBOR", fill="#a89366", font=font(15, True))

# Actual-size proof on light neutral to check dark edges.
bd.rectangle((642, 189, 871, 513), fill="#d9d6cc")
board.paste(sprite, (661, 207), sprite)
bd.text((890, 210), "原生像素", fill="#e2dac7", font=font(22))
bd.text((890, 252), "192 × 288 px", fill="#a89366", font=font(21, True))
bd.text((890, 292), f"{len(colors)} 色 · 透明背景", fill="#a3adb5", font=font(18))
bd.text((890, 330), "单帧 / 无平滑插值", fill="#a3adb5", font=font(18))
bd.text((890, 382), "身份特征", fill="#e2dac7", font=font(20))
for i, text in enumerate(["银白后梳发 · 金色骷髅面具", "黑金耳机 · 胸前玫瑰", "黑色护具 · 金色外骨骼支架"]):
    bd.text((890, 424 + i * 29), text, fill="#a3adb5", font=font(16))

# Face and chest details use the exact same pixel grid.
face = sprite.crop((67, 10, 127, 67)).resize((300, 285), Image.Resampling.NEAREST)
chest = sprite.crop((62, 74, 126, 139)).resize((256, 260), Image.Resampling.NEAREST)
bd.rectangle((642, 560, 959, 879), fill="#1a222b")
bd.rectangle((990, 560, 1354, 879), fill="#1a222b")
board.paste(face, (650, 576), face)
board.paste(chest, (1042, 589), chest)
bd.text((644, 891), "面具 / 耳机 / 发型 · 5×", fill="#a3adb5", font=font(16))
bd.text((992, 891), "胸甲 / 金玫瑰 · 4×", fill="#a3adb5", font=font(16))
for i, color in enumerate(colors):
    x = 644 + i * 20
    bd.rectangle((x, 948, x + 17, 965), fill=color)
bd.text((644, 986), "待确认：人物还原度、头身比例、装备细节。", fill="#7e8a96", font=font(16))
board.save(OUT / "redwolf-review.png")
print(json.dumps({k: metadata[k] for k in ("canvas", "frameCount", "paletteSize", "bounds")}))
