'use strict';
(() => {
 const $=s=>document.querySelector(s);
 const keys={notes:'chronos-lab-notebook-v1',hyp:'chronos-lab-hypotheses-v1',data:'chronos-lab-datasets-v1',tasks:'chronos-lab-tasks-v1'};
 const apiKey='chronos-lab-api-base-v1',tokenKey='chronos-lab-v2-token',userKey='chronos-lab-v2-user';
 let remote=false, user=null, busy=false;
 const read=k=>{try{const v=JSON.parse(localStorage.getItem(k)||'[]');return Array.isArray(v)?v:[]}catch{return[]}};
 const write=(k,v)=>localStorage.setItem(k,JSON.stringify(v));
 const stamp=()=>new Date().toISOString();
 const api=()=> (localStorage.getItem(apiKey)||'').trim().replace(/\/$/,'');
 const token=()=>sessionStorage.getItem(tokenKey)||'';
 function download(name,data,type='application/json'){const blob=new Blob([data],{type}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();URL.revokeObjectURL(url)}
 function node(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e}
 function action(label,fn,disabled=false){const b=node('button','cl-mini',label);b.type='button';b.disabled=disabled;b.addEventListener('click',fn);return b}
 async function apiFetch(path,options={}) {
  const base=api();if(!base)throw new Error('URL API non configurée.');
  const headers=new Headers(options.headers||{});headers.set('Accept','application/json');headers.set('Authorization','Bearer '+token());
  if(options.body&&!headers.has('Content-Type'))headers.set('Content-Type','application/json');
  const r=await fetch(base+path,{...options,headers});let body={};try{body=await r.json()}catch{}
  if(!r.ok)throw new Error(body.error||('Erreur HTTP '+r.status));return body;
 }
 function status(s){const el=$('#clBundleStatus');if(el)el.textContent=s}
 function who(){try{return JSON.parse(sessionStorage.getItem(userKey)||'null')}catch{return null}}
 function mapType(type){return ({note:'notes',hypothesis:'hyp',dataset:'data',task:'tasks'})[type]}
 function localId(){return crypto.randomUUID?crypto.randomUUID():String(Date.now())+'-'+Math.random().toString(16).slice(2)}
 async function listItems(type){
  if(remote){
   const rows=await apiFetch('/api/v2/research-artifacts?type='+encodeURIComponent(type));
   const mapped=rows.map(r=>({id:r.id,at:r.created_at,updated_at:r.updated_at,created_by:r.created_by,...r.payload}));
   return mapped;
  }
  return read(keys[mapType(type)]);
 }
 async function createItem(type,payload){
  if(remote){await apiFetch('/api/v2/research-artifacts',{method:'POST',body:JSON.stringify({type,payload})});}
  else write(keys[mapType(type)],[...read(keys[mapType(type)]),{id:localId(),at:stamp(),...payload}]);
 }
 async function updateItem(type,item){
  if(remote){await apiFetch('/api/v2/research-artifacts/'+encodeURIComponent(item.id),{method:'PUT',body:JSON.stringify({payload:item})});}
  else write(keys[mapType(type)],read(keys[mapType(type)]).map(x=>x.id===item.id?item:x));
 }
 async function removeItem(type,id){
  if(remote)await apiFetch('/api/v2/research-artifacts/'+encodeURIComponent(id),{method:'DELETE'});
  else write(keys[mapType(type)],read(keys[mapType(type)]).filter(x=>x.id!==id));
 }
 function item(host,title,meta,body,buttons=[],hash=''){
  const card=node('article','cl-item'),head=node('div','cl-item-head'),left=node('div');
  left.append(node('strong','',title),node('div','cl-meta',meta));head.append(left);card.append(head);
  if(body)card.append(node('p','',body));if(hash)card.append(node('div','cl-hash','SHA-256 · '+hash));
  if(buttons.length){const actions=node('div','cl-item-actions');buttons.forEach(b=>actions.append(b));card.append(actions)}host.append(card);
 }
 function empty(host,message){if(!host.children.length)host.append(node('div','v2-empty',message))}
 async function render(){
  const n=$('#clNotebookList'),h=$('#clHypothesisList'),d=$('#clDatasetList'),t=$('#clTaskList');
  [n,h,d,t].forEach(x=>x?.replaceChildren());
  try{
   const [notes,hyps,datasets,tasks]=await Promise.all([listItems('note'),listItems('hypothesis'),listItems('dataset'),listItems('task')]);
   notes.slice().reverse().forEach(x=>item(n,x.title,x.kind+' · '+new Date(x.at).toLocaleString('fr-FR')+(x.experiment?' · '+x.experiment:''),x.body,[action('Supprimer',()=>removeAndRender('note',x.id))]));
   hyps.slice().reverse().forEach(x=>item(h,x.claim,x.status+' · '+new Date(x.at).toLocaleString('fr-FR'),'Critère : '+x.criterion+(x.evidence?'\n'+x.evidence:''),[action('Supprimer',()=>removeAndRender('hypothesis',x.id))]));
   datasets.slice().reverse().forEach(x=>item(d,x.name,'Source : '+x.source+' · Licence : '+(x.license||'non précisée'),'Fichier : '+x.filename,[action('Copier le hash',async()=>{try{await navigator.clipboard.writeText(x.hash);status('Empreinte copiée.')}catch{status('Presse-papiers indisponible.')} }),action('Supprimer',()=>removeAndRender('dataset',x.id))],x.hash));
   tasks.slice().reverse().forEach(x=>item(t,x.title,(x.done?'Terminée':'À faire')+' · priorité '+x.priority+' · '+(x.owner||'sans responsable'),'',[action(x.done?'Rouvrir':'Terminer',()=>toggleTask(x)),action('Supprimer',()=>removeAndRender('task',x.id))]));
   empty(n,'Aucune note pour le moment.');empty(h,'Aucune hypothèse enregistrée.');empty(d,'Aucun jeu de données enregistré.');empty(t,'Aucune tâche en attente.');
   status(remote?'Synchronisé avec le serveur CHRONOS LAB · espace partagé.':'Mode local : ces données restent dans ce navigateur. Connecte-toi et configure l’API pour les partager.');
  }catch(err){remote=false;status('Synchronisation impossible : '+err.message+'. Les données locales restent conservées.');}
 }
 async function removeAndRender(type,id){try{await removeItem(type,id);await render();status('Ressource supprimée.')}catch(e){status(e.message)}}
 async function toggleTask(task){try{await updateItem('task',{...task,done:!task.done});await render()}catch(e){status(e.message)}}
 async function addFromForm(formId,type,build){
  $('#'+formId)?.addEventListener('submit',async e=>{e.preventDefault();if(busy)return;busy=true;const btn=e.currentTarget.querySelector('button[type=submit]');if(btn)btn.disabled=true;
   try{const f=new FormData(e.currentTarget),payload=build(f);await createItem(type,payload);e.currentTarget.reset();await render();status(remote?'Enregistré et partagé avec le laboratoire.':'Enregistré localement.');}
   catch(err){status('Échec de l’enregistrement : '+err.message)}finally{busy=false;if(btn)btn.disabled=false}
  });
 }
 addFromForm('clNotebookForm','note',f=>({title:f.get('title').trim(),kind:f.get('kind'),experiment:f.get('experiment').trim(),body:f.get('body').trim()}));
 addFromForm('clHypothesisForm','hypothesis',f=>({claim:f.get('claim').trim(),criterion:f.get('criterion').trim(),status:f.get('status'),evidence:f.get('evidence').trim()}));
 addFromForm('clTaskForm','task',f=>({title:f.get('title').trim(),owner:f.get('owner').trim(),priority:f.get('priority'),done:false}));
 $('#clDatasetForm')?.addEventListener('submit',async e=>{
  e.preventDefault();if(busy)return;const f=new FormData(e.currentTarget),file=$('#clDatasetFile').files[0],btn=e.currentTarget.querySelector('button[type=submit]');
  if(!file)return;if(!crypto.subtle){status('SHA-256 indisponible : utilise HTTPS ou localhost.');return}
  busy=true;btn.disabled=true;btn.textContent='Calcul de l’empreinte…';
  try{const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await file.arrayBuffer()))).map(b=>b.toString(16).padStart(2,'0')).join('');
   await createItem('dataset',{name:f.get('name').trim(),source:f.get('source').trim(),license:f.get('license').trim(),filename:file.name,size_bytes:file.size,hash});
   e.currentTarget.reset();await render();status(remote?'Métadonnées et empreinte partagées. Le fichier lui-même n’a pas été envoyé.':'Empreinte enregistrée localement ; aucun fichier n’a été envoyé.');
  }catch(err){status('Impossible d’enregistrer le jeu de données : '+err.message)}finally{busy=false;btn.disabled=false;btn.textContent='Calculer SHA-256 et enregistrer'}
 });
 $('#clExportBundle')?.addEventListener('click',async()=>{
  try{const [notebook,hypotheses,datasets,tasks]=await Promise.all([listItems('note'),listItems('hypothesis'),listItems('dataset'),listItems('task')]);
   const bundle={schema:'chronos-lab-research-bundle-v2',created_at:stamp(),workspace:'CHRONOS LAB',source:remote?'backend partagé':'stockage local de ce navigateur',storage_note:'L’export est un instantané; il ne remplace pas une sauvegarde serveur. Vérifier les sources et sécuriser le fichier.',notebook,hypotheses,datasets,tasks,legacy_local_experiments:read('chronos-lab-v2-experiments'),legacy_local_validations:read('chronos-lab-v2-validations'),documentary_workspace:read('chronos-lab-workspace-v1')};
   download('chronos-lab-research-bundle-'+new Date().toISOString().slice(0,10)+'.json',JSON.stringify(bundle,null,2));status('Dossier de recherche exporté depuis '+(remote?'le serveur':'ce navigateur')+'.');
  }catch(err){status('Export impossible : '+err.message)}
 });
 $('#clExportNotes')?.addEventListener('click',async()=>{try{const rows=[['date','type','titre','experience','note'],...(await listItems('note')).map(x=>[x.at,x.kind,x.title,x.experiment,x.body])];const csv=rows.map(r=>r.map(v=>'"'+String(v??'').replace(/"/g,'""')+'"').join(',')).join('\r\n');download('chronos-lab-carnet.csv','\uFEFF'+csv,'text/csv;charset=utf-8')}catch(e){status(e.message)}});
 $('#clClearCompleted')?.addEventListener('click',async()=>{try{const all=await listItems('task'),done=all.filter(x=>x.done);for(const task of done)await removeItem('task',task.id);await render();status(done.length+' tâche(s) terminée(s) supprimée(s).')}catch(e){status(e.message)}});
 async function authChanged(){
  user=who();remote=!!(api()&&token()&&user);
  const badge=$('#clStorageMode');if(badge)badge.textContent=remote?'SERVEUR · PARTAGÉ':'LOCAL · NAVIGATEUR';
  await render();
 }
 document.addEventListener('chronos-auth-changed',authChanged);
 document.addEventListener('DOMContentLoaded',authChanged);
 authChanged();
})();