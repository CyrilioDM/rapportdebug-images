# Outils Rapport de bug

- `carousel.py` : génère un carrousel 1080×1350 en JPEG (TikTok refuse le PNG).
  `python3 outils/carousel.py specs/004.json 004` → crée `004/004-01.jpg` à `004-08.jpg`.
- `specs/NNN.json` : texte de chaque rapport. Types de diapositives :
  `cover` (title), `text` (label, text, note facultative), `status` (status, text), `cta` (text, next).
- Polices attendues : Inter (/usr/share/fonts/opentype/inter) et DejaVu Sans Mono.
- Liens pour Metricool : `https://raw.githubusercontent.com/CyrilioDM/rapportdebug-images/<commit>/NNN/NNN-01.jpg`
  (toujours figer le lien sur le hash du commit).
