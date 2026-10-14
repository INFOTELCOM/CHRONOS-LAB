# Mise en ligne de CHRONOS LAB

## A. Interface web GitHub Pages

Le dossier `site/` contient une interface statique installable comme PWA. Elle fonctionne dans le navigateur pour créer et comparer des hypothèses, consigner des avis, maintenir un journal de hachages et exporter/importer des dossiers JSON/CSV. Les données sont stockées dans le navigateur courant ; elles ne sont pas automatiquement partagées entre appareils.

### Publier sur GitHub

**Méthode automatique (recommandée) :**

1. Installe Git et GitHub CLI (`gh`) sur ton ordinateur Windows.
2. Ouvre PowerShell et connecte le compte qui a les droits sur `INFOTELCOM` : `gh auth login`.
3. Configure ton identité Git si nécessaire : `git config --global user.name "Ton nom"` puis `git config --global user.email "ton-email@example.com"`.
4. Décompresse l’archive, ouvre PowerShell dans le dossier `chronos_lab/`, puis exécute :

   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass
   .\publish-to-github.ps1
   ```

5. Tape `PUBLIC` après avoir vérifié que tu souhaites bien publier le code source publiquement. Le dépôt `INFOTELCOM/CHRONOS-LAB` existe déjà : le script l’utilise, initialise le dépôt local et pousse la branche `main`. Il ne force pas l’écrasement si le dépôt distant n’est plus vide.
6. Vérifie l’onglet **Actions**. Le workflow `Deploy CHRONOS LAB web workspace` doit être vert. Si nécessaire, ouvre **Settings → Pages → Build and deployment → Source → GitHub Actions**.

L’adresse prévue est `https://infotelcom.github.io/CHRONOS-LAB/`.

**Important :** le dépôt GitHub est déjà créé et actuellement vide. Le script est adapté à ce cas précis. Si un autre commit est ajouté au dépôt distant avant l’exécution, le push sera refusé sans écraser l’historique.

Le workflow déploie uniquement `site/` ; les données locales, corpus, modèles, images et base SQLite sont ignorés et ne sont pas publiés par Pages.

## B. Utiliser l'application complète avec Python

La page Pages ne peut pas exécuter le serveur Python. Pour toutes les fonctions d'analyse d'image, OpenCV, calendrier, NASA/JPL et modèle PyTorch, lance le backend localement :

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```

Puis ouvre `http://127.0.0.1:5000`.

## C. Docker (usage privé ou réseau de confiance)

```bash
docker compose up --build
```

L'application sera accessible sur `http://localhost:8000` et conservera ses données dans un volume Docker. Le Dockerfile utilise Gunicorn et un répertoire de données configurable.

## D. Avant de rendre le backend public

Le backend V2 inclut une authentification par jeton, des rôles et des journaux d'audit pour les routes privées. Avant un déploiement public, conserve HTTPS, limite CORS aux origines maîtrisées, configure le disque persistant, protège les secrets, surveille les abus et teste régulièrement la restauration des sauvegardes. La protection multi-organisations indépendante n'est pas encore implémentée : ne présente pas l'espace partagé CHRONOS LAB comme une isolation entre entreprises.

## E. Contrôles automatiques

À chaque push/PR, `.github/workflows/tests.yml` vérifie la syntaxe Python et JavaScript et lance les tests API. Le workflow Pages valide le paquet statique puis publie le dossier `site/`.


## F. Backend avec comptes chercheurs et stockage partagé (V2)

La V2 utilise le backend pour stocker les expériences et évaluations dans SQLite. Les données ne dépendent donc plus du navigateur qui les a créées. Les tables sont rattachées à l'espace de travail CHRONOS LAB. Les fiches V2 ne doivent pas être utilisées avec plusieurs instances de base SQLite non partagée.

### Variables d'environnement obligatoires en production

Configure-les dans le panneau privé de l'hébergeur, jamais dans le dépôt public :

- `CHRONOS_BOOTSTRAP_ADMIN_EMAIL` : adresse du premier administrateur.
- `CHRONOS_BOOTSTRAP_ADMIN_PASSWORD` : mot de passe unique d'au moins 14 caractères. Il n'est utilisé qu'à la création initiale du compte ; changer la variable ne remplace pas le mot de passe d'un compte déjà créé.
- `CHRONOS_ALLOWED_ORIGINS=https://infotelcom.github.io` : autorise uniquement l'interface GitHub Pages. Ajoute une autre origine seulement si tu la contrôles.
- `CHRONOS_DATA_DIR=/var/data` : dossier persistant pour la base SQLite et les fichiers.

Le premier administrateur est créé automatiquement au démarrage lorsque les deux variables de bootstrap sont valides. Si le compte existe déjà, le démarrage ne réinitialise pas son mot de passe. Utilise un volume disque persistant et des sauvegardes testées ; le volume éphémère d'un hébergeur ne convient pas.

### Première connexion et gestion des comptes

1. Déploie le backend Docker/Gunicorn sur un hébergeur Python avec HTTPS et un disque persistant.
2. Configure les quatre variables ci-dessus, puis redémarre le service.
3. Dans [CHRONOS LAB V2](https://infotelcom.github.io/CHRONOS-LAB/v2.html), ouvre « Données & connexion », colle l'URL HTTPS du backend, puis enregistre-la.
4. Connecte-toi avec l'e-mail et le mot de passe admin définis dans les variables privées.
5. Depuis « Accès au laboratoire », crée les comptes chercheurs et évaluateurs. Le formulaire public d'inscription est volontairement absent.

### Rôles

- **admin** : crée les comptes, consulte le journal d'audit et gère les fiches de l'espace.
- **researcher** : crée des expériences et des évaluations ; peut supprimer uniquement ses propres expériences.
- **evaluator** : consulte les expériences et peut consigner des évaluations, sans créer d'expérience.
- Les jetons expirent après 8 heures et sont stockés dans `sessionStorage` du navigateur. Déconnexion = révocation du jeton côté serveur.


### Studio de recherche avancé

La V2 ajoute les routes privées suivantes pour le carnet de laboratoire, les hypothèses, les métadonnées de jeux de données et les tâches :

- `GET /api/v2/research-artifacts?type=note|hypothesis|dataset|task` : liste les ressources partagées du workspace.
- `POST /api/v2/research-artifacts` : crée une ressource avec `type` et `payload`.
- `PUT /api/v2/research-artifacts/<id>` : modifie une ressource créée par l'utilisateur, ou par l'admin.
- `DELETE /api/v2/research-artifacts/<id>` : supprime une ressource créée par l'utilisateur, ou par l'admin.

Les actions de création, modification et suppression sont ajoutées au journal d'audit. Les évaluateurs peuvent lire les ressources, mais pas les créer/modifier/supprimer. Les métadonnées et empreintes SHA-256 des jeux de données peuvent être partagées ; le calcul de l'empreinte dans le navigateur ne téléverse pas le fichier lui-même. Sans session backend, l'interface garde un mode local. L'import local vers le serveur est une action explicite et conserve les originaux dans le navigateur.

### Limites à respecter

La base initiale est conçue pour une équipe CHRONOS LAB dans un espace partagé ; elle ne propose pas encore la création d'organisations indépendantes avec administrateurs séparés. Les comptes d'une même équipe partagent les données de recherche. Pour une plateforme multi-organisations, ajouter une gestion de tenants et tester l'isolation de toutes les tables existantes. Le backend exige désormais une authentification sur les routes privées de l'API et les fichiers téléversés ; les routes de calcul/publication de statut restent accessibles sans connexion.

Les scores de précision, rappel et F1 saisis dans l'interface restent des valeurs déclaratives. Cette couche d'authentification ne constitue pas une validation scientifique automatique.
