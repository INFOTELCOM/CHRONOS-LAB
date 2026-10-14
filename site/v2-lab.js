'use strict';
(() => {
 const $=s=>document.querySelector(s);
 const keys={notes:'chronos-lab-notebook-v1',hyp:'chronos-lab-hypotheses-v1',data:'chronos-lab-datasets-v1',tasks:'chronos-lab-tasks-v1'};
 const read=k=>{try{const v=JSON.parse(localStorage.getItem(k)||'[]');return Array.isArray(v)?v:[]}catch{return[]}};
 const write=(k,v)=>localStorage.setItem(k,JSON.stringify(v));
 const stamp=()=>new Date().toISOString();
 const esc=s=>String(s??'');
 function download(name,data,type='application/json'){const blob=new Blob([data],{type}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();URL.revokeObjectURL(url)}
 function node(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e}
 function action(label,fn){const b=node('button','cl-mini',label);b.type='button';b.addEventListener('click',fn);return b}
 function item(host,title,meta,body,buttons=[],hash=''){
  const card=node('article','cl-item'),head=node('div','cl-item-head'),left=node('div');
  left.append(node('strong','',title),node('div','cl-meta',meta));head.append(left);card.append(head);
  if(body)card.append(node('p','',body));if(hash)card.append(node('div','cl-hash','SHA-256 · '+hash));
  if(buttons.length){const actions=node('div','cl-item-actions');buttons.forEach(b=>actions.append(b));card.append(actions)}host.append(card);
 }
 function render(){
  const notes=read(keys.notes),hyps=read(keys.hyp),datasets=read(keys.data),tasks=read(keys.tasks);
  const n=$('#clNotebookList'),h=$('#clHypothesisList'),d=$('#clDatasetList'),t=$('#clTaskList');
  [[n,notes],[h,hyps],[d,datasets],[t,tasks]].forEach(([host,arr])=>host.replaceChildren());
  if(!notes.length)n.append(node('div','v2-empty','Aucune note pour le moment.'));
  notes.slice().reverse().forEach(x=>item(n,x.title,x.kind+' · '+new Date(x.at).toLocaleString('fr-FR')+(x.experiment?' · '+x.experiment:''),x.body,[action('Supprimer',()=>removeItem(keys.notes,x.id))]));
  if(!hyps.length)h.append(node('div','v2-empty','Aucune hypothèse enregistrée.'));
  hyps.slice().reverse().forEach(x=>item(h,x.claim,x.status+' · '+new Date(x.at).toLocaleString('fr-FR'),'Critère : '+x.criterion+(x.evidence?'\n'+x.evidence:''),[action('Supprimer',()=>removeItem(keys.hyp,x.id))]));
  if(!datasets.length)d.append(node('div','v2-empty','Aucun jeu de données enregistré.'));
  datasets.slice().reverse().forEach(x=>item(d,x.name,'Source : '+x.source+' · Licence : '+(x.license||'non précisée'), 'Fichier : '+x.filename,[action('Copier le hash',()=>{navigator.clipboard?.writeText(x.hash);status('Empreinte copiée si le navigateur autorise le presse-papiers.') }),action('Supprimer',()=>removeItem(keys.data,x.id))],x.hash));
  if(!tasks.length)t.append(node('div','v2-empty','Aucune tâche en attente.'));
  tasks.slice().reverse().forEach(x=>item(t,x.title,(x.done?'Terminée':'À faire')+' · priorité '+x.priority+' · '+(x.owner||'sans responsable'),'',[action(x.done?'Rouvrir':'Terminer',()=>{const all=read(keys.tasks),v=all.find(y=>y.id===x.id);if(v)v.done=!v.done;write(keys.tasks,all);render()}),action('Supprimer',()=>removeItem(keys.tasks,x.id))]));
 }
 function status(s){const el=$('#clBundleStatus');if(el)el.textContent=s}
 function removeItem(k,id){write(k,read(k).filter(x=>x.id!==id));render()}
 function submit(id,key,build){$('#'+id)?.addEventListener('submit',e=>{e.preventDefault();const f=new FormData(e.currentTarget),v=build(f);write(key,[...read(key),{id:crypto.randomUUID?crypto.randomUUID():String(Date.now())+'-'+Math.random(),at:stamp(),...v}]);e.currentTarget.reset();render();status('Enregistré sur cet appareil. Pense à exporter régulièrement le dossier.');})}
 submit('clNotebookForm',keys.notes,f=>({title:f.get('title').trim(),kind:f.get('kind'),experiment:f.get('experiment').trim(),body:f.get('body').trim()}));
 submit('clHypothesisForm',keys.hyp,f=>({claim:f.get('claim').trim(),criterion:f.get('criterion').trim(),status:f.get('status'),evidence:f.get('evidence').trim()}));
 submit('clTaskForm',keys.tasks,f=>({title:f.get('title').trim(),owner:f.get('owner').trim(),priority:f.get('priority'),done:false}));
 $('#clDatasetForm')?.addEventListener('submit',async e=>{
  e.preventDefault();const f=new FormData(e.currentTarget),file=$('#clDatasetFile').files[0],btn=e.currentTarget.querySelector('button[type=submit]');
  if(!file)return; if(!crypto.subtle){status('SHA-256 indisponible : utilise une page HTTPS ou localhost.');return}
  btn.disabled=true;btn.textContent='Calcul de l’empreinte…';
  try{const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await file.arrayBuffer()))).map(b=>b.toString(16).padStart(2,'0')).join('');
   write(keys.data,[...read(keys.data),{id:crypto.randomUUID?crypto.randomUUID():String(Date.now()),at:stamp(),name:f.get('name').trim(),source:f.get('source').trim(),license:f.get('license').trim(),filename:file.name,size_bytes:file.size,hash}]);e.currentTarget.reset();render();status('Empreinte SHA-256 calculée. Le fichier lui-même n’a pas été envoyé ni stocké.');
  }catch(err){status('Impossible de calculer l’empreinte : '+err.message)}finally{btn.disabled=false;btn.textContent='Calculer SHA-256 et enregistrer'}
 });
 $('#clExportBundle')?.addEventListener('click',()=>{
  const bundle={schema:'chronos-lab-research-bundle-v1',created_at:stamp(),workspace:'CHRONOS LAB',storage_note:'Ce dossier est assemblé depuis le stockage local de ce navigateur. Vérifier les sources et conserver une copie sécurisée.',notebook:read(keys.notes),hypotheses:read(keys.hyp),datasets:read(keys.data),tasks:read(keys.tasks),legacy_local_experiments:read('chronos-lab-v2-experiments'),legacy_local_validations:read('chronos-lab-v2-validations'),documentary_workspace:read('chronos-lab-workspace-v1')};
  download('chronos-lab-research-bundle-'+new Date().toISOString().slice(0,10)+'.json',JSON.stringify(bundle,null,2));status('Dossier de recherche exporté. Il contient des données locales, pas une sauvegarde du serveur.');
 });
 $('#clExportNotes')?.addEventListener('click',()=>{const rows=[['date','type','titre','experience','note'],...read(keys.notes).map(x=>[x.at,x.kind,x.title,x.experiment,x.body])];const csv=rows.map(r=>r.map(v=>'"'+String(v??'').replace(/"/g,'""')+'"').join(',')).join('\r\n');download('chronos-lab-carnet.csv','\uFEFF'+csv,'text/csv;charset=utf-8');});
 $('#clClearCompleted')?.addEventListener('click',()=>{const all=read(keys.tasks),done=all.filter(x=>x.done).length;write(keys.tasks,all.filter(x=>!x.done));render();status(done+' tâche(s) terminée(s) supprimée(s).');});
 render();
})();