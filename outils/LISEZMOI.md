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
- `motion2.py` : moteur vidéo v2 (Claude en personnage animé qui réagit et « parle », sous-titres mot à mot synchronisés,
  illustrations, secousses et zooms). Activé quand la spec vidéo contient `"engine": "v2"` ; voix.py l'appelle alors.
  Visuels : plate, timer, cut, think (défaut sans visuel), bubbles. Dans `voice`, *mot* = mot surligné en vert.
- `motion3.py` : vidéo v3 « typo animée » (style retenu le 03/11/2026) : mots géants calés sur la voix, coupes rapides,
  mots clés sur fond vert, tampon final, appel à s'abonner. 25-30 s. Spec : `specs/video/NNN-v3.json` (champ beats).
  `python3 outils/motion3.py specs/video/004-v3.json 004/004-video-v3.mp4`
  Règle d'écriture : la 1re phrase pose le sujet (souvent une question : « Pourquoi personne ne prend le dernier morceau ? »), jamais une phrase sans contexte.
  Champ `emoji` par beat (police Noto Color Emoji, OFL) + `fx` facultatif : bounce, chop, spin, blink, point.
