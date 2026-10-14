'use strict';
(() => {
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const EK='chronos-lab-v2-experiments', VK='chronos-lab-v2-validations', AK='chronos-lab-api-base-v1', TK='chronos-lab-v2-token', UK='chronos-lab-v2-user';
let ex=[], va=[], user=null, previewUrl='', serverPreviewUrl='';
const read=k=>{try{const v=JSON.parse(localStorage.getItem(k)||'[]');return Array.isArray(v)?v:[]}catch{return[]}};
const api=()=> (localStorage.getItem(AK)||'').trim().replace(/\/$/,'');
const token=()=>sessionStorage.getItem(TK)||'';
function notify(s){const t=$('#toast');if(t){t.textContent=s;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),3200)}}
function download(name,data,type='application/json'){const b=new Blob([data],{type}),u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download=name;document.body.append(a);a.click();a.remove();URL.revokeObjectURL(u)}
function addCell(row,value){const td=document.createElement('td');td.textContent=String(value??'');row.append(td)}
function renderTable(id,rows,heads){const host=$(id);if(!host)return;host.replaceChildren();if(!rows.length){const p=document.createElement('div');p.className='v2-empty';p.textContent='Aucun enregistrement sur le serveur pour le moment.';host.append(p);return}const wrap=document.createElement('div');wrap.className='v2-table-wrap';const table=document.createElement('table');table.className='v2-table';const thead=document.createElement('thead'),tr=document.createElement('tr');heads.forEach(h=>addCell(tr,h));thead.append(tr);table.append(thead);const body=document.createElement('tbody');rows.slice().reverse().forEach(r=>{const tr=document.createElement('tr');r.forEach(v=>addCell(tr,v));body.append(tr)});table.append(body);wrap.append(table);host.append(wrap)}
async function apiFetch(path, options={}) {
 const base=api(); if(!base)throw new Error('URL de l’API non configurée.');
 const headers=new Headers(options.headers||{});headers.set('Accept','application/json');
 if(token())headers.set('Authorization','Bearer '+token());
 if(options.body && !(options.body instanceof FormData) && !headers.has('Content-Type'))headers.set('Content-Type','application/json');
 const response=await fetch(base+path,{...options,headers});
 let payload={};try{payload=await response.json()}catch{}
 if(response.status===401 && path!=='/api/auth/login'){sessionStorage.removeItem(TK);sessionStorage.removeItem(UK);user=null;updateAuthUI();throw new Error('Session expirée. Reconnecte-toi.')}
 if(!response.ok)throw new Error(payload.error||('Erreur HTTP '+response.status));
 return payload;
}
function dateLabel(v){try{return new Date(v).toLocaleString('fr-FR')}catch{return String(v||'')}}
function sync(){
 const put=(s,v)=>{const e=$(s);if(e)e.textContent=v};
 put('#v2ClaimCount',read('chronos-lab-workspace-v1').length);
 put('#v2EventCount',read('chronos-lab-events-v1').length);
 put('#v2ExperimentCount',ex.length);put('#v2ValidationCount',va.length);
 put('#v2AverageF1',va.length?(va.reduce((s,v)=>s+Number(v.f1||0),0)/va.length).toFixed(1)+'%':'—');
 renderTable('#v2ExperimentsList',ex.map(e=>[e.name,e.model+' '+(e.version||''),e.dataset,dateLabel(e.created_at||e.at)]),['Expérience','Modèle / version','Jeu de données','Créée le']);
 renderTable('#v2ValidationsList',va.map(v=>[v.model,v.dataset,v.precision+'%',v.recall+'%',v.f1+'%',v.samples,dateLabel(v.created_at||v.at)]),['Modèle','Jeu de test','Précision','Rappel','F1','Échantillons','Date']);
 const chart=$('#v2ValidationChart');if(chart){chart.replaceChildren();va.slice(-8).forEach(v=>{const col=document.createElement('div');col.className='v2-chart-col';const label=document.createElement('small');label.textContent=v.model;const bar=document.createElement('div');bar.className='v2-chart-bar';bar.style.height=Math.max(3,Math.min(100,Number(v.f1)||0))+'%';const score=document.createElement('b');score.textContent=v.f1+'%';col.append(score,bar,label);chart.append(col)})}
}
function updateAuthUI(){
 const status=$('#v2AuthStatus'), logout=$('#v2Logout'), userForm=$('#v2UserForm'), syncBtn=$('#v2SyncLocal'), users=$('#v2UsersList');
 if(status)status.textContent=user?(user.display_name+' · '+user.email+' · rôle : '+user.role+' · espace : CHRONOS LAB'):'Non connecté. Les fiches partagées nécessitent une connexion au backend.';
 if(logout)logout.hidden=!user;if(userForm)userForm.hidden=!(user&&user.role==='admin');
 if(syncBtn)syncBtn.disabled=!user;
 if(users && !(user&&user.role==='admin'))users.textContent='Connecte-toi comme administrateur pour créer des comptes.';
}
async function loadRecords(){
 const [experiments,validations]=await Promise.all([apiFetch('/api/v2/experiments'),apiFetch('/api/v2/validations')]);
 ex=experiments;va=validations;sync();updateAuthUI();
}
async function loadUsers(){
 if(!user||user.role!=='admin')return;
 const users=await apiFetch('/api/auth/users'),host=$('#v2UsersList');if(!host)return;
 host.replaceChildren();if(!users.length){host.textContent='Aucun compte créé.';return}
 const wrap=document.createElement('div');wrap.className='v2-table-wrap';const table=document.createElement('table');table.className='v2-table';
 const head=document.createElement('tr');['Nom','E-mail','Rôle','Statut'].forEach(v=>addCell(head,v));const thead=document.createElement('thead');thead.append(head);table.append(thead);
 const body=document.createElement('tbody');users.forEach(u=>{const tr=document.createElement('tr');[u.display_name,u.email,u.role,u.is_active?'Actif':'Désactivé'].forEach(v=>addCell(tr,v));body.append(tr)});table.append(body);wrap.append(table);host.append(wrap);
}
async function login(email,password){
 const result=await apiFetch('/api/auth/login',{method:'POST',body:JSON.stringify({email,password})});
 sessionStorage.setItem(TK,result.token);sessionStorage.setItem(UK,JSON.stringify(result.user));user=result.user;
 await loadRecords();updateAuthUI();await loadUsers();document.dispatchEvent(new Event('chronos-auth-changed'));notify('Connexion réussie. Les fiches sont chargées depuis le serveur.');
}
function showNoAuth(){notify('Connecte-toi pour enregistrer ou consulter les fiches partagées.')}
$('#v2LoginForm')?.addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.currentTarget),status=$('#v2AuthStatus');status.textContent='Connexion…';try{await login(f.get('email'),f.get('password'));e.currentTarget.reset()}catch(err){status.textContent=err.message;notify(err.message)}});
$('#v2Logout')?.addEventListener('click',async()=>{try{if(token())await apiFetch('/api/auth/logout',{method:'POST'})}catch{}sessionStorage.removeItem(TK);sessionStorage.removeItem(UK);user=null;ex=[];va=[];sync();updateAuthUI();document.dispatchEvent(new Event('chronos-auth-changed'));notify('Déconnexion effectuée.')});
$('#v2UserForm')?.addEventListener('submit',async e=>{e.preventDefault();if(!user||user.role!=='admin')return;const f=new FormData(e.currentTarget);try{const result=await apiFetch('/api/auth/users',{method:'POST',body:JSON.stringify({display_name:f.get('display_name'),email:f.get('email'),password:f.get('password'),role:f.get('role')})});e.currentTarget.reset();await loadUsers();notify('Compte créé : '+result.user.email)}catch(err){notify(err.message)}});
$('#v2SyncLocal')?.addEventListener('click',async()=>{
 if(!user){showNoAuth();return}
 const marker='chronos-lab-v2-imported-'+user.id;
 if(localStorage.getItem(marker)){notify('Les anciennes fiches locales ont déjà été importées pour ce compte.');return}
 const oldEx=read(EK),oldVa=read(VK);if(!oldEx.length&&!oldVa.length){notify('Aucune ancienne fiche locale à importer.');return}
 const out=$('#v2ImportStatus');out.textContent='Import en cours…';let importedE=0,importedV=0;
 try{
  for(const x of oldEx){await apiFetch('/api/v2/experiments',{method:'POST',body:JSON.stringify({name:x.name,model:x.model,version:x.version||'',dataset:x.dataset,parameters:x.parameters||'',notes:x.notes||''})});importedE++}
  for(const v of oldVa){await apiFetch('/api/v2/validations',{method:'POST',body:JSON.stringify({model:v.model,dataset:v.dataset,precision:Number(v.precision),recall:Number(v.recall),f1:Number(v.f1),samples:Number(v.samples),protocol:v.protocol||'Import local historique ; protocole original à vérifier.'})});importedV++}
  localStorage.setItem(marker,new Date().toISOString());await loadRecords();out.textContent='Import terminé : '+importedE+' expérience(s), '+importedV+' évaluation(s). Les données locales sont conservées.';notify('Import vers le serveur terminé.')
 }catch(err){out.textContent='Import partiel : '+importedE+' expérience(s), '+importedV+' évaluation(s). Corrige le problème avant de relancer pour éviter les doublons.';notify(err.message)}
});
$('#v2ExperimentForm')?.addEventListener('submit',async e=>{e.preventDefault();if(!user){showNoAuth();return}const f=new FormData(e.currentTarget);try{await apiFetch('/api/v2/experiments',{method:'POST',body:JSON.stringify({name:f.get('name'),model:f.get('model'),version:f.get('version'),dataset:f.get('dataset'),parameters:f.get('parameters'),notes:f.get('notes')})});await loadRecords();e.currentTarget.reset();notify('Expérience enregistrée sur le serveur.')}catch(err){notify(err.message)}});
$('#v2ValidationForm')?.addEventListener('submit',async e=>{e.preventDefault();if(!user){showNoAuth();return}const f=new FormData(e.currentTarget),n=k=>Number(f.get(k));try{await apiFetch('/api/v2/validations',{method:'POST',body:JSON.stringify({model:f.get('model'),dataset:f.get('dataset'),precision:n('precision'),recall:n('recall'),f1:n('f1'),samples:n('samples'),protocol:f.get('protocol')})});await loadRecords();e.currentTarget.reset();notify('Évaluation enregistrée sur le serveur. Les métriques restent déclaratives.')}catch(err){notify(err.message)}});
$('#v2Image')?.addEventListener('change',e=>{const f=e.target.files[0],p=$('#v2ImagePreview');if(previewUrl)URL.revokeObjectURL(previewUrl);if(!f){p.hidden=true;return}previewUrl=URL.createObjectURL(f);p.src=previewUrl;p.hidden=false});
async function loadProtectedImage(path,base){const p=$('#v2ServerPreview');if(serverPreviewUrl)URL.revokeObjectURL(serverPreviewUrl);const u=new URL(path,base).href;const r=await fetch(u,{headers:{Authorization:'Bearer '+token()}});if(!r.ok)throw new Error('Impossible de charger l’aperçu image ('+r.status+').');serverPreviewUrl=URL.createObjectURL(await r.blob());p.src=serverPreviewUrl;p.hidden=false}
$('#v2AnalyzeImage')?.addEventListener('submit',async e=>{e.preventDefault();const out=$('#v2GlyphResult'),f=$('#v2Image')?.files[0],b=api();if(!user){showNoAuth();out.textContent='Connecte-toi avant de lancer une analyse.';return}if(!f){out.textContent='Sélectionne une image.';return}if(!b){out.textContent='Configure l’URL de ton API Flask. GitHub Pages ne peut pas exécuter Python/PyTorch.';return}const data=new FormData();data.append('image',f);data.append('script',$('#v2Script').value);data.append('segmentation',$('#v2Segmentation').value);out.textContent='Analyse en cours…';try{const j=await apiFetch('/api/analyze-image',{method:'POST',body:data});out.textContent=JSON.stringify(j,null,2);const path=j.segmentation_overlay||j.processed_image||j.original_image;if(path)await loadProtectedImage(path,b);else $('#v2ServerPreview').hidden=true}catch(err){out.textContent+='\\nErreur : '+err.message+' — vérifie le backend, HTTPS et CORS.'}});
$('#v2CheckBackend')?.addEventListener('click',async()=>{const out=$('#v2BackendStatus'),b=api();if(!b){out.textContent='API non configurée. Renseigne son URL dans Données & connexion.';return}out.textContent='Vérification…';try{const results=await Promise.all(['/api/health','/api/model-status','/api/corpus-stats'].map(async p=>{const r=await fetch(b+p);return {route:p,status:r.status,data:await r.json()}}));out.textContent=JSON.stringify(results,null,2)}catch(err){out.textContent='Connexion impossible : '+err.message+' — vérifie URL, CORS et serveur.'}});
$('#v2ExportJson')?.addEventListener('click',()=>download('chronos-lab-v2.json',JSON.stringify({exported_at:new Date().toISOString(),workspace:'CHRONOS LAB',experiments:ex,validations:va,scientific_note:'Les métriques manuelles ne sont pas recalculées ni certifiées.'},null,2)));
$('#v2ExportCsv')?.addEventListener('click',()=>{const rows=[['type','date','model','dataset','precision','recall','f1','samples']];ex.forEach(v=>rows.push(['experience',v.created_at,v.model,v.dataset,'','','','']));va.forEach(v=>rows.push(['validation',v.created_at,v.model,v.dataset,v.precision,v.recall,v.f1,v.samples]));download('chronos-lab-v2.csv','\uFEFF'+rows.map(r=>r.map(v=>'"'+String(v??'').replace(/"/g,'""')+'"').join(',')).join('\r\n'),'text/csv;charset=utf-8')});
$('#v2PrintReport')?.addEventListener('click',()=>window.print());
const sec=$('#v2SecurityChecklist');if(sec)sec.textContent='Le backend exige un jeton valide pour les routes privées. Les rôles sont contrôlés côté serveur ; les actions importantes sont journalisées. Avant la production : HTTPS, sauvegardes restaurables, secret admin hors du dépôt, CORS limité à Pages, stockage persistant et rotation des secrets.';
const savedUser=sessionStorage.getItem(UK);try{user=savedUser?JSON.parse(savedUser):null}catch{user=null}
updateAuthUI();sync();
if(token()){apiFetch('/api/auth/me').then(r=>{user=r.user;sessionStorage.setItem(UK,JSON.stringify(user));updateAuthUI();return loadRecords()}).then(loadUsers).then(()=>document.dispatchEvent(new Event('chronos-auth-changed'))).catch(err=>{const s=$('#v2AuthStatus');if(s)s.textContent=err.message})}
})();