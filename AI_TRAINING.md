# CHRONOS LAB — IA spécialisée, corpus et validation

## Ce que fait réellement le moteur

CHRONOS LAB peut charger un classifieur ResNet-18 entraîné localement. Le classifieur attribue une image de glyphe à l'une des classes annotées qu'il a apprises et affiche plusieurs candidats. Il n'est pas fourni avec un corpus universel prêt à l'emploi et ne peut pas traduire toutes les écritures anciennes. Le score softmax est un score de classement, pas une probabilité épigraphique calibrée. Le moteur peut s’abstenir à partir du score maximal et de la distance aux prototypes de classes apprises. Cette détection ouverte réduit certains risques mais ne garantit pas de détecter tous les signes inconnus.

## Installation Windows / PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-ai.txt
```

Si PyTorch ne s'installe pas, choisissez la commande adaptée à votre système dans le sélecteur officiel : https://pytorch.org/get-started/locally/ . Un entraînement avec les poids ImageNet préentraînés peut nécessiter un téléchargement. `--no-pretrained` évite ce téléchargement mais démarre sans ces poids.

## Entraîner un modèle spécialisé

Utilisez une clé stable pour le système d'écriture. Les exemples proposés dans l'interface sont `egyptian_hieroglyphs`, `maya_classical`, `cuneiform`, `linear_b`, `linear_a`, `indus`, `oracle_bone` et `phoenician`.

Structure recommandée :

```text
data/training/
  egyptian_hieroglyphs/
    A001/
      photo_objet_001.png
      photo_objet_002.png
    A002/
      photo_objet_003.png
      photo_objet_004.png
  maya_classical/
    T501/
      stelae_A_crop_01.png
      stelae_B_crop_02.png
    T502/
      panel_C_crop_01.png
```

Chaque sous-dossier de classes doit contenir des images du même signe/concept graphique, selon une convention d'annotation documentée. Évitez de mélanger allographes distincts, signes endommagés, variantes d'époque ou catégories incertaines sans les documenter. Minimum technique du script : 5 images par classe; recommandation pratique : plusieurs dizaines d'images indépendantes, provenant de supports, photographies, orientations, états de conservation et conditions lumineuses variés.

Audit préalable du corpus :

```powershell
python audit_corpus.py --script egyptian_hieroglyphs
```

Le manifeste attendu est `data/training/<script>/manifest.csv` ; un exemple est fourni dans `data/training/MANIFEST_TEMPLATE.csv`. Il contient la provenance, la licence, la publication, l’identifiant d’artefact, l’annotateur, le relecteur et l’état de révision.

L’audit vérifie les fichiers image, compte les classes, détecte les doublons exacts et utilise un hash perceptuel (pHash) pour signaler des quasi-doublons candidats, y compris des images visuellement proches dans des classes différentes. Il vérifie aussi le manifeste de provenance. Ces alertes ne sont pas des preuves : les quasi-doublons doivent être examinés, et aucune vérification automatique ne peut certifier l’exactitude épigraphique d’une étiquette.

Entraînement d'un modèle spécialisé :

```powershell
python train_glyph_model.py --script egyptian_hieroglyphs --epochs 20 --batch-size 16 --unknown-threshold 0.65
# Facultatif : évaluer le rejet d’images qui ne correspondent à aucune classe connue
# Déposer ces images dans data/unknown/egyptian_hieroglyphs/
python train_glyph_model.py --script maya_classical --epochs 20 --batch-size 16
```

Le modèle sera enregistré sous `models/egyptian_hieroglyphs_glyph_classifier.pth` ou `models/maya_classical_glyph_classifier.pth`. Pour un modèle général (non recommandé si les écritures ont des morphologies très différentes), utilisez la disposition historique `data/training/<classe>/...` et omettez `--script`.

Redémarrez l'application après l'entraînement :

```powershell
python app.py
```

Puis ouvrez http://127.0.0.1:5000 et sélectionnez l'écriture dans le module d'analyse d'image. Un modèle spécialisé est utilisé s'il existe; sinon le moteur tente le modèle général. Les résultats ne doivent pas être présentés comme identifications certaines.

## Corpus scientifiquement traçable

Pour chaque image, gardez en dehors du dossier d'entraînement ou dans un manifeste séparé : identifiant de l'objet, musée/collection, inventaire, site et contexte archéologique, datation et méthode de datation, bibliographie, URL/licence d'image, photographe, orientation, état de conservation, lecture éditoriale, annotateur, niveau d'accord et date de révision. Respectez les licences et droits des images.

Ne répartissez pas au hasard des recadrages d'une même photographie entre entraînement et validation : le modèle pourrait mémoriser le support au lieu d'apprendre le signe. Quand `manifest.csv` contient un `artifact_id` pour chaque image, le script tente une séparation globale par artefact pour limiter les fuites entre entraînement et validation. Si ce n’est pas possible sans retirer une classe d’un des jeux, il utilise un repli aléatoire par image et l’indique dans le rapport; les performances peuvent alors être optimistes. Une validation plus crédible sépare les artefacts, sites, photographies ou éditions, puis utilise un jeu de test indépendant. Pour refuser tout repli aléatoire pendant l’entraînement, ajoutez `--require-artifact-groups` : le programme s’arrête si une séparation complète par artefact n’est pas possible. Une seule valeur d'accuracy ne suffit pas : inspectez matrice de confusion, rappel par classe, classes rares et taux d'abstention sur des signes hors corpus.

## Reconnaissance de l'inconnu

Le moteur combine deux signaux : le score maximal du classifieur et la distance à un prototype appris pour chaque classe. Le seuil de distance est estimé sur les exemples de validation connus. Pour évaluer la détection ouverte, placez des signes absents des classes apprises dans `data/unknown/<script-key>/`. Le script écrit un rapport `data/training_report_<script>.json` avec le taux de rejet observé. Ce taux dépend du corpus et n’est pas une garantie pour de futurs signes inconnus; évaluez aussi les faux rejets de signes connus et utilisez un jeu de test indépendant.

## Segmentation et transcription

La segmentation utilise plusieurs propositions (seuil d’Otsu, seuil adaptatif et, sur demande, watershed), élimine les cadres presque identiques et signale les zones imbriquées ou qui se chevauchent comme possibles sur-segmentations. L’image annotée est affichée pour inspection. Cela diminue le risque de prendre des fragments pour des signes distincts, mais les signes touchants peuvent encore être fusionnés et un signe complexe peut encore être découpé. Vérifiez toujours les cadres sur l’image d’origine et corrigez-les avant toute transcription. Une transcription complète nécessite en plus les conventions de direction de lecture, l'ordre des blocs, les variantes, lacunes, ligatures et règles propres à chaque système.

## Écritures non déchiffrées

Pour le Linéaire A, l'Indus, le rongorongo ou d'autres corpus dont le déchiffrement n'est pas consensuel, utilisez l'analyse statistique de séquences comme outil descriptif. Fréquences, bigrammes, trigrammes et entropie peuvent aider à formuler des questions; ils ne prouvent ni la langue ni le sens des signes. CHRONOS LAB ne génère pas de traduction certaine pour ces écritures.

## Détection prudente des classes inconnues (mise à jour)

L'entraînement peut maintenant produire une calibration de type conformel lorsque le jeu de validation contient suffisamment d'exemples séparés pour chaque classe. Exemple :

```powershell
python train_glyph_model.py --script egyptian_hieroglyphs --epochs 20 --batch-size 16 --conformal-alpha 0.05
```

Le rapport `data/training_report_<script>.json` précise si la calibration a été produite, son seuil et le nombre d'exemples de calibration. Si le jeu est trop petit, la calibration est désactivée plutôt que simulée et le moteur s'abstient de valider la classe. Le seuil conformel vise une couverture des exemples connus sous hypothèses statistiques (notamment échangeabilité); il ne prouve pas qu'un signe hors distribution sera toujours rejeté. Des inconnus visuellement très proches d'une classe connue restent un risque. Réservez des signes inconnus et des artefacts entiers, jamais vus pendant l'entraînement, pour mesurer les faux acceptés.

## Corriger la segmentation manuellement

Après l'analyse d'une image, utilisez le canevas **Correction manuelle des frontières** : tracez un cadre autour de chaque glyphe complet, annulez les cadres erronés ou effacez-les, puis cliquez sur **Analyser mes cadres corrigés**. Les prédictions sont recalculées sur ces crops et un rapport est enregistré dans `data/segmentation_reviews/`. Les cadres dessinés par l'utilisateur remplacent les propositions automatiques pour cette analyse; ils ne prouvent pas l'identité du signe. Conservez l'image originale et vérifiez les limites au regard du contexte de l'inscription.

## Revue épigraphique et références

L'onglet **Revue scientifique** permet de déposer une proposition (identification, transcription, translittération, traduction, datation ou interprétation), deux références déclarées et des avis argumentés. Le système consigne les désaccords; si deux avis distincts sont favorables et qu'aucun désaccord n'est enregistré, le statut indique `TWO_REVIEWS_RECORDED_NOT_SCIENTIFIC_CERTIFICATION`.

Ce statut atteste uniquement que deux avis ont été enregistrés dans l'application. Les identités, affiliations, qualifications, sources et citations sont déclaratives et ne sont pas authentifiées par le logiciel. Pour une vraie certification institutionnelle, ajoutez une authentification, une vérification des affiliations, des références persistantes, une politique de conflits d'intérêts, un historique immuable et une procédure d'arbitrage par une institution compétente. Le programme ne doit jamais présenter une transcription ou une traduction comme scientifiquement vraie sur la seule base d'un modèle IA ou de deux formulaires.

## Audit du corpus et quasi-doublons

`audit_corpus.py` combine maintenant SHA-256, pHash, dHash et corrélation de miniatures pour signaler des doublons visuels probables. Ces signaux sont complémentaires mais ne détectent pas tous les doublons sémantiques; les candidats doivent être vérifiés. Le champ `technical_gate` dans le rapport indique si les contrôles techniques et de provenance examinés passent. Même avec `PASS_TECHNICAL_CHECKS_ONLY`, `scientific_truth_certified` reste toujours `false` : un contrôle automatique ne peut pas prouver qu'une étiquette épigraphique est vraie.

**Isolation des écritures :** si une écriture spécialisée est sélectionnée mais que son modèle n'existe pas, CHRONOS LAB n'utilise plus silencieusement le modèle général. Il affiche « aucun modèle entraîné » et s'abstient, afin d'éviter de présenter les classes d'une autre écriture comme des identifications pertinentes.


## Règle de présentation des sorties IA

Les sorties de reconnaissance sont toujours présentées comme des candidats exploratoires. Le programme expose explicitement l’état de calibration et l’incertitude; si la calibration est absente, il s’abstient de valider la classe, tout en gardant les candidats visibles pour l’examen humain. Même si la calibration est disponible et que les tests techniques passent, aucune sortie n’est certifiée comme fait scientifique. Les scores sont des scores de classement du modèle, pas des probabilités de vérité historique.


## Évaluation indépendante avant usage scientifique

Consultez `SCIENTIFIC_VALIDATION_PROTOCOL.md`. Le dossier `data/independent_eval/<script-key>/` doit contenir `known/<classe>/`, `unknown/` et un `manifest.csv` complet. Les artefacts doivent être absents du corpus d'entraînement. Exemple :

```powershell
python evaluate_independent_glyphs.py --script maya_classical
```

Le script bloque en cas de manifeste incomplet ou d'identifiants d'artefact partagés avec le corpus d'entraînement. Il produit des mesures de rejet et de justesse avec abstention pour ce test seulement; il ne certifie jamais une lecture historique.
