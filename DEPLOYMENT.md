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

**Ne déploie pas directement l'API Flask actuelle sur une URL publique accessible en écriture.** L'API n'a pas encore d'authentification utilisateur, de rôles, de protection contre les abus ni de gestion multi-tenant. Avant un déploiement public du backend, ajouter au minimum authentification robuste, autorisation par dossier, protections CSRF si des cookies sont utilisés, limites de débit, sauvegardes restaurables, journalisation, suppression/export des données, politique de conservation et revue de sécurité. Le site Pages statique est utilisable sans exposer cette API.

## E. Contrôles automatiques

À chaque push/PR, `.github/workflows/tests.yml` vérifie la syntaxe Python et JavaScript et lance les tests API. Le workflow Pages valide le paquet statique puis publie le dossier `site/`.
