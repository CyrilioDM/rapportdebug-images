# Outils Rapport de bug

- `carousel.py` : génère un carrousel 1080×1350 en JPEG (TikTok refuse le PNG).
  `python3 outils/carousel.py specs/004.json 004` → crée `004/004-01.jpg` à `004-08.jpg`.
- `specs/NNN.json` : texte de chaque rapport. Types de diapositives :
  `cover` (title), `text` (label, text, note facultative), `status` (status, text), `cta` (text, next).
- Polices attendues : Inter (/usr/share/fonts/opentype/inter) et DejaVu Sans Mono.
- Liens pour Metricool : `https://raw.githubusercontent.com/CyrilioDM/rapportdebug-images/<commit>/NNN/NNN-01.jpg`
  (toujours figer le lien sur le hash du commit).

## Vidéo (test depuis le 23/10/2026)

- `video.py` : transforme une spec en vidéo verticale 1080×1920 (MP4 H.264, ~30 s, piste audio muette).
  `python3 outils/video.py specs/008.json` → crée `008/008.mp4`.
- Les diapositives sont régénérées en « mode vidéo » : « Glissez… » devient « Regardez jusqu'au bout » / « Attendez… ».
- Durée de chaque diapositive : 2,5 à 5 s selon la longueur du texte, fondu enchaîné, léger zoom, barre de progression.
- Lien pour Metricool : `https://raw.githubusercontent.com/CyrilioDM/rapportdebug-images/<commit>/NNN/NNN.mp4`.

## Vidéo (motion design + voix off)
- `motion.py` : vidéo verticale 1080×1920 animée (texte tapé, visuels, tampon, glitchs, effets sonores) depuis `specs/video/NNN.json`.
- `voix.py` : ajoute la voix off de Claude (Piper, voix libre `fr_FR-tom-medium`) et cale chaque scène sur sa réplique.
  `python3 outils/voix.py specs/video/004.json 004/004-video.mp4` → vidéo finale avec voix.
  Nécessite huggingface.co autorisé (téléchargement de la voix au premier lancement). `--secours` = voix espeak-ng pour tester.
- Spec vidéo : scènes cover / text (visual : plate, timer, cut) / bubbles / status / cta, chacune avec un champ `voice`.
