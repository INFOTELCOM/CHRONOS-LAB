# Corpus d'entraînement CHRONOS LAB

Créez un dossier par écriture et un sous-dossier par classe de signe :

```text
data/training/egyptian_hieroglyphs/A001/*.png
data/training/egyptian_hieroglyphs/A002/*.png
data/training/maya_classical/T501/*.png
```

Pour chaque écriture, copiez `MANIFEST_TEMPLATE.csv` en `manifest.csv` dans son dossier de corpus et adaptez chaque ligne. Les chemins `image_path` sont relatifs au dossier de l'écriture. Les statuts reconnus comme révisés sont `reviewed`, `verified`, `validated` et `expert-reviewed`.

Les champs de provenance sont importants : identifiant de l'objet, source, licence, publication, datation, annotateur, relecteur et état de révision. Une étiquette ne devient pas vraie parce que le CSV est complet : l'audit vérifie la cohérence technique et la traçabilité, pas l'interprétation épigraphique.

Pour mesurer le rejet de signes hors corpus, ajoutez des images qui ne correspondent à aucune classe connue dans `data/unknown/<script-key>/`. Ces exemples doivent être distincts du corpus d'entraînement. Ils servent à mesurer le taux de rejet, pas à prouver une garantie universelle.
