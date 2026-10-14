# CHRONOS LAB — sécurité et limites de la V2

## Ce qui est livré dans l'interface statique

- Tableau de bord local et compteurs issus de l'espace documentaire du navigateur.
- Fiches locales d'expériences et de résultats d'évaluation.
- Export JSON et CSV ; impression navigateur pour enregistrer un PDF.
- Interface d'import d'image qui appelle la route existante `POST /api/analyze-image`.
- Contrôle facultatif des routes de santé, de modèles et de statistiques du backend.
- Avertissements explicites sur les métriques saisies manuellement et l'absence de certification scientifique automatique.

Les fiches V2 sont stockées dans le `localStorage` du navigateur. Elles ne sont ni synchronisées entre appareils ni sauvegardées automatiquement. N'y conserve pas de données sensibles.

## Avant d'exposer Flask sur Internet

La V2 ne fournit pas encore un système d'authentification multi-utilisateur complet. Ne publie pas une instance Flask avec des routes d'écriture accessibles à tous. Avant un déploiement partagé, implémenter et tester :

1. Authentification côté serveur (par exemple OIDC avec un fournisseur d'identité maintenu).
2. Rôles et permissions vérifiés à chaque requête par le backend, jamais seulement dans l'interface.
3. Isolation par espace de travail et vérification de propriété de chaque ressource.
4. HTTPS, CORS limité aux origines nécessaires et limitation de débit.
5. Validation stricte des entrées, limites de taille et types de fichiers, noms générés par le serveur.
6. Gestion des secrets par variables d'environnement ou gestionnaire de secrets, jamais dans Git ou dans le code du navigateur.
7. Journal d'audit côté serveur, sauvegardes chiffrées si nécessaire, rétention et test de restauration.
8. Protection CSRF si des cookies de session sont utilisés, expiration/révocation de session et politique de mots de passe ou MFA selon le fournisseur.
9. Analyse des dépendances, tests de sécurité et vérification des logs avant mise en production.

## Déploiement

GitHub Pages ne peut héberger que les ressources statiques du dossier `site/`. Les routes d'analyse, OpenCV, SQLite et les modèles IA s'exécutent dans le backend Flask, qui doit être hébergé séparément avec un stockage persistant et une configuration de sécurité adaptée.

## Validité scientifique

Les scores enregistrés dans les fiches de validation sont des valeurs déclarées par l'utilisateur ; la V2 ne les recalcule pas à partir des prédictions. Pour une évaluation vérifiable, conserver le jeu de test, les étiquettes de référence, la version du code et du modèle, le protocole, les prédictions brutes et le rapport de calcul. Une métrique ou une sortie IA n'est pas une certification de lecture épigraphique.
