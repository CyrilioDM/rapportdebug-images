"""Transforme un carrousel (NNN/NNN-01.jpg à -08.jpg) en vidéo verticale 1080×1920 (MP4 H.264)
pour Reels Instagram, Reels Facebook et TikTok.

Usage : python3 outils/video.py specs/006.json   → crée 006/006.mp4

Les diapositives sont régénérées en « mode vidéo » à partir de la spec (pas de « Glissez… »),
et la durée de chacune dépend de la longueur de son texte.

Chaque diapositive reste affichée le temps de la lire (2,5 à 5,5 s), avec un léger zoom,
un fondu enchaîné et une barre de progression. Piste audio silencieuse : la musique
s'ajoute dans l'appli (ou via autoAddMusic sur TikTok), pour éviter tout problème de droits.
"""
import sys, os, json, subprocess, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import carousel
from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
NAVY = (20, 33, 61); PANEL = (27, 43, 77); GREEN = (61, 220, 151); MUTED = (154, 166, 191)
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
FADE = 0.4      # secondes de fondu entre deux diapositives
ZOOM = 0.035    # zoom total sur la durée d'une diapositive


# En vidéo on ne glisse pas : on adapte les consignes de la spec.
SWAP = (("Glissez pour la réponse", "Attendez la réponse"), ("Répondez avant de glisser", "Répondez avant la fin"),
        ("avant de glisser", "avant la fin"), ("Glissez", "Attendez"), ("glissez", "attendez"))


def video_spec(spec):
    spec = json.loads(json.dumps(spec))
    for s in spec["slides"]:
        for k, v in s.items():
            if isinstance(v, str):
                for a, b in SWAP:
                    v = v.replace(a, b)
                s[k] = v
    return spec


def durations(slides):
    out = []
    for s in slides:
        words = sum(len(str(s.get(k, "")).split()) for k in ("title", "label", "text", "note", "status", "next"))
        out.append(max(2.5, min(5.0, 1.0 + words * 0.2)))
    return out


def slide_frame(img, t, dur):
    """Diapositive 1080×1350 zoomée selon t/dur, centrée sur le fond 1080×1920."""
    z = 1 + ZOOM * (t / dur)
    w, h = int(img.width * z), int(img.height * z)
    big = img.resize((w, h), Image.BILINEAR)
    left, top = (w - img.width) // 2, (h - img.height) // 2
    return big.crop((left, top, left + img.width, top + img.height))


def base(progress, idx, n):
    im = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(im)
    font = ImageFont.truetype(MONO, 40)
    title = "> RAPPORT DE BUG"
    d.text(((W - d.textlength(title, font=font)) / 2, 150), title, font=font, fill=GREEN)
    # barre de progression en bas
    y = H - 190
    d.rounded_rectangle([90, y, W - 90, y + 14], radius=7, fill=PANEL)
    d.rounded_rectangle([90, y, 90 + int((W - 180) * progress), y + 14], radius=7, fill=GREEN)
    return im


def main():
    spec = video_spec(json.load(open(sys.argv[1])))
    num = spec["num"]
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tmp = tempfile.mkdtemp()
    slides = [Image.open(p).convert("RGB") for p in carousel.render(spec, tmp, video=True)]
    durs = durations(spec["slides"])
    total = sum(durs)
    os.makedirs(os.path.join(root, num), exist_ok=True)
    out = os.path.join(root, num, f"{num}.mp4")
    y0 = (H - slides[0].height) // 2

    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
           "-shortest", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
           "-profile:v", "high", "-movflags", "+faststart", "-c:a", "aac", "-b:a", "128k", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    start = 0.0
    for i, (img, dur) in enumerate(zip(slides, durs)):
        for f in range(int(round(dur * FPS))):
            t = f / FPS
            frame = base((start + t) / total, i, len(slides))
            cur = slide_frame(img, t, dur)
            # fondu vers la diapositive suivante sur la fin
            if i + 1 < len(slides) and t > dur - FADE:
                a = (t - (dur - FADE)) / FADE
                nxt = slide_frame(slides[i + 1], 0, durs[i + 1])
                cur = Image.blend(cur, nxt, a)
            frame.paste(cur, (0, y0))
            p.stdin.write(frame.tobytes())
        start += dur
    p.stdin.close()
    p.wait()
    print(f"{out} ({total:.1f} s)")


if __name__ == "__main__":
    main()
