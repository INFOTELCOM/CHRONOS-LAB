"""Train a CHRONOS LAB glyph classifier, optionally specialized by writing system.

Specialist dataset layout:
  data/training/<script-key>/<class-name>/*.png
General/legacy layout:
  data/training/<class-name>/*.png

Example: python train_glyph_model.py --script egyptian_hieroglyphs --epochs 20
"""
from __future__ import annotations
import argparse, random, json, math, csv
from pathlib import Path
from datetime import datetime, timezone
import re, unicodedata

import torch
from torch import nn
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, models, transforms
import numpy as np
from PIL import Image

BASE = Path(__file__).resolve().parent
TRAINING_ROOT = BASE / "data" / "training"
MODELS_ROOT = BASE / "models"


def keyify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", value).strip("_") or "general"


def main():
    parser = argparse.ArgumentParser(description="Entraîner un classifieur de glyphes CHRONOS LAB")
    parser.add_argument("--script", default="general", help="Clé d'écriture (ex. egyptian_hieroglyphs, maya_classical, cuneiform). Défaut: general.")
    parser.add_argument("--epochs", type=int, default=18)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--lr", type=float, default=0.0003)
    parser.add_argument("--val-fraction", type=float, default=0.2)
    parser.add_argument("--unknown-threshold", type=float, default=0.60, help="Seuil d'abstention complémentaire entre 0.5 et 0.99.")
    parser.add_argument("--conformal-alpha", type=float, default=0.05, help="Niveau d'erreur marginal visé pour le jeu de calibration connu (ex. 0.05 = 95%%), sous hypothèses statistiques.")
    parser.add_argument("--no-pretrained", action="store_true", help="Ne pas télécharger les poids ImageNet (moins performant au départ)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--require-artifact-groups", action="store_true", help="Refuser l’entraînement si les manifestes ne permettent pas une séparation complète par artefact (recommandé pour les évaluations scientifiques).")
    parser.add_argument("--unknown-dir", default="", help="Dossier optionnel contenant des signes hors classes connues, ex. data/unknown/maya_classical")
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1 or not 0.05 <= args.val_fraction <= 0.5:
        parser.error("epochs et batch-size doivent être positifs; val-fraction doit être entre 0.05 et 0.5")
    if not 0.5 <= args.unknown_threshold <= 0.99:
        parser.error("unknown-threshold doit être entre 0.5 et 0.99")
    if not 0.01 <= args.conformal_alpha <= 0.25:
        parser.error("conformal-alpha doit être compris entre 0.01 et 0.25")
    script_key = keyify(args.script)
    dataset_root = TRAINING_ROOT if script_key == "general" else TRAINING_ROOT / script_key
    output_path = MODELS_ROOT / ("glyph_classifier.pth" if script_key == "general" else f"{script_key}_glyph_classifier.pth")
    random.seed(args.seed); torch.manual_seed(args.seed)
    if not dataset_root.exists():
        raise SystemExit(f"Dossier absent : {dataset_root}\nCréez data/training/{'' if script_key == 'general' else script_key + '/'}<classe>/ puis ajoutez des images annotées.")

    train_transform = transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.RandomAffine(degrees=8, translate=(0.04, 0.04), scale=(0.92, 1.08)),
        transforms.ColorJitter(brightness=0.15, contrast=0.15),
        transforms.RandomCrop(224), transforms.ToTensor(),
        transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225]),
    ])
    eval_transform = transforms.Compose([
        transforms.Resize((224,224)), transforms.ToTensor(),
        transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225]),
    ])
    ds_aug = datasets.ImageFolder(dataset_root, transform=train_transform)
    ds_eval = datasets.ImageFolder(dataset_root, transform=eval_transform)
    if len(ds_aug.classes) < 2:
        raise SystemExit("Il faut au moins 2 classes de glyphes distinctes.")
    by_class = {}
    for i, (_, label) in enumerate(ds_aug.samples): by_class.setdefault(label, []).append(i)
    for label, ids in by_class.items():
        if len(ids) < 5:
            raise SystemExit(f"Classe '{ds_aug.classes[label]}' : {len(ids)} images seulement. Minimum technique recommandé : 5; idéalement plusieurs dizaines d'exemples variés et indépendants.")
    train_ids, val_ids = [], []
    rng = random.Random(args.seed)
    split_strategy = 'random_image_split_fallback'
    manifest_path = dataset_root / 'manifest.csv'
    artifact_by_path = {}
    if manifest_path.exists():
        try:
            with manifest_path.open('r', encoding='utf-8-sig', newline='') as mf:
                for row in csv.DictReader(mf):
                    rel=(row.get('image_path') or '').replace('\\','/')
                    artifact=(row.get('artifact_id') or '').strip()
                    if rel and artifact: artifact_by_path[rel]=artifact
        except (OSError, csv.Error) as exc:
            print(f'⚠ Impossible de lire manifest.csv ({exc}); séparation aléatoire par image.')
    group_to_ids={}; group_to_labels={}; labels_seen=set()
    can_group=bool(artifact_by_path)
    for index,(sample_path,label) in enumerate(ds_aug.samples):
        try: rel=Path(sample_path).resolve().relative_to(dataset_root.resolve()).as_posix()
        except ValueError: rel=Path(sample_path).name
        artifact=artifact_by_path.get(rel)
        if not artifact: can_group=False
        group=artifact or f'__image__{index}'
        group_to_ids.setdefault(group,[]).append(index)
        group_to_labels.setdefault(group,set()).add(label)
        labels_seen.add(label)
    # Split whole artefacts globally, so two signs cropped from one object cannot leak across train/validation.
    if can_group:
        groups=list(group_to_ids); rng.shuffle(groups)
        n_val_groups=max(1,int(round(len(groups)*args.val_fraction)))
        if n_val_groups>=len(groups): n_val_groups=len(groups)-1
        proposed_val=set(groups[:n_val_groups])
        val_labels=set(); train_labels=set()
        for group,labels in group_to_labels.items():
            (val_labels if group in proposed_val else train_labels).update(labels)
        if labels_seen.issubset(val_labels) and labels_seen.issubset(train_labels):
            for group,ids in group_to_ids.items():
                (val_ids if group in proposed_val else train_ids).extend(ids)
            split_strategy='artifact_grouped_global'
        else:
            print('⚠ Séparation globale par artefact impossible sans supprimer une classe d’un des jeux; repli sur une séparation par image, potentiellement optimiste.')
    if not train_ids or not val_ids:
        train_ids, val_ids = [], []
        if manifest_path.exists() and not can_group:
            print('⚠ Manifeste incomplet; séparation par image potentiellement optimiste.')
        for ids in by_class.values():
            ids=list(ids); rng.shuffle(ids)
            n_val=max(1,int(len(ids)*args.val_fraction))
            if n_val>=len(ids): n_val=len(ids)-1
            val_ids.extend(ids[:n_val]); train_ids.extend(ids[n_val:])
        split_strategy='random_image_split_fallback'
    if args.require_artifact_groups and split_strategy != 'artifact_grouped_global':
        raise SystemExit('Barrière scientifique : séparation complète par artefact impossible. Complétez manifest.csv (image_path + artifact_id pour chaque image) ou relancez sans --require-artifact-groups pour un essai exploratoire uniquement.')
    # Reserve a separate calibration slice from the held-out validation partition. If a class
    # has fewer than two held-out examples, calibration is disabled rather than fabricated.
    val_by_class = {}
    for index in val_ids:
        val_by_class.setdefault(ds_eval.samples[index][1], []).append(index)
    model_val_ids, calibration_ids = [], []
    calibration_possible = bool(val_by_class) and all(len(ids) >= 2 for ids in val_by_class.values())
    if calibration_possible:
        for label, ids in val_by_class.items():
            ids = list(ids); rng.shuffle(ids)
            n_cal = max(1, int(round(len(ids) * 0.5)))
            if n_cal >= len(ids): n_cal = len(ids) - 1
            calibration_ids.extend(ids[:n_cal]); model_val_ids.extend(ids[n_cal:])
    else:
        model_val_ids = list(val_ids)
        calibration_ids = []
        print('⚠ Calibration conformelle désactivée : il faut au moins deux images de validation indépendantes par classe.')
    train_loader = DataLoader(Subset(ds_aug, train_ids), batch_size=args.batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(Subset(ds_eval, model_val_ids), batch_size=args.batch_size, shuffle=False, num_workers=0)
    calibration_loader = DataLoader(Subset(ds_eval, calibration_ids), batch_size=args.batch_size, shuffle=False, num_workers=0) if calibration_ids else None
    weights = None if args.no_pretrained else models.ResNet18_Weights.DEFAULT
    try:
        model = models.resnet18(weights=weights)
    except Exception as exc:
        raise SystemExit(f"Téléchargement des poids pré-entraînés impossible : {exc}\nRéessayez avec --no-pretrained si nécessaire.")
    model.fc = nn.Linear(model.fc.in_features, len(ds_aug.classes))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    criterion = nn.CrossEntropyLoss()
    best_acc = -1.0; best_state = None
    print(f"Écriture : {script_key} | classes : {len(ds_aug.classes)} | images : {len(ds_aug)} | train : {len(train_ids)} | validation : {len(val_ids)} | appareil : {device}")
    for epoch in range(args.epochs):
        model.train(); train_loss = 0.0
        for x,y in train_loader:
            x,y=x.to(device),y.to(device); optimizer.zero_grad(set_to_none=True)
            logits=model(x); loss=criterion(logits,y); loss.backward(); optimizer.step(); train_loss += loss.item()*len(y)
        model.eval(); correct=total=0
        with torch.no_grad():
            for x,y in val_loader:
                x,y=x.to(device),y.to(device); pred=model(x).argmax(1); correct += int((pred==y).sum()); total += len(y)
        acc=correct/max(total,1)
        print(f"Époque {epoch+1:02d}/{args.epochs} — perte train {train_loss/max(len(train_ids),1):.4f} — exactitude validation {acc:.1%}")
        if acc > best_acc:
            best_acc=acc; best_state={k:v.detach().cpu().clone() for k,v in model.state_dict().items()}
    # Restore best checkpoint and compute normalized penultimate-layer embeddings on held-out known images.
    model.load_state_dict(best_state); model.eval()
    def embedding_batch(x):
        z = model.avgpool(model.layer4(model.layer3(model.layer2(model.layer1(model.maxpool(model.relu(model.bn1(model.conv1(x)))))))))
        return torch.flatten(z, 1)
    class_vectors = {name: [] for name in ds_aug.classes}
    validation_scores=[]; validation_distances=[]
    train_eval_loader=DataLoader(Subset(ds_eval, train_ids), batch_size=args.batch_size, shuffle=False, num_workers=0)
    # Build class prototypes from the training partition only, using deterministic evaluation transforms.
    with torch.no_grad():
        for x,y in train_eval_loader:
            emb=torch.nn.functional.normalize(embedding_batch(x.to(device)),dim=1)
            for vec,label in zip(emb.cpu().numpy(), y.numpy()): class_vectors[ds_aug.classes[int(label)]].append(vec)
    centroids={}
    for label, vectors in class_vectors.items():
        if vectors:
            center=np.mean(np.stack(vectors),axis=0); norm=float(np.linalg.norm(center))
            if norm: centroids[label]=(center/norm).astype(float).tolist()
    # Calibrate the distance boundary on held-out known images, not the training images.
    with torch.no_grad():
        for x,y in val_loader:
            x=x.to(device); raw_emb=embedding_batch(x); logits=model.fc(raw_emb)
            validation_scores.extend(torch.softmax(logits,dim=1).max(1).values.cpu().tolist())
            emb=torch.nn.functional.normalize(raw_emb,dim=1).cpu().numpy()
            for vec,label in zip(emb,y.numpy()):
                center=np.asarray(centroids[ds_aug.classes[int(label)]],dtype=np.float32)
                validation_distances.append(float(np.linalg.norm(vec-center)))
    # Conformal-style threshold is calibrated on examples not used to select the checkpoint.
    # It controls known-class prediction-set coverage only under exchangeability; it does not
    # provide a universal OOD/unknown-sign guarantee.
    calibration_nonconformity=[]
    with torch.no_grad():
        if calibration_loader is not None:
            for x,y in calibration_loader:
                logits=model(x.to(device)); probs_cal=torch.softmax(logits,dim=1).cpu().numpy()
                for row,label in zip(probs_cal,y.numpy()):
                    calibration_nonconformity.append(float(1.0-row[int(label)]))
    conformal_score_threshold=None
    if calibration_nonconformity:
        sorted_scores=np.sort(np.asarray(calibration_nonconformity,dtype=np.float64))
        rank=min(len(sorted_scores), int(math.ceil((len(sorted_scores)+1)*(1.0-args.conformal_alpha))))
        conformal_score_threshold=float(sorted_scores[max(0,rank-1)])
    # A floor avoids a zero boundary when validation is tiny; this distance remains heuristic.
    ood_distance_threshold=max(0.25, float(np.percentile(validation_distances,99)*1.15)) if validation_distances else None
    unknown_dir=Path(args.unknown_dir) if args.unknown_dir else (BASE/'data'/'unknown'/script_key)
    unknown_results={'available':False,'images':0,'rejection_rate':None,'note':'Ajoutez des exemples de signes absents du corpus dans data/unknown/<script>/ pour mesurer les faux rejets et les inconnus détectés.'}
    if unknown_dir.exists():
        unknown_files=[f for f in unknown_dir.rglob('*') if f.is_file() and f.suffix.lower() in {'.png','.jpg','.jpeg','.webp','.bmp','.tif','.tiff'}]
        rejected=0; unknown_max_scores=[]; unknown_distances=[]
        eval_transform_ood=eval_transform
        with torch.no_grad():
            for path in unknown_files:
                try:
                    with Image.open(path) as im: x=eval_transform_ood(im.convert('RGB')).unsqueeze(0).to(device)
                    raw_emb=embedding_batch(x); emb=torch.nn.functional.normalize(raw_emb,dim=1); logits=model.fc(raw_emb); prob_row=torch.softmax(logits,1)[0]
                    score=float(prob_row.max().item())
                    distances=[float(np.linalg.norm(emb[0].cpu().numpy()-np.asarray(center,dtype=np.float32))) for center in centroids.values()]
                    dist=min(distances) if distances else 0.0
                    conformal_count=sum((1.0-float(v)) <= conformal_score_threshold for v in prob_row.cpu().tolist()) if conformal_score_threshold is not None else 0
                    is_rejected=(score < args.unknown_threshold) or (ood_distance_threshold is not None and dist > ood_distance_threshold) or (conformal_score_threshold is None) or (conformal_count != 1)
                    rejected += int(is_rejected); unknown_max_scores.append(score); unknown_distances.append(dist)
                except Exception as exc: print(f"⚠ Exemple inconnu illisible {path}: {exc}")
        unknown_results={'available':True,'images':len(unknown_max_scores),'rejected':rejected,
                         'rejection_rate':round(rejected/max(1,len(unknown_max_scores)),4),
                         'false_acceptance_rate':round(1.0-rejected/max(1,len(unknown_max_scores)),4),
                         'mean_max_score':round(float(np.mean(unknown_max_scores)),4) if unknown_max_scores else None,
                         'mean_nearest_centroid_distance':round(float(np.mean(unknown_distances)),4) if unknown_distances else None,
                         'note':'Mesure exploratoire sur les inconnus fournis avec la règle d’abstention de production; ne garantit pas le rejet de futurs signes inconnus.'}
    MODELS_ROOT.mkdir(parents=True, exist_ok=True)
    torch.save({'state_dict':best_state,'classes':ds_aug.classes,'trained_at':datetime.now(timezone.utc).isoformat(),
                'validation_accuracy':round(best_acc,4),'epochs':args.epochs,'num_images':len(ds_aug),
                'train_images':len(train_ids),'validation_images':len(val_ids),'architecture':'torchvision.resnet18',
                'pretrained_imagenet':not args.no_pretrained,'script':script_key,
                'unknown_threshold':args.unknown_threshold, 'class_centroids':centroids, 'split_strategy':split_strategy,
                'ood_distance_threshold':ood_distance_threshold, 'conformal_alpha':args.conformal_alpha if conformal_score_threshold is not None else None,
                'conformal_score_threshold':conformal_score_threshold, 'calibration_count':len(calibration_nonconformity),
                'open_set_validation':{'known_validation_images':len(val_ids),'known_score_p05':round(float(np.percentile(validation_scores,5)),4) if validation_scores else None,
                                       'known_distance_p99':round(float(np.percentile(validation_distances,99)),4) if validation_distances else None,
                                       'unknown_set':unknown_results},
                'warning':'Le rejet des inconnus est probabiliste et ne peut pas garantir la détection de tous les signes inconnus. Validation indicative; séparer par artefact/source et tester des inconnus indépendants.'}, output_path)
    report_path=BASE/'data'/f'training_report_{script_key}.json'; report_path.parent.mkdir(parents=True,exist_ok=True)
    report_path.write_text(json.dumps({'script':script_key,'validation_accuracy':best_acc,'known_validation_images':len(val_ids),'split_strategy':split_strategy,
                                       'ood_distance_threshold':ood_distance_threshold,'unknown_validation':unknown_results,
                                       'conformal':{'available':conformal_score_threshold is not None,'alpha':args.conformal_alpha if conformal_score_threshold is not None else None,'score_threshold':conformal_score_threshold,'calibration_count':len(calibration_nonconformity),'note':'Couverture des classes connues sous hypothèses d’échangeabilité; ne garantit pas le rejet de tout signe inconnu.'},
                                       'warning':'Aucune garantie universelle sur les inconnus arbitraires; tester sur des objets indépendants et faire relire les erreurs.'},ensure_ascii=False,indent=2),encoding='utf-8')
    print(f"\nModèle enregistré : {output_path}\nExactitude validation : {best_acc:.1%}\nSéparation : {split_strategy}\nRapport : {report_path}")
    print(f"Rejet des signes inconnus : {unknown_results.get('rejection_rate') if unknown_results.get('available') else 'non mesuré (aucun dossier unknown)'}")
    print("Relancez l'application; sélectionnez ensuite cette écriture dans l'analyse d'image.")

if __name__ == '__main__': main()
