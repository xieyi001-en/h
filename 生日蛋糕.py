import os
import sys
import ctypes
from ctypes import wintypes
import numpy as np
import pyvista as pv
import time
from PIL import Image, ImageDraw, ImageFont
import tkinter as tk


def ask_age():
    win = tk.Tk()
    win.withdraw()
    dlg = tk.Toplevel(win)
    dlg.overrideredirect(True)
    dlg.attributes('-topmost', True)
    dlg.configure(bg="#FFB3C6")
    w, h = 380, 180
    dlg.geometry(f"{w}x{h}+{(dlg.winfo_screenwidth()-w)//2}+{(dlg.winfo_screenheight()-h)//2}")
    fr = tk.Frame(dlg, bg="#FFFFFF", padx=6, pady=6)
    fr.pack(fill="both", expand=True)
    tk.Label(fr, text="宝宝多少岁生日?", font=("Microsoft YaHei", 14, "bold"),
             bg="#FFFFFF", fg="#333333").pack(pady=(20, 8))
    tk.Label(fr, text="回车默认 18", font=("Microsoft YaHei", 9),
             bg="#FFFFFF", fg="#999999").pack()
    ev = tk.StringVar(value="18")
    en = tk.Entry(fr, textvariable=ev, font=("Microsoft YaHei", 14),
                  justify="center", relief="flat", bg="#FFF0F5", fg="#333333",
                  insertbackground="#333333")
    en.pack(pady=12, ipadx=6, ipady=10, fill="x", padx=40)
    en.select_range(0, "end")
    en.focus_set()
    r = {"v": "18"}

    def ok(e=None):
        r["v"] = ev.get()
        dlg.destroy()
        win.quit()

    en.bind("<Return>", ok)
    dlg.bind("<Return>", ok)
    dlg.bind("<Escape>", lambda e: ok())
    win.mainloop()
    try:
        win.destroy()
    except Exception:
        pass
    return r["v"]


_age = ask_age()
num = "".join(c for c in (_age or "18") if c.isdigit())[:2] or "18"
print(f"年龄: {num}")

pv.global_theme.background = "#0B1026"
TITLE = "生日蛋糕"
rst = [False]


def max_win():
    if sys.platform != "win32":
        return True
    try:
        u32 = ctypes.windll.user32
        fnd = [None]
        CB = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def cb(hwnd, lp):
            n = u32.GetWindowTextLengthW(hwnd)
            if n > 0:
                buf = ctypes.create_unicode_buffer(n + 1)
                u32.GetWindowTextW(hwnd, buf, n + 1)
                if TITLE in buf.value:
                    fnd[0] = hwnd
                    return False
            return True

        u32.EnumWindows(CB(cb), 0)
        if not fnd[0]:
            return False
        u32.ShowWindow(fnd[0], 3)
        u32.SetForegroundWindow(fnd[0])
        u32.BringWindowToTop(fnd[0])
        return True
    except Exception:
        return False


# 相机
CPOS = (8.5, -9.3, 6.5)
CTGT = (0.0, 0.0, 1.7)
CUP = (0.0, 0.0, 1.0)
CZOOM = 0.85
CYAW = float(np.degrees(np.arctan2(CPOS[0], -CPOS[1])))


def find_font():
    for p in ["C:/Windows/Fonts/comicbd.ttf", "C:/Windows/Fonts/comic.ttf",
              "C:/Windows/Fonts/ARLRDBD.TTF", "C:/Windows/Fonts/arialbd.ttf",
              "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf",
              "/Library/Fonts/Comic Sans MS.ttf",
              "/usr/share/fonts/truetype/msttcorefonts/Comic_Sans_MS_Bold.ttf"]:
        if os.path.exists(p):
            return p
    return None


FONT = find_font()
print(f"字体: {FONT}" if FONT else "未找到卡通字体")


# 通用函数
def hex_rgb(h: str):
    return np.array([int(h.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)], dtype=float) / 255.0


def lighter(h: str, a: float | int =0.5):
    c = hex_rgb(h)
    return tuple(np.clip(c + (1.0 - c) * a, a_min=0.0, a_max=1.0))


def sample_cyl(c, r: float, h, ns: int =8000, nc: int =2500, rng=None):
    rng = rng or np.random.default_rng()
    th, zz = rng.uniform(0, 2*np.pi, ns), rng.uniform(0, h, ns)
    side = np.stack([c[0] + r*np.cos(th), c[1] + r*np.sin(th), c[2] + zz], axis=1)
    th2 = rng.uniform(0, 2*np.pi, nc)
    r2 = r * np.sqrt(rng.uniform(0, 1, nc))
    top = np.stack([c[0] + r2*np.cos(th2), c[1] + r2*np.sin(th2),
                    c[2] + h + rng.normal(0, 0.002, nc)], axis=1)
    return np.vstack([side, top])


def sample_ell(c, radii, n: int =200, rng=None):
    rng = rng or np.random.default_rng()
    u, v = rng.uniform(0, 1, n), rng.uniform(0, 1, n)
    th, ph = 2*np.pi*u, np.arccos(2*v - 1)
    pts = np.stack([np.sin(ph)*np.cos(th), np.sin(ph)*np.sin(th),
                    np.cos(ph)], axis=1) * np.asarray(radii)
    return pts + np.asarray(c)


def sample_flame(c, h, mr, n, rng):
    t = rng.uniform(0, 1, n)
    r = mr * np.sin(np.pi * t**0.45) * (1 - 0.75*t) * np.sqrt(rng.uniform(0, 1, n))
    th = rng.uniform(0, 2*np.pi, n)
    return np.stack([c[0] + r*np.cos(th), c[1] + r*np.sin(th),
                     c[2] + t*h], axis=1).astype(np.float32)


def sample_mesh(mesh, n: int =500, rng=None):
    rng = rng or np.random.default_rng()
    if not isinstance(mesh, pv.PolyData):
        mesh = mesh.extract_surface()
    mesh = mesh.triangulate()
    pts = np.asarray(mesh.points)
    fs = mesh.faces.reshape(-1, 4)[:, 1:]
    if len(fs) == 0:
        return pts
    v0, v1, v2 = pts[fs[:, 0]], pts[fs[:, 1]], pts[fs[:, 2]]
    ar = 0.5 * np.linalg.norm(np.cross(v1 - v0, v2 - v0), axis=1)
    if ar.sum() <= 0:
        return pts
    ch = rng.choice(len(fs), size=n, p=ar/ar.sum())
    a, b = rng.uniform(0, 1, n), rng.uniform(0, 1, n)
    m = a + b > 1
    a[m], b[m] = 1 - a[m], 1 - b[m]
    return v0[ch] + a[:, None]*(v1[ch]-v0[ch]) + b[:, None]*(v2[ch]-v0[ch])


def _rc(t):
    b = t.bounds
    t.points -= np.array([0.5*(b[0]+b[1]), 0.5*(b[2]+b[3]), 0.5*(b[4]+b[5])])


def make_text(s, th: float | int =1.0):
    """生成 3D 文字 PolyData (基于 vtkVectorText, 使用内置字体)。"""
    t = None
    # 生成 3D 文字。注意: vtkVectorText 不支持自定义 TTF 字体,
    # 所以 font_file 参数无效; 自定义字体仅用于 2D 贴图文字 text_pts()。
    try:
        t = pv.Text3D(s)
    except Exception as e:
        print(f"Text3D 失败: {e}")
        return None
    # 确保是 PolyData
    if not isinstance(t, pv.PolyData):
        try:
            t = t.extract_surface()
        except Exception:
            pass
    # 挤出厚度
    try:
        t = t.extrude((0, 0, 0.12), capping=True)
    except Exception as e:
        print(f"extrude 失败: {e}")
    t.rotate_x(90, inplace=True)
    _rc(t)
    h = t.bounds[3] - t.bounds[2]
    if h > 1e-6:
        t.points *= th / h
    t.rotate_z(CYAW, inplace=True)
    _rc(t)
    return t


def make_ribbon(L: float | int =0.9, W: float | int =0.12, seg: int =8, wv: int =2):
    t = np.linspace(0, 1, seg)
    x, z = 0.08 * np.sin(t * np.pi * wv), -t * L
    pts = np.vstack([np.stack([x - W/2, np.zeros_like(t), z], axis=1),
                     np.stack([x + W/2, np.zeros_like(t), z], axis=1)]).astype(np.float32)
    fs = []
    for i in range(seg - 1):
        l0, r0, l1, r1 = i, seg + i, seg + i + 1, i + 1
        fs += [[3, l0, r0, r1], [3, l0, r1, l1]]
    mesh = pv.PolyData()
    mesh.points = pts
    mesh.faces = np.array(fs).ravel().astype(np.int32)
    return mesh


def text_pts(s, tw: float | int =5.0, step: int =2, fsize: int =200):
    try:
        font = ImageFont.truetype(FONT, fsize) if FONT else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()
    pad = 40
    bb = font.getbbox(s)
    w, h = bb[2]-bb[0] + pad*2, bb[3]-bb[1] + pad*2
    if w <= 0 or h <= 0:
        return np.zeros((0, 3), dtype='f4')
    img = Image.new('L', (w, h), 0)
    ImageDraw.Draw(img).text((pad - bb[0], pad - bb[1]), s, font=font, fill=255)
    ys, xs = np.where(np.array(img) > 128)
    if len(xs) == 0:
        return np.zeros((0, 3), dtype='f4')
    ix = np.arange(0, len(xs), step)
    px = (xs[ix] - w/2.0).astype('f4')
    py = -(ys[ix] - h/2.0).astype('f4')
    sc = tw / float(w)
    px *= sc
    py *= sc
    yaw = np.radians(CYAW)
    cy, sy = np.cos(yaw), np.sin(yaw)
    return np.stack([px*cy, px*sy, py], axis=1).astype('f4')


def flame_deform(bp, bz, br, dx, dy, dz):
    p = bp.copy()
    p[:, 2] = bz + (p[:, 2] - bz) * br
    p[:, 0] = p[:, 0] * br + dx
    p[:, 1] = p[:, 1] * br + dy
    p[:, 2] += dz
    return p


# ============ 场景 ============
plotter = pv.Plotter(window_size=(1200, 1000), title=TITLE)
plotter.set_background("#0B1026")
rng = np.random.default_rng(20240601)
cake = []

# 盘子
th = rng.uniform(0, 2*np.pi, 5000)
rr = np.sqrt(rng.uniform(0, 1, 5000)) * 2.35
plate = np.stack([rr*np.cos(th), rr*np.sin(th), rng.normal(-0.05, 0.006, 5000)], axis=1)
cake.append(plotter.add_mesh(pv.PolyData(plate), color="#E7DCF2",
                             style='points', render_points_as_spheres=True,
                             point_size=1.5, lighting=False))

# 五层蛋糕
layers = [(1.90, 0.85, "#FFB3C6"), (1.62, 0.78, "#FFE7A8"),
          (1.36, 0.72, "#A8E6CF"), (1.12, 0.66, "#A9C9FF"),
          (0.88, 0.60, "#D9BFFF")]
z = 0.0
for r, h, col in layers:
    cake.append(plotter.add_mesh(
        pv.PolyData(sample_cyl((0, 0, z), r, h, rng=rng)),
        color=col, style='points', render_points_as_spheres=True,
        point_size=1.8, lighting=False))
    balls = [sample_ell((r*1.03*np.cos(2*np.pi*(i+0.5)/26),
                         r*1.03*np.sin(2*np.pi*(i+0.5)/26),
                         z + h - 0.05), radii=(0.10, 0.10, 0.10), n=150, rng=rng)
             for i in range(26)]
    cake.append(plotter.add_mesh(
        pv.PolyData(np.vstack(balls)), color=lighter(col, a=0.55),
        style='points', render_points_as_spheres=True, point_size=1.8, lighting=False))
    z += h
tz = z

# 数字蜡烛
t = make_text(num, th=0.85)
if t is None:
    print("蜡烛文字生成失败, 使用默认块")
    t = pv.Cube(center=(0, 0, tz + 0.4), x_length=0.6, y_length=0.2, z_length=0.85)
mw = t.bounds[1] * 1.03 * 2 * 0.70
w_now = t.bounds[1] - t.bounds[0]
if w_now > mw and w_now > 1e-6:
    t.points *= mw / w_now
t.points += np.array([0, 0, tz - t.bounds[4]])
cake.append(plotter.add_mesh(
    pv.PolyData(sample_mesh(t, n=7000, rng=rng)), color="#FF8FA3",
    style='points', render_points_as_spheres=True, point_size=2, lighting=False))

# 两层火焰
fz = t.bounds[5] + 0.03
fo_pts = sample_flame((0, 0, fz), h=0.30, mr=0.075, n=5000, rng=rng)
fi_pts = sample_flame((0, 0, fz), h=0.22, mr=0.042, n=3500, rng=rng)
fo_act = plotter.add_mesh(pv.PolyData(fo_pts), color="#FF4A0F",
                          style='points', render_points_as_spheres=True,
                          point_size=1.2, lighting=False)
fi_act = plotter.add_mesh(pv.PolyData(fi_pts), color="#FFE9A8",
                          style='points', render_points_as_spheres=True,
                          point_size=1.2, lighting=False)
cake += [fo_act, fi_act]

# 顶层装饰
SPCOL = ["#FF8FA3", "#7EC8E3", "#FFC857", "#9AE6B4", "#C79BFF", "#FFFFFF"]
tr = layers[-1][0] * 1.03
spts, scols = [], []
for k in range(30):
    rad = tr * np.sqrt(rng.random()) * 0.92
    ang = rng.random() * 2*np.pi
    p = sample_ell((rad*np.cos(ang), rad*np.sin(ang), tz + 0.02),
                   radii=(0.04, 0.04, 0.03), n=50, rng=rng)
    spts.append(p)
    scols.append(np.tile(hex_rgb(SPCOL[rng.integers(len(SPCOL))]) * 255, (len(p), 1)))
scld = pv.PolyData(np.vstack(spts))
scld["colors"] = np.vstack(scols).astype(np.uint8)
cake.append(plotter.add_mesh(scld, scalars="colors", rgb=True,
                             style='points', render_points_as_spheres=True,
                             point_size=1.5, lighting=False))

# 倒数数字
NCOL = {3: "#F50057", 2: "#FF9100", 1: "#00E676"}
CD0 = 3
nums = {}
for n in range(1, CD0 + 1):
    tt = make_text(str(n), th=3.0)
    if tt is None:
        tt = pv.Cube(center=(0, 0, 0), x_length=1.2, y_length=0.2, z_length=2.4)
        tt.points += np.array([0.0, 0.0, 2.4])
    a = plotter.add_mesh(pv.PolyData(sample_mesh(tt, n=7000, rng=rng)),
                         color=NCOL[n], style='points',
                         render_points_as_spheres=True, point_size=2.5, lighting=False)
    a.SetVisibility(False)
    # 几何体已居中在 z≈0, 缩放中心设为原点, 避免弹出时上下滑动
    a.SetOrigin(0, 0, 0)
    nums[n] = a

# Happy Birthday
HBZ = 2.4
hb_pts = text_pts("Happy Birthday", tw=5.0, step=2, fsize=200)
if len(hb_pts) > 0:
    hb_pts[:, 2] += HBZ
    hb = plotter.add_mesh(pv.PolyData(hb_pts), color="#FF69B4",
                          style='points', render_points_as_spheres=True,
                          point_size=2.0, lighting=False)
    hb.SetVisibility(False)
    hb.SetOrigin(0, 0, HBZ)
    print(f"HB 粒子数: {len(hb_pts)}")
else:
    hb = None
    print("Happy Birthday 生成失败")

# 大飘带
NB = 150
BORIG = np.array([0.0, 0.0, 2.4])
RPAL = ["#FF1744", "#FF6D00", "#FFD600", "#76FF03",
        "#00E5FF", "#2979FF", "#AA00FF", "#F50057",
        "#00E676", "#FF9100", "#FF4081", "#18FFFF",
        "#FFFF00", "#FF6E40", "#B388FF", "#69F0AE"]
ribbons = []
brng = np.random.default_rng(9999)
for i in range(NB):
    mesh = make_ribbon(L=float(brng.uniform(0.7, 1.2)),
                       W=float(brng.uniform(0.10, 0.16)))
    a = plotter.add_mesh(mesh, color=RPAL[brng.integers(len(RPAL))],
                         lighting=False, show_edges=False)
    a.SetVisibility(False)
    th_, ph_ = brng.uniform(0, 2*np.pi), np.arccos(brng.uniform(-1, 1))
    sp = brng.uniform(0.22, 0.40)
    vx, vy, vz = sp*np.sin(ph_)*np.cos(th_), sp*np.sin(ph_)*np.sin(th_), sp*np.cos(ph_)*0.9 + 0.20
    io = np.array([brng.uniform(0, 360) for _ in range(3)], dtype=np.float64)
    ribbons.append({
        "a": a, "pos": BORIG.copy(),
        "v": np.array([vx, vy, vz]), "o": io.copy(),
        "rs": np.array([brng.uniform(-25, 25) for _ in range(3)]),
        "iv": np.array([vx, vy, vz]), "io": io.copy(),
        "bf": -1, "act": False,
    })

# 小彩带
NC = 500
crng = np.random.default_rng(7)
CPAL = ["#FF6B9D", "#FFD93D", "#6BCBFF", "#A0E76E",
        "#C78CFF", "#FF9A6B", "#FF1744", "#00E5FF"]
CTOP, CBOT = 11.0, -2.0


def reset_cf():
    return (crng.uniform(-5, 5, NC).astype(np.float32),
            crng.uniform(-5, 5, NC).astype(np.float32),
            crng.uniform(CBOT, CTOP, NC).astype(np.float32),
            crng.uniform(-0.02, 0.02, NC).astype(np.float32),
            crng.uniform(-0.02, 0.02, NC).astype(np.float32),
            -crng.uniform(0.08, 0.18, NC).astype(np.float32))


cf_x, cf_y, cf_z, cf_vx, cf_vy, cf_vz = reset_cf()
cf_cols = np.array([(hex_rgb(CPAL[crng.integers(8)]) * 255).astype(np.uint8)
                    for _ in range(NC)], dtype=np.uint8)
cf_cloud = pv.PolyData(np.stack([cf_x, cf_y, cf_z], axis=1).astype(np.float32))
cf_cloud["colors"] = cf_cols
cf = plotter.add_mesh(cf_cloud, scalars="colors", rgb=True, style='points',
                      render_points_as_spheres=True, point_size=7, lighting=False)
cf.SetVisibility(False)

# 初始隐藏
for a in cake:
    a.SetVisibility(False)


def set_cam():
    tg = np.array(CTGT, dtype=float)
    d = np.array(CPOS, dtype=float) - tg
    d /= np.linalg.norm(d)
    plotter.camera.position = tuple(tg + d * (np.linalg.norm(np.array(CPOS) - tg) / CZOOM))
    plotter.camera.focal_point = CTGT
    plotter.camera.up = CUP


set_cam()

# 时间参数
SPN = 12
CDEND = CD0 * SPN
HBPOP = CDEND + 10
HBHOLD = CDEND + 45
HBFADE = CDEND + 65
CAKEF = CDEND + 70
BLIFE = 110
FDELAY = 0.04
RSPD = 0.4
GRAV = 0.012
st = {"n": None, "nf": 0}
ROT = False
FALL = False
BSTART = False
fc = [0]


def do_reset():
    global cf_x, cf_y, cf_z, cf_vx, cf_vy, cf_vz, ROT, FALL, BSTART
    for a in nums.values():
        a.SetVisibility(False)
        a.SetScale(1.0, 1.0, 1.0)
    st["n"] = None
    st["nf"] = 0
    if hb is not None:
        hb.SetVisibility(False)
        hb.SetScale(1.0, 1.0, 1.0)
        try:
            hb.prop.opacity = 1.0
        except Exception:
            pass
    for a in cake:
        a.SetVisibility(False)
        a.SetPosition(0, 0, 0)
        a.SetOrientation(0, 0, 0)
    for r in ribbons:
        r["a"].SetVisibility(False)
        r["act"] = False
        r["bf"] = -1
        r["pos"] = BORIG.copy()
        r["v"] = r["iv"].copy()
        r["o"] = r["io"].copy()
    cf_x, cf_y, cf_z, cf_vx, cf_vy, cf_vz = reset_cf()
    cf_cloud.points = np.stack([cf_x, cf_y, cf_z], axis=1).astype(np.float32)
    cf_cloud.Modified()
    cf.SetVisibility(False)
    fo_act.mapper.dataset.points = fo_pts.copy()
    fo_act.mapper.dataset.Modified()
    fi_act.mapper.dataset.points = fi_pts.copy()
    fi_act.mapper.dataset.Modified()
    ROT = False
    FALL = False
    BSTART = False
    fc[0] = 0
    set_cam()
    print("重新播放")


# 空格重置
plotter.add_key_event("space", lambda: rst.__setitem__(0, True))

# 显示
plotter.show(auto_close=False, interactive_update=True)
plotter.render()

for i in range(30):
    if max_win():
        print(f"窗口已最大化 (第 {i + 1} 次尝试)")
        break
    plotter.render()
    time.sleep(0.06)
else:
    print("未找到窗口, 请手动最大化")

# 主循环
try:
    while True:
        if getattr(plotter, "_closed", False):
            break
        if rst[0]:
            rst[0] = False
            do_reset()
        fc[0] += 1
        fr = fc[0]

        # 倒数阶段
        if fr < CDEND:
            cur = CD0 - (fr // SPN)
            if cur != st["n"]:
                if st["n"] is not None:
                    old = nums[st["n"]]
                    old.SetVisibility(False)
                    old.SetScale(1.0, 1.0, 1.0)
                nums[cur].SetVisibility(True)
                st["n"] = cur
                st["nf"] = fr
            ts = (fr - st["nf"]) / SPN
            s = max(1.0, 1.5 - 1.5 * (ts / 0.35)) if ts < 0.35 else 1.0
            if st["n"] is not None:
                nums[st["n"]].SetScale(s, s, s)
        elif fr == CDEND:
            if st["n"] is not None:
                nums[st["n"]].SetVisibility(False)
                st["n"] = None
            if hb is not None:
                hb.SetVisibility(True)
                hb.SetScale(0.4, 0.4, 0.4)
                try:
                    hb.prop.opacity = 1.0
                except Exception:
                    pass

        # HB 弹出 - 保持 - 放大淡出
        if hb is not None and CDEND <= fr < HBFADE:
            t_ = fr - CDEND
            if t_ < (HBPOP - CDEND):
                p = t_ / float(HBPOP - CDEND)
                sc, op = 0.4 + 0.6 * (1.0 - (1.0 - p) **3), 1.0
            elif t_ < (HBHOLD - CDEND):
                sc, op = 1.0 + 0.03 * np.sin((t_ - 10) * 0.3), 1.0
            else:
                p = min(1.0, (t_ - (HBHOLD - CDEND)) / float(HBFADE - HBHOLD))
                sc, op = 1.0 + 1.5 * (p ** 1.6), max(0.0, 1.0 - p)
            hb.SetScale(sc, sc, sc)
            try:
                hb.prop.opacity = op
            except Exception:
                pass

        # HB 结束，飘带爆破
        if fr == HBFADE:
            if hb is not None:
                hb.SetVisibility(False)
            for r in ribbons:
                r["pos"] = BORIG.copy()
                r["v"] = r["iv"].copy()
                r["o"] = r["io"].copy()
                r["bf"] = fr
                r["act"] = True
                r["a"].SetVisibility(True)
                r["a"].SetPosition(*r["pos"])
                r["a"].SetOrientation(*r["o"])
            cf.SetVisibility(True)
            FALL = True
            BSTART = True

        # 飘带运动
        if BSTART:
            for r in ribbons:
                if not r["act"]:
                    continue
                r["v"][2] -= GRAV
                r["pos"] = r["pos"] + r["v"]
                r["o"] = r["o"] + r["rs"]
                r["a"].SetPosition(*r["pos"])
                r["a"].SetOrientation(*r["o"])
                if (fr - r["bf"]) > BLIFE \
                        or abs(r["pos"][0]) > 14 \
                        or abs(r["pos"][1]) > 14 \
                        or r["pos"][2] < -5:
                    r["a"].SetVisibility(False)
                    r["act"] = False

        # 小彩带下落
        if FALL:
            cf_x += cf_vx
            cf_y += cf_vy
            cf_z += cf_vz
            below = cf_z < CBOT
            if below.any():
                n = int(below.sum())
                cf_x[below] = crng.uniform(-5, 5, n).astype(np.float32)
                cf_y[below] = crng.uniform(-5, 5, n).astype(np.float32)
                cf_z[below] = CTOP
                cf_vx[below] = crng.uniform(-0.02, 0.02, n).astype(np.float32)
                cf_vy[below] = crng.uniform(-0.02, 0.02, n).astype(np.float32)
                cf_vz[below] = -crng.uniform(0.08, 0.18, n).astype(np.float32)
            cf_cloud.points = np.stack([cf_x, cf_y, cf_z], axis=1).astype(np.float32)
            cf_cloud.Modified()

        # 蛋糕出现
        if fr == CAKEF:
            for a in cake:
                a.SetVisibility(True)
                a.SetPosition(0, 0, 0)
            ROT = True

        # 蛋糕旋转
        if ROT:
            for a in cake:
                a.RotateZ(RSPD)

        # 烛光抖动
        if ROT:
            t_ = fr * 0.4
            dz = 0.010*np.sin(t_*1.7) + 0.005*np.sin(t_*5.1)
            dx = 0.006*np.sin(t_*2.3 + 0.5)
            dy = 0.006*np.cos(t_*2.7 + 1.1)
            bo = 1.0 + 0.06*np.sin(t_*4.3)
            bi = 1.0 + 0.10*np.sin(t_*6.1 + 0.9)
            fo_act.mapper.dataset.points = flame_deform(fo_pts, fz, bo, dx, dy, dz)
            fo_act.mapper.dataset.Modified()
            fi_act.mapper.dataset.points = flame_deform(fi_pts, fz, bi, dx, dy, dz)
            fi_act.mapper.dataset.Modified()

        plotter.update()
        time.sleep(FDELAY)
except KeyboardInterrupt:
    print("用户中断")
except Exception as e:
    print(f"结束: {e}")
try:
    plotter.close()
except Exception:
    pass