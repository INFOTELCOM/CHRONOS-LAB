# CHRONOS Lab — application de recherche

> **Nouveauté — interface GitHub Pages :** le dossier `site/` fournit un espace de travail web installable (PWA) pour enregistrer des hypothèses, déclarer des références, comparer jusqu’à trois propositions, consigner des avis indépendants, vérifier une chaîne de hachages et exporter les preuves en JSON/CSV. Les données de cette interface statique restent dans le navigateur local.
>
> GitHub Pages n’exécute pas Python, OpenCV, PyTorch ou SQLite. Pour l’analyse d’image et les fonctions serveur complètes, lance l’application Flask localement ou sur une infrastructure privée correctement sécurisée. Voir [`DEPLOYMENT.md`](DEPLOYMENT.md) et [`SCIENTIFIC_VALIDATION_PROTOCOL.md`](SCIENTIFIC_VALIDATION_PROTOCOL.md). Le script `publish-to-github.ps1` aide à créer le dépôt public `INFOTELCOM/CHRONOS-LAB` et à déclencher le déploiement Pages.

CHRONOS Lab est une application web locale exécutable, avec API Python/Flask et base SQLite. Ce n'est pas un déchiffreur universel et ne prétend pas l'être : aucun logiciel ne peut garantir la traduction de tout symbole inconnu sans contexte, corpus de référence et validation experte.

## Fonctionnalités réellement implémentées

- **Calendrier maya** : calcul du Tzolk'in, Haab' et Compte long à partir d'une date grégorienne, avec corrélations GMT 584283, 584285 et 584286 sélectionnables.
- **Astronomie** : appel en direct à l'API NASA/JPL Horizons pour obtenir une éphéméride de la planète et de la date choisies. Une connexion Internet est nécessaire. La réponse JPL et un extrait sont affichés pour vérification.
- **Analyse d'image** : téléversement, prétraitement OpenCV, segmentation par composants ou tentative de séparation `watershed` (utile pour certains signes touchants, mais susceptible de sur-segmenter), puis comparaison de formes normalisées avec les images de signes documentées.
- **Classifieurs IA spécialisés** : `train_glyph_model.py` entraîne un ResNet-18 par système d’écriture (égyptien, maya, cunéiforme, etc.) ou un modèle général. Le moteur exige le modèle spécialisé correspondant à l’écriture sélectionnée et ne retombe pas silencieusement sur un modèle d’un autre système. Un mécanisme d’abstention indique les résultats incertains; il ne garantit pas la détection de tous les signes inconnus. Aucun corpus antique universel n’est inclus.
- **OCR facultatif** : si l'exécutable Tesseract et ses modèles linguistiques sont installés séparément, le programme peut tenter de lire le texte pris en charge par ces modèles. La présence de Tesseract ne signifie pas qu'il sait lire les hiéroglyphes égyptiens ou le cunéiforme.
- **Catalogue d'écritures** : un catalogue de départ couvre plus de 20 systèmes ou corpus (égyptien, maya, cunéiforme, Linéaire A/B, Indus, grec, latin, etc.) et distingue les systèmes lisibles, les besoins de modèles spécialisés et les écritures non déchiffrées.
- **Base documentaire** : stockage local SQLite des signes et inscriptions, avec culture, lecture, sens, transcription, provenance et sources bibliographiques.
- **Laboratoire de séquences** : fréquences, diversité, entropie et motifs de 2 ou 3 signes pour explorer des corpus non déchiffrés, sans générer de traduction.
- **Audit de corpus** : `audit_corpus.py` vérifie les fichiers, compte les exemples par classe et repère les doublons exacts avant l’entraînement.
- **Export** : téléchargement de la base au format JSON.

## Installation (Windows 10/11)

1. Installez Python 3.11 ou 3.12 depuis le site officiel : https://www.python.org/downloads/ . Pendant l'installation, cochez **Add Python to PATH**.
2. Décompressez l'archive dans un dossier, par exemple `C:\CHRONOS-Lab`.
3. Ouvrez PowerShell dans ce dossier.
4. Exécutez :

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

5. Ouvrez `http://127.0.0.1:5000` dans Chrome ou Edge.

Si PowerShell bloque l'activation, lancez la commande `Set-ExecutionPolicy -Scope Process Bypass` dans cette fenêtre puis réessayez l'activation.

## Classifieur IA de glyphes (optionnel)

Pour entraîner un modèle visuel réel sur votre corpus annoté, suivez [`AI_TRAINING.md`](AI_TRAINING.md). Les dépendances PyTorch/torchvision sont optionnelles et s’installent via `pip install -r requirements-ai.txt`. Un modèle spécialisé s’entraîne par exemple avec `python train_glyph_model.py --script maya_classical --epochs 20`, après avoir organisé les images sous `data/training/maya_classical/<classe>/`. Le score de classement n’est pas une probabilité calibrée et le modèle ne fournit pas une traduction linguistique.

## OCR facultatif (Windows)

L'application fonctionne sans Tesseract : les calendriers, la base et la comparaison visuelle restent disponibles. Pour activer l'OCR générique, installez Tesseract OCR pour Windows puis ajoutez au PATH l'exécutable et les modèles (`tessdata`) des langues voulues. Redémarrez PowerShell et relancez CHRONOS LAB. Dans le champ OCR, saisissez un code de modèle effectivement installé, par exemple `eng` ou `fra`; vérifiez la liste dans l'onglet « Écritures anciennes ». Les modèles modernes ne lisent pas automatiquement les écritures antiques.

## Dossiers et données

- `data/chronos.sqlite3` : base de données locale, créée automatiquement.
- `data/reference_glyphs/` : images de référence des signes enregistrés.
- `uploads/` : images soumises et versions prétraitées.

Les données sont stockées sur la machine qui exécute l'application. Ce projet n'inclut pas de corpus archéologique sous licence ni de modèle entraîné sur tous les hiéroglyphes. Pour une recherche scientifique, chaque entrée doit citer une source fiable. Les données d'inscription ne sont pas des traductions validées automatiquement.

## Catalogue des écritures

- `GET /api/scripts` et `GET /api/scripts?q=maya` : catalogue documentaire filtrable.
- `GET /api/ocr-status` : présence de Tesseract et modèles OCR installés.
- `GET /api/model-status?script=maya_classical` : présence et métadonnées du classifieur spécialisé ou général.
- `GET /api/corpus-stats` : statistiques du corpus local et registre des modèles.
- `POST /api/pattern-analysis` avec `{"sequence":"A12 B03 A12 C07"}` : statistiques descriptives de séquence.

## API locale

- `GET /api/health`
- `POST /api/calendar` avec JSON `{"date":"2012-12-21","correlation":584283}`
- `POST /api/astronomy` avec JSON `{"date":"2026-10-14","planet":"Mars"}`
- `POST /api/analyze-image` avec multipart `image`
- `GET /api/signs?q=...`
- `POST /api/signs` (multipart/form-data, image facultative)
- `GET /api/inscriptions?q=...`
- `POST /api/inscriptions` (JSON)
- `GET /api/export`

## Limites importantes

1. Les écritures maya et sumérienne ne sont pas interchangeables. Une ressemblance graphique ne démontre pas une relation linguistique ou historique.
2. Le module d'image segmente des fragments par composants ou avec une tentative `watershed`, puis les compare au corpus ajouté par l'utilisateur. Les caractères qui se touchent, les gravures endommagées, les angles et les photos de mauvaise qualité peuvent fausser les résultats. Il ne reconnaît pas tous les glyphes, ne traduit pas une inscription inconnue et n'authentifie pas un artefact.
3. Les résultats astronomiques viennent de NASA/JPL Horizons, mais doivent être interprétés selon les paramètres de référence, de temps et de coordonnées. Consulter la documentation officielle : https://ssd-api.jpl.nasa.gov/doc/horizons.html .
4. Le convertisseur maya fournit une conversion arithmétique selon une corrélation sélectionnée; les conventions historiques et calendaires doivent être explicitées dans les publications.
5. Le serveur écoute uniquement sur `127.0.0.1` par défaut. Il n'est pas déployé publiquement et n'inclut pas de comptes utilisateurs ou de sécurité multi-utilisateur.


## Détection des signes inconnus et contrôle de segmentation

Le classifieur spécialisé utilise un mécanisme de rejet ouvert : score de classe + distance à des prototypes de classes connues. Il s'abstient lorsqu'un des signaux est défavorable. Pour évaluer ce mécanisme, placez des images de signes absents des classes apprises dans `data/unknown/<script-key>/` avant l'entraînement. Le rapport `data/training_report_<script>.json` donne le taux de rejet observé. **Aucun système ne peut garantir qu'il détectera tous les signes inconnus.**

La segmentation combine plusieurs seuils et peut utiliser watershed. L'interface affiche une image annotée et signale les cadres imbriqués ou chevauchants, susceptibles de représenter une fragmentation d'un glyphe. Les cadres restent des propositions : vérifiez et corrigez-les sur l'image originale.

L'audit `audit_corpus.py` vérifie les images, les doublons exacts, les quasi-doublons candidats via pHash, les conflits visuels entre classes et le manifeste de provenance. Il ne certifie pas scientifiquement les étiquettes. Utilisez `data/training/MANIFEST_TEMPLATE.csv` comme modèle.

## Statut explicite des propositions IA

Chaque résultat du classifieur expose maintenant `presentation_mode: EXPLORATORY_ONLY`, `scientific_status: NOT_CERTIFIED_HYPOTHESIS` et `automatic_scientific_validation: false`. Le champ `accepted` reste toujours faux pour éviter de confondre un contrôle technique avec une validation scientifique. Le champ `technical_candidate_passed` indique seulement si les tests internes de rejet ont été franchis.

Sans calibration, le modèle s’abstient obligatoirement, mais affiche quand même ses meilleurs candidats à titre exploratoire. Le score affiché est un score de classement, pas une probabilité épigraphique. Avec calibration, les candidats restent des hypothèses à vérifier; la calibration ne certifie ni la lecture ni l’origine de l’artefact.

## Garde-fous supplémentaires

- Détection ouverte prudente : seuil de score, distance aux prototypes et ensemble de prédiction calibré lorsque le corpus est assez grand. Sans calibration, la reconnaissance n'est pas validée automatiquement. Cela réduit les faux positifs mais ne garantit pas le rejet de tout signe inconnu arbitraire.
- Segmentation multi-propositions et canevas de correction manuelle : l'utilisateur peut redessiner les cadres avant de relancer la reconnaissance; le rapport est conservé dans `data/segmentation_reviews/`.
- Audit du corpus multi-signal : SHA-256, pHash, dHash, corrélation visuelle, vérification de manifeste et statut de contrôle technique.
- Revue épigraphique : propositions sourcées, deux avis consignés, désaccords visibles et statut de processus distinct d'une certification scientifique.

Aucune fonction ne certifie automatiquement la vérité d'une lecture, d'une traduction ou de l'identité d'un relecteur. Le feu vert technique concerne uniquement les contrôles que le programme sait effectuer. Voir `AI_TRAINING.md`.


## Workspace web statique et GitHub Pages

- `site/index.html`, `site/app.js`, `site/style.css` : interface responsive d'hypothèses et de revue documentaire.
- Stockage local dans le navigateur; import/export JSON et CSV; chaîne d'événements SHA-256 avec vérification intégrée. Ce n'est pas un journal inviolable et cela ne synchronise pas les appareils.
- `site/manifest.webmanifest` et `site/sw.js` : installation PWA et cache hors connexion pour l'interface.
- `.github/workflows/pages.yml` : validation et publication automatique du dossier `site/`.
- `.github/workflows/tests.yml` : compilation Python/JavaScript et tests API à chaque push/PR.
- `evaluate_independent_glyphs.py` : évaluation séparée sur des artefacts tenus à l'écart, avec barrière de provenance et mesure du taux de faux acceptés sur signes inconnus.

Pour publier, suis [`DEPLOYMENT.md`](DEPLOYMENT.md). L'URL prévue si le dépôt s'appelle `CHRONOS-LAB` sous `INFOTELCOM` est `https://infotelcom.github.io/CHRONOS-LAB/`.

## Sécurité du déploiement

Le backend Flask contient des routes d'écriture et ne fournit pas encore une authentification multi-utilisateur complète. Ne l'expose pas directement à Internet en écriture. Avant tout déploiement public du backend, ajouter authentification, autorisations, sauvegardes, limitation de débit et revue de sécurité. Le workspace Pages statique est utilisable indépendamment, avec des données conservées localement.

## Évaluation indépendante

Lire [`SCIENTIFIC_VALIDATION_PROTOCOL.md`](SCIENTIFIC_VALIDATION_PROTOCOL.md). Le script `evaluate_independent_glyphs.py --script maya_classical` exige un corpus test indépendant, un manifeste complet et l'absence de chevauchement d'identifiants d'artefacts avec l'entraînement. Il produit un rapport technique et n'émet jamais de certification scientifique.
