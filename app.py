from __future__ import annotations
import os, sqlite3, json, math, hashlib, secrets, re
from functools import wraps
from datetime import timezone
from datetime import datetime, timedelta, date
from pathlib import Path
from urllib.parse import urlencode
import requests
import shutil
import subprocess
import numpy as np
import cv2
from PIL import Image, ImageOps
from flask import Flask, render_template, request, jsonify, send_from_directory, g
from werkzeug.security import generate_password_hash, check_password_hash

BASE = Path(__file__).resolve().parent
# Set CHRONOS_DATA_DIR to a persistent mounted directory in production (e.g. /var/data).
DATA = Path(os.environ.get('CHRONOS_DATA_DIR', str(BASE / 'data'))).resolve()
UPLOADS = Path(os.environ.get('CHRONOS_UPLOAD_DIR', str(DATA / 'uploads'))).resolve()
REFS = DATA / 'reference_glyphs'
DB = Path(os.environ.get('CHRONOS_DB_PATH', str(DATA / 'chronos.sqlite3'))).resolve()
MODELS = Path(os.environ.get('CHRONOS_MODELS_DIR', str(BASE / 'models'))).resolve()
MODEL_FILE = MODELS / 'glyph_classifier.pth'
for p in (DATA, UPLOADS, REFS, MODELS): p.mkdir(parents=True, exist_ok=True)
_GLYPH_MODEL = {}
_GLYPH_MODEL_META = {}
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 12 * 1024 * 1024
app.config['JSON_SORT_KEYS'] = False
app.config['UPLOAD_FOLDER'] = str(UPLOADS)
ALLOWED = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tif', '.tiff'}

TZOLKIN = ['Imix’', 'Ik’', 'Ak’b’al', 'K’an', 'Chikchan', 'Kimi', 'Manik’', 'Lamat', 'Muluk', 'Ok', 'Chuwen', 'Eb’', 'B’en', 'Ix', 'Men', 'K’ib’', 'Kab’an', 'Etz’nab’', 'Kawak', 'Ajaw']
HAAB = ['Pop', 'Wo', 'Sip', 'Sotz’', 'Sek', 'Xul', 'Yaxk’in', 'Mol', 'Ch’en', 'Yax', 'Sak', 'Keh', 'Mak', 'K’ank’in', 'Muwan', 'Pax', 'K’ayab', 'Kumk’u', 'Wayeb’']
PLANETS = {'Mercury':'199','Venus':'299','Earth':'399','Mars':'499','Jupiter':'599','Saturn':'699','Uranus':'799','Neptune':'899','Pluto':'999'}



# Catalog is an orientation aid, not a claim that every script can be automatically read.
# Each OCR method is explicitly marked according to what the local software can actually do.
SCRIPT_CATALOG = [
 {"name":"Égyptien ancien — hiéroglyphes","script":"Hieroglyphes égyptiens","family":"afro-asiatique","period":"env. 3200 av. n.è. – époque romaine","status":"lecture assistée par corpus; OCR spécialisé requis","code":"Egyptian hieroglyphs","method":"Segmentation + comparaison avec signes documentés; pas de traduction automatique fiable."},
 {"name":"Maya classique","script":"Écriture maya","family":"maya","period":"env. 300 av. n.è. – XVIe siècle","status":"corpus et analyse visuelle","code":"Maya hieroglyphs","method":"Comparaison de glyphes avec références annotées; lecture dépend du contexte et des conventions épigraphiques."},
 {"name":"Sumérien","script":"Cunéiforme","family":"isolat (classification discutée)","period":"IVe–IIe millénaire av. n.è.","status":"OCR générique non garanti","code":"Sumerian cuneiform","method":"Catalogue de signes et transcriptions Unicode; comparer les signes cunéiformes à des références."},
 {"name":"Akkadien","script":"Cunéiforme","family":"sémitique","period":"IIIe–Ier millénaire av. n.è.","status":"OCR générique non garanti","code":"Akkadian cuneiform","method":"Interprétation dépend de la langue, de l'époque et du contexte de la tablette."},
 {"name":"Élamite","script":"Cunéiforme / linéaire selon période","family":"élamite","period":"IIIe–Ier millénaire av. n.è.","status":"corpus spécialisé requis","code":"Elamite","method":"Les systèmes et les états de déchiffrement varient selon le corpus."},
 {"name":"Hittite","script":"Cunéiforme","family":"anatolienne indo-européenne","period":"IIe millénaire av. n.è.","status":"OCR générique non garanti","code":"Hittite cuneiform","method":"La langue est déchiffrée; une photo nécessite segmentation et édition de référence."},
 {"name":"Ourartéen","script":"Cunéiforme","family":"ourartéenne","period":"IXe–VIe siècles av. n.è.","status":"corpus spécialisé requis","code":"Urartian cuneiform","method":"Lecture experte et comparaison aux éditions d'inscriptions."},
 {"name":"Linéaire B","script":"Linéaire B","family":"syllabaire grec ancien","period":"env. 1450–1200 av. n.è.","status":"OCR spécialisé requis","code":"Linear B","method":"Écriture déchiffrée; les tablettes demandent une transcription paléographique."},
 {"name":"Linéaire A","script":"Linéaire A","family":"inconnue / non établie","period":"IIe millénaire av. n.è.","status":"non déchiffré de manière consensuelle","code":"Linear A","method":"Le programme ne doit pas inventer de traduction; comparer et documenter les signes."},
 {"name":"Étrusque","script":"Alphabet étrusque","family":"tyrrhénienne","period":"VIIIe–Ier siècles av. n.è.","status":"OCR possible seulement si modèle adapté installé","code":"Etruscan","method":"Une partie des textes est lisible; traduction parfois incertaine faute de contexte."},
 {"name":"Phénicien","script":"Alphabet phénicien","family":"sémitique","period":"env. 1050–300 av. n.è.","status":"OCR possible via modèle OCR adapté","code":"Phoenician","method":"Translittération possible avec ressources linguistiques; vérifier orientation et état de l'inscription."},
 {"name":"Araméen ancien","script":"Araméen","family":"sémitique","period":"Ier millénaire av. n.è.","status":"OCR dépend des données installées","code":"Aramaic","method":"OCR multilingue si le modèle correspondant existe; traduction séparée nécessaire."},
 {"name":"Grec ancien","script":"Alphabet grec","family":"indo-européenne","period":"à partir du IXe siècle av. n.è.","status":"OCR Tesseract possible si langue installée","code":"Greek","method":"OCR de texte imprimé ou net; manuscrits et inscriptions demandent correction."},
 {"name":"Latin ancien","script":"Alphabet latin","family":"indo-européenne","period":"à partir du VIIe siècle av. n.è.","status":"OCR Tesseract possible si langue installée","code":"Latin","method":"OCR générique possible; abréviations et formes épigraphiques nécessitent contrôle."},
 {"name":"Sanskrit","script":"Brahmi, Devanagari et autres selon époque","family":"indo-aryenne","period":"textes anciens et inscriptions de périodes variées","status":"OCR dépend du script et du modèle installé","code":"Sanskrit","method":"La langue et le système d'écriture sont distincts; sélectionner le script exact."},
 {"name":"Brahmi","script":"Brahmi","family":"abugida","period":"à partir du IIIe siècle av. n.è.","status":"OCR spécialisé requis","code":"Brahmi","method":"Les descendants et variantes historiques ne sont pas interchangeables."},
 {"name":"Chinois classique","script":"Caractères chinois","family":"sino-tibétaine","period":"textes anciens sur plusieurs millénaires","status":"OCR dépend du modèle chinois installé","code":"Chinese","method":"OCR moderne possible pour certains imprimés; bronzes, os oraculaires et sceaux requièrent des modèles dédiés."},
 {"name":"Os oraculaires","script":"Jiaguwen","family":"écriture chinoise ancienne","period":"env. XIIIe–XIe siècles av. n.è.","status":"reconnaissance spécialisée requise","code":"Oracle bone script","method":"Variantes graphiques, lacunes et contexte rendent l'identification incertaine."},
 {"name":"Japonais ancien","script":"Kanji / man'yōgana et écritures anciennes","family":"japonique","period":"premier millénaire de n.è.","status":"OCR dépend du modèle et du support","code":"Japanese","method":"Un OCR japonais moderne ne suffit pas pour tous les manuscrits anciens."},
 {"name":"Géorgien ancien","script":"Asomtavruli / Nuskhuri","family":"kartvélienne","period":"à partir du Ve siècle de n.è.","status":"OCR spécialisé requis","code":"Georgian","method":"Utiliser un modèle correspondant à la forme historique de l'alphabet."},
 {"name":"Écriture oghamique","script":"Ogham","family":"alphabetique","period":"env. IVe–VIIe siècles de n.è.","status":"reconnaissance géométrique spécialisée requise","code":"Ogham","method":"La position des traits sur une arête est essentielle; photo et orientation comptent."},
 {"name":"Rongorongo","script":"Rongorongo","family":"non établie","period":"datation et corpus débattus","status":"non déchiffré de manière consensuelle","code":"Rongorongo","method":"Aucune traduction universelle validée; conserver les hypothèses comme hypothèses."},
 {"name":"Indus","script":"Signes de la civilisation de l'Indus","family":"inconnue","period":"env. 2600–1900 av. n.è.","status":"non déchiffré de manière consensuelle","code":"Indus script","method":"Analyse de séquences et corpus possible, traduction fiable non établie."},
 {"name":"Proto-élamite","script":"Proto-élamite","family":"non établie","period":"fin du IVe millénaire av. n.è.","status":"partiellement déchiffré / recherche en cours","code":"Proto-Elamite","method":"Interprétations limitées; ne pas présenter des conjectures comme traductions."},
 {"name":"Écriture du disque de Phaistos","script":"Disque de Phaistos","family":"inconnue","period":"IIe millénaire av. n.è. (datation discutée)","status":"non déchiffré de manière consensuelle","code":"Phaistos Disc","method":"Les motifs peuvent être catalogués; le sens du texte n'est pas établi."},
 {"name":"Gothique","script":"Alphabet gothique","family":"germanique","period":"IVe siècle de n.è.","status":"OCR possible avec modèle adapté","code":"Gothic","method":"La langue est attestée; l'OCR dépend de l'alphabet et de la qualité du support."},
]


def connect():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys = ON')
    c.execute('''CREATE TABLE IF NOT EXISTS inscriptions(id INTEGER PRIMARY KEY, culture TEXT NOT NULL, title TEXT NOT NULL, location TEXT DEFAULT '', period TEXT DEFAULT '', transcription TEXT DEFAULT '', translation TEXT DEFAULT '', source TEXT DEFAULT '', notes TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS signs(id INTEGER PRIMARY KEY, culture TEXT NOT NULL, sign_code TEXT DEFAULT '', label TEXT NOT NULL, reading TEXT DEFAULT '', meaning TEXT DEFAULT '', source TEXT DEFAULT '', image_file TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS epigraphic_claims(id INTEGER PRIMARY KEY, culture TEXT NOT NULL, artifact_id TEXT DEFAULT '', claim_type TEXT NOT NULL, claim_text TEXT NOT NULL, context TEXT DEFAULT '', sources_json TEXT NOT NULL DEFAULT '[]', created_by TEXT DEFAULT '', status TEXT NOT NULL DEFAULT 'NEEDS_REVIEW', created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS epigraphic_reviews(id INTEGER PRIMARY KEY, claim_id INTEGER NOT NULL, reviewer_name TEXT NOT NULL, affiliation TEXT DEFAULT '', credential_id TEXT DEFAULT '', decision TEXT NOT NULL, rationale TEXT NOT NULL, references_checked TEXT DEFAULT '', created_at TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(claim_id) REFERENCES epigraphic_claims(id))''')
    c.execute("""CREATE TABLE IF NOT EXISTS workspaces (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("INSERT OR IGNORE INTO workspaces(id,name) VALUES(1,'CHRONOS LAB')")
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL UNIQUE,
        display_name TEXT NOT NULL, password_hash TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin','researcher','evaluator')),
        workspace_id INTEGER NOT NULL DEFAULT 1, is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(workspace_id) REFERENCES workspaces(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS api_tokens (
        token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires_at TEXT NOT NULL,
        revoked_at TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)""")
    c.execute("""CREATE TABLE IF NOT EXISTS auth_login_attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ip_hash TEXT NOT NULL,
        email TEXT NOT NULL, success INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS experiments (
        id TEXT PRIMARY KEY, workspace_id INTEGER NOT NULL, created_by INTEGER NOT NULL,
        name TEXT NOT NULL, model TEXT NOT NULL, version TEXT DEFAULT '',
        dataset TEXT NOT NULL, parameters TEXT DEFAULT '', notes TEXT DEFAULT '',
        created_at TEXT NOT NULL, FOREIGN KEY(workspace_id) REFERENCES workspaces(id),
        FOREIGN KEY(created_by) REFERENCES users(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS validations (
        id TEXT PRIMARY KEY, workspace_id INTEGER NOT NULL, created_by INTEGER NOT NULL,
        model TEXT NOT NULL, dataset TEXT NOT NULL, precision REAL NOT NULL,
        recall REAL NOT NULL, f1 REAL NOT NULL, samples INTEGER NOT NULL,
        protocol TEXT NOT NULL, created_at TEXT NOT NULL,
        FOREIGN KEY(workspace_id) REFERENCES workspaces(id),
        FOREIGN KEY(created_by) REFERENCES users(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT, workspace_id INTEGER NOT NULL,
        user_id INTEGER, action TEXT NOT NULL, resource TEXT NOT NULL,
        resource_id TEXT DEFAULT '', details_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(workspace_id) REFERENCES workspaces(id))""")
    c.commit(); return c
connect().close()


def jdn(g: date) -> int:
    a=(14-g.month)//12; y=g.year+4800-a; m=g.month+12*a-3
    return g.day+(153*m+2)//5+365*y+y//4-y//100+y//400-32045


def maya_calendar(g: date, correlation: int=584283):
    days = jdn(g) - correlation
    if days < 0: raise ValueError('Cette date précède le point de corrélation sélectionné; la conversion Long Count n’est pas prise en charge ici.')
    rem=days
    baktun, rem = divmod(rem,144000); katun, rem = divmod(rem,7200); tun, rem = divmod(rem,360); winal, kin = divmod(rem,20)
    tz_num=((days+3)%13)+1; tz_name=TZOLKIN[(days+19)%20]
    h=(days+348)%365; h_month, h_day=divmod(h,20)
    haab = f'{h_day} {HAAB[h_month]}' if h_month < 18 else f'{h_day} Wayeb’'
    return {'gregorian':g.isoformat(),'correlation_gmt':correlation,'julian_day_number':jdn(g),'days_from_correlation':days,'tzolkin':f'{tz_num} {tz_name}','haab':haab,'long_count':f'{baktun}.{katun}.{tun}.{winal}.{kin}','calendar_round_note':'La roue calendaire se répète tous les 18 980 jours (52 années Haab’).'}


def perceptual_hash(path):
    img=Image.open(path).convert('L').resize((32,32))
    arr=np.asarray(img, dtype=np.float32)
    # DCT-based perceptual hash: 8x8 low-frequency block, median threshold excluding DC.
    d=cv2.dct(arr)
    low=d[:8,:8].flatten(); med=np.median(low[1:])
    bits=low>med
    value=0
    for b in bits: value=(value<<1)|int(b)
    return value


def hamming(a,b): return (a^b).bit_count()


def normalized_shape(path_or_image):
    """Build a normalized binary glyph and a robust shape descriptor."""
    if isinstance(path_or_image, (str, Path)):
        gray=cv2.imread(str(path_or_image),cv2.IMREAD_GRAYSCALE)
        if gray is None: raise ValueError('Image de référence illisible.')
    else:
        gray=cv2.cvtColor(np.array(path_or_image.convert('RGB')),cv2.COLOR_RGB2GRAY)
    gray=cv2.GaussianBlur(gray,(3,3),0)
    _, binary=cv2.threshold(gray,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    # Glyphs are normalized with dark ink on a white background.
    if np.mean(binary)>127: binary=255-binary
    coords=cv2.findNonZero(255-binary)
    if coords is not None:
        x,y,w,h=cv2.boundingRect(coords); binary=binary[y:y+h,x:x+w]
    canvas=np.full((96,96),255,np.uint8)
    h,w=binary.shape[:2]
    if h and w:
        scale=min(78/max(w,1),78/max(h,1)); resized=cv2.resize(binary,(max(1,int(w*scale)),max(1,int(h*scale))),interpolation=cv2.INTER_AREA)
        y0=(96-resized.shape[0])//2; x0=(96-resized.shape[1])//2; canvas[y0:y0+resized.shape[0],x0:x0+resized.shape[1]]=resized
    return canvas


def glyph_similarity(a,b):
    """Similarity combines normalized pixels and Hu shape moments; still a heuristic."""
    try:
        aa=normalized_shape(a); bb=normalized_shape(b)
        pixel=float(np.mean(np.abs(aa.astype(np.float32)-bb.astype(np.float32)))/255.0)
        def hu(img):
            _,th=cv2.threshold(img,127,255,cv2.THRESH_BINARY_INV)
            m=cv2.moments(th); h=cv2.HuMoments(m).flatten()
            return np.sign(h)*np.log10(np.abs(h)+1e-12)
        ha,hb=hu(aa),hu(bb); shape=float(np.mean(np.minimum(np.abs(ha-hb),20))/20)
        return max(0.0,1.0-(0.72*pixel+0.28*shape))
    except Exception: return 0.0


def _box_iou(a, b):
    ax, ay, aw, ah = a; bx, by, bw, bh = b
    ix1, iy1 = max(ax, bx), max(ay, by)
    ix2, iy2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    union = aw * ah + bw * bh - inter
    return inter / union if union else 0.0


def segment_glyphs(image, method="ensemble"):
    """High-recall multi-strategy proposals. Boxes are candidates, never unquestioned glyph boundaries."""
    rgb = np.array(image.convert('RGB'))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    # Use both global and adaptive thresholds: ancient inscriptions often have uneven lighting.
    global_bin = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    adaptive_bin = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 7)
    h, w = gray.shape
    proposals = []

    def collect(binary, source):
        # Light closing helps preserve a glyph's connected strokes; too much closing merges neighbours.
        closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            x, y, bw, bh = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)
            if bw < 7 or bh < 7 or bw * bh < 55 or area < 12: continue
            if bw > w * .97 and bh > h * .97: continue
            # Exclude page-sized background blobs but keep elongated strokes for expert review.
            if bw > w * .80 and bh > h * .50: continue
            proposals.append((x, y, bw, bh, source))

    collect(global_bin, 'otsu')
    collect(adaptive_bin, 'adaptive')

    if method in ('watershed', 'ensemble'):
        # Watershed is a second opinion. Keep its boxes alongside contour proposals instead of
        # assuming each watershed basin is one true sign.
        binary = cv2.morphologyEx(global_bin, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8), iterations=1)
        dist = cv2.distanceTransform(binary, cv2.DIST_L2, 5)
        if dist.max() > 0:
            sure_fg = np.uint8(dist > max(1.0, 0.42 * dist.max()))
            sure_bg = cv2.dilate(binary, np.ones((3, 3), np.uint8), iterations=2)
            unknown = cv2.subtract(sure_bg, sure_fg * 255)
            _, markers = cv2.connectedComponents(sure_fg)
            markers = markers + 1
            markers[unknown > 0] = 0
            try:
                cv2.watershed(rgb.copy(), markers)
                for label in np.unique(markers):
                    if label <= 1: continue
                    ys, xs = np.where(markers == label)
                    if len(xs) < 20: continue
                    x, y = int(xs.min()), int(ys.min()); bw = int(xs.max()-x+1); bh = int(ys.max()-y+1)
                    if bw >= 7 and bh >= 7 and bw * bh >= 55 and not (bw > w*.97 and bh > h*.97):
                        proposals.append((x, y, bw, bh, 'watershed'))
            except cv2.error:
                pass

    # Remove near-identical proposals only; do not merge touching candidates automatically because
    # that could join two real signs. Keep source tags to expose disagreement in the UI.
    proposals.sort(key=lambda b: b[2]*b[3], reverse=True)
    kept = []
    for box in proposals:
        coords = box[:4]
        duplicate = next((k for k in kept if _box_iou(coords, k[:4]) >= 0.78), None)
        if duplicate:
            if box[4] not in duplicate[4].split('+'):
                duplicate[4] += '+' + box[4]
            continue
        kept.append([*coords, box[4]])
    kept.sort(key=lambda b: (b[1] // max(1, h // 15), b[0]))
    # Keep high-recall candidate proposals and limit pathological page noise.
    kept = kept[:120]
    details=[]
    for i,b in enumerate(kept):
        x,y,bw,bh=b[:4]; nested=False; overlaps=[]
        for j,other in enumerate(kept):
            if i==j or other[2]*other[3] <= bw*bh: continue
            ox,oy,ow,oh=other[:4]
            cx,cy=x+bw/2,y+bh/2
            if ox <= cx <= ox+ow and oy <= cy <= oy+oh:
                nested=True; overlaps.append(j+1)
            elif _box_iou(b[:4],other[:4]) > 0.25:
                overlaps.append(j+1)
        details.append({'box':list(b[:4]),'sources':b[4], 'possible_oversegmentation':nested,
                        'overlap_candidates':overlaps[:8],
                        'review_note':'Cadre inclus dans une zone plus grande : possible fragmentation d’un glyphe.' if nested else ('Cadres en chevauchement : vérifier les limites.' if overlaps else 'Cadre candidat à vérifier sur l’original.')})
    return global_bin, [tuple(b[:4]) for b in kept], details


def safe_model_key(value: str) -> str:
    """Normalize a script identifier to a safe, predictable filename key."""
    import re, unicodedata
    value = unicodedata.normalize('NFKD', str(value or 'general')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '_', value).strip('_') or 'general'


def model_path_for_script(script: str = '') -> Path:
    """Never silently use a general model for a named specialist script.

    A model trained on the wrong writing system can create confidently wrong labels;
    fail closed instead and tell the user that the specialist model is missing.
    """
    key = safe_model_key(script)
    if key and key != 'general':
        return MODELS / f'{key}_glyph_classifier.pth'
    return MODEL_FILE


def load_glyph_classifier(script: str = ''):
    """Load only the exact specialist model selected; never cross-fallback between scripts."""
    global _GLYPH_MODEL, _GLYPH_MODEL_META
    chosen = model_path_for_script(script)
    cache_key = str(chosen)
    if not chosen.exists():
        return None, None, f'Aucun modèle entraîné pour « {script or "général"} ». Préparez un corpus et consultez AI_TRAINING.md.'
    if cache_key in _GLYPH_MODEL:
        return _GLYPH_MODEL[cache_key], _GLYPH_MODEL_META.get(cache_key), None
    try:
        import torch
        from torchvision import models, transforms
        checkpoint = torch.load(chosen, map_location='cpu', weights_only=False)
        classes = checkpoint.get('classes', [])
        if not classes:
            return None, None, 'Le fichier du modèle ne contient pas de classes.'
        model = models.resnet18(weights=None)
        model.fc = torch.nn.Linear(model.fc.in_features, len(classes))
        model.load_state_dict(checkpoint['state_dict'])
        model.eval()
        loaded = (model, transforms.Compose([
            transforms.Resize((224, 224)), transforms.ToTensor(),
            transforms.Normalize(mean=[0.485,0.456,0.406], std=[0.229,0.224,0.225])
        ]), torch, classes)
        meta = {'classes': classes, 'trained_at': checkpoint.get('trained_at'),
                'validation_accuracy': checkpoint.get('validation_accuracy'),
                'epochs': checkpoint.get('epochs'), 'num_images': checkpoint.get('num_images'),
                'script': checkpoint.get('script', 'general'), 'model_file': chosen.name,
                'unknown_threshold': checkpoint.get('unknown_threshold', 0.65),
                'class_centroids': checkpoint.get('class_centroids', {}),
                'ood_distance_threshold': checkpoint.get('ood_distance_threshold'),
                'conformal_alpha': checkpoint.get('conformal_alpha'),
                'conformal_score_threshold': checkpoint.get('conformal_score_threshold'),
                'calibration_count': checkpoint.get('calibration_count')}
        _GLYPH_MODEL[cache_key] = loaded
        _GLYPH_MODEL_META[cache_key] = meta
        return loaded, meta, None
    except Exception as exc:
        return None, None, f'Impossible de charger {chosen.name} : {exc}. Vérifiez requirements-ai.txt et réentraînez si nécessaire.'


def predict_glyph(crop, script: str = ''):
    loaded, meta, error = load_glyph_classifier(script)
    if loaded is None:
        return {'available': False, 'message': error, 'predictions': [], 'unknown': True, 'decision': 'NO_MODEL'}
    model, transform, torch, classes = loaded
    try:
        image = crop.convert('RGB')
        tensor = transform(image).unsqueeze(0)
        with torch.no_grad():
            # Inspect both class scores and penultimate-layer representation for open-set rejection.
            features = model.avgpool(model.layer4(model.layer3(model.layer2(model.layer1(model.maxpool(model.relu(model.bn1(model.conv1(tensor)))))))))
            embedding = torch.flatten(features, 1)[0]
            logits = model.fc(embedding.unsqueeze(0))[0]
            probs = torch.softmax(logits, dim=0)
        k = min(5, len(classes))
        vals, idxs = torch.topk(probs, k=k)
        predictions = [{'class': classes[int(i)], 'score_percent': round(float(v)*100, 2)} for v,i in zip(vals,idxs)]
        top = predictions[0] if predictions else None
        threshold = float(meta.get('unknown_threshold', 0.65))
        max_score = float(vals[0]) if len(vals) else 0.0
        # Nearest class-centroid distance is a second, independent warning signal when checkpoint has it.
        distance = None; distance_limit = meta.get('ood_distance_threshold')
        centers = meta.get('class_centroids') or {}
        if centers:
            emb = torch.nn.functional.normalize(embedding.detach().cpu(), dim=0).numpy()
            distances = []
            for label, center in centers.items():
                center_arr = np.asarray(center, dtype=np.float32)
                denom = float(np.linalg.norm(center_arr))
                if denom:
                    center_arr = center_arr / denom
                    distances.append((float(np.linalg.norm(emb-center_arr)), label))
            if distances:
                distance, nearest = min(distances)
                distance_limit = float(distance_limit) if distance_limit is not None else None
                if nearest != (top['class'] if top else None):
                    nearest_mismatch = True
                else: nearest_mismatch = False
            else: nearest_mismatch = False
        else: nearest_mismatch = False
        low_score = max_score < threshold
        conformal_cutoff = meta.get('conformal_score_threshold')
        conformal_candidate_set = [classes[i] for i, value in enumerate(probs.tolist()) if conformal_cutoff is not None and (1.0 - float(value)) <= float(conformal_cutoff)]
        # If no conformal calibration was recorded, explicitly report that this safeguard is unavailable.
        conformal_ambiguous = bool(conformal_cutoff is not None and len(conformal_candidate_set) != 1)
        far_from_known = distance is not None and distance_limit is not None and distance > distance_limit
        # Fail closed: if either confidence is weak or the crop is out-of-distribution, abstain.
        unknown = bool(not top or low_score or far_from_known or nearest_mismatch or conformal_ambiguous or conformal_cutoff is None)
        reasons=[]
        if low_score: reasons.append(f'score maximal inférieur au seuil ({threshold:.2f})')
        if far_from_known: reasons.append('forme éloignée des prototypes connus')
        if conformal_ambiguous: reasons.append('ensemble calibré non singleton : plusieurs classes compatibles ou aucune classe')
        if conformal_cutoff is None: reasons.append('calibration conformelle absente; seuil statistique non disponible')
        if nearest_mismatch: reasons.append('désaccord entre classe prédite et prototype le plus proche')
        if not reasons: reasons.append('aucun signal d’alerte détecté; vérification humaine toujours requise')
        calibration_available = conformal_cutoff is not None
        # The software never grants scientific truth status, even when a calibrated
        # classifier passes its technical rejection checks. Uncalibrated outputs remain
        # visible only as exploratory candidates and always trigger abstention.
        return {'available': True, 'predictions': predictions, 'accepted': False,
                'technical_candidate_passed': not unknown,
                'unknown': unknown,
                'decision': 'UNKNOWN_OR_UNCERTAIN' if unknown else 'KNOWN_CLASS_CANDIDATE',
                'presentation_mode': 'EXPLORATORY_ONLY',
                'scientific_status': 'NOT_CERTIFIED_HYPOTHESIS',
                'automatic_scientific_validation': False,
                'calibration_status': 'AVAILABLE' if calibration_available else 'MISSING',
                'candidates_are_exploratory': True,
                'message': ('Signe inconnu ou incertain : abstention automatique. ' if unknown else 'Classe candidate, non certifiée. ') + '; '.join(reasons) + '.',
                'open_set': {'max_score_percent': round(max_score*100,2), 'score_threshold_percent': round(threshold*100,2),
                             'nearest_prototype_distance': round(distance,4) if distance is not None else None,
                             'prototype_distance_limit': distance_limit, 'nearest_class_disagrees': nearest_mismatch,
                             'signals': reasons, 'conformal': {'available': conformal_cutoff is not None, 'alpha': meta.get('conformal_alpha'), 'candidate_set': conformal_candidate_set, 'score_threshold': conformal_cutoff, 'calibration_count': meta.get('calibration_count'), 'interpretation': 'La couverture conformelle ne vaut que sous les hypothèses de calibration et d’échangeabilité; elle ne garantit pas le rejet de tout signe hors distribution.' if conformal_cutoff is not None else 'Entraînez de nouveau le modèle pour produire la calibration conformelle.'}, 'guarantee': 'Aucune garantie universelle sur des signes inconnus arbitraires. Le logiciel applique une abstention prudente et expose ses signaux d’incertitude.'},
                'model': {'classes': len(classes), 'validation_accuracy': meta.get('validation_accuracy'),
                         'trained_at': meta.get('trained_at'), 'script': meta.get('script'), 'model_file': meta.get('model_file'),
                         'unknown_threshold': threshold}}
    except Exception as exc:
        return {'available': False, 'message': f'Inférence impossible : {exc}', 'predictions': [], 'unknown': True, 'decision':'ERROR'}

def match_glyphs(upload_path, ocr_lang='', script='', segmentation='components'):
    try: img=Image.open(upload_path).convert('RGB')
    except Exception as e: raise ValueError('Le fichier ne peut pas être lu comme une image.') from e
    gray=cv2.cvtColor(np.array(img),cv2.COLOR_RGB2GRAY)
    gray=cv2.GaussianBlur(gray,(3,3),0)
    binary=cv2.adaptiveThreshold(gray,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,31,7)
    processed=UPLOADS/(Path(upload_path).stem+'_processed.png'); cv2.imwrite(str(processed),binary)
    conn=connect(); refs=conn.execute('SELECT * FROM signs WHERE image_file != ""').fetchall(); conn.close()
    ref_paths=[]
    for r in refs:
        p=REFS/r['image_file']
        if p.exists(): ref_paths.append((r,p))
    _,boxes,segment_details=segment_glyphs(img, segmentation if segmentation in ('components','watershed','ensemble') else 'ensemble')
    overlay = np.array(img.convert('RGB')).copy()
    for si, detail in enumerate(segment_details, start=1):
        x,y,bw,bh=detail['box']; box_color=(0,140,255) if detail.get('possible_oversegmentation') else (0,210,255)
        cv2.rectangle(overlay,(x,y),(x+bw,y+bh),box_color,2)
        cv2.putText(overlay,str(si),(x,max(14,y-4)),cv2.FONT_HERSHEY_SIMPLEX,0.45,(0,90,255),1,cv2.LINE_AA)
    overlay_path=UPLOADS/(Path(upload_path).stem+'_segments.png')
    cv2.imwrite(str(overlay_path),cv2.cvtColor(overlay,cv2.COLOR_RGB2BGR))
    glyph_reports=[]; aggregate={}
    # Compare each detected connected component against every labeled reference glyph.
    for idx,(x,y,w,h) in enumerate(sorted(boxes,key=lambda z:(z[1],z[0]))[:30],start=1):
        pad=max(3,int(min(w,h)*.08)); x0=max(0,x-pad); y0=max(0,y-pad); x1=min(img.width,x+w+pad); y1=min(img.height,y+h+pad)
        crop=img.crop((x0,y0,x1,y1)); matches=[]
        for r,rpath in ref_paths:
            score=glyph_similarity(crop,rpath)
            item={'id':r['id'],'culture':r['culture'],'code':r['sign_code'],'label':r['label'],'reading':r['reading'],'meaning':r['meaning'],'source':r['source'],'similarity_percent':round(score*100,1),'image_file':r['image_file']}
            matches.append(item)
            if r['id'] not in aggregate or score>aggregate[r['id']]['_score']:
                aggregate[r['id']]={**item,'_score':score,'detected_in_glyph':idx}
        matches.sort(key=lambda x:x['similarity_percent'],reverse=True)
        ai_prediction = predict_glyph(crop, script)
        glyph_reports.append({'index':idx,'box':{'x':x,'y':y,'width':w,'height':h},'segmentation_sources': next((d['sources'] for d in segment_details if d['box']==[x,y,w,h]), 'unknown'), 'segmentation_warning': next((d['review_note'] for d in segment_details if d['box']==[x,y,w,h]), 'Vérification humaine requise'), 'possible_oversegmentation': next((d['possible_oversegmentation'] for d in segment_details if d['box']==[x,y,w,h]), False), 'review_required': True, 'matches':matches[:3], 'ai_prediction': ai_prediction})
    candidates=sorted(aggregate.values(),key=lambda x:x['_score'],reverse=True)
    for item in candidates: item.pop('_score',None)
    ocr={'attempted':False,'available':bool(shutil.which('tesseract')),'text':'','languages':[],'message':'OCR non exécuté.'}
    if shutil.which('tesseract'):
        try:
            langs=subprocess.run(['tesseract','--list-langs'],capture_output=True,text=True,timeout=8)
            installed=[x.strip() for x in (langs.stdout+'\n'+langs.stderr).splitlines() if x.strip() and not x.lower().startswith('list of available') and 'tesseract' not in x.lower()]
            requested=ocr_lang.strip() or ('eng' if 'eng' in installed else (installed[0] if installed else ''))
            if requested and all(x in installed for x in requested.split('+')):
                proc=subprocess.run(['tesseract',str(processed),'stdout','-l',requested,'--psm','11'],capture_output=True,text=True,timeout=30)
                ocr={'attempted':True,'available':True,'text':proc.stdout.strip(),'languages':installed,'used_language':requested,'message':'OCR générique via Tesseract. Les hiéroglyphes/cunéiformes exigent des modèles spécialisés qui ne sont pas fournis automatiquement.'}
            else:
                ocr={'attempted':False,'available':True,'text':'','languages':installed,'message':f'Modèle OCR demandé indisponible : {requested or "aucun modèle installé"}.'}
        except Exception as e: ocr={'attempted':True,'available':True,'text':'','languages':[],'message':f'Échec OCR : {e}'}
    _, model_meta, model_error = load_glyph_classifier(script)
    ai_status = {'trained_model_available': model_meta is not None, 'model': model_meta, 'selected_script': script or 'general', 'segmentation': segmentation, 'message': model_error or 'Modèle spécialisé ou général disponible. Les propositions doivent être vérifiées.'}
    return {'original_image':'/uploads/'+Path(upload_path).name,'processed_image':'/'+processed.relative_to(BASE).as_posix(),'segmentation_overlay':'/'+overlay_path.relative_to(BASE).as_posix(),'segmentation_method':segmentation,'segmentation_review_note':'Les rectangles sont des propositions automatiques, pas une vérité sur les frontières des glyphes. Inspectez l’original et l’overlay; les signes collés, cassés ou décorés exigent une correction humaine.','reference_count':len(ref_paths),'candidate_glyph_count':len(boxes),'matches':candidates[:10], 'glyph_reports':glyph_reports,'ocr':ocr,'ai_model':ai_status,'message':'Les correspondances sont des pistes de recherche, pas une traduction. La segmentation propose plusieurs découpages et signale les candidats; elle ne peut garantir une frontière correcte pour chaque glyphe.' if ref_paths else 'Aucune référence visuelle disponible. Ajoutez des signes documentés pour activer la comparaison. Si Tesseract est installé, l’OCR peut reconnaître uniquement les modèles disponibles.'}

@app.get('/api/scripts')
def scripts_catalog():
    q=request.args.get('q','').strip().casefold()
    items=SCRIPT_CATALOG
    if q: items=[x for x in items if q in ' '.join(str(v) for v in x.values()).casefold()]
    return jsonify({'count':len(items),'scripts':items})

@app.get('/api/model-status')
def model_status():
    requested = request.args.get('script', '')
    _, meta, error = load_glyph_classifier(requested)
    specialists = []
    for path in sorted(MODELS.glob('*_glyph_classifier.pth')):
        specialists.append({'file': path.name, 'script_key': path.name[:-len('_glyph_classifier.pth')]})
    public_meta = None
    if meta:
        public_meta = {k: meta.get(k) for k in ('classes','trained_at','validation_accuracy','epochs','num_images','script','model_file','unknown_threshold','ood_distance_threshold','conformal_alpha','conformal_score_threshold','calibration_count')}
        public_meta['open_set_calibration_available'] = meta.get('conformal_score_threshold') is not None and bool(meta.get('class_centroids')) and meta.get('ood_distance_threshold') is not None
    return jsonify({'available': meta is not None, 'model': public_meta, 'selected_script': requested or 'general',
                    'specialist_models': specialists,
                    'message': error or 'Classifieur de glyphes disponible. Le rejet des inconnus est probabiliste; les résultats restent à valider scientifiquement.'})

@app.get('/api/ocr-status')
def ocr_status():
    binary=shutil.which('tesseract')
    if not binary: return jsonify({'installed':False,'binary':None,'languages':[],'message':'Tesseract non installé; comparaison visuelle toujours disponible.'})
    try:
        result=subprocess.run([binary,'--list-langs'],capture_output=True,text=True,timeout=8)
        langs=[x.strip() for x in (result.stdout+'\n'+result.stderr).splitlines() if x.strip() and not x.lower().startswith('list of available') and 'tesseract' not in x.lower()]
        return jsonify({'installed':True,'binary':binary,'languages':langs,'message':'OCR limité aux modèles installés. Cela ne garantit pas la lecture des écritures anciennes.'})
    except Exception as e: return jsonify({'installed':True,'binary':binary,'languages':[],'message':str(e)})

@app.get('/api/corpus-stats')
def corpus_stats():
    c = connect()
    signs = c.execute('SELECT culture, COUNT(*) AS n FROM signs GROUP BY culture ORDER BY n DESC').fetchall()
    inscriptions = c.execute('SELECT culture, COUNT(*) AS n FROM inscriptions GROUP BY culture ORDER BY n DESC').fetchall()
    refs = c.execute("SELECT COUNT(*) FROM signs WHERE image_file != '' AND image_file IS NOT NULL").fetchone()[0]
    c.close()
    models = [{'file': p.name, 'bytes': p.stat().st_size} for p in sorted(MODELS.glob('*_glyph_classifier.pth'))]
    if MODEL_FILE.exists() and all(x['file'] != MODEL_FILE.name for x in models): models.append({'file': MODEL_FILE.name, 'bytes': MODEL_FILE.stat().st_size})
    return jsonify({'signs_total': sum(r['n'] for r in signs), 'inscriptions_total': sum(r['n'] for r in inscriptions),
                    'reference_images': refs, 'signs_by_culture': [dict(r) for r in signs],
                    'inscriptions_by_culture': [dict(r) for r in inscriptions], 'trained_models': models,
                    'scientific_note': 'Les statistiques décrivent le corpus local; elles ne garantissent ni représentativité ni qualité épigraphique.'})


@app.post('/api/pattern-analysis')
def pattern_analysis():
    """Descriptive sequence analysis for undeciphered scripts; never attempts translation."""
    d = request.json or {}
    raw = str(d.get('sequence', '')).strip()
    if not raw:
        return jsonify({'error': 'Saisissez une séquence de signes ou de codes.'}), 400
    import re, math
    tokens = [t for t in re.split(r'[\s,;|]+', raw) if t]
    if len(tokens) > 10000:
        return jsonify({'error': 'Limite : 10 000 tokens par analyse.'}), 400
    from collections import Counter
    counts = Counter(tokens)
    n = len(tokens)
    entropy = -sum((v/n) * math.log2(v/n) for v in counts.values()) if n else 0.0
    bigrams = Counter(zip(tokens, tokens[1:]))
    trigrams = Counter(zip(tokens, tokens[1:], tokens[2:]))
    return jsonify({'token_count': n, 'unique_signs': len(counts), 'type_token_ratio': round(len(counts)/n, 4) if n else 0,
                    'shannon_entropy_bits_per_token': round(entropy, 4),
                    'frequencies': [{'token': k, 'count': v, 'frequency_percent': round(v/n*100, 2)} for k,v in counts.most_common(30)],
                    'common_bigrams': [{'sequence': list(k), 'count': v} for k,v in bigrams.most_common(20)],
                    'common_trigrams': [{'sequence': list(k), 'count': v} for k,v in trigrams.most_common(20)],
                    'interpretation': 'Analyse statistique descriptive uniquement. Ces régularités ne constituent ni un déchiffrement ni une traduction.'})


@app.get('/')
def index(): return render_template('index.html')

@app.get('/uploads/<path:filename>')
def uploaded_file(filename): return send_from_directory(UPLOADS, filename)

@app.after_request
def add_security_and_cors_headers(response):
    # CORS is opt-in and restricted to an explicit allowlist; configure the Pages origin in production.
    origin = request.headers.get('Origin', '')
    allowed = {x.strip().rstrip('/') for x in os.environ.get('CHRONOS_ALLOWED_ORIGINS', 'http://localhost:5000,http://127.0.0.1:5000').split(',') if x.strip()}
    if origin.rstrip('/') in allowed:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Vary'] = 'Origin'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Max-Age'] = '600'
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
    return response

@app.get('/api/health')
def health():
    c = connect()
    count = c.execute('SELECT COUNT(*) FROM signs WHERE image_file != ""').fetchone()[0]
    c.close()
    return jsonify({'status':'ok','app':'CHRONOS Lab','database':str(DB.name),'reference_signs':count,'scientific_validation_automatic':False})

@app.get('/api/scientific-policy')
def scientific_policy():
    return jsonify({'presentation_mode':'EXPLORATORY_ONLY','scientific_status':'NOT_CERTIFIED_HYPOTHESIS','automatic_scientific_validation':False,'rules':['Model outputs are hypotheses, not scientific facts.','Without sufficient calibration, the model must abstain from automatic acceptance.','Human reviews and declared sources are traceability evidence, not automatic proof of truth.','Technical checks never certify an epigraphic interpretation.']})

@app.post('/api/calendar')
def calendar():
    d=request.json or {}; raw=d.get('date',''); corr=int(d.get('correlation',584283))
    if corr not in (584283,584285,584286): return jsonify({'error':'Corrélation non reconnue.'}),400
    try: return jsonify(maya_calendar(date.fromisoformat(raw),corr))
    except Exception as e: return jsonify({'error':str(e) or 'Date invalide.'}),400

@app.post('/api/astronomy')
def astronomy():
    d=request.json or {}; raw=d.get('date',''); planet=d.get('planet','Mars')
    if planet not in PLANETS: return jsonify({'error':'Corps céleste non pris en charge.'}),400
    try: date.fromisoformat(raw)
    except Exception: return jsonify({'error':'Date invalide.'}),400
    # NASA/JPL Horizons provides the authoritative ephemeris; this call returns the service's raw result
    # rather than fabricating a position from a simplified orbital model.
    params={'format':'json','COMMAND':f"'{PLANETS[planet]}'",'OBJ_DATA':'YES','MAKE_EPHEM':'YES','EPHEM_TYPE':'OBSERVER','CENTER':"'500@399'",'START_TIME':f"'{raw}'",'STOP_TIME':f"'{(date.fromisoformat(raw)+timedelta(days=1)).isoformat()}'",'STEP_SIZE':"'1 d'",'QUANTITIES':"'1,9,20,23,24,29'"}
    try:
        r=requests.get('https://ssd.jpl.nasa.gov/api/horizons.api',params=params,timeout=25); r.raise_for_status(); payload=r.json()
        if payload.get('error'): return jsonify({'error':payload['error'],'source':'NASA/JPL Horizons'}),502
        result=payload.get('result','')
        # Extract the first ephemeris row, while preserving the original response for scientific verification.
        row=''
        if '$$SOE' in result:
            lines=result.split('$$SOE',1)[1].split('$$EOE',1)[0].strip().splitlines()
            row='\n'.join(lines[:3])
        return jsonify({'planet':planet,'date':raw,'source':'NASA/JPL Horizons','api_version':payload.get('signature',{}).get('version','non précisée'),'ephemeris_excerpt':row or result[:3500],'raw_result':result[:12000],'note':'Résultat calculé par JPL Horizons. Les colonnes et conventions sont celles du service; vérifiez la documentation avant toute utilisation scientifique.'})
    except requests.RequestException as e: return jsonify({'error':f'Connexion à NASA/JPL Horizons impossible : {e}','hint':'Vérifiez votre connexion internet puis réessayez.'}),502
    except ValueError: return jsonify({'error':'La réponse de NASA/JPL Horizons n’est pas un JSON valide.'}),502

@app.post('/api/analyze-image')
def analyze_image():
    f=request.files.get('image')
    if not f or not f.filename: return jsonify({'error':'Choisissez une image.'}),400
    ext=Path(f.filename).suffix.lower()
    if ext not in ALLOWED: return jsonify({'error':'Format non pris en charge. Utilisez PNG, JPG, WEBP, BMP ou TIFF.'}),400
    name=hashlib.sha256((f.filename+str(datetime.utcnow().timestamp())).encode()).hexdigest()[:20]+ext
    path=UPLOADS/name; f.save(path)
    try: return jsonify(match_glyphs(path, request.form.get('ocr_lang',''), request.form.get('script',''), request.form.get('segmentation','components')))
    except Exception as e: return jsonify({'error':str(e)}),400

@app.post('/api/segmentation-review')
def segmentation_review():
    """Save human-corrected boxes and re-run recognition only on those approved crops."""
    d=request.json or {}
    filename=Path(str(d.get('image_filename',''))).name
    image_path=UPLOADS/filename
    boxes=d.get('boxes') or []
    script=str(d.get('script','general'))
    if not image_path.exists() or image_path.suffix.lower() not in ALLOWED:
        return jsonify({'error':'Image source introuvable. Relancez l’analyse de cette image.'}),404
    if not isinstance(boxes,list) or not boxes or len(boxes)>300:
        return jsonify({'error':'Ajoutez entre 1 et 300 cadres corrigés.'}),400
    try:
        with Image.open(image_path) as im: original=im.convert('RGB')
        w_img,h_img=original.size; results=[]; normalized=[]
        for i,box in enumerate(boxes,1):
            x=max(0,min(w_img,int(box.get('x',0)))); y=max(0,min(h_img,int(box.get('y',0))))
            w=max(0,min(w_img-x,int(box.get('width',0)))); h=max(0,min(h_img-y,int(box.get('height',0))))
            if w<4 or h<4: continue
            crop=original.crop((x,y,x+w,y+h))
            prediction=predict_glyph(crop,script)
            normalized.append({'index':i,'x':x,'y':y,'width':w,'height':h})
            results.append({'index':i,'box':{'x':x,'y':y,'width':w,'height':h},'ai_prediction':prediction,
                            'review_state':'HUMAN_BOX_PROPOSED_NOT_EXPERT_CERTIFIED'})
        if not results: return jsonify({'error':'Aucun cadre valide. Chaque cadre doit mesurer au moins 4×4 pixels.'}),400
        review_id=hashlib.sha256((filename+str(datetime.utcnow().timestamp())).encode()).hexdigest()[:16]
        review_dir=DATA/'segmentation_reviews'; review_dir.mkdir(parents=True,exist_ok=True)
        payload={'review_id':review_id,'image_filename':filename,'script':script,'image_size':{'width':w_img,'height':h_img},
                 'boxes':normalized,'results':results,'created_at':datetime.utcnow().isoformat()+'Z',
                 'policy':'Les boîtes sont des corrections de segmentation proposées par l’utilisateur. Elles ne certifient pas l’identification du signe.'}
        (review_dir/f'{review_id}.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
        return jsonify(payload)
    except Exception as exc:
        return jsonify({'error':f'Impossible de vérifier cette segmentation : {exc}'}),400

@app.get('/api/signs')
def signs_list():
    q=request.args.get('q','').strip(); culture=request.args.get('culture','').strip()
    sql='SELECT * FROM signs WHERE 1=1'; args=[]
    if q: sql+=' AND (label LIKE ? OR reading LIKE ? OR meaning LIKE ? OR sign_code LIKE ?)'; args += [f'%{q}%']*4
    if culture: sql+=' AND culture = ?'; args.append(culture)
    sql+=' ORDER BY culture,label LIMIT 300'
    c=connect(); rows=[dict(r) for r in c.execute(sql,args).fetchall()]; c.close(); return jsonify(rows)

@app.post('/api/signs')
def add_sign():
    d=request.form if request.form else (request.json or {})
    label=(d.get('label') or '').strip(); culture=(d.get('culture') or '').strip()
    if not label or not culture: return jsonify({'error':'Culture et libellé sont obligatoires.'}),400
    image_file=''; f=request.files.get('image')
    if f and f.filename:
        ext=Path(f.filename).suffix.lower()
        if ext not in ALLOWED: return jsonify({'error':'Format d’image non pris en charge.'}),400
        image_file=hashlib.sha256((f.filename+str(datetime.utcnow().timestamp())).encode()).hexdigest()[:20]+ext
        f.save(REFS/image_file)
    c=connect(); cur=c.execute('INSERT INTO signs(culture,sign_code,label,reading,meaning,source,image_file) VALUES(?,?,?,?,?,?,?)',(culture,d.get('sign_code',''),label,d.get('reading',''),d.get('meaning',''),d.get('source',''),image_file)); c.commit(); ident=cur.lastrowid; c.close()
    return jsonify({'ok':True,'id':ident,'message':'Référence enregistrée. Toute interprétation doit conserver sa source.'})

@app.get('/api/inscriptions')
def inscriptions_list():
    q=request.args.get('q','').strip(); c=connect()
    if q: rows=c.execute('SELECT * FROM inscriptions WHERE title LIKE ? OR transcription LIKE ? OR translation LIKE ? OR location LIKE ? ORDER BY id DESC LIMIT 300',[f'%{q}%']*4).fetchall()
    else: rows=c.execute('SELECT * FROM inscriptions ORDER BY id DESC LIMIT 300').fetchall()
    c.close(); return jsonify([dict(r) for r in rows])

@app.post('/api/inscriptions')
def add_inscription():
    d=request.json or {}; required=('culture','title')
    if any(not str(d.get(k,'')).strip() for k in required): return jsonify({'error':'Culture et titre sont obligatoires.'}),400
    c=connect(); cur=c.execute('INSERT INTO inscriptions(culture,title,location,period,transcription,translation,source,notes) VALUES(?,?,?,?,?,?,?,?)',tuple(d.get(k,'') for k in ('culture','title','location','period','transcription','translation','source','notes'))); c.commit(); ident=cur.lastrowid; c.close()
    return jsonify({'ok':True,'id':ident})

@app.get('/api/epigraphy/claims')
def epigraphy_claims_list():
    c=connect()
    rows=c.execute('SELECT * FROM epigraphic_claims ORDER BY id DESC LIMIT 300').fetchall()
    out=[]
    for row in rows:
        item=dict(row); item['sources']=json.loads(item.pop('sources_json') or '[]')
        item['reviews']=[dict(r) for r in c.execute('SELECT reviewer_name, affiliation, credential_id, decision, rationale, references_checked, created_at FROM epigraphic_reviews WHERE claim_id=? ORDER BY id',(item['id'],)).fetchall()]
        out.append(item)
    c.close(); return jsonify(out)

@app.post('/api/epigraphy/claims')
def epigraphy_claim_create():
    d=request.json or {}
    culture=str(d.get('culture','')).strip(); claim_type=str(d.get('claim_type','')).strip()
    claim_text=str(d.get('claim_text','')).strip(); sources=d.get('sources') or []
    if not culture or not claim_text or claim_type not in ('transcription','transliteration','translation','dating','identification','interpretation'):
        return jsonify({'error':'Renseignez l’écriture/culture, la proposition et un type de proposition valide.'}),400
    clean=[]; seen_sources=set()
    for src in sources[:20]:
        title=str(src.get('title','')).strip(); citation=str(src.get('citation','')).strip(); locator=str(src.get('url_or_doi','')).strip(); source_type=str(src.get('source_type','publication')).strip()
        identity=(locator or citation or title).casefold().strip()
        if locator and not locator.startswith(('http://','https://','doi:','10.')):
            return jsonify({'error':f'Référence invalide : {locator}. Utilisez une URL http(s), un DOI ou une citation bibliographique claire.'}),400
        if title and (citation or locator) and identity not in seen_sources:
            clean.append({'title':title,'citation':citation,'url_or_doi':locator,'source_type':source_type}); seen_sources.add(identity)
    if len(clean)<2:
        return jsonify({'error':'Ajoutez au moins deux références bibliographiques distinctes (URL/DOI/citation non dupliqués). Leur qualité et leur indépendance ne sont pas authentifiées automatiquement.'}),400
    c=connect(); cur=c.execute('INSERT INTO epigraphic_claims(culture,artifact_id,claim_type,claim_text,context,sources_json,created_by,status) VALUES(?,?,?,?,?,?,?,?)', (culture,str(d.get('artifact_id','')).strip(),claim_type,claim_text,str(d.get('context','')).strip(),json.dumps(clean,ensure_ascii=False),str(d.get('created_by','')).strip(),'NEEDS_INDEPENDENT_REVIEW'))
    c.commit(); ident=cur.lastrowid; c.close()
    return jsonify({'ok':True,'id':ident,'status':'NEEDS_INDEPENDENT_REVIEW','message':'Proposition enregistrée. Elle ne sera jamais déclarée scientifiquement vraie par le seul système automatique.'})

@app.post('/api/epigraphy/claims/<int:claim_id>/reviews')
def epigraphy_claim_review(claim_id):
    d=request.json or {}
    name=str(d.get('reviewer_name','')).strip(); affiliation=str(d.get('affiliation','')).strip(); credential=str(d.get('credential_id','')).strip()
    decision=str(d.get('decision','')).strip().upper(); rationale=str(d.get('rationale','')).strip(); refs=str(d.get('references_checked','')).strip()
    if not name or not affiliation or not rationale or decision not in ('AGREE','DISAGREE','ABSTAIN'):
        return jsonify({'error':'Nom, affiliation, justification et décision AGREE/DISAGREE/ABSTAIN sont obligatoires.'}),400
    c=connect(); claim=c.execute('SELECT * FROM epigraphic_claims WHERE id=?',(claim_id,)).fetchone()
    if not claim: c.close(); return jsonify({'error':'Proposition introuvable.'}),404
    existing=c.execute('SELECT id FROM epigraphic_reviews WHERE claim_id=? AND lower(reviewer_name)=lower(?)',(claim_id,name)).fetchone()
    if existing: c.close(); return jsonify({'error':'Ce nom a déjà déposé une revue pour cette proposition. Pour corriger une revue, une procédure de révision versionnée est nécessaire.'}),409
    c.execute('INSERT INTO epigraphic_reviews(claim_id,reviewer_name,affiliation,credential_id,decision,rationale,references_checked) VALUES(?,?,?,?,?,?,?)',(claim_id,name,affiliation,credential,decision,rationale,refs))
    reviews=c.execute('SELECT reviewer_name,decision FROM epigraphic_reviews WHERE claim_id=? ORDER BY id',(claim_id,)).fetchall()
    approvals=[r for r in reviews if r['decision']=='AGREE']; disagreements=[r for r in reviews if r['decision']=='DISAGREE']
    if disagreements: status='DISPUTED_REQUIRES_ADJUDICATION'
    elif len({r['reviewer_name'].strip().casefold() for r in approvals})>=2 and len(claim['sources_json'] and json.loads(claim['sources_json']) or [])>=2: status='TWO_REVIEWS_RECORDED_NOT_SCIENTIFIC_CERTIFICATION'
    else: status='NEEDS_INDEPENDENT_REVIEW'
    c.execute('UPDATE epigraphic_claims SET status=? WHERE id=?',(status,claim_id)); c.commit(); c.close()
    return jsonify({'ok':True,'claim_id':claim_id,'status':status,'reviews_count':len(reviews),'approvals_count':len(approvals),'disagreements_count':len(disagreements),'identity_note':'Les noms, affiliations et identifiants sont déclaratifs et ne sont pas authentifiés par cette application. Ce statut atteste un processus enregistré, pas la vérité de la lecture.'})

@app.get('/api/epigraphy/claims/<int:claim_id>')
def epigraphy_claim_get(claim_id):
    c=connect(); row=c.execute('SELECT * FROM epigraphic_claims WHERE id=?',(claim_id,)).fetchone()
    if not row: c.close(); return jsonify({'error':'Proposition introuvable.'}),404
    item=dict(row); item['sources']=json.loads(item.pop('sources_json') or '[]'); item['reviews']=[dict(r) for r in c.execute('SELECT reviewer_name,affiliation,credential_id,decision,rationale,references_checked,created_at FROM epigraphic_reviews WHERE claim_id=? ORDER BY id',(claim_id,)).fetchall()]; c.close(); return jsonify(item)

@app.get('/api/export')
def export_db():
    c=connect(); data={'signs':[dict(r) for r in c.execute('SELECT * FROM signs')],'inscriptions':[dict(r) for r in c.execute('SELECT * FROM inscriptions')],'epigraphic_claims':[dict(r) for r in c.execute('SELECT * FROM epigraphic_claims')],'epigraphic_reviews':[dict(r) for r in c.execute('SELECT * FROM epigraphic_reviews')]}; c.close()
    from flask import Response
    return Response(json.dumps(data,ensure_ascii=False,indent=2),mimetype='application/json',headers={'Content-Disposition':'attachment; filename=chronos-database-export.json'})


# Authentication for the research API.
# The static Pages client uses short-lived bearer tokens; no passwords or tokens are stored in Git.
TOKEN_LIFETIME_HOURS = 8
PUBLIC_API_ENDPOINTS = {
    'health', 'scientific_policy', 'scripts', 'model_status', 'ocr_status',
    'corpus_stats', 'calendar', 'astronomy', 'pattern_analysis'
}

def _utc_now():
    return datetime.now(timezone.utc)

def _token_digest(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

def _audit(user, action, resource, resource_id='', details=None):
    c = connect()
    c.execute('INSERT INTO audit_log(workspace_id,user_id,action,resource,resource_id,details_json) VALUES(?,?,?,?,?,?)',
              (user['workspace_id'], user['id'], action, resource, str(resource_id or ''),
               json.dumps(details or {}, ensure_ascii=False)[:4000]))
    c.commit()
    c.close()

def _public_user(row):
    return {'id': row['id'], 'email': row['email'], 'display_name': row['display_name'],
            'role': row['role'], 'workspace_id': row['workspace_id'],
            'is_active': bool(row['is_active']), 'created_at': row['created_at']}

def _auth_user_from_request():
    header = request.headers.get('Authorization', '')
    if not header.startswith('Bearer '):
        return None
    token = header[7:].strip()
    if len(token) < 32 or len(token) > 256:
        return None
    c = connect()
    row = c.execute("""SELECT u.*, w.name AS workspace_name, t.expires_at
                       FROM api_tokens t JOIN users u ON u.id=t.user_id
                       JOIN workspaces w ON w.id=u.workspace_id
                       WHERE t.token_hash=? AND t.revoked_at IS NULL AND u.is_active=1""",
                    (_token_digest(token),)).fetchone()
    c.close()
    if not row or row['expires_at'] <= _utc_now().isoformat():
        return None
    return dict(row)

@app.before_request
def enforce_api_authentication():
    if not request.path.startswith('/api/') or request.method == 'OPTIONS':
        return None
    if request.endpoint == 'auth_login':
        return None
    if request.endpoint in PUBLIC_API_ENDPOINTS:
        return None
    user = _auth_user_from_request()
    if not user:
        return jsonify({'error':'Authentification requise ou session expirée.', 'code':'AUTH_REQUIRED'}), 401
    g.current_user = user
    return None

@app.post('/api/auth/login')
def auth_login():
    d = request.get_json(silent=True) or {}
    email = str(d.get('email','')).strip().lower()[:254]
    password = str(d.get('password',''))
    ip_hash = hashlib.sha256((request.remote_addr or 'unknown').encode()).hexdigest()
    now = _utc_now()
    c = connect()
    attempts = c.execute("SELECT COUNT(*) FROM auth_login_attempts WHERE ip_hash=? AND success=0 AND created_at>=?",
                         (ip_hash, (now-timedelta(minutes=15)).isoformat())).fetchone()[0]
    if attempts >= 10:
        c.close()
        return jsonify({'error':'Trop de tentatives. Réessaie dans 15 minutes.'}), 429
    row = c.execute('SELECT * FROM users WHERE email=? AND is_active=1', (email,)).fetchone()
    if not row or not check_password_hash(row['password_hash'], password):
        c.execute('INSERT INTO auth_login_attempts(ip_hash,email,success,created_at) VALUES(?,?,0,?)',
                  (ip_hash, email, now.isoformat()))
        c.commit(); c.close()
        return jsonify({'error':'Identifiants incorrects.'}), 401
    c.execute('DELETE FROM auth_login_attempts WHERE ip_hash=? AND success=0', (ip_hash,))
    token = secrets.token_urlsafe(48)
    expires = (now+timedelta(hours=TOKEN_LIFETIME_HOURS)).isoformat()
    c.execute('INSERT INTO api_tokens(token_hash,user_id,expires_at) VALUES(?,?,?)',
              (_token_digest(token), row['id'], expires))
    c.execute('INSERT INTO auth_login_attempts(ip_hash,email,success,created_at) VALUES(?,?,1,?)',
              (ip_hash, email, now.isoformat()))
    c.execute('INSERT INTO audit_log(workspace_id,user_id,action,resource,details_json) VALUES(?,?,?,?,?)',
              (row['workspace_id'], row['id'], 'LOGIN', 'auth', '{}'))
    c.commit()
    user = dict(row)
    c.close()
    return jsonify({'token':token, 'token_type':'Bearer', 'expires_at':expires,
                    'user':_public_user(user), 'workspace':{'id':user['workspace_id'],'name':'CHRONOS LAB'}})

@app.post('/api/auth/logout')
def auth_logout():
    token = request.headers.get('Authorization','')[7:].strip()
    c=connect()
    c.execute('UPDATE api_tokens SET revoked_at=? WHERE token_hash=? AND revoked_at IS NULL',
              (_utc_now().isoformat(), _token_digest(token)))
    c.execute('INSERT INTO audit_log(workspace_id,user_id,action,resource,details_json) VALUES(?,?,?,?,?)',
              (g.current_user['workspace_id'],g.current_user['id'],'LOGOUT','auth','{}'))
    c.commit(); c.close()
    return jsonify({'ok':True})

@app.get('/api/auth/me')
def auth_me():
    return jsonify({'user':_public_user(g.current_user), 'workspace':{'id':g.current_user['workspace_id'],'name':g.current_user['workspace_name']},
                    'token_expires_at':g.current_user['expires_at']})

@app.get('/api/auth/users')
def auth_list_users():
    if g.current_user['role'] != 'admin':
        return jsonify({'error':'Réservé à l’administrateur.'}), 403
    c=connect()
    rows=c.execute('SELECT * FROM users WHERE workspace_id=? ORDER BY created_at DESC',
                   (g.current_user['workspace_id'],)).fetchall()
    c.close()
    return jsonify([_public_user(r) for r in rows])

@app.post('/api/auth/users')
def auth_create_user():
    if g.current_user['role'] != 'admin':
        return jsonify({'error':'Seul l’administrateur peut créer des comptes.'}), 403
    d=request.get_json(silent=True) or {}
    email=str(d.get('email','')).strip().lower()
    name=str(d.get('display_name','')).strip()
    password=str(d.get('password',''))
    role=str(d.get('role','researcher')).strip()
    if not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',email) or len(email)>254:
        return jsonify({'error':'Adresse e-mail invalide.'}),400
    if not name or len(name)>120:
        return jsonify({'error':'Le nom affiché est obligatoire (120 caractères maximum).'}),400
    if len(password)<14 or len(password)>256:
        return jsonify({'error':'Le mot de passe initial doit contenir au moins 14 caractères.'}),400
    if role not in ('researcher','evaluator'):
        return jsonify({'error':'Rôle autorisé : researcher ou evaluator.'}),400
    c=connect()
    try:
        cur=c.execute('INSERT INTO users(email,display_name,password_hash,role,workspace_id) VALUES(?,?,?,?,?)',
                      (email,name,generate_password_hash(password),role,g.current_user['workspace_id']))
        user_id=cur.lastrowid
        c.execute('INSERT INTO audit_log(workspace_id,user_id,action,resource,resource_id,details_json) VALUES(?,?,?,?,?,?)',
                  (g.current_user['workspace_id'],g.current_user['id'],'USER_CREATED','user',str(user_id),
                   json.dumps({'role':role,'email':email})))
        c.commit()
        row=c.execute('SELECT * FROM users WHERE id=?',(user_id,)).fetchone()
        return jsonify({'ok':True,'user':_public_user(row)}),201
    except sqlite3.IntegrityError:
        c.rollback()
        return jsonify({'error':'Un compte utilise déjà cette adresse e-mail.'}),409
    finally:
        c.close()

def _require_roles(*roles):
    if g.current_user['role'] not in roles:
        return jsonify({'error':'Permission insuffisante pour cette action.'}),403
    return None

def _record_dict(row):
    return {k:row[k] for k in row.keys()}

@app.get('/api/v2/experiments')
def v2_list_experiments():
    c=connect()
    rows=c.execute('SELECT * FROM experiments WHERE workspace_id=? ORDER BY created_at DESC',
                    (g.current_user['workspace_id'],)).fetchall()
    c.close()
    return jsonify([_record_dict(r) for r in rows])

@app.post('/api/v2/experiments')
def v2_create_experiment():
    denied=_require_roles('admin','researcher')
    if denied: return denied
    d=request.get_json(silent=True) or {}
    name=str(d.get('name','')).strip(); model=str(d.get('model','')).strip()
    dataset=str(d.get('dataset','')).strip()
    if not name or not model or not dataset:
        return jsonify({'error':'Le nom, le modèle et le jeu de données sont obligatoires.'}),400
    if any(len(str(d.get(k,'')))>10000 for k in ('parameters','notes')) or max(len(name),len(model),len(dataset))>250:
        return jsonify({'error':'Un champ dépasse la taille autorisée.'}),400
    ident=secrets.token_hex(16); created=_utc_now().isoformat(); c=connect()
    c.execute('INSERT INTO experiments(id,workspace_id,created_by,name,model,version,dataset,parameters,notes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
              (ident,g.current_user['workspace_id'],g.current_user['id'],name,model,str(d.get('version',''))[:250],
               dataset,str(d.get('parameters','')),str(d.get('notes','')),created))
    c.execute('INSERT INTO audit_log(workspace_id,user_id,action,resource,resource_id,details_json) VALUES(?,?,?,?,?,?)',
              (g.current_user['workspace_id'],g.current_user['id'],'EXPERIMENT_CREATED','experiment',ident,json.dumps({'name':name})))
    c.commit(); row=c.execute('SELECT * FROM experiments WHERE id=?',(ident,)).fetchone(); c.close()
    return jsonify(_record_dict(row)),201

@app.delete('/api/v2/experiments/<string:experiment_id>')
def v2_delete_experiment(experiment_id):
    denied=_require_roles('admin','researcher')
    if denied: return denied
    c=connect()
    row=c.execute('SELECT * FROM experiments WHERE id=? AND workspace_id=?',
                  (experiment_id,g.current_user['workspace_id'])).fetchone()
    if not row:
        c.close(); return jsonify({'error':'Expérience introuvable.'}),404
    if g.current_user['role']!='admin' and row['created_by']!=g.current_user['id']:
        c.close(); return jsonify({'error':'Tu peux supprimer uniquement tes propres expériences.'}),403
    c.execute('DELETE FROM experiments WHERE id=?',(experiment_id,))
    c.execute('INSERT INTO audit_log(workspace_id,user_id,action,resource,resource_id,details_json) VALUES(?,?,?,?,?,?)',
              (g.current_user['workspace_id'],g.current_user['id'],'EXPERIMENT_DELETED','experiment',experiment_id,'{}'))
    c.commit(); c.close()
    return jsonify({'ok':True})

@app.get('/api/v2/validations')
def v2_list_validations():
    c=connect()
    rows=c.execute('SELECT * FROM validations WHERE workspace_id=? ORDER BY created_at DESC',
                    (g.current_user['workspace_id'],)).fetchall()
    c.close()
    return jsonify([_record_dict(r) for r in rows])

@app.post('/api/v2/validations')
def v2_create_validation():
    denied=_require_roles('admin','researcher','evaluator')
    if denied: return denied
    d=request.get_json(silent=True) or {}
    model=str(d.get('model','')).strip(); dataset=str(d.get('dataset','')).strip()
    protocol=str(d.get('protocol','')).strip()
    if not model or not dataset or not protocol:
        return jsonify({'error':'Le modèle, le jeu de test et le protocole sont obligatoires.'}),400
    try:
        precision=float(d.get('precision')); recall=float(d.get('recall')); f1=float(d.get('f1')); samples=int(d.get('samples'))
    except (TypeError,ValueError):
        return jsonify({'error':'Les métriques doivent être numériques.'}),400
    if any(not math.isfinite(x) or x<0 or x>100 for x in (precision,recall,f1)) or samples<0:
        return jsonify({'error':'Les scores doivent être entre 0 et 100 et les échantillons positifs ou nuls.'}),400
    ident=secrets.token_hex(16); created=_utc_now().isoformat(); c=connect()
    c.execute('INSERT INTO validations(id,workspace_id,created_by,model,dataset,precision,recall,f1,samples,protocol,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
              (ident,g.current_user['workspace_id'],g.current_user['id'],model,dataset,precision,recall,f1,samples,protocol,created))
    c.execute('INSERT INTO audit_log(workspace_id,user_id,action,resource,resource_id,details_json) VALUES(?,?,?,?,?,?)',
              (g.current_user['workspace_id'],g.current_user['id'],'VALIDATION_CREATED','validation',ident,json.dumps({'model':model,'dataset':dataset})))
    c.commit(); row=c.execute('SELECT * FROM validations WHERE id=?',(ident,)).fetchone(); c.close()
    return jsonify(_record_dict(row)),201

@app.delete('/api/v2/validations/<string:validation_id>')
def v2_delete_validation(validation_id):
    denied=_require_roles('admin')
    if denied: return denied
    c=connect()
    row=c.execute('SELECT id FROM validations WHERE id=? AND workspace_id=?',(validation_id,g.current_user['workspace_id'])).fetchone()
    if not row:
        c.close(); return jsonify({'error':'Évaluation introuvable.'}),404
    c.execute('DELETE FROM validations WHERE id=?',(validation_id,))
    c.execute('INSERT INTO audit_log(workspace_id,user_id,action,resource,resource_id,details_json) VALUES(?,?,?,?,?,?)',
              (g.current_user['workspace_id'],g.current_user['id'],'VALIDATION_DELETED','validation',validation_id,'{}'))
    c.commit(); c.close()
    return jsonify({'ok':True})

@app.get('/api/v2/audit')
def v2_audit_log():
    if g.current_user['role']!='admin':
        return jsonify({'error':'Réservé à l’administrateur.'}),403
    c=connect()
    rows=c.execute('SELECT id,user_id,action,resource,resource_id,details_json,created_at FROM audit_log WHERE workspace_id=? ORDER BY id DESC LIMIT 500',
                   (g.current_user['workspace_id'],)).fetchall()
    c.close()
    return jsonify([_record_dict(r) for r in rows])

def bootstrap_admin():
    email=os.environ.get('CHRONOS_BOOTSTRAP_ADMIN_EMAIL','').strip().lower()
    password=os.environ.get('CHRONOS_BOOTSTRAP_ADMIN_PASSWORD','')
    if not email or not password:
        return
    if len(password)<14:
        app.logger.error('CHRONOS_BOOTSTRAP_ADMIN_PASSWORD must contain at least 14 characters; admin was not bootstrapped.')
        return
    c=connect()
    existing=c.execute('SELECT id FROM users WHERE email=?',(email,)).fetchone()
    if not existing:
        c.execute('INSERT INTO users(email,display_name,password_hash,role,workspace_id) VALUES(?,?,?,?,1)',
                  (email,email.split('@')[0],generate_password_hash(password),'admin'))
        c.commit()
        app.logger.warning('Initial CHRONOS LAB admin account created from environment configuration.')
    c.close()

bootstrap_admin()

if __name__=='__main__':
    host = os.environ.get('CHRONOS_HOST', '127.0.0.1')
    print(f'CHRONOS Lab démarre sur http://{host}:{os.environ.get("PORT","5000")}')
    app.run(host=host,port=int(os.environ.get('PORT','5000')),debug=False)
