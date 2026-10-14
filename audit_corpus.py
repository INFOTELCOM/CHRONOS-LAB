"""Audit technique and traçabilité des corpus CHRONOS LAB (sans certification scientifique)."""
from __future__ import annotations
import argparse, csv, hashlib, json
from collections import defaultdict
from pathlib import Path
from PIL import Image, UnidentifiedImageError, ImageOps
import numpy as np

BASE = Path(__file__).resolve().parent
EXTS = {'.png','.jpg','.jpeg','.webp','.bmp','.tif','.tiff'}
MANIFEST_FIELDS = ['image_path','class_label','script','artifact_id','source','source_url','license','publication','dating','annotator','reviewer','review_status','label_confidence','notes']


def perceptual_hash(path: Path):
    """64-bit DCT pHash; flags near-duplicates, not a proof that images are duplicates."""
    import cv2
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert('L').resize((32,32))
        arr = np.asarray(im, dtype=np.float32)
    dct = cv2.dct(arr)
    low = dct[:8,:8].copy(); values = low.flatten()[1:]
    median = float(np.median(values))
    bits = (low.flatten() > median)
    out = 0
    for bit in bits: out = (out << 1) | int(bit)
    return out


def hamming(a, b): return int((a ^ b).bit_count())


def difference_hash(path: Path):
    """64-bit dHash catches some resized/recompressed copies missed by exact hashes."""
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert('L').resize((9, 8))
        arr = np.asarray(im, dtype=np.uint8)
    bits = arr[:, 1:] > arr[:, :-1]
    value = 0
    for bit in bits.flatten(): value = (value << 1) | int(bit)
    return value


def normalized_thumbnail(path: Path):
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert('L').resize((64, 64))
        arr = np.asarray(im, dtype=np.float32)
    arr = arr - arr.mean()
    norm = float(np.linalg.norm(arr))
    return arr / norm if norm else arr


def main():
    p = argparse.ArgumentParser(description='Audit technique, doublons visuels et provenance du corpus CHRONOS LAB')
    p.add_argument('--script', default='general', help='Clé du corpus, ex. maya_classical')
    p.add_argument('--near-duplicate-distance', type=int, default=8, help='Distance pHash max (0-64) pour signaler un doublon visuel possible')
    args = p.parse_args()
    root = BASE / 'data' / 'training'
    if args.script != 'general': root /= args.script
    if not root.exists(): raise SystemExit(f'Corpus introuvable : {root}')
    classes = sorted(x for x in root.iterdir() if x.is_dir())
    report = {'dataset': str(root.relative_to(BASE)), 'classes': [], 'errors': [], 'exact_duplicates': [],
              'perceptual_duplicate_candidates': [], 'cross_class_visual_conflicts': [], 'manifest': {}, 'recommendations': []}
    hashes = defaultdict(list); phashes=[]; total=0; all_paths=[]
    for folder in classes:
        files = sorted(x for x in folder.rglob('*') if x.is_file() and x.suffix.lower() in EXTS)
        item = {'class': folder.name, 'images': len(files), 'min_dimension': None, 'max_dimension': None, 'files': []}
        widths=[]; heights=[]
        for f in files:
            total += 1; rel=str(f.relative_to(root)); all_paths.append((rel,folder.name))
            try:
                with Image.open(f) as im: im.verify()
                with Image.open(f) as im: im=ImageOps.exif_transpose(im); w,h=im.size; widths.append(w); heights.append(h)
                digest=hashlib.sha256(f.read_bytes()).hexdigest(); hashes[digest].append(rel)
                ph=perceptual_hash(f); dh=difference_hash(f); thumb=normalized_thumbnail(f)
                phashes.append((ph,dh,thumb,rel,folder.name,digest))
                item['files'].append({'path':rel,'width':w,'height':h,'sha256':digest,'perceptual_hash':f'{ph:016x}','difference_hash':f'{dh:016x}'})
            except (UnidentifiedImageError, OSError, ValueError) as exc:
                report['errors'].append({'file':rel,'error':str(exc)})
        if widths: item['min_dimension']=[min(widths),min(heights)]; item['max_dimension']=[max(widths),max(heights)]
        if len(files)<5: report['recommendations'].append(f"Classe {folder.name}: {len(files)} image(s); viser plusieurs dizaines d'exemples indépendants si possible.")
        item['files']=item['files'][:1000]; report['classes'].append(item)
    report['class_count']=len(classes); report['image_count']=total
    report['exact_duplicates']=[{'sha256':h,'files':paths} for h,paths in hashes.items() if len(paths)>1]
    # Pairwise near duplicate search; cap quadratic work for very large corpora.
    if len(phashes) <= 5000:
        for i in range(len(phashes)):
            hi, dhi, ti, pi, ci, di = phashes[i]
            for hj, dhj, tj, pj, cj, dj in phashes[i+1:]:
                if di == dj: continue
                pdist=hamming(hi,hj); ddist=hamming(dhi,dhj)
                # Correlation on normalized grayscale thumbnails catches close visual copies
                # after resize/recompression. It remains a candidate detector, not semantic proof.
                corr=float(np.sum(ti*tj)) if ti.shape == tj.shape else -1.0
                if pdist <= args.near_duplicate_distance or ddist <= 10 or corr >= 0.94:
                    methods=[]
                    if pdist <= args.near_duplicate_distance: methods.append('pHash')
                    if ddist <= 10: methods.append('dHash')
                    if corr >= 0.94: methods.append('thumbnail_correlation')
                    entry={'file_a':pi,'class_a':ci,'file_b':pj,'class_b':cj,
                           'phash_distance':pdist,'dhash_distance':ddist,'thumbnail_correlation':round(corr,4),
                           'signals':methods,'classification':'POSSIBLE_VISUAL_DUPLICATE_REQUIRES_HUMAN_CHECK'}
                    report['perceptual_duplicate_candidates'].append(entry)
                    if ci != cj: report['cross_class_visual_conflicts'].append(entry)
    else:
        report['recommendations'].append('Plus de 5 000 images : comparaison exhaustive pair-à-pair omise pour maîtriser le coût; utiliser un index de voisinage visuel dédié.')
    manifest_path = root / 'manifest.csv'
    if not manifest_path.exists():
        report['manifest']={'present':False,'missing_fields':MANIFEST_FIELDS,'rows':0,'errors':['manifest.csv absent']}
        report['recommendations'].append('Ajouter manifest.csv avec provenance, licence, identifiant d’artefact, annotateur et état de révision pour chaque image.')
    else:
        rows=[]; manifest_errors=[]
        try:
            with manifest_path.open('r',encoding='utf-8-sig',newline='') as f:
                reader=csv.DictReader(f); fields=reader.fieldnames or []
                missing=[x for x in MANIFEST_FIELDS if x not in fields]
                for n,row in enumerate(reader,start=2):
                    rel=(row.get('image_path') or '').replace('\\','/')
                    if not rel: manifest_errors.append({'row':n,'error':'image_path vide'}); continue
                    target=(root / rel).resolve()
                    if root.resolve() not in target.parents:
                        manifest_errors.append({'row':n,'image_path':rel,'error':'chemin hors du corpus'}); continue
                    if not target.exists(): manifest_errors.append({'row':n,'image_path':rel,'error':'fichier référencé introuvable'})
                    if row.get('class_label','').strip() and row.get('class_label','').strip() != Path(rel).parent.name:
                        manifest_errors.append({'row':n,'image_path':rel,'error':'class_label ne correspond pas au dossier de classe'})
                    if row.get('review_status','').strip().lower() not in ('reviewed','verified','validated','expert-reviewed'):
                        manifest_errors.append({'row':n,'image_path':rel,'warning':'annotation non marquée comme révisée par une personne compétente'})
                    for field in ('class_label','script','artifact_id','source','license','publication','annotator','reviewer'):
                        if not (row.get(field) or '').strip(): manifest_errors.append({'row':n,'image_path':rel,'warning':f'champ {field} vide'})
                    rows.append(row)
                seen={}
                for row in rows:
                    rel=(row.get('image_path') or '').replace('\\','/')
                    if rel in seen: manifest_errors.append({'image_path':rel,'error':'entrée répétée dans manifest.csv'})
                    seen[rel]=1
                missing_from_manifest=sorted(set(p for p,_ in all_paths)-set(seen))
                unknown_in_manifest=sorted(set(seen)-set(p for p,_ in all_paths))
                report['manifest']={'present':True,'rows':len(rows),'fields':fields,'missing_fields':missing,'errors':manifest_errors,
                                    'images_missing_from_manifest':missing_from_manifest[:500], 'manifest_paths_missing_from_disk':unknown_in_manifest[:500]}
        except (OSError,csv.Error) as exc:
            report['manifest']={'present':True,'rows':0,'errors':[str(exc)]}
    if len(classes)<2: report['recommendations'].append('Créer au moins deux classes distinctes.')
    if report['exact_duplicates']: report['recommendations'].append('Retirer les doublons exacts ou justifier leur présence.')
    if report['perceptual_duplicate_candidates']: report['recommendations'].append('Inspecter manuellement les quasi-doublons visuels signalés; le pHash est un détecteur de candidats, pas un juge sémantique.')
    if report['cross_class_visual_conflicts']: report['recommendations'].append('Vérifier les images visuellement proches dans des classes différentes : étiquette erronée, variante légitime ou signe ambigu possibles.')
    report['recommendations'].append('Le script ne peut pas certifier la vérité épigraphique d’une étiquette. Le pHash, le dHash et la corrélation détectent des candidats de doublons, jamais tous les doublons sémantiques; conserver sources, contre-lectures, désaccords et historique.')
    report['recommendations'].append('Séparer train/validation/test par artefact ou source, pas par recadrage aléatoire de la même photo.')
    manifest_ok=bool(report['manifest'].get('present')) and not report['manifest'].get('missing_fields') and not report['manifest'].get('images_missing_from_manifest') and not report['manifest'].get('manifest_paths_missing_from_disk') and not any('error' in e for e in report['manifest'].get('errors',[]))
    reviewed_ok=bool(report['manifest'].get('present')) and not any('annotation non marquée' in e.get('warning','').lower() or 'reviewer' in e.get('warning','').lower() for e in report['manifest'].get('errors',[]))
    report['technical_gate']={'status':'PASS_TECHNICAL_CHECKS_ONLY' if not report['errors'] and manifest_ok and reviewed_ok and len(classes)>=2 and total>0 and not report['exact_duplicates'] and not report['perceptual_duplicate_candidates'] else 'BLOCKED_TECHNICAL_OR_PROVENANCE_ISSUES', 'images_readable':not bool(report['errors']), 'manifest_complete':manifest_ok, 'review_metadata_warnings_absent':reviewed_ok, 'duplicate_candidates_clear':not bool(report['exact_duplicates'] or report['perceptual_duplicate_candidates']), 'class_count':len(classes), 'scientific_truth_certified':False, 'meaning':'Ce feu vert porte uniquement sur les contrôles techniques et métadonnées examinés. Il ne certifie ni l’exactitude des étiquettes, ni une transcription, ni une traduction.'}
    out=BASE/'data'/f'corpus_audit_{args.script}.json'; out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f"Corpus : {root}\nClasses : {len(classes)}\nImages : {total}\nImages illisibles : {len(report['errors'])}\nDoublons exacts : {len(report['exact_duplicates'])}\nCandidats quasi-doublons : {len(report['perceptual_duplicate_candidates'])}\nConflits visuels entre classes : {len(report['cross_class_visual_conflicts'])}\nManifeste : {'présent' if report['manifest'].get('present') else 'absent'}\nRapport : {out}")
    for rec in report['recommendations']: print('⚠',rec)
    if report['errors']: raise SystemExit(2)

if __name__ == '__main__': main()
