# Jeu de test des signes inconnus

Pour évaluer le rejet ouvert d'un modèle, créez un sous-dossier par écriture :

`data/unknown/egyptian_hieroglyphs/`

Ajoutez des images de signes qui ne sont dans aucune classe du corpus d'entraînement correspondant. Ne réutilisez pas des images de validation ou d'entraînement. À l'entraînement, le script calcule le taux de rejet sur ces exemples et l'enregistre dans `data/training_report_<script>.json`.

Un taux de rejet élevé sur ce jeu ne prouve pas que tous les futurs signes inconnus seront détectés. Diversifiez les signes, supports, photographies, dommages, rotations, éclairages et écritures hors domaine; conservez aussi un jeu de test indépendant.
