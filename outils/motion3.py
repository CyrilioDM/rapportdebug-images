"""Vidéo v3 « Rapport de bug » : typographie animée, rythme court (25-30 s), voix off de Claude.

Usage : python3 outils/motion3.py specs/video/NNN.json NNN/NNN-video.mp4 [--secours]

Spec : {"num": "004", "engine": "v3", "next": "Rapport suivant : dimanche",
        "beats": [{"say": "Il reste un *morceau*.", "label": "OBSERVATION"}, ...,
                  {"say": "Bug confirmé.", "kind": "stamp"},
                  {"say": "Et vous, vous le prenez ?", "kind": "cta"}]}
- say   : la phrase dite ; elle s'affiche en gros, un à trois mots à la fois, calée sur la voix.
- *mot* : mot clé, affiché en vert sur fond inversé.
- label : petite étiquette terminal en haut (facultatif, reste affichée jusqu'au label suivant).
- kind  : "stamp" (tampon final secoué) ou "cta" (appel à s'abonner). Par défaut : texte.
Règles d'écriture : 8 à 11 phrases courtes, la première est l'accroche, total 25-30 s.
"""
import sys, os, json, math, subprocess, tempfile, shutil, wave
import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import motion as m1
import voix

W, H, FPS, SR = 1080, 1920, 30, 44100
NAVY = (20, 33, 61); NAVY2 = (12, 20, 40); PANEL = (27, 43, 77); GREEN = (61, 220, 151); WHITE = (245, 243, 238)
MUTED = (154, 166, 191); RED = (255, 107, 107); YELLOW = (255, 209, 102)
font = m1.font; BOLD, SEMI, REG, MONO, MONO_R = m1.BOLD, m1.SEMI, m1.REG, m1.MONO, m1.MONO_R
CY = 840            # centre vertical du texte (au-dessus de la zone masquée par TikTok/Reels)
GAP = 0.06          # silence entre deux phrases
LEAD = 0.04         # la voix démarre juste après la coupe


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def eo(x):
    x = clamp(x); return 1 - (1 - x) ** 3


def eb(x):
    x = clamp(x); c = 2.2; return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


# ---------- découpage en blocs de 1 à 3 mots ----------
WEAK = {"un", "une", "le", "la", "les", "l'", "de", "du", "des", "d'", "ne", "n'", "en", "et", "à", "a", "au", "aux",
        "ce", "c'est", "n'est", "il", "ils", "elle", "on", "qui", "que", "qu'", "pas", "se", "sa", "son", "ses", "vous", "nous",
        "mon", "ma", "mes", "est", "par", "pour", "sur", "dans", "plus"}


def tokens(say):
    """Mots, en recollant la ponctuation isolée (« ? : ! ; ») au mot voisin."""
    out = []
    for w in say.split():
        if out and (all(ch in "?!:;»" for ch in w)):
            out[-1] += "\u00a0" + w
        elif out and out[-1] in ("«",):
            out[-1] += "\u00a0" + w
        else:
            out.append(w)
    return out


def blocks(say):
    words = tokens(say); out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        plain = " ".join(x.replace("*", "") for x in cur)
        last = w.replace("*", "").lower()
        end = last.rstrip("»\u00a0 ")[-1:] in ".?!,:"
        weak = last in WEAK and i < len(words) - 1
        if end or ((len(cur) >= 3 or len(plain) >= 13) and not weak):
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    return out


def timings(blks, dur):
    """Début de chaque bloc dans la phrase, au prorata du nombre de caractères (+ pauses de ponctuation)."""
    wts = []
    for b in blks:
        k = sum(len(w.replace("*", "")) + 1 for w in b)
        if b[-1][-1:] in ".?!»":
            k += 5
        elif b[-1][-1:] in ",:":
            k += 3
        wts.append(k)
    tot = sum(wts); t = 0.0; out = []
    for k in wts:
        out.append(t); t += dur * k / tot
    return out


# ---------- rendu ----------
_bg = None


def background(gt):
    global _bg
    if _bg is None:
        g = np.linspace(0, 1, H + 60)[:, None]
        arr = (np.array(NAVY) * (1 - g) + np.array(NAVY2) * g)[:, None, :].repeat(W, axis=1).astype(np.uint8)
        _bg = Image.fromarray(arr); d = ImageDraw.Draw(_bg)
        for y in range(0, H + 60, 60):
            for x in range(30, W, 60):
                d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=(40, 56, 92))
    off = int((gt * 30) % 60)
    return _bg.crop((0, off, W, off + H)).copy()


def chrome(d, gt, total, num, label, inv=False):
    G = NAVY if inv else GREEN; Wt = NAVY if inv else WHITE; M = NAVY if inv else MUTED
    f = font(MONO, 34)
    d.text((70, 150), f"> RAPPORT DE BUG n°{num}", font=f, fill=G)
    tag = "@rapportdebug"; f2 = font(SEMI, 32)
    d.text((W - 70 - d.textlength(tag, font=f2), 151), tag, font=f2, fill=Wt)
    d.rounded_rectangle([70, 206, W - 70, 212], radius=3, fill=(48, 180, 124) if inv else PANEL)
    d.rounded_rectangle([70, 206, 70 + (W - 140) * clamp(gt / total), 212], radius=3, fill=G)
    f3 = font(MONO_R, 24); s = "contenu IA"
    d.text((W - 70 - d.textlength(s, font=f3), 224), s, font=f3, fill=M)
    if label:
        f4 = font(MONO, 40); tx = "> " + label
        d.text((70, 330), tx, font=f4, fill=G)


def fit_lines(d, text, maxw=940, maxsize=250, minsize=120):
    size = maxsize
    while size > minsize:
        lines = m1.wrap(d, text, font(BOLD, size), maxw)
        if len(lines) <= 2 and all(d.textlength(l, font=font(BOLD, size)) <= maxw for l in lines):
            return size, lines
        size -= 10
    return size, m1.wrap(d, text, font(BOLD, size), maxw)


def word_layer(d, blk, key, inv=True):
    text = m1.fr(" ".join(w.replace("*", "") for w in blk)).upper()
    size, lines = fit_lines(d, text)
    f = font(BOLD, size); lh = int(size * 1.02)
    w = int(max(d.textlength(l, font=f) for l in lines)) + 60; h = lh * len(lines) + 60
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); ld = ImageDraw.Draw(im)
    for i, l in enumerate(lines):
        lw = ld.textlength(l, font=f)
        ld.text(((w - lw) / 2, 20 + i * lh), l, font=f, fill=((NAVY if inv else GREEN) if key else WHITE) + (255,))
    return im


ANIMS = ("pop", "up", "left", "tilt", "drop")

EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
_emo = {}


def emoji_img(ch, size):
    """Émoji couleur (Noto Color Emoji, licence OFL), rogné et mis à l'échelle."""
    if (ch, size) not in _emo:
        from PIL import ImageFont
        f = ImageFont.truetype(EMOJI_FONT, 109)
        im = Image.new("RGBA", (220 * max(1, len(ch)), 160), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((10, 10), ch, font=f, embedded_color=True)
        im = im.crop(im.getbbox())
        r = size / max(im.width, im.height)
        _emo[(ch, size)] = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)
    return _emo[(ch, size)]


def draw_emoji(frame, ch, fx, t, cx, cy, size=230):
    """fx : bounce (défaut), chop (s'abat en boucle), blink (clignote), point (montre le bas)."""
    k = eb(t / 0.35)
    if k <= 0:
        return
    sc, ang, dx, dy = k, 7 * math.sin(t * 5), 0, 10 * math.sin(t * 4)
    if fx == "chop":
        ph = (t * 2.2) % 1.0; ang = 35 - 70 * eo(min(1, ph / 0.25)) if ph < 0.25 else -35 + 70 * eo((ph - 0.25) / 0.75)
    elif fx == "blink":
        sc = k * (1.0 + 0.12 * (math.sin(t * 18) > 0)); ang = 0
    elif fx == "point":
        dy = 22 * abs(math.sin(t * 6)); ang = 0
    elif fx == "spin":
        ang = (t * 240) % 360
    im = emoji_img(ch, size)
    if ang:
        im = im.rotate(ang, expand=True, resample=Image.BICUBIC)
    if sc != 1.0:
        im = im.resize((max(1, int(im.width * sc)), max(1, int(im.height * sc))))
    frame.paste(im, (int(cx - im.width / 2 + dx), int(cy - im.height / 2 + dy)), im)


def place(frame, layer, anim, k, shake=(0, 0)):
    """k = progression de l'entrée (0 → 1)."""
    sc, dx, dy, ang = 1.0, 0, 0, 0.0
    if anim == "pop":
        sc = 1.35 - 0.35 * eb(k)
    elif anim == "up":
        dy = 90 * (1 - eo(k))
    elif anim == "left":
        dx = -220 * (1 - eo(k))
    elif anim == "tilt":
        ang = 8 * (1 - eo(k)); sc = 1.1 - 0.1 * eo(k)
    elif anim == "drop":
        dy = -140 * (1 - eb(k))
    L = layer
    if ang:
        L = L.rotate(ang, expand=True, resample=Image.BICUBIC)
    if sc != 1.0:
        L = L.resize((max(1, int(L.width * sc)), max(1, int(L.height * sc))))
    x = int(W / 2 - L.width / 2 + dx + shake[0]); y = int(CY - L.height / 2 + dy + shake[1])
    frame.paste(L, (x, y), L)


def stamp_layer(text):
    f = font(BOLD, 150); d = ImageDraw.Draw(Image.new("L", (1, 1)))
    lines = m1.wrap(d, text.upper(), f, 820)
    tw = max(d.textlength(l, font=f) for l in lines)
    w, h = int(tw + 120), int(len(lines) * 160 + 90)
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0)); ld = ImageDraw.Draw(im)
    ld.rounded_rectangle([8, 8, w - 8, h - 8], radius=34, outline=GREEN, width=16, fill=NAVY + (235,))
    y = 40
    for l in lines:
        ld.text(((w - ld.textlength(l, font=f)) / 2, y), l, font=f, fill=GREEN); y += 160
    return im.rotate(7, expand=True, resample=Image.BICUBIC)


def render(spec, out, voice_engine):
    beats = spec["beats"]; d0 = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    work = tempfile.mkdtemp(prefix="v3_")
    # 1. voix phrase par phrase
    clips = []
    for i, b in enumerate(beats):
        if voice_engine:
            wav = os.path.join(work, f"b{i:02d}.wav"); voix.say(voice_engine, b["say"], wav)
            c = voix.load(wav)
            nz = np.nonzero(np.abs(c) > 0.01)[0]          # retire les silences de début et de fin
            c = c[max(0, nz[0] - 400): nz[-1] + 1500] if len(nz) else c
        else:
            c = np.zeros(int(len(b["say"]) / 15 * SR))
        clips.append(c)
    durs = []
    for b, c in zip(beats, clips):
        dd = LEAD + len(c) / SR + GAP
        if b.get("kind") == "stamp":
            dd = max(dd, 1.6)
        if b.get("kind") == "cta":
            dd = max(dd + 1.4, 3.0)
        durs.append(dd)
    frames = [int(round(dd * FPS)) for dd in durs]; total = sum(frames) / FPS
    # piste voix
    track = np.zeros(int((total + 1) * SR)); t0 = 0.0
    for c, n in zip(clips, frames):
        i = int((t0 + LEAD) * SR); track[i:i + len(c)] += c[:len(track) - i]; t0 += n / FPS
    if np.abs(track).max() > 0:
        track = track / np.abs(track).max() * 0.9
    vwav = os.path.join(work, "voix.wav")
    with wave.open(vwav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((track * 32767).astype(np.int16).tobytes())
    # 2. images
    snd = m1.Sound(total); parts = []; start = 0.0; label = ""; anim_i = 0
    for bi, (b, n, c) in enumerate(zip(beats, frames, clips)):
        label = b.get("label", label)
        kind = b.get("kind", "text")
        blks = blocks(b["say"]); st = timings(blks, len(c) / SR)
        layers = [word_layer(d0, blk, any(w.startswith("*") for w in blk), kind == "text") for blk in blks]
        keys = [any(w.startswith("*") for w in blk) for blk in blks]
        anims = []
        for _ in blks:
            anims.append(ANIMS[anim_i % len(ANIMS)]); anim_i += 1
        stamp = stamp_layer(b["say"].replace("*", "").rstrip(".!")) if kind == "stamp" else None

        def frame(i, b=b, blks=blks, st=st, layers=layers, keys=keys, anims=anims, stamp=stamp, kind=kind,
                  label=label, start=start, n=n):
            t = i / FPS; gt = start + t
            im = background(gt)
            j = max([k for k, s in enumerate(st) if t >= LEAD + s - 0.02] or [0])
            inv = kind == "text" and keys[j]
            if inv:                                  # mot clé : fond inversé
                im.paste(GREEN, (0, 0, W, H))
            d = ImageDraw.Draw(im)
            chrome(d, gt, total, spec["num"], label, inv)
            if kind == "stamp":
                a = t / 0.22
                sc = 1 + 1.4 * (1 - eo(a)) if a > 0 else 2.4
                sh = (int(26 * math.sin(t * 85) * max(0, 1 - (t - 0.2) / 0.4)), int(16 * math.cos(t * 70) * max(0, 1 - (t - 0.2) / 0.4)))
                L = stamp.resize((int(stamp.width * sc), int(stamp.height * sc)))
                im.paste(L, (W // 2 - L.width // 2 + sh[0], CY - L.height // 2 + sh[1]), L)
            elif kind == "cta":
                k = (t - LEAD - st[j]) / 0.18
                place(im, layers[j], anims[j], k)
                if t > len(c) / SR + LEAD:
                    a = eb((t - len(c) / SR - LEAD) / 0.35)
                    pw = 760 * a
                    d.rounded_rectangle([W / 2 - pw / 2, 1120, W / 2 + pw / 2, 1240], radius=60, fill=GREEN)
                    if a > 0.85:
                        f = font(BOLD, 66); s = "ABONNEZ-VOUS"
                        d.text((W / 2 - d.textlength(s, font=f) / 2, 1145), s, font=f, fill=NAVY)
                        f2 = font(REG, 44); s2 = m1.fr(spec.get("next", ""))
                        d.text((W / 2 - d.textlength(s2, font=f2) / 2, 1270), s2, font=f2, fill=MUTED)
            else:
                k = (t - LEAD - st[j]) / 0.16
                place(im, layers[j], anims[j], k)
            if b.get("emoji"):
                fx = b.get("fx", "bounce")
                if kind == "stamp":
                    for ex in (210, W - 210):
                        draw_emoji(im, b["emoji"], "blink", t - 0.3, ex, CY + 330, 170)
                elif kind == "cta":
                    if t > len(c) / SR + LEAD:
                        for ex, ch in ((90, "👉"), (W - 90, "👈")):
                            draw_emoji(im, ch, "point", t - len(c) / SR - LEAD, ex, 1180, 100)
                else:
                    draw_emoji(im, b["emoji"], fx, t, W / 2, 1250, 230)
            return im

        part = os.path.join(work, f"p{bi:02d}.mp4")
        m1.encode(frame, n, part); parts.append(part)
        for s_, key in zip(st, keys):
            (snd.pop if key else snd.tick)(start + LEAD + s_)
        if bi > 0:
            snd.whoosh(start)
        if b.get("emoji") and kind == "text":
            snd.pop(start + 0.05)
        if kind == "stamp":
            snd.stamp(start + 0.2)
        if kind == "cta":
            snd.chime(start + LEAD + len(c) / SR)
        start += n / FPS
    # 3. assemblage
    lst = os.path.join(work, "list.txt"); open(lst, "w").write("".join(f"file '{p}'\n" for p in parts))
    sfx = os.path.join(work, "sfx.wav"); snd.write(sfx); silent = os.path.join(work, "v.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent], check=True)
    tmp = out[:-4] + ".tmp.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", sfx, "-i", vwav, "-filter_complex",
                    "[1:a]volume=0.25[a1];[2:a]volume=1.0[a2];[a1][a2]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-14:TP=-1.5[a]",
                    "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest",
                    "-movflags", "+faststart", tmp], check=True)
    os.replace(tmp, out)
    shutil.rmtree(work, ignore_errors=True)
    print(out, f"{total:.1f} s")


def main(spec_path, out, fallback=False, no_voice=False):
    spec = json.load(open(spec_path))
    os.environ.setdefault("RDB_VITESSE", "0.85")
    voix.SPEED = float(os.environ["RDB_VITESSE"])
    eng = None if no_voice else voix.setup(fallback)
    render(spec, out, eng)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0], args[1], fallback="--secours" in sys.argv, no_voice="--sans-voix" in sys.argv)
