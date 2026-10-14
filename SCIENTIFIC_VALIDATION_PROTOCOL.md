# Protocole de validation scientifique — CHRONOS LAB

Ce protocole complète l'audit documentaire et l'entraînement. Il ne transforme pas le logiciel en autorité épigraphique : la validation de la lecture reste une tâche scientifique humaine.

## 1. Constituer des corpus traçables

Pour chaque image, conserver au minimum :

- identifiant stable de l'image et de l'artefact original ;
- institution, inventaire ou corpus d'origine et URL/catalogue ;
- publication, édition, page ou numéro de planche ;
- licence/droits d'utilisation ;
- système d'écriture, classe proposée et variantes possibles ;
- annotateur, relecteur, date et statut de relecture ;
- qualité de l'image, dommages, orientation, segmentation manuelle et notes d'incertitude.

Un manifeste complet améliore la traçabilité, mais ne garantit ni l'exactitude des labels ni l'indépendance réelle des sources.

## 2. Éviter la fuite de données

Ne répartissez pas au hasard des crops d'une même inscription entre entraînement et test. Toutes les images dérivées d'un même artefact, d'une même photographie, d'une même planche ou d'une même chaîne de traitement doivent rester dans une seule partition. Fournissez `artifact_id` dans `manifest.csv` pour activer la séparation groupée de l'entraînement.

Pour une évaluation indépendante, rassemblez des artefacts qui n'apparaissent pas dans le corpus d'entraînement et placez-les dans `data/independent_eval/<script-key>/`. Le script `evaluate_independent_glyphs.py` bloque si les identifiants d'artefact se chevauchent ou si la provenance/relecture manque dans les manifestes.

## 3. Structure du test indépendant

```text
data/independent_eval/maya_classical/
├── known/
│   ├── A001/*.png
│   └── A002/*.png
├── unknown/
│   └── unknown_sign_001.png
└── manifest.csv
```

Le `manifest.csv` du test doit contenir `image_path,class_label,script,artifact_id,source,reviewer,review_status`. Les chemins sont relatifs au dossier d'évaluation, par exemple `known/A001/photo.png` ou `unknown/unknown_sign_001.png`. Pour les inconnus, `class_label` doit être `UNKNOWN`, `OOD` ou `UNSEEN`. Utilisez un `artifact_id` inédit par rapport au manifeste d'entraînement. Les métadonnées de revue sont déclaratives : l'identité du relecteur n'est pas authentifiée par le script.

Lancer :

```powershell
python evaluate_independent_glyphs.py --script maya_classical
```

Le rapport JSON fournit l'acceptation des signes connus, la justesse avec abstention, le taux de rejet des inconnus et le taux de faux acceptés observé. Les valeurs dépendent de ce test précis ; elles ne garantissent pas le comportement futur. Si le modèle n'a pas de calibration, la règle de rejet renverra prudemment les signes comme inconnus/incertains.

## 4. Métriques à publier

Ne publiez pas uniquement l'exactitude globale. Rapportez également :

- effectifs par classe, artefact et source ;
- précision/rappel/F1 par classe et macro-F1 ;
- matrice de confusion avec une catégorie `UNKNOWN/ABSTAIN` ;
- taux d'abstention sur signes connus et taux de faux acceptés sur inconnus ;
- couverture et taille des ensembles de prédiction calibrés ;
- intervalles d'incertitude, erreurs par qualité/support/orientation ;
- résultats sur une partition indépendante verrouillée avant les réglages du modèle.

L'évaluateur livré fournit les métriques opérationnelles de rejet de base. Pour une publication, compléter l'analyse statistique et les intervalles de confiance avec une méthodologie préenregistrée.

## 5. Relecture épigraphique

Deux avis concordants documentés sont une étape de processus, pas une preuve automatique. Les spécialistes doivent pouvoir voir l'artefact, le contexte, les éditions, les alternatives, les conventions de translittération et les incertitudes. Consignez les désaccords et une procédure d'arbitrage, sans écraser l'historique.

## 6. Limites d'hébergement

GitHub Pages héberge uniquement les fichiers statiques de `site/`. Il ne peut pas exécuter Flask, OpenCV, PyTorch, le stockage SQLite ni l'analyse d'image serveur. L'espace Pages livré permet de conserver des dossiers localement dans le navigateur, de comparer des hypothèses et d'exporter un journal JSON/CSV. Pour l'IA complète, utilisez l'application Flask en local ou un serveur privé correctement sécurisé. **Ne publiez pas l'API d'écriture sur Internet sans authentification, contrôle d'accès, sauvegardes, limites de débit et politique de confidentialité.**
