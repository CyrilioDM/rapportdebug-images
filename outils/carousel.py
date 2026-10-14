import sys, json, os
HERE = os.path.dirname(os.path.abspath(__file__))
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
NAVY = "#14213D"; PANEL = "#1B2B4D"; GREEN = "#3DDC97"; WHITE = "#F5F3EE"; MUTED = "#9AA6BF"; RED = "#FF6B6B"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
MONO_R = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
BOLD = "/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf"
SEMI = "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf"
REG = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"
LOGO = Image.open(os.path.join(HERE, "photo-profil-rapport-de-bug.png")).convert("RGB").resize((64, 64), Image.LANCZOS)

_b = Image.open(os.path.join(HERE, "photo-profil-rapport-de-bug.png")).convert("RGB").crop((150,60,930,930)).resize((470,524), Image.LANCZOS)
BIG = _b
BIGMASK = _b.convert("L").point(lambda v: 60 if v > 120 else 0)
def f(p, s): return ImageFont.truetype(p, s)

NB = "\u00a0"
def fr(t):
    for a, b in ((" »", NB+"»"), ("« ", "«"+NB), (" ?", NB+"?"), (" :", NB+":"), (" !", NB+"!"), (" ;", NB+";")):
        t = t.replace(a, b)
    return t

def wrap(d, text, font, maxw):
    text = fr(text)
    lines = []
    for para in text.split("\n"):
        words, cur = para.split(" "), ""
        for w in words:
            t = (cur + " " + w).strip()
            if d.textlength(t, font=font) <= maxw: cur = t
            else: lines.append(cur); cur = w
        lines.append(cur)
    return lines

def block(d, text, font, x, y, maxw, fill, lh=1.25):
    for line in wrap(d, text, font, maxw):
        d.text((x, y), line, font=font, fill=fill)
        y += int(font.size * lh)
    return y

def frame(n, total, num):
    im = Image.new("RGB", (W, H), NAVY); d = ImageDraw.Draw(im)
    # terminal header bar
    d.rounded_rectangle([60, 60, W - 60, 140], radius=18, fill=PANEL)
    for i, c in enumerate([RED, "#FFD166", GREEN]):
        d.ellipse([92 + i * 36, 88, 116 + i * 36, 112], fill=c)
    hdr = f"rapport_{num}.log"
    d.text((220, 82), hdr, font=f(MONO_R, 30), fill=MUTED)
    pg = f"{n}/{total}"
    d.text((W - 100 - d.textlength(pg, font=f(MONO, 30)), 82), pg, font=f(MONO, 30), fill=GREEN)
    # footer
    im.paste(LOGO, (60, H - 124))
    d.text((140, H - 108), "@rapportdebug", font=f(SEMI, 32), fill=WHITE)
    d.text((W - 60 - d.textlength("contenu IA", font=f(MONO_R, 26)), H - 102), "contenu IA", font=f(MONO_R, 26), fill=MUTED)
    return im, d

def render(spec, outdir):
    slides, num = spec["slides"], spec["num"]
    total = len(slides); paths = []
    for i, s in enumerate(slides, 1):
        im, d = frame(i, total, num)
        x, maxw = 90, W - 180
        k = s["kind"]
        if k == "cover":
            size = 190
            while size > 110 and len(wrap(d, s["title"], f(BOLD, size), maxw)) > 1: size -= 10
            tb = 400 + len(wrap(d, s["title"], f(BOLD, size), maxw)) * size
            im.paste(BIG, (W - 530, max(640, tb + 40)), BIGMASK)
            d = ImageDraw.Draw(im)
            d.text((x, 250), f"> RAPPORT DE BUG n°{num}", font=f(MONO, 44), fill=GREEN)
            d.text((x, 330), "Objet :", font=f(REG, 56), fill=MUTED)
            block(d, s["title"], f(BOLD, size), x, 400, maxw, WHITE, 1.0)
            d.text((x, H - 260), "Glissez pour lire le rapport  →", font=f(SEMI, 40), fill=GREEN)
        elif k == "status":
            d.text((x, 380), "> STATUT", font=f(MONO, 44), fill=GREEN)
            # stamp
            sw = f(BOLD, 92)
            lines = wrap(d, s["status"], sw, maxw - 80)
            bh = len(lines) * 110 + 70
            d.rounded_rectangle([x, 470, W - x, 470 + bh], radius=24, outline=GREEN, width=8)
            yy = 505
            for l in lines:
                d.text((x + 40, yy), l, font=sw, fill=GREEN); yy += 110
            block(d, s["text"], f(SEMI, 52), x, 470 + bh + 70, maxw, WHITE, 1.3)
        elif k == "cta":
            d.text((x, 400), "> ACTION REQUISE", font=f(MONO, 44), fill=GREEN)
            block(d, s["text"], f(BOLD, 88), x, 490, maxw, WHITE, 1.15)
            d.text((x, H - 260), s.get("next", "Rapport suivant : bientôt"), font=f(REG, 36), fill=MUTED)
        else:
            tf, nf = f(SEMI, 68), f(REG, 46)
            h = 90 + len(wrap(d, s["text"], tf, maxw)) * int(68*1.28)
            if s.get("note"): h += 40 + len(wrap(d, s["note"], nf, maxw)) * int(46*1.3)
            top = max(220, (H - h) // 2 - 20)
            d.text((x, top), "> " + s["label"], font=f(MONO, 44), fill=GREEN)
            y = block(d, s["text"], tf, x, top + 90, maxw, WHITE, 1.28)
            if s.get("note"):
                block(d, s["note"], nf, x, y + 40, maxw, MUTED, 1.3)
        p = f"{outdir}/{num}-{i:02d}.jpg"; im.save(p, "JPEG", quality=92, optimize=True); paths.append(p)
    return paths

if __name__ == "__main__":
    # Usage : python3 outils/carousel.py specs/004.json 004
    spec = json.load(open(sys.argv[1])); os.makedirs(sys.argv[2], exist_ok=True)
    print("\n".join(render(spec, sys.argv[2])))
