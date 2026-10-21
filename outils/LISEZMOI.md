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
