"""Motion design « Rapport de bug » : vidéo verticale 1080×1920 animée, avec effets sonores.

Usage : python3 outils/motion.py specs/video/004.json 004/004-motion.mp4 [voix.wav]

Spec : {"num": "004", "next": "Rapport suivant : dimanche", "scenes": [...]}
Types de scène :
  cover  : title
  text   : label, text, note (facultatif), visual (facultatif : plate, timer, cut)
  bubbles: label, lines (liste de répliques)
  status : status, text
  cta    : text
Chaque scène peut fixer "duration" (secondes) : utile quand une voix off impose le rythme.
"""
import sys, os, json, math, random, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, FPS, SR = 1080, 1920, 30, 44100
NAVY = (20, 33, 61); PANEL = (27, 43, 77); GREEN = (61, 220, 151); WHITE = (245, 243, 238)
MUTED = (154, 166, 191); RED = (255, 107, 107); YELLOW = (255, 209, 102); CAKE = (242, 193, 78); CRUST = (176, 116, 62)
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
MONO_R = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
BOLD = "/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf"
SEMI = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
REG = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"
X0, XW = 90, 900           # zone de texte
TOP = 430                  # haut du contenu (sous l'en-tête)
CPS = 30                   # vitesse de frappe, caractères par seconde
_F = {}


def font(p, s):
    if (p, s) not in _F:
        _F[(p, s)] = ImageFont.truetype(p, s)
    return _F[(p, s)]


NB = " "


def fr(t):
    for a, b in ((" »", NB + "»"), ("« ", "«" + NB), (" ?", NB + "?"), (" :", NB + ":"), (" !", NB + "!"), (" ;", NB + ";")):
        t = t.replace(a, b)
    return t


def wrap(d, text, f, maxw):
    lines = []
    for para in fr(text).split("\n"):
        cur = ""
        for w in para.split(" "):
            t = (cur + " " + w).strip()
            if d.textlength(t, font=f) <= maxw:
                cur = t
            else:
                lines.append(cur); cur = w
        lines.append(cur)
    return lines


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(x):
    x = clamp(x); return 1 - (1 - x) ** 3


def ease_back(x):
    x = clamp(x); c = 1.7; return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def mix(c1, c2, a):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * a) for i in range(3))


# ---------- icône ----------
_logo = Image.open(os.path.join(HERE, "photo-profil-rapport-de-bug.png")).convert("RGB")
_arr = np.asarray(_logo).astype(int)
_mask = (np.abs(_arr - np.array(NAVY)).sum(axis=2) > 60).astype(np.uint8) * 255
BUG = _logo.copy(); BUG.putalpha(Image.fromarray(_mask))
BUG = BUG.crop((150, 60, 930, 930))


# ---------- sons ----------
class Sound:
    def __init__(self, dur):
        self.buf = np.zeros(int(dur * SR) + SR)
        self.rng = np.random.default_rng(7)

    def add(self, t, sig, gain=1.0):
        i = int(t * SR)
        if i < 0 or i >= len(self.buf):
            return
        n = min(len(sig), len(self.buf) - i)
        self.buf[i:i + n] += sig[:n] * gain

    def env(self, n, a=0.003, r=None):
        e = np.ones(n); na = max(1, int(a * SR)); e[:na] = np.linspace(0, 1, na)
        e *= np.exp(-np.linspace(0, 1, n) * (r or 6))
        return e

    def click(self, t):
        n = int(0.018 * SR); s = self.rng.normal(0, 1, n) * self.env(n, 0.001, 12)
        s = np.convolve(s, np.ones(4) / 4, "same")
        self.add(t, s, 0.10)

    def tone(self, t, f0, f1, dur, gain=0.2, kind="sine"):
        n = int(dur * SR); tt = np.arange(n) / SR
        f = np.linspace(f0, f1, n); ph = 2 * np.pi * np.cumsum(f) / SR
        s = np.sin(ph) if kind == "sine" else np.sign(np.sin(ph)) * 0.5
        self.add(t, s * self.env(n, 0.004, 5), gain)

    def beep(self, t):
        self.tone(t, 1320, 1320, 0.07, 0.12, "square")

    def pop(self, t):
        self.tone(t, 380, 900, 0.09, 0.25)

    def whoosh(self, t):
        n = int(0.28 * SR); s = self.rng.normal(0, 1, n)
        s = np.convolve(s, np.ones(30) / 30, "same") * np.sin(np.linspace(0, np.pi, n))
        self.add(t, s, 0.35)

    def stamp(self, t):
        n = int(0.35 * SR); tt = np.arange(n) / SR
        s = np.sin(2 * np.pi * 70 * tt) * np.exp(-tt * 14) + self.rng.normal(0, 0.4, n) * np.exp(-tt * 40)
        self.add(t, s, 0.6)

    def glitch(self, t):
        n = int(0.12 * SR); s = np.sign(np.sin(2 * np.pi * self.rng.integers(200, 900) * np.arange(n) / SR))
        s *= (self.rng.random(n) > 0.5)
        self.add(t, s * self.env(n, 0.001, 4), 0.08)

    def tick(self, t):
        self.tone(t, 2000, 2000, 0.012, 0.15)

    def cut(self, t):
        n = int(0.16 * SR); s = self.rng.normal(0, 1, n) * np.linspace(1, 0, n)
        s = s - np.convolve(s, np.ones(8) / 8, "same")
        self.add(t, s, 0.5)

    def chime(self, t):
        self.tone(t, 880, 880, 0.18, 0.15); self.tone(t + 0.12, 1318, 1318, 0.3, 0.15)

    def write(self, path):
        b = self.buf / max(1e-6, np.abs(self.buf).max()) * 0.8
        pcm = (b * 32767).astype(np.int16)
        with wave.open(path, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())


# ---------- texte animé ----------
class Typed:
    """Bloc de texte tapé à la machine, mise en page fixe."""

    def __init__(self, d, text, f, color, x, y, maxw=XW, lh=1.25, cps=CPS):
        self.lines = wrap(d, text, f, maxw); self.f = f; self.color = color
        self.x, self.y, self.lh, self.cps = x, y, int(f.size * lh), cps
        self.n = sum(len(l) for l in self.lines)
        self.dur = self.n / cps
        self.bottom = y + len(self.lines) * self.lh

    def draw(self, d, t, caret=True):
        k = int(clamp(t * self.cps, 0, self.n)) if t >= 0 else 0
        if t < 0:
            return
        y = self.y; last = (self.x, self.y)
        for l in self.lines:
            s = l[:k]; k -= len(s)
            if s:
                d.text((self.x, y), s, font=self.f, fill=self.color)
                last = (self.x + d.textlength(s, font=self.f), y)
            if k <= 0 and len(s) < len(l):
                break
            y += self.lh
        if caret and (t * self.cps < self.n or int(t * 2.5) % 2 == 0):
            d.rectangle([last[0] + 6, last[1] + 6, last[0] + 6 + self.f.size * 0.45, last[1] + self.f.size * 1.05], fill=GREEN)

    def sounds(self, snd, t0):
        for i in range(0, self.n, 2):
            snd.click(t0 + i / self.cps)


# ---------- scènes ----------
_meas = ImageDraw.Draw(Image.new("RGB", (10, 10)))


def plan(scene):
    """Calcule la mise en page et la durée naturelle d'une scène."""
    k = scene["kind"]; p = {}
    if k == "cover":
        p["kicker"] = Typed(_meas, "> RAPPORT DE BUG n°" + SPEC["num"], font(MONO, 46), GREEN, X0, TOP + 20, cps=40)
        size = 190
        while size > 110 and len(wrap(_meas, scene["title"], font(BOLD, size), XW)) > 2:
            size -= 10
        p["size"] = size; p["title"] = wrap(_meas, scene["title"], font(BOLD, size), XW)
        dur = 4.2
    elif k in ("text", "bubbles"):
        p["label"] = Typed(_meas, "> " + scene["label"], font(MONO, 46), GREEN, X0, TOP, cps=45)
        y = TOP + 100; dur = 0.6
        if k == "text":
            p["body"] = Typed(_meas, scene["text"], font(SEMI, 80), WHITE, X0, y)
            y = p["body"].bottom; dur += p["body"].dur
            if scene.get("note"):
                p["note"] = wrap(_meas, scene["note"], font(REG, 50), XW); p["note_y"] = y + 40
                p["note_t"] = dur + 0.3; y = p["note_y"] + len(p["note"]) * 64; dur += 0.7 + len(scene["note"]) / 40
            p["vis_t"] = min(dur, 1.0 + p["body"].dur)
            dur += {"plate": 1.6, "timer": 2.8, "cut": 3.4}.get(scene.get("visual"), 0)
            dur += 0.7 + len(scene["text"]) / 70
        else:
            p["lines"] = [fr(l) for l in scene["lines"]]
            dur = 0.8 + len(p["lines"]) * 1.1 + 1.2
    elif k == "status":
        p["label"] = Typed(_meas, "> STATUT", font(MONO, 46), GREEN, X0, TOP + 60, cps=45)
        sf = font(BOLD, 100); p["st"] = wrap(_meas, scene["status"], sf, XW - 100)
        p["bh"] = len(p["st"]) * 120 + 80
        p["body"] = Typed(_meas, scene["text"], font(SEMI, 60), WHITE, X0, TOP + 200 + p["bh"] + 70)
        dur = 1.6 + p["body"].dur + 1.5
    elif k == "cta":
        p["label"] = Typed(_meas, "> ACTION REQUISE", font(MONO, 46), GREEN, X0, TOP + 60, cps=45)
        p["body"] = Typed(_meas, scene["text"], font(BOLD, 90), WHITE, X0, TOP + 170, lh=1.15)
        dur = 0.6 + p["body"].dur + 2.6
    p["dur"] = float(scene.get("duration", dur))
    return p


def chrome(d, gt, total):
    """En-tête permanent : fenêtre terminal, compte, barre de progression."""
    d.rounded_rectangle([60, 150, W - 60, 236], radius=20, fill=PANEL)
    for i, c in enumerate([RED, YELLOW, GREEN]):
        d.ellipse([94 + i * 38, 181, 120 + i * 38, 207], fill=c)
    d.text((228, 174), f"rapport_{SPEC['num']}.log", font=font(MONO_R, 32), fill=MUTED)
    tag = "@rapportdebug"; f = font(SEMI, 34)
    d.text((W - 96 - d.textlength(tag, font=f), 172), tag, font=f, fill=WHITE)
    d.rounded_rectangle([60, 254, W - 60, 262], radius=4, fill=PANEL)
    d.rounded_rectangle([60, 254, 60 + (W - 120) * clamp(gt / total), 262], radius=4, fill=GREEN)
    f = font(MONO_R, 26); s = "contenu IA"
    d.text((W - 60 - d.textlength(s, font=f), 276), s, font=f, fill=MUTED)


def background(t):
    im = Image.new("RGB", (W, H), NAVY); d = ImageDraw.Draw(im)
    off = (t * 12) % 60
    for y in range(-60, H + 60, 60):
        for x in range(30, W, 60):
            d.point((x, int(y + off)), fill=(40, 56, 90))
    return im, d


def wedge(d, cx, cy, r, a0, a1, alpha=1.0):
    col = mix(NAVY, CAKE, alpha); crust = mix(NAVY, CRUST, alpha)
    d.pieslice([cx - r, cy - r, cx + r, cy + r], a0, a1, fill=col, outline=crust, width=max(2, int(r * 0.06)))


def visual(im, d, kind, t, s, snd=None):
    if t < 0:
        return
    cx, cy = W // 2, 1180
    if kind == "plate":
        a = ease_back(t / 0.5); r = int(270 * a)
        if r > 4:
            d.ellipse([cx - r, cy - r * 0.55, cx + r, cy + r * 0.55], outline=WHITE, width=6)
            d.ellipse([cx - r * 0.75, cy - r * 0.4, cx + r * 0.75, cy + r * 0.4], outline=MUTED, width=3)
        b = ease_back((t - 0.4) / 0.4)
        if b > 0:
            wedge(d, cx, cy + 50, int(160 * b), -118, -62)
        if t > 1.0:
            pr = 170 + 12 * math.sin(t * 6)
            for i in range(0, 360, 20):
                d.arc([cx - pr, cy - 60 - pr * 0.7, cx + pr, cy - 60 + pr * 0.7], i, i + 10, fill=GREEN, width=5)
    elif kind == "timer":
        p = ease_out(t / 2.2); v = 47 * p
        txt = f"{int(v):02d}:{int((v % 1) * 60):02d}"
        f = font(MONO, 210); w = d.textlength(txt, font=f)
        d.text((cx - w / 2, cy - 130), txt, font=f, fill=GREEN if p >= 1 else WHITE)
        f2 = font(REG, 44); lab = "minutes (estimation)"
        d.text((cx - d.textlength(lab, font=f2) / 2, cy + 120), lab, font=f2, fill=MUTED)
    elif kind == "cut":
        base = cy + 220; R = 340
        ang = 60.0; x_off = 0.0; scale = 1.0
        phases = [(0.7, 30.0), (1.5, 15.0), (2.3, 7.5)]
        for t0, newa in phases:
            if t > t0 + 0.25:
                ang = newa
        # morceau qui s'éloigne après chaque coupe
        for t0, newa in phases:
            dt = t - (t0 + 0.25)
            if 0 <= dt < 0.6:
                wedge(d, int(cx - 260 * ease_out(dt / 0.6)), base, R, -90 - newa * 2 + newa, -90, 1 - dt / 0.6)
            if t0 <= t < t0 + 0.25:
                k = (t - t0) / 0.25; yy = base - R * 1.05 + 40
                d.line([cx, yy - 40, cx, yy - 40 + (R + 40) * k], fill=GREEN, width=6)
        scale = 1.0 - 0.75 * ease_out((t - 2.7) / 0.6)
        wedge(d, cx, base, int(R * scale), -90, -90 + ang)
        if t > 3.0:
            f = font(MONO, 56); lab = "3 mm"
            d.text((cx + 80, base - R * scale - 40), lab, font=f, fill=GREEN)


def render_scene(si, scene, p, t, gt, total):
    im, d = background(gt)
    chrome(d, gt, total)
    k = scene["kind"]
    if k == "cover":
        p["kicker"].draw(d, t - 0.15, caret=t < 1.2)
        a = ease_out((t - 0.9) / 0.4)
        if a > 0:
            d.text((X0, TOP + 100 - 20 * (1 - a)), "Objet" + NB + ":", font=font(REG, 60), fill=mix(NAVY, MUTED, a))
        f = font(BOLD, p["size"])
        for i, line in enumerate(p["title"]):
            b = ease_back((t - 1.2 - i * 0.18) / 0.35)
            if b > 0:
                layer = Image.new("RGBA", (W, p["size"] + 60), (0, 0, 0, 0))
                ImageDraw.Draw(layer).text((X0, 10), line, font=f, fill=WHITE + (255,))
                sc = 0.7 + 0.3 * b
                lw, lh = int(W * sc), int(layer.height * sc)
                layer = layer.resize((max(1, lw), max(1, lh)))
                im.paste(layer, (int(X0 * (1 - sc)), TOP + 190 + i * int(p["size"] * 1.0)), layer)
        c = ease_back((t - 1.9) / 0.5)
        if c > 0:
            sz = int(400 * c); bug = BUG.resize((sz, int(sz * 1.115))).rotate(6 * math.sin(t * 5), expand=False)
            im.paste(bug, (W // 2 - sz // 2, 1470 - bug.height), bug)
    elif k in ("text", "bubbles"):
        p["label"].draw(d, t, caret=False)
        if k == "text":
            p["body"].draw(d, t - 0.6, caret=t < p.get("note_t", 99))
            if "note" in p:
                a = ease_out((t - p["note_t"]) / 0.5)
                if a > 0:
                    y = p["note_y"] + 20 * (1 - a)
                    for l in p["note"]:
                        d.text((X0, y), l, font=font(REG, 50), fill=mix(NAVY, MUTED, a)); y += 64
            if scene.get("visual"):
                visual(im, d, scene["visual"], t - p["vis_t"], scene)
        else:
            y = TOP + 140; f = font(SEMI, 56)
            for i, line in enumerate(p["lines"]):
                b = ease_back((t - 0.8 - i * 1.1) / 0.3)
                ls = wrap(d, line, f, 640); h = len(ls) * 72 + 50
                if b > 0:
                    w = max(d.textlength(l, font=f) for l in ls) + 70
                    left = i % 2 == 0
                    x = X0 if left else W - X0 - w
                    layer = Image.new("RGBA", (int(w) + 4, h + 4), (0, 0, 0, 0)); ld = ImageDraw.Draw(layer)
                    ld.rounded_rectangle([0, 0, w, h], radius=36, fill=(PANEL if left else GREEN) + (255,))
                    yy = 22
                    for l in ls:
                        ld.text((35, yy), l, font=f, fill=(WHITE if left else NAVY) + (255,)); yy += 72
                    sc = 0.6 + 0.4 * b
                    layer = layer.resize((max(1, int(layer.width * sc)), max(1, int(layer.height * sc))))
                    im.paste(layer, (int(x if left else x + w * (1 - sc)), int(y + h * (1 - sc) / 2)), layer)
                y += h + 50
    elif k == "status":
        p["label"].draw(d, t, caret=False)
        b = (t - 0.6) / 0.22
        if b > 0:
            sc = 1.0 + 0.8 * (1 - ease_out(b))
            bw, bh = XW, p["bh"]
            layer = Image.new("RGBA", (bw + 20, bh + 20), (0, 0, 0, 0)); ld = ImageDraw.Draw(layer)
            ld.rounded_rectangle([6, 6, bw + 6, bh + 6], radius=28, outline=GREEN + (255,), width=10)
            yy = 46
            for l in p["st"]:
                ld.text((52, yy), l, font=font(BOLD, 100), fill=GREEN + (255,)); yy += 120
            layer = layer.rotate(-4, expand=True, resample=Image.BICUBIC)
            layer = layer.resize((int(layer.width * sc), int(layer.height * sc)))
            cxs, cys = W // 2, TOP + 200 + bh // 2
            im.paste(layer, (cxs - layer.width // 2, cys - layer.height // 2), layer)
        p["body"].draw(d, t - 1.4)
    elif k == "cta":
        p["label"].draw(d, t, caret=False)
        p["body"].draw(d, t - 0.6)
        a = ease_out((t - 0.8 - p["body"].dur) / 0.5)
        if a > 0:
            d.text((X0, 1150 + 20 * (1 - a)), fr(SPEC.get("next", "")), font=font(REG, 48), fill=mix(NAVY, MUTED, a))
            d.text((X0, 1230 + 20 * (1 - a)), "Abonnez-vous pour le prochain rapport", font=font(SEMI, 48), fill=mix(NAVY, GREEN, a))
            sz = int(220 * ease_back((t - 1.0 - p["body"].dur) / 0.5))
            if sz > 4:
                bug = BUG.resize((sz, int(sz * 1.115))).rotate(8 * math.sin(t * 6))
                im.paste(bug, (W - 90 - sz, 1000 - bug.height // 2), bug)
    # glitch d'entrée de scène
    if t < 0.15 and si > 0:
        rng = random.Random(si * 1000 + int(t * FPS))
        arr = np.asarray(im).copy()
        for _ in range(9):
            y = rng.randrange(0, H - 80); hgt = rng.randrange(10, 80); sh = rng.randrange(-60, 60)
            arr[y:y + hgt] = np.roll(arr[y:y + hgt], sh, axis=1)
        arr[:, :, 0] = np.roll(arr[:, :, 0], 8, axis=1)
        im = Image.fromarray(arr)
    return im


def scene_sounds(snd, si, scene, p, t0):
    k = scene["kind"]
    if si > 0:
        snd.glitch(t0); snd.whoosh(t0)
    if k == "cover":
        p["kicker"].sounds(snd, t0 + 0.15); snd.beep(t0 + 0.9)
        for i in range(len(p["title"])):
            snd.pop(t0 + 1.2 + i * 0.18)
        snd.pop(t0 + 1.9); snd.chime(t0 + 2.2)
    elif k in ("text", "bubbles"):
        snd.beep(t0 + 0.05)
        if k == "text":
            p["body"].sounds(snd, t0 + 0.6)
            v = scene.get("visual"); tv = t0 + p["vis_t"]
            if v == "plate":
                snd.pop(tv); snd.pop(tv + 0.4)
            elif v == "timer":
                for i in range(22):
                    snd.tick(tv + 2.2 * (1 - (1 - i / 22) ** (1 / 3)))
                snd.beep(tv + 2.2)
            elif v == "cut":
                for c in (0.7, 1.5, 2.3):
                    snd.cut(tv + c)
                snd.beep(tv + 3.0)
        else:
            for i in range(len(p["lines"])):
                snd.pop(t0 + 0.8 + i * 1.1)
    elif k == "status":
        snd.stamp(t0 + 0.6); p["body"].sounds(snd, t0 + 1.4)
    elif k == "cta":
        p["body"].sounds(snd, t0 + 0.6); snd.chime(t0 + 0.8 + p["body"].dur)


def encode(frames_fn, n, path):
    tmp = path[:-4] + ".tmp.mp4"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-c:v", "libx264", "-crf", "20", "-preset", "veryfast", "-pix_fmt", "yuv420p", tmp]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        pr.stdin.write(frames_fn(i).tobytes())
    pr.stdin.close()
    if pr.wait() != 0:
        raise SystemExit("ffmpeg a échoué")
    os.replace(tmp, path)


def main(spec_path, out, voice=None, only_frames=None):
    global SPEC
    SPEC = json.load(open(spec_path))
    plans = [plan(s) for s in SPEC["scenes"]]
    total = sum(p["dur"] for p in plans)
    work = out[:-4] + "_parts"; os.makedirs(work, exist_ok=True)
    if only_frames:   # aperçu : quelques images clés
        for si, t in only_frames:
            gt = sum(p["dur"] for p in plans[:si]) + t
            render_scene(si, SPEC["scenes"][si], plans[si], t, gt, total).save(f"{work}/frame_{si}_{t:.1f}.jpg", quality=88)
        return
    snd = Sound(total); start = 0.0; parts = []
    for si, (s, p) in enumerate(zip(SPEC["scenes"], plans)):
        n = int(round(p["dur"] * FPS))
        part = f"{work}/scene{si:02d}.mp4"
        encode(lambda i, si=si, s=s, p=p, st=start: render_scene(si, s, p, i / FPS, st + i / FPS, total), n, part)
        scene_sounds(snd, si, s, p, start)
        parts.append(part); start += n / FPS
    lst = f"{work}/list.txt"
    open(lst, "w").write("".join(f"file '{os.path.abspath(x)}'\n" for x in parts))
    sfx = f"{work}/sfx.wav"; snd.write(sfx)
    silent = f"{work}/video.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent], check=True)
    if voice:
        audio = ["-i", sfx, "-i", voice, "-filter_complex", "[1:a]volume=0.35[a1];[2:a]volume=1.0[a2];[a1][a2]amix=inputs=2:duration=first[a]", "-map", "0:v", "-map", "[a]"]
    else:
        audio = ["-i", sfx, "-map", "0:v", "-map", "1:a"]
    tmp = out[:-4] + ".tmp.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent] + audio +
                   ["-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", tmp], check=True)
    os.replace(tmp, out)
    print(out, f"{total:.1f} s")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
