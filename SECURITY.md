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


## Authentification et stockage V2

- Les routes privées de l'API et les fichiers téléversés exigent un jeton Bearer opaque, aléatoire et expirant après huit heures.
- Le serveur ne stocke que l'empreinte SHA-256 du jeton ; les mots de passe sont hachés avec Werkzeug.
- La création des comptes est réservée à l'administrateur ; aucune inscription publique ni mot de passe administrateur par défaut.
- Les rôles sont vérifiés côté serveur : admin, researcher, evaluator.
- Les expériences, évaluations et événements d'audit sont stockés côté serveur et associés à l'espace CHRONOS LAB.
- Le jeton du navigateur est conservé dans sessionStorage, pas dans le code public ni dans le dépôt.
- Configure `CHRONOS_BOOTSTRAP_ADMIN_EMAIL`, `CHRONOS_BOOTSTRAP_ADMIN_PASSWORD`, `CHRONOS_ALLOWED_ORIGINS` et un volume persistant `CHRONOS_DATA_DIR` chez l'hébergeur.

### Points de déploiement à vérifier

1. HTTPS obligatoire en production ; ne publie pas l'API en HTTP sur Internet.
2. Le stockage SQLite doit être persistant et sauvegardé. Une seule instance applicative est recommandée pour le déploiement SQLite initial.
3. CORS doit contenir uniquement les origines contrôlées ; CORS n'est pas un mécanisme d'authentification.
4. Les jetons expirent en huit heures ; les sessions expirées doivent se reconnecter.
5. Le bootstrap ne réinitialise pas le mot de passe si l'administrateur existe déjà. Utilise une procédure de changement de mot de passe contrôlée avant production.
6. Cette V2 est conçue pour une équipe dans un espace partagé, pas encore pour plusieurs organisations indépendantes. Les données historiques de l'API sont partagées au sein de cet espace.
