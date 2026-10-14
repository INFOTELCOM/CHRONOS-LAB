"""Evaluate a saved glyph model on a separately curated, artifact-independent test set.

Layout:
  data/independent_eval/<script-key>/known/<class-name>/*.png
  data/independent_eval/<script-key>/unknown/*.{png,jpg,...}
  data/independent_eval/<script-key>/manifest.csv

The manifest must include image_path,class_label,script,artifact_id,source,reviewer,review_status.
The script fails closed when provenance is missing or artifact IDs overlap the training manifest.
It evaluates technical behavior only; it never certifies an epigraphic reading.
"""
from __future__ import annotations
import argparse, csv, json, math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from PIL import Image
import torch
from torchvision import models, transforms

BASE = Path(__file__).resolve().parent
EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff'}
REQUIRED = {'image_path', 'class_label', 'script', 'artifact_id', 'source', 'reviewer', 'review_status'}


def read_manifest(path: Path):
    if not path.exists():
        raise SystemExit(f'Manifeste requis introuvable : {path}')
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        fields = set(reader.fieldnames or [])
        missing = REQUIRED - fields
        if missing:
            raise SystemExit('Colonnes manquantes dans le manifeste : ' + ', '.join(sorted(missing)))
        rows = list(reader)
    result = {}
    for row in rows:
        rel = (row.get('image_path') or '').replace('\\', '/').strip()
        if rel:
            if rel in result:
                raise SystemExit(f'Chemin dupliqué dans le manifeste : {rel}')
            result[rel] = row
    return result


def gather_images(root: Path):
    known = []
    known_root = root / 'known'
    if known_root.exists():
        for class_dir in sorted(p for p in known_root.iterdir() if p.is_dir()):
            known.extend((p, class_dir.name, False) for p in sorted(class_dir.rglob('*')) if p.is_file() and p.suffix.lower() in EXTS)
    unknown_root = root / 'unknown'
    unknown = [(p, 'UNKNOWN', True) for p in sorted(unknown_root.rglob('*')) if p.is_file() and p.suffix.lower() in EXTS] if unknown_root.exists() else []
    return known + unknown


def main():
    parser = argparse.ArgumentParser(description='Évaluer CHRONOS sur des inscriptions indépendantes')
    parser.add_argument('--script', required=True, help='Clé du modèle, ex. maya_classical')
    parser.add_argument('--dataset-dir', default='', help='Dossier test indépendant; défaut data/independent_eval/<script>')
    parser.add_argument('--model', default='', help='Chemin de checkpoint; défaut models/<script>_glyph_classifier.pth')
    parser.add_argument('--output', default='', help='Rapport JSON; défaut data/independent_eval_report_<script>.json')
    args = parser.parse_args()
    script = args.script
    root = Path(args.dataset_dir).resolve() if args.dataset_dir else BASE / 'data' / 'independent_eval' / script
    model_path = Path(args.model).resolve() if args.model else BASE / 'models' / f'{script}_glyph_classifier.pth'
    output = Path(args.output).resolve() if args.output else BASE / 'data' / f'independent_eval_report_{script}.json'
    if not model_path.exists(): raise SystemExit(f'Modèle introuvable : {model_path}')
    manifest = read_manifest(root / 'manifest.csv')
    images = gather_images(root)
    if not images: raise SystemExit('Aucune image trouvée sous known/<classe>/ ou unknown/.')
    train_root = BASE / 'data' / 'training' / script
    train_manifest_path = train_root / 'manifest.csv'
    if not train_manifest_path.exists():
        raise SystemExit(f'Manifeste du corpus d’entraînement requis pour vérifier l’indépendance : {train_manifest_path}')
    train_manifest = read_manifest(train_manifest_path)
    train_artifacts = {str(r.get('artifact_id','')).strip() for r in train_manifest.values() if str(r.get('artifact_id','')).strip()}
    eval_artifacts = set(); missing_metadata = []; checked = []
    for path, label, is_unknown in images:
        rel = path.relative_to(root).as_posix()
        row = manifest.get(rel)
        if row is None:
            missing_metadata.append({'image_path': rel, 'reason': 'missing_manifest_row'}); continue
        artifact = str(row.get('artifact_id','')).strip()
        if not artifact or not str(row.get('source','')).strip() or not str(row.get('reviewer','')).strip() or str(row.get('review_status','')).strip().lower() not in {'reviewed','verified','validated','expert-reviewed'}:
            missing_metadata.append({'image_path': rel, 'reason': 'incomplete_provenance_or_review_metadata'}); continue
        if artifact in train_artifacts:
            missing_metadata.append({'image_path': rel, 'reason': 'artifact_id_overlaps_training_corpus'}); continue
        if str(row.get('class_label','')).strip() != label and not (is_unknown and str(row.get('class_label','')).strip().upper() in {'UNKNOWN','OOD','UNSEEN'}):
            missing_metadata.append({'image_path': rel, 'reason': 'manifest_label_does_not_match_directory'}); continue
        eval_artifacts.add(artifact); checked.append((path, label, is_unknown, row))
    if missing_metadata:
        raise SystemExit('La barrière de provenance a échoué. Corrigez le manifeste avant l’évaluation :\n' + json.dumps(missing_metadata[:30], ensure_ascii=False, indent=2))
    if len(eval_artifacts) < 2:
        raise SystemExit('Il faut au moins deux identifiants d’artefact indépendants pour une évaluation exploratoire.')
    checkpoint = torch.load(model_path, map_location='cpu', weights_only=False)
    classes = checkpoint.get('classes') or []
    if not classes: raise SystemExit('Le checkpoint ne contient aucune classe.')
    model = models.resnet18(weights=None); model.fc = torch.nn.Linear(model.fc.in_features, len(classes))
    model.load_state_dict(checkpoint['state_dict']); model.eval()
    tfm = transforms.Compose([transforms.Resize((224,224)), transforms.ToTensor(), transforms.Normalize([.485,.456,.406],[.229,.224,.225])])
    centroids = checkpoint.get('class_centroids') or {}
    threshold = float(checkpoint.get('unknown_threshold', .60))
    dist_limit = checkpoint.get('ood_distance_threshold')
    conformal_cutoff = checkpoint.get('conformal_score_threshold')
    results=[]
    with torch.no_grad():
        for path, true_label, is_unknown, row in checked:
            try:
                with Image.open(path) as image: x=tfm(image.convert('RGB')).unsqueeze(0)
                feat=model.avgpool(model.layer4(model.layer3(model.layer2(model.layer1(model.maxpool(model.relu(model.bn1(model.conv1(x)))))))))
                emb=torch.flatten(feat,1)[0]
                probs=torch.softmax(model.fc(emb.unsqueeze(0))[0],dim=0)
                top_i=int(torch.argmax(probs)); pred=classes[top_i]; score=float(probs[top_i])
                normalized=torch.nn.functional.normalize(emb.detach(),dim=0).numpy()
                distances=[]
                for name, center in centroids.items():
                    arr=np.asarray(center,dtype=np.float32); norm=float(np.linalg.norm(arr))
                    if norm: distances.append((float(np.linalg.norm(normalized-arr/norm)),name))
                nearest_distance, nearest_class = min(distances) if distances else (None,None)
                conformal_set=[classes[i] for i,v in enumerate(probs.tolist()) if conformal_cutoff is not None and (1-float(v))<=float(conformal_cutoff)]
                reject=(score < threshold or conformal_cutoff is None or len(conformal_set)!=1 or (dist_limit is not None and nearest_distance is not None and nearest_distance>float(dist_limit)) or (nearest_class is not None and nearest_class != pred))
                final='UNKNOWN' if reject else pred
                results.append({'image_path':path.relative_to(root).as_posix(),'artifact_id':row['artifact_id'],'true_label':'UNKNOWN' if is_unknown else true_label,'predicted_class':pred,'system_decision':final,'max_score':round(score,6),'nearest_prototype_distance':round(nearest_distance,6) if nearest_distance is not None else None,'conformal_set_size':len(conformal_set),'rejected':bool(reject)})
            except Exception as exc:
                results.append({'image_path':path.relative_to(root).as_posix(),'artifact_id':row['artifact_id'],'true_label':'UNKNOWN' if is_unknown else true_label,'predicted_class':None,'system_decision':'EVALUATION_ERROR','rejected':None,'error':str(exc)})
    known=[r for r in results if r['true_label']!='UNKNOWN' and r['system_decision']!='EVALUATION_ERROR']
    unknown=[r for r in results if r['true_label']=='UNKNOWN' and r['system_decision']!='EVALUATION_ERROR']
    correct=sum(r['system_decision']==r['true_label'] for r in known)
    known_accepted=sum(r['system_decision']!='UNKNOWN' for r in known)
    unknown_accepted=sum(r['system_decision']!='UNKNOWN' for r in unknown)
    per_class={}
    for cls in sorted(set(r['true_label'] for r in known)):
        rows=[r for r in known if r['true_label']==cls]
        per_class[cls]={'n':len(rows),'correct_and_accepted':sum(r['system_decision']==cls for r in rows),'rejected':sum(r['system_decision']=='UNKNOWN' for r in rows),'accuracy_with_abstention':round(sum(r['system_decision']==cls for r in rows)/max(1,len(rows)),4)}
    report={'report_type':'INDEPENDENT_GLYPH_EVALUATION','created_at':datetime.now(timezone.utc).isoformat(),'script':script,'model_path':str(model_path),'dataset_dir':str(root),'independent_artifacts':len(eval_artifacts),'known_images':len(known),'unknown_images':len(unknown),'known_correct_and_accepted':correct,'known_accuracy_with_abstention':round(correct/max(1,len(known)),4),'known_acceptance_rate':round(known_accepted/max(1,len(known)),4),'unknown_rejection_rate':round((len(unknown)-unknown_accepted)/max(1,len(unknown)),4) if unknown else None,'unknown_false_acceptance_rate':round(unknown_accepted/max(1,len(unknown)),4) if unknown else None,'per_class':per_class,'images':results,'scientific_status':'TECHNICAL_EVALUATION_ONLY_NOT_SCIENTIFIC_CERTIFICATION','automatic_scientific_validation':False,'caveats':['Manifest metadata is self-declared; this script cannot authenticate reviewers or source rights.','An artifact-group split prevents known artifact leakage only when artifact IDs are accurate.','Results apply to this held-out set and do not guarantee performance on future unknown signs.','Review failures and image errors before interpreting aggregate metrics.']}
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('report_type','independent_artifacts','known_images','unknown_images','known_accuracy_with_abstention','known_acceptance_rate','unknown_rejection_rate','unknown_false_acceptance_rate','scientific_status')},ensure_ascii=False,indent=2))
    print(f'Rapport complet : {output}')

if __name__=='__main__': main()
