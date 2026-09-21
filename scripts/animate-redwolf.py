"""Build native pixel animation atlases from the approved Red Wolf study.

Offline joint posing uses nearest-neighbor sampling. Runtime only selects
complete frames; it never rotates/scales the character or mirrors the cannon.
Python 3.9+, Pillow (scripts/requirements-art.txt).
"""
from pathlib import Path
import json
import math
import os
from PIL import Image, ImageDraw, ImageFont, ImageChops

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "asset/sprites/redwolf-gilded-rose"
src = Image.open(OUT / "redwolf-idle-front.png").convert("RGBA")
C = json.loads((OUT / "sprite.json").read_text())["palette"]
SIZE = (320, 320)
BASE = (64, 22)
NEAREST = Image.Resampling.NEAREST


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


def paste(frame, part, x=64, y=22):
    frame.alpha_composite(part, (round(x), round(y)))


def bone(frame, part, pivot, endpoint, target, tip, preserve_width=False):
    """Place a limb by its two joints, reusing its original pixels."""
    dx, dy = endpoint[0] - pivot[0], endpoint[1] - pivot[1]
    tx, ty = tip[0] - target[0], tip[1] - target[1]
    angle = math.atan2(ty, tx) - math.atan2(dy, dx)
    scale = math.hypot(tx, ty) / math.hypot(dx, dy)
    co, si = math.cos(angle) / scale, math.sin(angle) / scale
    # Inverse affine transform, integer output grid, no smoothing.
    coeffs = (co, si, pivot[0] - co * target[0] - si * target[1],
              -si, co, pivot[1] + si * target[0] - co * target[1])
    if preserve_width:
        length, travel = math.hypot(dx,dy), math.hypot(tx,ty)
        ex, ey, vx, vy = dx/length, dy/length, tx/travel, ty/travel
        a,b = ex*vx/scale+ey*vy, ex*vy/scale-ey*vx
        c,e = ey*vx/scale-ex*vy, ey*vy/scale+ex*vx
        coeffs=(a,b,pivot[0]-a*target[0]-b*target[1],
                c,e,pivot[1]-c*target[0]-e*target[1])
    transformed = part.transform(SIZE, Image.Transform.AFFINE, coeffs, NEAREST)
    frame.alpha_composite(transformed)


def glove(frame, at, closed=False):
    d = ImageDraw.Draw(frame)
    x, y = map(round, at)
    d.polygon([(x-8, y+7), (x-9, y-4), (x-5, y-9), (x+5, y-8),
               (x+9, y-3), (x+7, y+7)], fill=C["carbon0"], outline=C["ink"])
    d.polygon([(x-6, y-5), (x+3, y-6), (x+6, y-1), (x+3, y+5),
               (x-6, y+3)], fill=C["carbon2"])
    for j in range(4):
        fx = x - 6 + j * 4
        # Curl each finger continuously; the little finger closes first.
        curl = max(0, min(1, float(closed)*1.25 - (3-j)*.08))
        if curl >= .95:
            d.rectangle((fx, y-4, fx+2, y), fill=C["carbon3"])
            d.line((fx, y+2, fx+1, y+5), fill=C["ink"])
        else:
            end = min(y-2,round(y-15+(abs(j-1)*2)+11*curl))
            d.rectangle((fx, end, fx+2, y-2), fill=C["carbon1"])
            d.point((fx, end+1), fill=C["edge"])
    d.line((x+7, y+3, x+2, y+4), fill=C["edge"], width=2)


def cannon(frame, elbow, wrist, charged=False):
    """Arm-mounted device on anatomical RIGHT forearm (screen left)."""
    x, y = elbow
    dx, dy = wrist[0]-x, wrist[1]-y
    length = math.hypot(dx, dy)
    ux, uy = dx/length, dy/length
    nx, ny = -uy, ux

    def pt(t, n):
        return (round(x+ux*t+nx*n), round(y+uy*t+ny*n))

    d = ImageDraw.Draw(frame)
    muzzle = length-2
    d.polygon([pt(2,-10), pt(8,-13), pt(muzzle,-10), pt(muzzle+4,-5),
               pt(muzzle+4,7), pt(6,10), pt(1,4)],
              fill=C["carbon0"], outline=C["ink"])
    d.polygon([pt(6,-9), pt(muzzle-3,-7), pt(muzzle,1), pt(8,3)],
              fill=C["carbon2"])
    d.line([pt(6,-10), pt(muzzle-4,-8)], fill=C["edge"])
    d.polygon([pt(5,4), pt(muzzle-7,3), pt(muzzle-6,7), pt(7,8)], fill=C["gold4"])
    d.line([pt(7,5), pt(muzzle-9,4)], fill=C["gold6"])
    for t in (10, 16, 22):
        d.line([pt(t,-6), pt(t,0)], fill=C["ink"], width=2)
    d.line([pt(muzzle+3,-6), pt(muzzle+3,5)], fill=C["gold2"], width=3)
    d.line([pt(muzzle+4,-3), pt(muzzle+4,2)],
           fill=C["gold7"] if charged else C["ink"], width=2)
    return pt(muzzle+7,0), (ux,uy)


def rose(frame, center, crushed=False):
    d = ImageDraw.Draw(frame)
    x,y = map(round, center)
    if crushed:
        d.polygon([(x-7,y-2),(x-1,y-5),(x+6,y-3),(x+5,y+2),
                   (x,y+3),(x-6,y+1)], fill=C["gold5"], outline=C["gold2"])
        return
    d.line((x,y+3,x-1,y+26), fill=C["gold3"], width=2)
    d.polygon([(x,y+15),(x+8,y+9),(x+5,y+16)], fill=C["gold4"])
    d.polygon([(x-1,y+20),(x-8,y+14),(x-6,y+21)], fill=C["gold2"])
    d.polygon([(x-11,y-4),(x-6,y-10),(x+3,y-12),(x+11,y-6),
               (x+12,y+2),(x+5,y+9),(x-5,y+8),(x-12,y+2)],
              fill=C["gold3"], outline=C["gold0"])
    d.line([(x-10,y-3),(x-5,y-8),(x+3,y-10),(x+8,y-6)], fill=C["gold7"], width=2)
    d.polygon([(x-6,y-4),(x,y-7),(x+7,y-3),(x+5,y+4),(x-1,y+6),
               (x-7,y+2)], fill=C["gold5"])
    d.line([(x-7,y+3),(x-2,y+7),(x+6,y+5),(x+10,y)], fill=C["gold6"], width=2)
    d.polygon([(x-4,y-2),(x+2,y-4),(x+5,y),(x+1,y+3),(x-4,y+1)],
              fill=C["gold1"])
    d.line([(x-3,y-2),(x+1,y-3),(x+3,y-1)], fill=C["gold7"])


def sparks(frame, center, phase):
    """Expanding rose petals: discrete gold fragments, no full-screen flash."""
    d=ImageDraw.Draw(frame)
    x,y = center
    for j in range(14):
        angle = j*math.tau/14 + .24
        r = 12+phase*(26+(j%4)*8)
        px = round(x+math.cos(angle)*r)
        py = round(y+math.sin(angle)*r+phase*phase*17)
        size = max(1,4-int(phase*2))
        d.polygon([(px-size,py),(px,py-size-1),(px+size+1,py+1),(px,py+size)],
                  fill=C["gold6" if j%3 else "gold3"])
        if phase<.55:
            d.line((px-4,py+2,px-7,py+4), fill=C["gold2"])


def shot_effect(f,muzzle,vector,phase):
    d=ImageDraw.Draw(f)
    x,y=muzzle
    ux,uy=vector
    nx,ny=-uy,ux
    def p(t,n=0):
        return (round(x+ux*t+nx*n),round(y+uy*t+ny*n))
    if phase<=1:
        d.polygon([p(0,-5),p(11,-10),p(8,-4),p(23,-1),p(10,4),p(13,9),p(0,5)],
                  fill=C["gold5"])
        d.polygon([p(0,-3),p(14,0),p(0,3)],fill=C["gold7"])
    t=18+phase*13
    d.line([p(t-10),p(t)],fill=C["gold4"],width=5)
    d.line([p(t-7),p(t+3)],fill=C["gold7"],width=2)
    for j in range(3):
        d.rectangle((*p(8+phase*5, -8-j*5), *p(8+phase*5, -8-j*5)),fill=C["gold5"])


def lerp(a,b,t):
    # Keep subpixel joint positions until the final nearest-neighbor raster.
    return (a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t)


def part_slice(name,top,bottom):
    layer=parts[name].copy()
    mask=Image.new("L",src.size)
    ImageDraw.Draw(mask).rectangle((0,top,191,bottom),fill=255)
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"),mask))
    return layer


# Shared 16-segment rig: pelvis, waist, chest, neck/head, two upper arms,
# forearms and hands, and separate thighs, shins and boots on each side.
# Overlapping cut boundaries keep bent joints covered with original art.
layers = {
    "pelvis": part_slice("torso",138,170),
    "waist": part_slice("torso",108,143),
    "chest": part_slice("torso",42,115),
}
for side in ("right","left"):
    for name,top,bottom in (("thigh",167,216),("shin",207,251),("boot",246,276)):
        layers[f"{side}_{name}"]=part_slice(f"{side}_leg",top,bottom)

REST = {
    "hip": (158,188), "waist": (158,162), "chest": (158,134),
    "neck": (158,92), "crown": (158,42),
    "right_hip": (137,192), "right_knee": (136,233),
    "right_ankle": (132,270), "right_toe": (126,293),
    "left_hip": (172,192), "left_knee": (173,233),
    "left_ankle": (176,270), "left_toe": (180,293),
    "right_shoulder": (124,100), "right_elbow": (111,153),
    "right_wrist": (106,182), "right_hand": (101,193),
    "left_shoulder": (190,100), "left_elbow": (204,158),
    "left_wrist": (209,184), "left_hand": (212,197),
}


def pose(**joints):
    return {**REST,**joints}


def smooth(t):
    t=max(0,min(1,t))
    return t*t*(3-2*t)


def sample(keys,ms):
    """Interpolate joint poses, never duplicate/crossfade finished images."""
    for (start,a),(end,b) in zip(keys,keys[1:]):
        if ms<=end:
            t=smooth((ms-start)/(end-start))
            return {joint:lerp(a[joint],b[joint],t) for joint in REST}
    return keys[-1][1].copy()


def render_pose(p,grip=1,charged=False):
    f=Image.new("RGBA",SIZE)
    for side in ("left","right"):
        joints=[f"{side}_{s}" for s in ("hip","knee","ankle","toe")]
        for part,a,b in zip(("thigh","shin","boot"),joints,joints[1:]):
            source_a=tuple(REST[a][i]-BASE[i] for i in (0,1))
            source_b=tuple(REST[b][i]-BASE[i] for i in (0,1))
            bone(f,layers[f"{side}_{part}"],source_a,source_b,p[a],p[b],True)
    for part,a,b in (("pelvis","hip","waist"),("waist","waist","chest"),
                     ("chest","chest","neck")):
        bone(f,layers[part],tuple(REST[a][i]-BASE[i] for i in (0,1)),
             tuple(REST[b][i]-BASE[i] for i in (0,1)),p[a],p[b],True)
    bone(f,parts["head"],(94,70),(94,20),p["neck"],p["crown"],True)
    for side in ("left","right"):
        for part,a,b in (("upper","shoulder","elbow"),("lower","elbow","wrist")):
            a,b=f"{side}_{a}",f"{side}_{b}"
            bone(f,parts[f"{side}_{part}"],
                 tuple(REST[a][i]-BASE[i] for i in (0,1)),
                 tuple(REST[b][i]-BASE[i] for i in (0,1)),p[a],p[b],True)
        if side=="right":
            muzzle,vector=cannon(f,p["right_elbow"],p["right_wrist"],charged)
        # Wrist-to-palm link stays covered even when the hand leads the forearm.
        d=ImageDraw.Draw(f)
        link=[tuple(round(v) for v in p[f"{side}_{joint}"]) for joint in ("wrist","hand")]
        d.line(link,fill=C["ink"],width=9)
        d.line(link,fill=C["carbon1"],width=5)
        glove(f,p[f"{side}_hand"],grip if side=="right" else 1)
    return f,muzzle,vector


clips={}
FRAME_MS=40  # 25 fps, exact milliseconds in both runtime and GIF previews.


def add(name,frames,label,keyframe,**extra):
    clips[name]={"frames":frames,"durations":[FRAME_MS]*len(frames),
                 "label":label,"keyframe":keyframe,**extra}


def breathing(t,sleeping=False):
    p=pose()
    breath=(1-math.cos(t*math.tau))/2
    for joint in ("waist","chest","neck","crown","right_shoulder","left_shoulder",
                  "right_elbow","left_elbow","right_wrist","left_wrist",
                  "right_hand","left_hand"):
        x,y=p[joint]
        weight=.45 if joint=="waist" else 1
        p[joint]=(x,y+(3 if sleeping else 0)-breath*3*weight)
    p["crown"]=(p["crown"][0]+(3 if sleeping else 0),
                 p["crown"][1]+(3 if sleeping else math.sin(t*math.tau)*.8))
    return p


add("idle",[render_pose(breathing(i/40))[0] for i in range(40)],"待机",0,loop=True)
frames=[]
for i in range(60):
    f,_,_=render_pose(breathing(i/60,True))
    d=ImageDraw.Draw(f)
    for j in range(2):
        phase=(i/60+j*.5)%1
        x,y=round(195+phase*18),round(77-phase*31)
        size=6 if j==0 else 4
        d.line([(x,y),(x+size,y),(x,y+size),(x+size,y+size)],
               fill=C["gold4" if phase<.65 else "gold2"])
    frames.append(f)
add("sleep",frames,"休整",0,loop=True)

# Hand cannon: shoulder leads the elbow, wrist settles into aim, then recoil
# travels through chest and head before the arm returns on a separate arc.
aim=pose(right_elbow=(117,142),right_wrist=(80,134),right_hand=(70,132),
         right_shoulder=(125,101),chest=(159,135),neck=(160,93),crown=(160,43))
recoil={**aim,"right_elbow":(125,145),"right_wrist":(88,136),
        "right_hand":(78,134),"chest":(161,136),"neck":(163,94),
        "crown":(164,44),"right_shoulder":(128,103)}
cannon_keys=[
    (0,pose()),
    (160,pose(right_elbow=(114,154),right_wrist=(99,171),right_hand=(92,179))),
    (440,aim),(560,aim),(640,recoil),(800,aim),
    (1000,pose(right_elbow=(118,149),right_wrist=(90,153),right_hand=(81,158))),
    (1360,pose()),(1400,pose()),
]
frames=[]
for ms in range(0,1440,FRAME_MS):
    f,m,v=render_pose(sample(cannon_keys,ms),charged=440<=ms<840)
    if 560<=ms<800:
        shot_effect(f,m,v,(ms-560)/80)
    frames.append(f)
add("cannon",frames,"右臂手炮",15)

# Rose: gradual finger curl with a delayed head response and petal trajectories.
raised=pose(right_elbow=(110,145),right_wrist=(116,116),right_hand=(118,105),
            neck=(157,93),crown=(154,43),right_shoulder=(125,101))
crush={**raised,"right_wrist":(115,111),"right_hand":(117,100)}
release={**crush,"right_elbow":(112,146),"right_wrist":(118,113),
         "right_hand":(120,102),"chest":(159,135),"crown":(157,44)}
rose_keys=[
    (0,pose()),(200,pose(right_elbow=(109,152),right_wrist=(104,171),
                       right_hand=(102,179))),
    (680,raised),(960,raised),(1200,crush),(1360,release),
    (1880,crush),(2200,pose(right_elbow=(108,147),right_wrist=(110,140),
                          right_hand=(111,132))),
    (2680,pose()),(2720,pose()),
]
frames=[]
for ms in range(0,2760,FRAME_MS):
    p=sample(rose_keys,ms)
    grip=1-smooth(ms/360) if ms<680 else smooth((ms-960)/320)
    f,_,_=render_pose(p,grip=grip)
    hand=p["right_hand"]
    if 160<=ms<1280:
        rose(f,(hand[0],hand[1]-15+grip*9),crushed=ms>=1200)
        glove(f,hand,grip)
    if 1280<=ms<2000:
        phase=(ms-1280)/720
        sparks(f,(120,90),phase)
    frames.append(f)
add("rose",frames,"捏爆金玫瑰",35)

# Slide has independent pelvis / lumbar / chest / neck curves and two distinct
# leg chains. Crouch keeps feet planted; extension starts only during travel.
crouch=pose(
    hip=(156,213),waist=(154,188),chest=(158,162),neck=(167,123),crown=(174,74),
    right_hip=(137,215),right_knee=(120,248),right_ankle=(132,270),right_toe=(126,293),
    left_hip=(172,215),left_knee=(190,248),left_ankle=(176,270),left_toe=(180,293),
    right_shoulder=(133,129),right_elbow=(104,171),right_wrist=(87,197),right_hand=(82,208),
    left_shoulder=(193,135),left_elbow=(211,181),left_wrist=(220,207),left_hand=(224,219))
extend=pose(
    hip=(161,240),waist=(148,219),chest=(137,195),neck=(134,154),crown=(139,104),
    right_hip=(144,244),right_knee=(116,270),right_ankle=(144,282),right_toe=(164,294),
    left_hip=(175,241),left_knee=(208,268),left_ankle=(243,279),left_toe=(265,292),
    right_shoulder=(106,164),right_elbow=(86,208),right_wrist=(75,249),right_hand=(72,262),
    left_shoulder=(162,161),left_elbow=(181,207),left_wrist=(208,218),left_hand=(220,221))
glide={**extend,
    "hip":(164,250),"waist":(149,231),"chest":(135,207),"neck":(126,166),"crown":(127,116),
    "right_hip":(147,253),"right_knee":(118,277),"right_ankle":(148,282),"right_toe":(169,294),
    "left_hip":(178,250),"left_knee":(218,275),"left_ankle":(254,281),"left_toe":(276,294),
    "right_shoulder":(98,176),"right_elbow":(81,225),"right_wrist":(73,263),"right_hand":(70,275),
    "left_shoulder":(153,174),"left_elbow":(178,213),"left_wrist":(207,228),"left_hand":(219,233)}
brake={**glide,
    "hip":(162,245),"waist":(153,220),"chest":(146,194),"neck":(147,153),"crown":(152,103),
    "left_hip":(176,245),"left_knee":(211,267),"left_ankle":(245,281),"left_toe":(268,294),
    "right_shoulder":(116,165),"right_elbow":(97,214),"right_wrist":(83,256),"right_hand":(80,269),
    "left_shoulder":(175,165),"left_elbow":(198,204),"left_wrist":(215,234),"left_hand":(217,247)}
# Draw the leading foot back under the pelvis before pushing upright.
gather=pose(
    hip=(156,220),waist=(158,194),chest=(166,169),neck=(178,129),crown=(185,80),
    right_hip=(137,222),right_knee=(119,253),right_ankle=(132,275),right_toe=(126,293),
    left_hip=(172,222),left_knee=(202,246),left_ankle=(198,275),left_toe=(203,294),
    right_shoulder=(145,134),right_elbow=(125,177),right_wrist=(117,205),right_hand=(116,218),
    left_shoulder=(202,143),left_elbow=(219,189),left_wrist=(222,216),left_hand=(224,229))
settle=pose(hip=(158,186),waist=(158,160),chest=(159,132),neck=(160,90),crown=(161,40),
            right_elbow=(109,151),right_wrist=(103,180),right_hand=(98,191))
slide_keys=[(0,pose()),(240,crouch),(440,extend),(600,glide),
            (1080,glide),(1320,brake),(1520,gather),(1800,settle),(1880,pose())]
frames=[]
for ms in range(0,1920,FRAME_MS):
    p=sample(slide_keys,ms)
    if 600<ms<1200:
        # Ground contact vibration is absorbed progressively up the spine.
        bounce=math.sin((ms-600)/600*math.tau*2)*1.8*math.sin((ms-600)/600*math.pi)
        for joint,weight in (("hip",1),("waist",.8),("chest",.5),("neck",.3),("crown",.15)):
            x,y=p[joint]
            p[joint]=(x,y+bounce*weight)
    f,_,_=render_pose(p)
    if 360<=ms<1520:
        d=ImageDraw.Draw(f)
        fade=1-smooth((ms-1240)/280)
        for j in range(12):
            age=((ms-360)/480+j/12)%1
            x=round(95-age*70)
            y=round(291-math.sin(age*math.pi)*(8+j%3*4))
            length=max(1,round((1-age)*9*fade))
            if fade>.05:
                d.line((x,y,x+length,y),fill=C["gold2" if j%3==0 else "cloth3"])
    frames.append(f)
add("slide",frames,"滑铲",20,movement={"start":320,"end":1320,"distance":150})

manifest={"version":1,"character":"redwolf","skin":"蚀金玫瑰",
          "frameWidth":320,"frameHeight":320,"clips":{}}
columns=5
for name,clip in clips.items():
    frames=clip["frames"]
    atlas=Image.new("RGBA",(columns*320,math.ceil(len(frames)/columns)*320))
    for i,f in enumerate(frames):
        assert set(f.getchannel("A").getdata()) <= {0,255}, name
        bbox=f.getbbox()
        assert bbox and bbox[0]>0 and bbox[1]>0 and bbox[2]<320 and bbox[3]<320, (name,i,bbox)
        atlas.alpha_composite(f,((i%columns)*320,(i//columns)*320))
    atlas.save(OUT/f"{name}-atlas.png")
    manifest["clips"][name]={k:v for k,v in clip.items() if k!="frames"}
    manifest["clips"][name].update({"file":f"{name}-atlas.png","columns":columns,
                                   "frameCount":len(frames),
                                   "durationMs":sum(clip["durations"])})
    # GIF review with a solid background only; runtime uses RGBA atlases.
    previews=[]
    for f in frames:
        bg=Image.new("RGB",SIZE,"#15191e")
        bg.paste(f,mask=f.getchannel("A"))
        previews.append(bg)
    previews[0].save(OUT/f"{name}-preview.gif",save_all=True,
                     append_images=previews[1:],duration=clip["durations"],loop=0,disposal=2)

(OUT/"animations.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")

# Contact sheet reveals the windup/contact/recovery, not just effects.
sheet=Image.new("RGB",(1280,1070),"#10151b")
sd=ImageDraw.Draw(sheet)
font_candidates=[
    os.environ.get("PIXEL_ART_FONT",""),
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "C:/Windows/Fonts/msyh.ttc",
]
font_path=next((p for p in font_candidates if p and Path(p).is_file()),None)
if not font_path:
    raise RuntimeError("Set PIXEL_ART_FONT to a Chinese font to render the review sheet.")
font=ImageFont.truetype(font_path,20)
for row,name in enumerate(("slide","rose","cannon")):
    clip=clips[name]
    sd.text((22,row*356+8),clip["label"],font=font,fill="#dfc27b")
    indices={"slide":[6,12,22,38],"rose":[10,22,31,39],"cannon":[0,10,15,18]}[name]
    for col,i in enumerate(indices):
        sheet.paste(clip["frames"][i],(col*320,row*356+30),clip["frames"][i])
sheet.save(OUT/"actions-review.png")
print(json.dumps({n:{"frames":v["frameCount"],"ms":v["durationMs"]}
                  for n,v in manifest["clips"].items()}))
