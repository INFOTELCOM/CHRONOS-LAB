$ErrorActionPreference = 'Stop'
$repo = 'INFOTELCOM/CHRONOS-LAB'
$remote = "https://github.com/$repo.git"
Write-Host 'CHRONOS LAB — publication vers le dépôt GitHub existant + GitHub Pages' -ForegroundColor Cyan
Write-Host 'Le dépôt sera public. Vérifie qu’aucun corpus privé, image sous licence restrictive, secret, clé API ou base personnelle ne se trouve dans le dossier.' -ForegroundColor Yellow
$confirmation = Read-Host "Tape PUBLIC pour publier le code dans $repo"
if ($confirmation -cne 'PUBLIC') { Write-Host 'Publication annulée.'; exit 1 }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git est absent. Installe Git avant de relancer ce script.' }
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw 'GitHub CLI (gh) est absent. Installe GitHub CLI avant de relancer ce script.' }
gh auth status
if ($LASTEXITCODE -ne 0) { throw 'Connecte GitHub CLI avec gh auth login sur le compte qui a les droits sur INFOTELCOM puis relance.' }
if (-not (git config user.name)) { throw 'Configure Git avec git config --global user.name "Votre nom".' }
if (-not (git config user.email)) { throw 'Configure Git avec git config --global user.email "votre-email@example.com".' }
if (-not (Test-Path '.github/workflows/pages.yml') -or -not (Test-Path 'site/index.html')) { throw 'Lance ce script depuis la racine du dossier chronos_lab extrait de l’archive.' }
if (Test-Path '.git') { throw 'Un dossier .git existe déjà. Pour éviter d’écraser un dépôt, utilise un dossier neuf extrait du ZIP.' }

# Le dépôt INFOTELCOM/CHRONOS-LAB a déjà été créé. Ce script l’utilise au lieu d’essayer de le recréer.
$repoExists = $true
gh repo view $repo *> $null
if ($LASTEXITCODE -ne 0) { $repoExists = $false }
if (-not $repoExists) {
    gh repo create $repo --public --description 'CHRONOS LAB — exploration épigraphique, incertitudes explicites et traçabilité documentaire'
    if ($LASTEXITCODE -ne 0) { throw 'Création du dépôt impossible. Vérifie le compte GitHub actif et les permissions sur INFOTELCOM.' }
}

git init -b main
git add -A
Write-Host 'Fichiers préparés pour publication :' -ForegroundColor Cyan
git status --short
git commit -m 'Publish CHRONOS LAB research workspace and Pages site'
if ($LASTEXITCODE -ne 0) { throw 'Commit Git impossible. Vérifie git status et la configuration Git.' }
git remote add origin $remote
if ($LASTEXITCODE -ne 0) { throw 'Impossible de configurer le dépôt distant GitHub.' }
# Le dépôt actuel est vide. Si quelqu’un y a ajouté des commits entre-temps, le push sera refusé sans écraser l’historique.
git push -u origin main
if ($LASTEXITCODE -ne 0) { throw 'Le push a échoué. Si le dépôt distant n’est plus vide, clone-le et fusionne les historiques avant de réessayer.' }
try {
    gh api --method POST "repos/$repo/pages" -f build_type=workflow | Out-Null
} catch {
    Write-Host 'Si Pages n’est pas activé automatiquement : Settings > Pages > Build and deployment > Source > GitHub Actions.' -ForegroundColor Yellow
}
Write-Host 'Code poussé. Le workflow GitHub Actions va tester le projet et déployer le site.' -ForegroundColor Green
Write-Host 'Vérifie l’onglet Actions et attends le succès de Deploy CHRONOS LAB web workspace.'
Write-Host 'URL prévue : https://infotelcom.github.io/CHRONOS-LAB/' -ForegroundColor Cyan
Write-Host 'Important : Pages héberge seulement l’interface statique. Flask/PyTorch nécessitent un backend séparé.' -ForegroundColor Yellow
