"""Voix off de Claude pour les vidéos « Rapport de bug ».

Usage : python3 outils/voix.py specs/video/004.json 004/004-video.mp4 [--secours]

Chaque scène de la spec porte un champ "voice" : le texte que Claude dit pendant cette scène.
L'outil synthétise chaque réplique avec Piper (voix française libre), allonge la scène si la
réplique dure plus longtemps que l'animation, assemble la piste voix puis appelle motion.py.

Piper et la voix sont téléchargés au premier lancement dans ~/.cache/rdb-voix :
  - moteur : github.com (release officielle rhasspy/piper)
  - voix   : huggingface.co (rhasspy/piper-voices) ; le domaine doit être autorisé.
--secours : si la voix Piper est inaccessible, utilise espeak-ng (voix très robotique, pour tester).
"""
import sys, os, json, subprocess, tarfile, urllib.request, wave, tempfile, shutil
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import motion
import motion2

CACHE = os.path.expanduser("~/.cache/rdb-voix")
PIPER_URL = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz"
VOICE = os.environ.get("RDB_VOIX", "fr_FR-tom-medium")   # autres choix : fr_FR-siwis-medium, fr_FR-upmc-medium
SPEED = float(os.environ.get("RDB_VITESSE", "0.95"))      # < 1 = plus rapide
START = 0.25      # la voix démarre 0,25 s après le début de la scène
TAIL = 0.8        # marge après la fin de la réplique


def fetch(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return
    tmp = dest + ".part"
    subprocess.run(["curl", "-sSfL", "--max-time", "300", "-o", tmp, url], check=True)
    os.replace(tmp, dest)


def setup(fallback):
    os.makedirs(CACHE, exist_ok=True)
    pdir = os.path.join(CACHE, "piper")
    if not os.path.exists(os.path.join(pdir, "piper")):
        tgz = os.path.join(CACHE, "piper.tgz"); fetch(PIPER_URL, tgz)
        with tarfile.open(tgz) as t:
            t.extractall(CACHE, filter="data")
        for b in ("piper", "espeak-ng"):
            os.chmod(os.path.join(pdir, b), 0o755)
    lang, reg = VOICE.split("-")[0], VOICE.split("-")[1]
    base = f"https://huggingface.co/rhasspy/piper-voices/resolve/main/{lang.split('_')[0]}/{lang}/{reg}/medium/{VOICE}"
    model = os.path.join(CACHE, VOICE + ".onnx")
    try:
        fetch(base + ".onnx", model); fetch(base + ".onnx.json", model + ".json")
        return ("piper", pdir, model)
    except subprocess.CalledProcessError:
        if not fallback:
            raise SystemExit("Voix Piper inaccessible : autoriser huggingface.co, ou relancer avec --secours.")
        print("ATTENTION : voix de secours espeak-ng (huggingface.co inaccessible).")
        return ("espeak", pdir, None)


def say(engine, text, out):
    kind, pdir, model = engine
    env = dict(os.environ, LD_LIBRARY_PATH=pdir)
    text = text.replace(" ", " ")
    if kind == "piper":
        text = text.replace("*", "")
        subprocess.run([os.path.join(pdir, "piper"), "-q", "-m", model, "--length_scale", str(SPEED),
                        "--sentence_silence", "0.25", "-f", out], input=text.encode(), env=env, check=True)
    else:
        text = text.replace("*", "")
        subprocess.run([os.path.join(pdir, "espeak-ng"), "--path=" + pdir, "-v", "fr", "-s", "160", "-w", out, "--stdin"],
                       input=text.encode(), env=env, check=True)


def load(path):
    """Lit un wav et le ramène en mono 44,1 kHz (float)."""
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", path, "-f", "s16le", "-ac", "1", "-ar", str(motion.SR), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(float) / 32768


def main(spec_path, out, fallback=False):
    spec = json.load(open(spec_path))
    engine = setup(fallback)
    work = tempfile.mkdtemp(prefix="voix_")
    v2 = spec.get("engine") == "v2"
    motion.SPEC = spec
    clips = []
    for i, sc in enumerate(spec["scenes"]):
        natural = motion2.natural(sc) if v2 else motion.plan(sc)["dur"]
        if sc.get("voice"):
            wav = os.path.join(work, f"v{i:02d}.wav"); say(engine, sc["voice"], wav)
            clip = load(wav); clips.append(clip)
            sc["voice_dur"] = round(len(clip) / motion.SR, 3)
            sc["duration"] = round(max(natural, START + len(clip) / motion.SR + TAIL), 2)
        else:
            clips.append(None); sc["duration"] = natural
    # piste voix complète, calée sur le début de chaque scène (arrondi aux images comme motion.py)
    total = sum(round(s["duration"] * motion.FPS) / motion.FPS for s in spec["scenes"])
    track = np.zeros(int((total + 1) * motion.SR)); t0 = 0.0
    for sc, clip in zip(spec["scenes"], clips):
        if clip is not None:
            i = int((t0 + START) * motion.SR); track[i:i + len(clip)] += clip[:len(track) - i]
        t0 += round(sc["duration"] * motion.FPS) / motion.FPS
    track = track / max(1e-6, np.abs(track).max()) * 0.9
    vwav = os.path.join(work, "voix.wav")
    with wave.open(vwav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(motion.SR); w.writeframes((track * 32767).astype(np.int16).tobytes())
    tspec = os.path.join(work, "spec.json"); json.dump(spec, open(tspec, "w"), ensure_ascii=False)
    (motion2 if v2 else motion).main(tspec, out, vwav)
    shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0], args[1], fallback="--secours" in sys.argv)
