"""Motion design v2 « Rapport de bug » : personnage animé, sous-titres mot à mot, illustrations, caméra.

Usage direct (sans voix) : python3 outils/motion2.py specs/video/004.json sortie.mp4
Avec voix : python3 outils/voix.py specs/video/004.json sortie.mp4   (voix.py appelle ce moteur)

Spec : {"num", "next", "scenes": [...]}, scènes cover / text / bubbles / status / cta,
champs : label, title, text, lines, status, visual (plate, timer, cut, think), voice (texte dit).
Dans "voice", *mot* = mot mis en valeur (vert) dans les sous-titres.
"""
import sys, os, json, math, random, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import motion as m1          # sons, polices, utilitaires de la v1

W, H, FPS, SR = 1080, 1920, 30, 44100
S = 2                        # sur-échantillonnage des dessins (anticrénelage)
OY, LH = 300, 1160           # calque de dessin : de y=300 à y=1460
NAVY = (20, 33, 61); NAVY2 = (14, 24, 46); PANEL = (27, 43, 77); GREEN = (61, 220, 151); GREEN_D = (40, 170, 114)
GREEN_L = (140, 240, 196); WHITE = (245, 243, 238); MUTED = (154, 166, 191); RED = (255, 107, 107); YELLOW = (255, 209, 102)
CREAM = (255, 241, 214); SPONGE = (242, 193, 78); SPONGE_D = (214, 158, 52); BERRY = (230, 57, 70)
SKIN = (241, 198, 168); SLEEVE_A = (224, 122, 95); SLEEVE_B = (108, 142, 191); STEEL = (217, 222, 231); WOOD = (110, 70, 45)
START = 0.25
font = m1.font
BOLD, SEMI, REG, MONO, MONO_R = m1.BOLD, m1.SEMI, m1.REG, m1.MONO, m1.MONO_R


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def eo(x):
    x = clamp(x); return 1 - (1 - x) ** 3


def eb(x):
    x = clamp(x); c = 1.7; return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def ei(x):
    x = clamp(x); return x * x * (3 - 2 * x)


def spring(t, f=14, d=6):
    if t < 0:
        return 0.0
    return 1 - math.exp(-d * t) * math.cos(f * t)


def pulse(t, t0, dur=0.25):
    """0 → 1 → 0 autour de t0 (pour les à-coups de caméra)."""
    x = (t - t0) / dur
    return math.sin(math.pi * x) if 0 <= x <= 1 else 0.0


# ---------- dessin à l'échelle ×2 ----------
class V:
    def __init__(self):
        self.im = Image.new("RGBA", (W * S, LH * S), (0, 0, 0, 0)); self.d = ImageDraw.Draw(self.im)

    def P(self, x, y):
        return (x * S, (y - OY) * S)

    def ell(self, cx, cy, rx, ry, fill=None, outline=None, width=0):
        if rx <= 0.5 or ry <= 0.5:
            return
        a, b = self.P(cx - rx, cy - ry), self.P(cx + rx, cy + ry)
        self.d.ellipse([a, b], fill=fill, outline=outline, width=int(width * S))

    def rr(self, x0, y0, x1, y1, r, fill=None, outline=None, width=0):
        if x1 - x0 < 1 or y1 - y0 < 1:
            return
        r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
        a, b = self.P(x0, y0), self.P(x1, y1)
        self.d.rounded_rectangle([a, b], radius=r * S, fill=fill, outline=outline, width=int(width * S))

    def poly(self, pts, fill=None, outline=None, width=0):
        self.d.polygon([self.P(x, y) for x, y in pts], fill=fill, outline=outline, width=int(width * S))

    def line(self, pts, fill, width):
        self.d.line([self.P(x, y) for x, y in pts], fill=fill, width=int(width * S), joint="curve")

    def text(self, x, y, s, fp, size, fill, anchor="la", stroke=0, sfill=None):
        self.d.text(self.P(x, y), s, font=font(fp, size * S), fill=fill, anchor=anchor,
                    stroke_width=int(stroke * S), stroke_fill=sfill)

    def paste(self, img, x, y):
        self.im.alpha_composite(img, (int(x * S), int((y - OY) * S)))

    def done(self):
        return self.im.reduce(S)


def rot(pts, cx, cy, a):
    c, s = math.cos(a), math.sin(a)
    return [(cx + (x - cx) * c - (y - cy) * s, cy + (x - cx) * s + (y - cy) * c) for x, y in pts]


# ---------- le personnage : Claude ----------
def claude(v, cx, cy, s, t, expr="normal", look=(0, 0), talk=0.0, walk=0.0, squash=0.0, wave=0.0, seed=0):
    """Dessine Claude (insecte-robot). cx, cy = centre du corps ; s = largeur du corps."""
    bob = math.sin(t * 3.2 + seed) * s * 0.02
    sy = 1 - squash * 0.12; sx = 1 + squash * 0.08
    bw, bh = s * sx, s * 1.12 * sy
    by = cy + bob + (s * 1.12 - bh) / 2
    # ombre
    v.ell(cx, cy + s * 0.62, s * 0.55, s * 0.07, fill=NAVY2 + (200,))
    # pattes
    for side in (-1, 1):
        for i, yy in enumerate((-0.25, 0.05, 0.35)):
            ph = math.sin(walk * 10 + i * 2.1 + (0 if side < 0 else math.pi)) * 0.35 if walk else 0
            x0 = cx + side * bw * 0.45; y0 = by + yy * bh
            ang = (-0.35 + i * 0.35 + ph) * side
            x1 = x0 + side * s * 0.3 * math.cos(ang); y1 = y0 + s * 0.3 * math.sin(ang * side) + s * 0.04 * i
            v.line([(x0, y0), (x1, y1)], GREEN_D, s * 0.06)
    # corps
    v.rr(cx - bw / 2, by - bh / 2, cx + bw / 2, by + bh / 2, s * 0.42, fill=GREEN)
    v.ell(cx - bw * 0.2, by - bh * 0.28, bw * 0.16, bh * 0.08, fill=GREEN_L + (160,))
    v.line([(cx, by - bh * 0.42), (cx, by + bh * 0.47)], GREEN_D, s * 0.03)
    # écran du ventre : égaliseur quand Claude parle
    sw, sh = bw * 0.62, bh * 0.26; sx0, sy0 = cx - sw / 2, by + bh * 0.04
    v.rr(sx0, sy0, sx0 + sw, sy0 + sh, s * 0.06, fill=NAVY)
    n = 7
    for i in range(n):
        lvl = talk * (0.35 + 0.65 * abs(math.sin(t * 17 + i * 1.7))) if talk > 0.02 else 0.08
        hh = max(sh * 0.1, sh * 0.8 * lvl); xx = sx0 + sw * (i + 0.5) / n
        v.rr(xx - sw * 0.03, sy0 + sh / 2 - hh / 2, xx + sw * 0.03, sy0 + sh / 2 + hh / 2, s * 0.015, fill=GREEN)
    # tête
    hw, hh = s * 0.72, s * 0.44; hy = by - bh / 2 - hh * 0.42
    # antennes (ressort) + salut
    for side in (-1, 1):
        wig = math.sin(t * 6 + side + seed) * 0.12 + (math.sin(t * 14) * 0.5 * wave if side > 0 else 0)
        base = (cx + side * hw * 0.25, hy - hh * 0.45)
        a = -math.pi / 2 + side * 0.55 + wig
        tip = (base[0] + math.cos(a) * s * 0.42, base[1] + math.sin(a) * s * 0.42)
        v.line([base, tip], GREEN, s * 0.05)
        v.ell(tip[0], tip[1], s * 0.075, s * 0.075, fill=GREEN)
    v.rr(cx - hw / 2, hy - hh / 2, cx + hw / 2, hy + hh / 2, s * 0.17, fill=GREEN)
    # yeux-écrans
    blink = (t + seed * 0.7) % 3.1 < 0.12
    for side in (-1, 1):
        ex, ey, er = cx + side * hw * 0.22, hy, s * 0.13
        v.rr(ex - er, ey - er, ex + er, ey + er, s * 0.04, fill=NAVY)
        lx, ly = look[0] * er * 0.45, look[1] * er * 0.45
        p = er * 0.42
        if expr == "x":
            v.line([(ex - p, ey - p), (ex + p, ey + p)], WHITE, s * 0.035); v.line([(ex - p, ey + p), (ex + p, ey - p)], WHITE, s * 0.035)
        elif expr in ("!", "?"):
            v.text(ex, ey, expr, BOLD, int(er * 1.5), WHITE, anchor="mm")
        elif expr == "happy":
            v.line([(ex - p, ey + p * 0.3), (ex, ey - p * 0.5), (ex + p, ey + p * 0.3)], WHITE, s * 0.035)
        elif expr == "sleepy" or blink:
            v.line([(ex - p, ey + p * 0.2), (ex + p, ey + p * 0.2)], WHITE, s * 0.035)
        else:
            v.rr(ex + lx - p, ey + ly - p, ex + lx + p, ey + ly + p, s * 0.02, fill=WHITE)


def talk_level(env, gt):
    i = int(gt * FPS)
    return float(env[i]) if env is not None and 0 <= i < len(env) else 0.0


# ---------- illustrations ----------
def slice3d(v, cx, cy, s, width=1.0, alpha=255):
    """Part de gâteau en 3/4. width < 1 : part plus fine (après découpe)."""
    w = s * width
    top = [(cx, cy - s * 0.55), (cx - w * 0.5, cy + s * 0.15), (cx + w * 0.5, cy + s * 0.15)]
    v.poly([(top[1][0], top[1][1]), (top[2][0], top[2][1]), (top[2][0], top[2][1] + s * 0.32), (top[1][0], top[1][1] + s * 0.32)], fill=SPONGE + (alpha,))
    v.poly([(top[1][0], top[1][1] + s * 0.12), (top[2][0], top[2][1] + s * 0.12), (top[2][0], top[2][1] + s * 0.18), (top[1][0], top[1][1] + s * 0.18)], fill=CREAM + (alpha,))
    v.poly([(top[2][0], top[2][1]), (top[2][0], top[2][1] + s * 0.32), (top[2][0] - w * 0.08, top[2][1] + s * 0.32)], fill=SPONGE_D + (alpha,))
    v.poly(top, fill=CREAM + (alpha,))
    if width > 0.3:
        v.ell(cx, cy - s * 0.08, s * 0.09 * min(1, width * 1.5), s * 0.08, fill=BERRY + (alpha,))
        v.ell(cx + s * 0.03, cy - s * 0.15, s * 0.04, s * 0.02, fill=GREEN_D + (alpha,))


def plate(v, cx, cy, r, sc=1.0):
    r *= sc
    v.ell(cx, cy + r * 0.12, r, r * 0.4, fill=NAVY2 + (220,))
    v.ell(cx, cy, r, r * 0.4, fill=(232, 230, 225))
    v.ell(cx, cy, r * 0.74, r * 0.29, fill=(214, 211, 204))


def arm(v, side, reach, y, color):
    """Bras qui entre par le bord (side -1 gauche / 1 droite), reach 0..1."""
    x_edge = -40 if side < 0 else W + 40
    x_hand = x_edge + side * -1 * (60 + 330 * reach)
    v.line([(x_edge, y + 30), (x_hand, y)], color, 70)
    v.ell(x_hand - side * 10, y, 48, 42, fill=SKIN)
    for k in range(3):
        v.ell(x_hand - side * 45, y - 25 + k * 22, 16, 11, fill=SKIN)


def knife(v, px, py, ang, length=520):
    blade = [(px, py), (px + length, py - 10), (px + length + 40, py + 18), (px + length, py + 70), (px, py + 60)]
    handle = [(px - 190, py + 5), (px, py + 5), (px, py + 55), (px - 190, py + 55)]
    v.poly(rot(handle, px, py + 30, ang), fill=WOOD)
    v.poly(rot(blade, px, py + 30, ang), fill=STEEL)
    v.line(rot([(px + 10, py + 58), (px + length, py + 68)], px, py + 30, ang), WHITE, 5)


def stopwatch(v, cx, cy, r, ang):
    v.rr(cx - 28, cy - r - 62, cx + 28, cy - r - 10, 10, fill=WHITE)
    v.ell(cx, cy, r + 18, r + 18, fill=WHITE)
    v.ell(cx, cy, r, r, fill=PANEL)
    for k in range(12):
        a = k / 12 * 2 * math.pi
        v.line([(cx + math.cos(a) * r * 0.82, cy + math.sin(a) * r * 0.82), (cx + math.cos(a) * r * 0.94, cy + math.sin(a) * r * 0.94)], MUTED, 6)
    v.line([(cx, cy), (cx + math.cos(ang - math.pi / 2) * r * 0.8, cy + math.sin(ang - math.pi / 2) * r * 0.8)], GREEN, 12)
    v.ell(cx, cy, 16, 16, fill=GREEN)


def bulb(v, cx, cy, on):
    if on > 0:
        v.ell(cx, cy, 120 * on, 120 * on, fill=YELLOW + (int(70 * on),))
    v.ell(cx, cy, 58, 58, fill=YELLOW if on > 0.5 else MUTED)
    v.rr(cx - 26, cy + 48, cx + 26, cy + 90, 8, fill=STEEL)


def stamp_img(lines):
    f = font(BOLD, 104 * S)
    tw = max(ImageDraw.Draw(Image.new("L", (1, 1))).textlength(l, font=f) for l in lines)
    w, h = int(tw + 110 * S), int(len(lines) * 124 * S + 70 * S)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([6 * S, 6 * S, w - 6 * S, h - 6 * S], radius=30 * S, outline=GREEN, width=12 * S, fill=NAVY + (230,))
    y = 36 * S
    for l in lines:
        d.text((55 * S, y), l, font=f, fill=GREEN); y += 124 * S
    return im


# ---------- sous-titres mot à mot ----------
def word_times(text, t0, dur):
    words = text.split()
    wts = [len(w.replace("*", "")) + (4 if w[-1] in ".?!:" else 2 if w[-1] == "," else 1) for w in words]
    tot = sum(wts); out = []; t = t0
    for w, k in zip(words, wts):
        out.append((t, w)); t += dur * k / tot
    return out


def chunks(words, d, f, maxw=920):
    """Regroupe les mots en blocs de 2 lignes maximum, coupés de préférence en fin de phrase."""
    res, cur = [], []
    for i, (t, w) in enumerate(words):
        test = cur + [(t, w)]
        lines = m1.wrap(d, " ".join(x[1].replace("*", "") for x in test), f, maxw)
        if len(lines) > 2 and cur:
            res.append(cur); cur = [(t, w)]
        else:
            cur = test
        if w[-1] in ".?!" and len(cur) >= 3:
            res.append(cur); cur = []
    if cur:
        res.append(cur)
    return res


def captions(im, d, t, sc):
    if not sc.get("_words"):
        return
    f = font(BOLD, 78)
    groups = sc["_chunks"]
    cur = None
    for g in groups:
        if t >= g[0][0] - 0.05:
            cur = g
    if cur is None:
        return
    nxt = groups.index(cur) + 1
    if nxt < len(groups) and t >= groups[nxt][0][0]:
        return
    if t > cur[-1][0] + 1.6 and nxt >= len(groups):
        return
    lines, line = [], []
    for wt in cur:
        trial = line + [wt]
        if line and d.textlength(" ".join(m1.fr(x[1].replace("*", "")) for x in trial), font=f) > 920:
            lines.append(line); line = [wt]
        else:
            line = trial
    lines.append(line)
    y = 1110
    for ln in lines:
        txts = [m1.fr(x[1].replace("*", "")) for x in ln]
        total = d.textlength(" ".join(txts), font=f); x = W / 2 - total / 2
        for (wt, w), tx in zip(ln, txts):
            ww = d.textlength(tx, font=f)
            if t >= wt:
                k = eo((t - wt) / 0.12); key = w.startswith("*")
                active = t < wt + 0.35
                col = GREEN if key else (YELLOW if active else WHITE)
                dy = 14 * (1 - k)
                d.text((x, y + dy), tx, font=f, fill=col, stroke_width=7, stroke_fill=NAVY2)
            x += ww + d.textlength(" ", font=f)
        y += 96


# ---------- fond et en-tête ----------
_bg = None


def background(gt):
    global _bg
    if _bg is None:
        g = np.linspace(0, 1, H + 120)[:, None]
        top, bot = np.array(NAVY), np.array(NAVY2)
        arr = (top * (1 - g) + bot * g)[:, None, :].repeat(W, axis=1).astype(np.uint8)
        _bg = Image.fromarray(arr); d = ImageDraw.Draw(_bg)
        for y in range(0, H + 120, 60):
            for x in range(30, W, 60):
                d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(42, 58, 94))
    off = int((gt * 18) % 60)
    return _bg.crop((0, off, W, off + H)).copy()


def chrome(d, gt, total, num):
    d.rounded_rectangle([60, 140, W - 60, 214], radius=18, fill=PANEL)
    for i, c in enumerate([RED, YELLOW, GREEN]):
        d.ellipse([92 + i * 36, 166, 116 + i * 36, 190], fill=c)
    d.text((220, 160), f"rapport_{num}.log", font=font(MONO_R, 30), fill=MUTED)
    tag = "@rapportdebug"; f = font(SEMI, 32)
    d.text((W - 92 - d.textlength(tag, font=f), 159), tag, font=f, fill=WHITE)
    d.rounded_rectangle([60, 228, W - 60, 234], radius=3, fill=PANEL)
    d.rounded_rectangle([60, 228, 60 + (W - 120) * clamp(gt / total), 234], radius=3, fill=GREEN)
    f = font(MONO_R, 24); s = "contenu IA"
    d.text((W - 60 - d.textlength(s, font=f), 244), s, font=f, fill=MUTED)


def label(v, t, text):
    k = eo(t / 0.3)
    if k <= 0:
        return
    f = font(MONO, 40)
    w = ImageDraw.Draw(Image.new("L", (1, 1))).textlength("> " + text, font=f) + 44
    x = 60 - (1 - k) * 200
    v.rr(x, 300, x + w, 362, 14, fill=GREEN + (40,), outline=GREEN, width=2)
    v.text(x + 22, 331, "> " + text, MONO, 40, GREEN, anchor="lm")


# ---------- scènes ----------
def scene_frame(si, sc, t, gt, total, ctx):
    im = background(gt); d = ImageDraw.Draw(im)
    chrome(d, gt, total, ctx["num"])
    v = V(); k = sc["kind"]; tl = talk_level(ctx["env"], gt)
    shake = (0, 0); zoom = 1.0
    if k == "cover":
        x = W / 2 + 700 * (1 - eo(t / 0.9))
        walking = t < 0.9
        claude(v, x, 1235, 290, t, expr="happy" if 1.6 < t < 2.4 else "normal", walk=t if walking else 0,
               squash=pulse(t, 0.9, 0.3), talk=tl, look=(0.3, -0.3))
        v.text(70, 330, "> RAPPORT DE BUG n°" + ctx["num"], MONO, 44, GREEN)
        a = (t - 0.9) / 0.25
        if a > 0:
            sz = 1.0 + 1.2 * (1 - eo(a))
            lines = m1.wrap(d, sc["title"], font(BOLD, 150), 940)
            layer = Image.new("RGBA", (W * S, int(len(lines) * 160 * S + 40)), (0, 0, 0, 0)); ld = ImageDraw.Draw(layer)
            for i, l in enumerate(lines):
                ld.text((70 * S, i * 160 * S), l, font=font(BOLD, 150 * S), fill=WHITE + (255,))
            if sz != 1.0:
                layer = layer.resize((int(layer.width * sz), int(layer.height * sz)))
            v.paste(layer, 70 * (1 - sz) / 1, 410 - (layer.height / S - len(lines) * 160) / 2 * 0)
            shake = (int(16 * pulse(t, 1.15, 0.3) * math.sin(t * 90)), 0)
    elif k in ("text", "bubbles"):
        label(v, t, sc["label"])
        vis = sc.get("visual") or ("bubbles" if k == "bubbles" else "think")
        if vis == "plate":
            plate(v, 470, 760, 300, eb(t / 0.4))
            if t > 0.3:
                slice3d(v, 470, 720, 190 * eb((t - 0.3) / 0.35))
            for j, (t0, side, y, col) in enumerate(((1.0, -1, 640, SLEEVE_A), (2.0, 1, 700, SLEEVE_B), (3.0, -1, 760, (130, 190, 140)))):
                r = math.sin(math.pi * clamp((t - t0) / 0.9)) if t > t0 else 0
                if r > 0:
                    arm(v, side, r * 0.9, y, col)
            look = (-0.8, 0.2) if int(t) % 2 else (0.3, 0.3)
            claude(v, 900, 1000, 170, t, look=look, talk=tl, expr="?" if t > 3.6 else "normal")
        elif vis == "timer":
            p = eo(t / 2.4); ang = t * 9 if t < 2.4 else 2.4 * 9
            stopwatch(v, 400, 680, 230 * eb(t / 0.4), ang)
            txt = f"{int(47 * p):02d}:{int((47 * p % 1) * 60):02d}"
            v.text(400, 1000, txt, MONO, 110, GREEN if p >= 1 else WHITE, anchor="mm")
            claude(v, 880, 960, 180, t, expr="sleepy" if t > 2.4 else "normal", talk=tl, look=(-0.6, -0.2),
                   squash=0.5 * abs(math.sin(t * 9)) if t < 2.4 else 0)
            if 2.4 < t < 2.7:
                zoom = 1 + 0.05 * pulse(t, 2.4, 0.3)
        elif vis == "bubbles":
            lines = sc.get("lines", []); y = 400
            for i, line in enumerate(lines):
                t0 = 0.5 + i * ctx["gap"]; b = eb((t - t0) / 0.3)
                if b <= 0:
                    continue
                left = i % 2 == 0; f = font(SEMI, 54)
                ls = m1.wrap(d, line, f, 560); bh = len(ls) * 68 + 44
                bw = max(d.textlength(l, font=f) for l in ls) + 64
                x = 150 if left else W - 150 - bw
                bub = Image.new("RGBA", (int((bw + 20) * S), int((bh + 20) * S)), (0, 0, 0, 0)); bd = ImageDraw.Draw(bub)
                bd.rounded_rectangle([0, 0, bw * S, bh * S], radius=34 * S, fill=(PANEL if left else GREEN) + (255,))
                yy = 22 * S
                for l in ls:
                    bd.text((32 * S, yy), l, font=font(SEMI, 54 * S), fill=(WHITE if left else NAVY) + (255,)); yy += 68 * S
                sc_ = 0.5 + 0.5 * b
                bub = bub.resize((max(1, int(bub.width * sc_)), max(1, int(bub.height * sc_))))
                v.paste(bub, x if left else x + bw * (1 - sc_), y + bh * (1 - sc_) / 2)
                av = (SLEEVE_A, SLEEVE_B, (130, 190, 140))[i % 3]
                ax = 95 if left else W - 95
                v.ell(ax, y + 40, 38 * b, 38 * b, fill=av); v.ell(ax, y + 18, 18 * b, 18 * b, fill=SKIN)
                y += bh + 40
            cur = int(clamp((t - 0.5) / ctx["gap"], 0, len(lines) - 1))
            claude(v, 935, 1005, 115, t, look=((-0.9 if cur % 2 == 0 else 0.9), -0.4), talk=tl,
                   expr="?" if t > 0.5 + len(lines) * ctx["gap"] else "normal")
        elif vis == "cut":
            cuts = (0.7, 1.6, 2.5); width = 1.0
            for c in cuts:
                if t > c + 0.12:
                    width *= 0.5
            for c in cuts:
                dt = t - (c + 0.12)
                if 0 <= dt < 0.7:
                    pw = width
                    slice3d(v, 430 - 380 * eo(dt / 0.7), 720 + 200 * dt * dt, 300, pw, int(255 * (1 - dt / 0.7)))
            slice3d(v, 470, 720, 300, width)
            for c in cuts:
                if c - 0.35 < t < c + 0.3:
                    a = -0.9 + 1.0 * eo((t - (c - 0.35)) / 0.35)
                    knife(v, 330, 380, a)
                    shake = (0, int(10 * pulse(t, c + 0.1, 0.2)))
            if t > 3.1:
                g = eb((t - 3.1) / 0.4)
                v.ell(470, 760, 150 * g, 150 * g, outline=WHITE, width=12)
                v.line([(470 + 106 * g, 866 * 1 + 0 * g), (470 + 200 * g, 960)], WOOD, 26)
                v.text(650, 600, "3 mm", MONO, 70, GREEN, anchor="lm")
            claude(v, 900, 1010, 160, t, expr="!" if 0.7 < t < 3.0 else "normal", talk=tl, look=(-0.8, 0))
        elif vis == "think":
            on = eo((t - 1.0) / 0.3) if t > 1.0 else 0
            bulb(v, 760, 450, on)
            claude(v, W / 2, 890, 290, t, expr="happy" if on > 0.5 and t < 1.8 else "normal", look=(0.6, -0.8),
                   talk=tl, squash=pulse(t, 1.0, 0.3))
    elif k == "status":
        a = (t - 0.4) / 0.2
        claude(v, W / 2, 900, 170, t, expr="!" if 0.4 < t < 1.2 else "happy", talk=tl,
               squash=pulse(t, 0.55, 0.3), look=(0, -0.6))
        v.text(70, 330, "> STATUT", MONO, 44, GREEN)
        if a > 0:
            st = stamp_img(m1.wrap(d, sc["status"], font(BOLD, 104), 760))
            sz = 1 + 1.3 * (1 - eo(a))
            st = st.rotate(6, expand=True, resample=Image.BICUBIC)
            st = st.resize((int(st.width * sz), int(st.height * sz)))
            v.paste(st, W / 2 - st.width / S / 2, 560 - st.height / S / 2)
            shake = (int(22 * pulse(t, 0.6, 0.35) * math.sin(t * 80)), int(14 * pulse(t, 0.6, 0.35) * math.cos(t * 70)))
    elif k == "cta":
        b = eb((t - 0.3) / 0.4)
        claude(v, W / 2, 900, 200, t, expr="happy", wave=1.0, talk=tl, squash=0.4 * abs(math.sin(t * 4)) * (t < 1.2))
        if b > 0:
            pw = 700 * b; ph = 110
            v.rr(W / 2 - pw / 2, 420, W / 2 + pw / 2, 420 + ph, 55, fill=GREEN)
            if b > 0.8:
                v.text(W / 2, 475, "Abonnez-vous", BOLD, 62, NAVY, anchor="mm")
            v.text(W / 2, 580, m1.fr(ctx.get("next", "")), REG, 44, MUTED, anchor="mm")
    layer = v.done()
    if zoom != 1.0:
        zw, zh = int(W * zoom), int(LH * zoom)
        layer = layer.resize((zw, zh)).crop(((zw - W) // 2, (zh - LH) // 2, (zw - W) // 2 + W, (zh - LH) // 2 + LH))
    # transition d'entrée : glissé rapide
    dx = int(W * 0.9 * (1 - eo(t / 0.22))) if si > 0 else 0
    im.paste(layer, (shake[0] + dx, OY + shake[1]), layer)
    if k != "cover":
        captions(im, d, t, sc)
    return im


def scene_sounds(snd, si, sc, t0, ctx):
    k = sc["kind"]; vis = sc.get("visual")
    if si > 0:
        snd.whoosh(t0)
    if k == "cover":
        snd.whoosh(t0 + 0.1); snd.stamp(t0 + 1.15); snd.chime(t0 + 1.7)
    elif k in ("text", "bubbles"):
        snd.beep(t0 + 0.05)
        if vis == "plate":
            snd.pop(t0 + 0.05); snd.pop(t0 + 0.35)
            for x in (1.0, 2.0, 3.0):
                snd.whoosh(t0 + x)
        elif vis == "timer":
            for i in range(24):
                snd.tick(t0 + i * 0.1)
            snd.chime(t0 + 2.4)
        elif k == "bubbles":
            for i in range(len(sc.get("lines", []))):
                snd.pop(t0 + 0.5 + i * ctx["gap"])
        elif vis == "cut":
            for c in (0.7, 1.6, 2.5):
                snd.cut(t0 + c + 0.05)
            snd.pop(t0 + 3.1)
        else:
            snd.pop(t0 + 1.0); snd.tone(t0 + 1.0, 600, 1400, 0.25, 0.15)
    elif k == "status":
        snd.stamp(t0 + 0.6)
    elif k == "cta":
        snd.pop(t0 + 0.3); snd.chime(t0 + 0.6)


def natural(sc):
    k = sc["kind"]; vis = sc.get("visual")
    base = {"cover": 3.0, "status": 3.2, "cta": 3.2}.get(k, 2.6)
    base = max(base, {"plate": 4.0, "timer": 3.4, "cut": 4.0}.get(vis, 0), 1.2 + len(sc.get("lines", [])) * 1.0)
    if sc.get("voice") and not sc.get("voice_dur"):
        base = max(base, START + len(sc["voice"]) / 14 + 0.6)
    return base


def envelope(voice, n):
    if not voice:
        return None
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", voice, "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(raw, dtype=np.int16).astype(float) / 32768
    hop = SR // FPS; out = np.zeros(n)
    for i in range(n):
        seg = a[i * hop:(i + 1) * hop]
        out[i] = np.sqrt((seg ** 2).mean()) if len(seg) else 0
    mx = np.percentile(out[out > 0], 95) if (out > 0).any() else 1
    return np.clip(out / max(mx, 1e-6), 0, 1)


def main(spec_path, out, voice=None):
    spec = json.load(open(spec_path)); scenes = spec["scenes"]
    durs = [float(sc.get("duration") or natural(sc)) for sc in scenes]
    frames = [int(round(dd * FPS)) for dd in durs]; total = sum(frames) / FPS
    _d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    for sc in scenes:
        if sc.get("voice") and sc["kind"] != "cover":
            vd = sc.get("voice_dur") or len(sc["voice"]) / 14
            sc["_words"] = word_times(sc["voice"], START, vd)
            sc["_chunks"] = chunks(sc["_words"], _d, font(BOLD, 78))
    env = envelope(voice, sum(frames))
    work = out[:-4] + "_parts"; os.makedirs(work, exist_ok=True)
    snd = m1.Sound(total); parts = []; start = 0.0
    for si, (sc, n) in enumerate(zip(scenes, frames)):
        nl = len(sc.get("lines", []))
        ctx = {"num": spec["num"], "next": spec.get("next", ""), "env": env,
               "gap": max(0.9, ((sc.get("voice_dur") or 3.0) - 0.4) / max(1, nl)) if nl else 1.0}
        part = f"{work}/s{si:02d}.mp4"
        m1.encode(lambda i, si=si, sc=sc, st=start, ctx=ctx: scene_frame(si, sc, i / FPS, st + i / FPS, total, ctx), n, part)
        scene_sounds(snd, si, sc, start, ctx); parts.append(part); start += n / FPS
    lst = f"{work}/list.txt"; open(lst, "w").write("".join(f"file '{os.path.abspath(x)}'\n" for x in parts))
    sfx = f"{work}/sfx.wav"; snd.write(sfx); silent = f"{work}/video.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent], check=True)
    if voice:
        audio = ["-i", sfx, "-i", voice, "-filter_complex",
                 "[1:a]volume=0.30[a1];[2:a]volume=1.0[a2];[a1][a2]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5[a]",
                 "-map", "0:v", "-map", "[a]"]
    else:
        audio = ["-i", sfx, "-map", "0:v", "-map", "1:a"]
    tmp = out[:-4] + ".tmp.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent] + audio +
                   ["-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", tmp], check=True)
    os.replace(tmp, out)
    import shutil; shutil.rmtree(work, ignore_errors=True)
    print(out, f"{total:.1f} s")


def preview(spec_path, shots, outdir):
    """Images clés sans encoder : shots = [(scène, t), ...]."""
    spec = json.load(open(spec_path)); scenes = spec["scenes"]; _d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    for sc in scenes:
        if sc.get("voice") and sc["kind"] != "cover":
            sc["_words"] = word_times(sc["voice"], START, len(sc["voice"]) / 14)
            sc["_chunks"] = chunks(sc["_words"], _d, font(BOLD, 78))
    for si, t in shots:
        sc = scenes[si]; nl = len(sc.get("lines", []))
        ctx = {"num": spec["num"], "next": spec.get("next", ""), "env": None, "gap": 1.1}
        scene_frame(si, sc, t, 10 + t, 60, ctx).save(f"{outdir}/p_{si}_{t}.jpg", quality=85)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
