// MKS Movie Producer — vue Studio (montage) d'un épisode.
// Même fichier épisode que la vue Liste : les modifications sont faites directement dans EP, puis Enregistrer.
// Champs propres au Studio (facultatifs, lus par le moteur de montage) :
//   media        : image ou vidéo choisie dans la bibliothèque ou importée (chemin relatif au projet)
//   voix_fichier : narration enregistrée ou importée, remplace la voix de synthèse (langue d'origine)
//   mus / mus_off: piste qui démarre sur ce plan et décalage (s) dans la piste
'use strict';

const ST = {ep: null, sel: 0, t: 0, cur: -1, playing: false, last: 0, raf: 0, zoom: 0, lib: null,
  onglet: 'medias', filtre: 'episode', recherche: '', voixOn: true, musOn: true, sonsOn: true,
  amb: [], sfx: [], sonUrl: {}, aAmb: new Audio(), ambCour: '', sfxJoues: new Set(),
  voixUrl: {}, voixDur: {}, segs: [], mus: [], total: 0, annuler: [], refaire: [],
  aVoix: new Audio(), aMus: new Audio(), aLib: new Audio(), libJoue: '', voixCour: '', musCour: '', vidCour: '',
  gen: false, genEtat: '', rec: null, memoChamp: null, minuteur: 0};
const MOTS_S = 2.2;                                    // débit estimé de la voix (mots/s) tant qu'elle n'est pas générée
const ICONES = {in: '⊕', out: '⊖', left: '←', right: '→', up: '↑', down: '↓', still: '■'};
const LIB_MOUV = {in: 'zoom avant', out: 'zoom arrière', left: 'panoramique gauche', right: 'panoramique droite',
  up: 'vers le haut', down: 'vers le bas', still: 'fixe'};

// ---------------------------------------------------------------- ouverture / fermeture
async function studio(ep, garder){
  studioQuitter();
  const autre = ST.ep !== ep;
  EP = garder || await api('/api/episode/' + ep); EP._ep = ep;
  await chargerProjet(); VL = ''; RETOUCHE = new Set();
  if(autre){ ST.sel = 0; ST.t = 0; ST.annuler = []; ST.refaire = []; ST.zoom = 0; }
  ST.ep = ep; ST.sel = Math.min(ST.sel, EP.shots.length - 1); ST.cur = -1;
  $('#main').classList.add('large');
  $('#main').oninput = null;
  $('#main').innerHTML = `
  <div class="studio">
    <div class="toolbar">
      ${choixVue()}
      <span class="id" style="color:var(--gold);font:600 12px var(--sans);letter-spacing:.1em">${esc(EP.id)}</span>
      <input id="titre" class="st-titre" value="${esc(EP.title)}" oninput="EP.title=this.value;stSale()" title="Titre de l'épisode">
      <div class="sp"></div>
      <span class="meta" id="stDuree"></span>
      <button class="btn small" onclick="stAnnuler()" title="Annuler (Ctrl+Z)">↶ Annuler</button>
      <button class="btn small" onclick="stRefaire()" title="Rétablir (Ctrl+Y)">↷</button>
      <button class="btn" onclick="fiche('${ep}')">Fiche Flow</button>
      <button class="btn" onclick="sauver().then(()=>exporterLots('${ep}'))" title="Un fichier de prompts par type et par personnage">Exporter les lots</button>
      <button class="btn" onclick="stRecharger()" title="Relire les médias du dossier (après avoir généré des images)">Rafraîchir</button>
      <button class="btn gold" onclick="sauver()" title="Ctrl+S">Enregistrer</button>
      <button class="btn" onclick="sauver().then(()=>action('monter',['${ep}']))">Enregistrer et monter</button>
    </div>
    <div class="st-body" id="stBody">
      <aside class="st-pane st-lib" id="stLib"></aside>
      <section class="st-pane st-mon">
        <div class="st-wrap" id="stWrap"><div class="st-stage" id="stStage">
          <img class="ly" id="stImg" alt=""><video class="ly" id="stVid" muted playsinline preload="auto"></video>
          <div class="ly st-manque" id="stManque"></div>
          <div class="ly st-card" id="stCard"><div class="c1"></div><div class="c2"></div></div>
          <div class="st-tit" id="stTit"></div>
          <div class="st-badge" id="stBadge"></div>
        </div></div>
        <div class="st-trans">
          <button class="st-rond" onclick="stAller(0)" title="Début">⏮</button>
          <button class="st-rond" onclick="stVoisin(-1)" title="Plan précédent (←)">◀</button>
          <button class="st-play" id="stPlay" onclick="stLecture()" title="Lecture / pause (Espace)">▶</button>
          <button class="st-rond" onclick="stVoisin(1)" title="Plan suivant (→)">▶</button>
          <div class="tc" id="stTc">00:00.0 <span>/ 00:00</span></div>
          <label class="st-bascule"><input type="checkbox" ${ST.voixOn?'checked':''} onchange="ST.voixOn=this.checked;stSync(true);if(this.checked)stVoixGen()"> Voix</label>
          <label class="st-bascule"><input type="checkbox" ${ST.musOn?'checked':''} onchange="ST.musOn=this.checked;stSync(true)"> Musique</label>
          <label class="st-bascule" title="Ambiances et bruitages"><input type="checkbox" ${ST.sonsOn?'checked':''} onchange="ST.sonsOn=this.checked;stSync(true)"> Sons</label>
          <div class="sp"></div><span class="st-etat" id="stEtat"></span>
        </div>
      </section>
      <aside class="st-pane st-insp" id="stInsp"></aside>
    </div>
    <div class="st-tl">
      <div class="st-tl-bar">
        <button class="btn small" onclick="stAjouter(false)" title="Nouveau plan après le plan sélectionné">＋ Plan</button>
        <button class="btn small" onclick="stAjouter(true)" title="Nouveau carton (titre sur fond noir)">＋ Carton</button>
        <button class="btn small" onclick="stDupliquer()">Dupliquer</button>
        <button class="btn small" onclick="stDeplacer(-1)" title="Avancer le plan">◀ Déplacer</button>
        <button class="btn small" onclick="stDeplacer(1)" title="Reculer le plan">Déplacer ▶</button>
        <button class="btn small" onclick="stSupprimer()" title="Supprimer le plan (Suppr)">Supprimer</button>
        <span class="meta" style="margin-left:8px">Zoom</span><input type="range" min="0" max="100" value="${ST.zoom?Math.round(Math.log(ST.zoom/2)/Math.log(100)*100):0}" oninput="stZoom(+this.value)">
        <button class="btn small" onclick="stZoom(0);this.previousElementSibling.value=0">Tout voir</button>
        <div class="st-legende">
          <span><i style="background:#6fbf8a"></i>voix de synthèse</span><span><i style="background:repeating-linear-gradient(135deg,#4c8a62 0 3px,#5a9c71 3px 6px)"></i>durée estimée</span>
          <span><i style="background:#7aa6d8"></i>voix importée</span><span><i style="background:#9d86c9"></i>musique</span><span><i style="background:#5fa8a0"></i>ambiance</span><span><i style="background:#e0915a"></i>bruitage</span></div>
      </div>
      <div class="st-zone">
        <div class="st-heads"><div style="height:25px"></div><div style="height:67px">🎞 Vidéo</div><div style="height:27px">Aa Titres</div><div style="height:35px">🎙 Voix</div><div style="height:31px">♫ Musique</div><div class="etroit" style="height:27px">≋ Ambiance</div><div class="etroit" style="height:25px">✦ Bruitage</div></div>
        <div class="st-scroll" id="stScroll"><div class="st-inner" id="stInner"></div></div>
      </div>
    </div>
  </div>`;
  const vid = $('#stVid'); vid.onloadedmetadata = () => stFrame();
  window.onresize = stTaille;
  stTaille(); stCalcul(); stTimeline(); stInsp(); stFrame();
  try { ST.lib = await api('/api/bibliotheque?ep=' + encodeURIComponent(ep)); } catch(e){ ST.lib = {medias: [], audios: [], musiques: [], dossiers: {}}; }
  stLib(); stMesurerFichiers(); stTimeline();
  if(ST.voixOn) stVoixGen();
}

function studioQuitter(){
  if(!ST.ep) return;
  stPause(); ST.aLib.pause(); ST.libJoue = '';
  if(ST.rec){ try { ST.rec.stop(); } catch(e){} ST.rec = null; }
  $('#main').classList.remove('large');
  if(window.onresize === stTaille) window.onresize = null;
}

function stTaille(){
  const studio = $('.studio'); if(!studio) return;
  const haut = Math.max(620, innerHeight - studio.getBoundingClientRect().top - 12 + scrollY);
  studio.style.height = haut + 'px';
  const w = $('#stWrap'), sg = $('#stStage'); if(!w || !sg) return;
  const W = w.clientWidth - 20, H = w.clientHeight - 20;
  let sw = W, sh = W * 9 / 16; if(sh > H){ sh = H; sw = H * 16 / 9; }
  sg.style.width = Math.max(160, sw) + 'px'; sg.style.height = Math.max(90, sh) + 'px';
  sg.style.setProperty('--sh', Math.max(90, sh) + 'px');
  if(!ST.zoom) stTimeline();
}

// ---------------------------------------------------------------- durées et sections
// voix d'un plan : celle du personnage qui parle (« qui »), sinon celle du narrateur (comme langues.voix_plan)
function voixPlan(s){
  const base = PROJET.voix || {}, p = s.qui && (PROJET.personnages || []).find(x => x.tag === s.qui);
  const code = PROJET.langue || 'fr', pv = (p && p.voix) || {}, v = pv[code] || pv[code.split('-')[0]];
  return v && v.nom ? {debit: '+0%', hauteur: '+0Hz', ...Object.fromEntries(Object.entries(v).filter(([k, x]) => x))} : base;
}
const cleVoix = s => { const v = voixPlan(s); return `${v.nom}|${v.debit}|${v.hauteur}|${(s.vo||'').trim()}`; };
function dureeVoix(s){
  if(s.voix_fichier){ const d = s._voix && ST.voixDur[s._voix]; return {d: d || 0, exact: !!d, fichier: true}; }
  const k = cleVoix(s), d = ST.voixDur[k];
  if(d) return {d, exact: true, fichier: false};
  const n = (s.vo||'').trim().split(/\s+/).filter(Boolean).length;
  return {d: n ? n / MOTS_S : 0, exact: !n, fichier: false};
}
function stCalcul(){
  let t = 0;
  ST.segs = EP.shots.map((s, i) => {
    let L, v = null;
    if(s.card) L = +(s.dur ?? 6) || 6;
    else { v = dureeVoix(s); L = Math.round(Math.max(+(s.min ?? 4) || 4, v.d + (+(s.pad ?? 1.5)))*100)/100; }
    const g = {i, t0: t, L, v}; t += L; return g;
  });
  ST.total = t;
  const sec = [];
  EP.shots.forEach((s, i) => { if(s.mus) sec.push({t0: ST.segs[i].t0, piste: s.mus, off: +(s.mus_off || 0), i}); });
  if(!sec.length) sec.push({t0: 0, piste: (ST.lib && ST.lib.musique_defaut) || PROJET.musique_defaut || '', off: 0, i: -1, defaut: true});
  sec[0].t0 = 0;
  sec.forEach((x, k) => x.t1 = k + 1 < sec.length ? sec[k + 1].t0 : t);
  ST.mus = sec;
  // ambiances (champ amb : démarre à ce plan, continue jusqu'au prochain amb ; « aucune » coupe) et bruitages (sfx, sfx_t)
  const amb = []; let cour = null;
  EP.shots.forEach((s, i) => {
    if(s.amb){ if(cour) cour.t1 = ST.segs[i].t0;
      cour = s.amb === 'aucune' ? null : {t0: ST.segs[i].t0, nom: s.amb, vol: +(s.amb_vol ?? 1), i}; if(cour) amb.push(cour); }
    else if(cour && s.amb_vol != null) cour.vol = +s.amb_vol;
  });
  if(cour) cour.t1 = t;
  ST.amb = amb;
  ST.sfx = [];
  EP.shots.forEach((s, i) => { const n = [].concat(s.sfx || []).filter(Boolean);       // plusieurs bruitages d'un plan : un repère
    if(n.length) ST.sfx.push({t: ST.segs[i].t0 + (+(s.sfx_t || 0)), noms: n, i}); });
  const d = $('#stDuree'); if(d) d.textContent = `${EP.shots.filter(s=>!s.card).length} plans · ${hms(ST.total)}${ST.segs.some(g=>g.v&&!g.v.exact)?' (estimée)':''}`;
}
const hms = (t, dix) => { t = Math.max(0, t); const m = Math.floor(t / 60), s = t - m * 60;
  return String(m).padStart(2, '0') + ':' + (dix ? s.toFixed(1).padStart(4, '0') : String(Math.floor(s)).padStart(2, '0')); };
const indexA = t => { const g = ST.segs; if(!g.length) return -1;
  for(let i = 0; i < g.length; i++) if(t < g[i].t0 + g[i].L) return i; return g.length - 1; };
const musiqueDe = nom => ((ST.lib && ST.lib.musiques) || []).find(m => m.nom === nom);

// ---------------------------------------------------------------- historique (annuler / rétablir)
function memo(){
  ST.annuler.push(JSON.stringify({title: EP.title, shots: EP.shots}));
  if(ST.annuler.length > 80) ST.annuler.shift();
  ST.refaire = [];
}
function restaurer(json){ const o = JSON.parse(json); EP.title = o.title; EP.shots = o.shots;
  ST.sel = Math.min(ST.sel, EP.shots.length - 1); $('#titre').value = EP.title; stSale(); stTout(); }
function stAnnuler(){ if(!ST.annuler.length) return toast('Rien à annuler');
  ST.refaire.push(JSON.stringify({title: EP.title, shots: EP.shots})); restaurer(ST.annuler.pop()); }
function stRefaire(){ if(!ST.refaire.length) return;
  ST.annuler.push(JSON.stringify({title: EP.title, shots: EP.shots})); restaurer(ST.refaire.pop()); }
function stSale(){ marquerSale(); }
function stTout(){ stCalcul(); stTimeline(); stInsp(); ST.cur = -1; stFrame(); if(ST.lib) stLib(); }
async function stRecharger(){ if(DIRTY){ if(!confirm('Enregistrer d\'abord les modifications ?')) return; await sauver(); } studio(EP._ep); }

// ---------------------------------------------------------------- bibliothèque
function stLib(){
  const L = ST.lib, s = EP.shots[ST.sel], n = numPlan(ST.sel), el = $('#stLib'); if(!el || !L) return;
  const r = ST.recherche.toLowerCase(), ok = x => !r || x.nom.toLowerCase().includes(r) || (x.groupe||'').toLowerCase().includes(r);
  const dEp = L.dossier_episode || '', dPe = (L.dossiers || {}).personnages || '';
  const dans = (x, d) => d && (x.groupe === d || x.groupe.startsWith(d + '/'));
  let corps = '', pied = '';
  const cible = s && !s.card ? `plan ${n}` : '';
  if(ST.onglet === 'medias'){
    const items = L.medias.filter(x => (ST.filtre === 'tout' || (ST.filtre === 'episode' ? dans(x, dEp) : dans(x, dPe))) && ok(x));
    const utilises = new Set(EP.shots.map(x => x.media || x._rel).filter(Boolean));
    corps = items.length ? `<div class="st-grille">${items.slice(0, 400).map(x => `
      <div class="st-item" draggable="true" data-lib="${esc(JSON.stringify({sorte:'media', rel:x.rel, url:x.url, type:x.type, nom:x.nom}))}"
        onclick="stAppliquer(this.dataset.lib)" title="${esc(x.rel)}">
        ${x.type === 'video' ? `<video src="${x.url}#t=0.5" muted preload="metadata"></video><span class="ty">VIDÉO</span>` : `<img loading="lazy" src="${x.url}">`}
        ${utilises.has(x.rel) ? '<span class="us">utilisé</span>' : ''}
        <div class="nm">${esc(x.nom)}</div><div class="plus">${cible ? '＋ ' + cible : 'Sélectionnez un plan'}</div></div>`).join('')}</div>`
      : `<div class="st-vide">Aucune image ni vidéo ici.${ST.filtre === 'episode' ? '<br>Essayez « Tout le projet ».' : ''}</div>`;
    pied = `<label class="btn gold">Importer des images ou vidéos…<input type="file" multiple accept="image/*,video/*" style="display:none" onchange="stImporter(this.files,'media')"></label>
      <span class="meta">Copiées dans ${esc(dEp || 'le dossier des images')} — cliquez ou glissez une vignette sur un plan.</span>`;
  } else if(ST.onglet === 'audios'){
    const items = L.audios.filter(x => (ST.filtre === 'tout' || (ST.filtre === 'episode' ? dans(x, dEp) : dans(x, dPe))) && ok(x));
    corps = items.length ? items.map(x => ligneAudio({sorte:'voix', rel:x.rel, url:x.url, nom:x.nom}, x.groupe,
        cible ? `<button class="btn small" data-app="${esc(JSON.stringify({sorte:'voix', rel:x.rel, url:x.url, nom:x.nom}))}" onclick="stAppliquer(this.dataset.app)">Voix du ${cible}</button>` : '')).join('')
      : `<div class="st-vide">Aucun fichier audio.${ST.filtre !== 'tout' ? '<br>Essayez « Tout le projet ».' : ''}</div>`;
    pied = `<label class="btn gold">Importer un enregistrement de voix…<input type="file" multiple accept="audio/*" style="display:none" onchange="stImporter(this.files,'voix')"></label>
      <span class="meta">Une voix importée remplace la voix de synthèse du plan (version d'origine).</span>`;
  } else {
    const items = L.musiques.filter(ok);
    corps = items.length ? items.map(x => ligneAudio({sorte:'musique', nom:x.nom, url:x.url}, x.absente ? 'non installée (lancer INSTALLER.bat)' : (x.projet ? 'musique du projet' : 'bibliothèque du logiciel'),
        !x.absente && EP.shots[ST.sel] ? `<button class="btn small" data-app="${esc(JSON.stringify({sorte:'musique', nom:x.nom, url:x.url}))}" onclick="stAppliquer(this.dataset.app)">Démarrer au ${cible || 'carton'}</button>` : '')).join('')
      : '<div class="st-vide">Aucune musique installée.</div>';
    pied = `<label class="btn gold">Importer une musique…<input type="file" multiple accept="audio/*" style="display:none" onchange="stImporter(this.files,'musique')"></label>
      <span class="meta">Copiée dans les musiques du projet. Pensez aux droits (crédit obligatoire pour les pistes CC BY).</span>`;
  }
  el.innerHTML = `<div class="hd">Bibliothèque</div>
    <div class="st-tabs">${[['medias','Médias'],['audios','Voix'],['musiques','Musiques']].map(([k,t]) =>
      `<button class="${ST.onglet===k?'on':''}" onclick="ST.onglet='${k}';stLib()">${t}</button>`).join('')}</div>
    <div class="st-filtres">${ST.onglet !== 'musiques' ? `<select onchange="ST.filtre=this.value;stLib()" style="width:auto">
        <option value="episode" ${ST.filtre==='episode'?'selected':''}>Cet épisode</option>
        <option value="persos" ${ST.filtre==='persos'?'selected':''}>Personnages</option>
        <option value="tout" ${ST.filtre==='tout'?'selected':''}>Tout le projet</option></select>` : ''}
      <input placeholder="Rechercher…" value="${esc(ST.recherche)}" oninput="ST.recherche=this.value;clearTimeout(ST.minR);ST.minR=setTimeout(()=>{stLib();const i=$('#stLib .st-filtres input');i.focus();i.setSelectionRange(i.value.length,i.value.length)},250)"></div>
    <div class="st-scrollv">${corps}</div><div class="st-pied">${pied}</div>`;
  el.querySelectorAll('[data-lib]').forEach(x => x.ondragstart = e => { e.dataTransfer.setData('text/x-st-lib', x.dataset.lib); e.dataTransfer.effectAllowed = 'copy'; });
}
function ligneAudio(item, sous, bouton){
  const j = JSON.stringify(item);
  return `<div class="st-ligne" draggable="${item.url ? 'true' : 'false'}" data-lib="${esc(j)}">
    <button class="st-rond ${ST.libJoue===item.url&&item.url?'on':''}" ${item.url?'':'disabled'} onclick="stEcouterLib('${esc(item.url)}')" title="Écouter">${ST.libJoue===item.url&&item.url?'❚❚':'▶'}</button>
    <div class="nm">${esc(item.nom.replace(/_/g, ' '))}<span class="gr">${esc(sous)}</span></div>${bouton}</div>`;
}
function stEcouterLib(url){
  if(!url) return;
  if(ST.libJoue === url){ ST.aLib.pause(); ST.libJoue = ''; }
  else { stPause(); ST.aLib.src = url; ST.aLib.currentTime = 0; ST.aLib.volume = 1; ST.aLib.play().catch(()=>{}); ST.libJoue = url; ST.aLib.onended = () => { ST.libJoue = ''; stLib(); stInsp(); }; }
  stLib(); stInsp();
}
const numPlan = i => EP.shots.slice(0, i + 1).filter(s => !s.card).length;

// applique un élément de la bibliothèque (média, voix, musique) au plan i (par défaut le plan sélectionné)
function stAppliquer(json, i = ST.sel){
  const x = typeof json === 'string' ? JSON.parse(json) : json, s = EP.shots[i];
  if(!s) return;
  if(s.card && x.sorte !== 'musique') return toast('Sélectionnez un plan (pas un carton)');
  memo();
  if(x.sorte === 'media'){ s.media = x.rel; s._media = x.url; s._type = x.type; s._rel = x.rel; delete s.img_url; delete s.vid_url;
    toast(`${x.type === 'video' ? 'Vidéo' : 'Image'} appliquée au plan ${numPlan(i)} — Ctrl+Z pour annuler`); }
  else if(x.sorte === 'voix'){ s.voix_fichier = x.rel; s._voix = x.url; stMesurer(x.url); toast(`Voix importée utilisée pour le plan ${numPlan(i)}`); }
  else if(x.sorte === 'musique'){ s.mus = x.nom; delete s.mus_off; toast(`« ${x.nom.replace(/_/g,' ')} » démarre au ${s.card ? 'carton' : 'plan ' + numPlan(i)}`); }
  stSale(); ST.sel = i; stTout();
}

// import depuis l'ordinateur : jamais d'écrasement (le serveur renomme si le nom existe déjà)
async function stImporter(fichiers, sorte, appliquer){
  const L = ST.lib || {}, ep = EP._ep, res = [];
  const base = sorte === 'musique' ? 'musique/' : `images/${ep}/` + (sorte === 'voix' ? 'voix/' : '');
  for(const f of fichiers){
    const nom = f.name.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^A-Za-z0-9._ -]+/g, '_').replace(/\s+/g, '_') || 'fichier';
    toast('Import de ' + f.name + '…');
    try {
      const r = await fetch('/api/fichier?unique=1&dest=' + encodeURIComponent(base + nom), {method: 'PUT', body: f});
      const j = await r.json(); if(!r.ok) throw new Error(j.erreur);
      res.push({rel: j.rel, nom: j.rel.split('/').pop(), type: (f.type || '').startsWith('video') ? 'video' : 'image'});
    } catch(e){ toast('Import impossible : ' + e.message); }
  }
  if(!res.length) return;
  try { ST.lib = await api('/api/bibliotheque?ep=' + encodeURIComponent(ep)); } catch(e){}
  if(sorte === 'musique'){ ST.onglet = 'musiques'; }
  else { ST.onglet = sorte === 'voix' ? 'audios' : 'medias'; ST.filtre = 'episode'; }
  if(appliquer){
    const r = res[0], url = '/projet/' + r.rel.split('/').map(encodeURIComponent).join('/');
    if(sorte === 'musique') stAppliquer({sorte: 'musique', nom: r.nom.replace(/\.[^.]+$/, ''), url});
    else stAppliquer({sorte: sorte === 'voix' ? 'voix' : 'media', rel: r.rel, url, type: r.type, nom: r.nom});
  } else { stLib(); toast(res.length + ' fichier(s) importé(s)'); }
  stCalcul(); stTimeline();
}

// ---------------------------------------------------------------- inspecteur
function stInsp(){
  const el = $('#stInsp'); if(!el) return;
  const i = ST.sel, s = EP.shots[i]; if(!s){ el.innerHTML = '<div class="st-vide">Aucun plan.</div>'; return; }
  const g = ST.segs[i] || {L: 0, t0: 0};
  const champ = (f, lib, type = 'text', extra = '') => `<div><label>${lib}</label><input data-st="${f}" type="${type}" value="${esc(s[f] ?? '')}" ${extra}></div>`;
  if(s.card){
    el.innerHTML = `<div class="hd">Carton <span class="meta" style="margin-left:auto;letter-spacing:0;text-transform:none">${hms(g.t0,1)} · ${g.L.toFixed(1)} s</span></div>
    <div class="st-scrollv"><div class="bloc"><h4>Texte</h4>${champ('card','Titre')}${champ('sub','Sous-titre')}${champ('dur','Durée (s)','number','step="0.5" min="1"')}</div>
    ${blocMusique(s, i)}${blocSons(s, i)}</div>`;
  } else {
    const v = dureeVoix(s), pv = voixPlan(s);
    const persos = (PROJET.personnages || []).filter(x => (s.p || '').includes('[' + x.tag + ']'));
    const origine = s.media ? `Choisi dans le Studio : <b>${esc(s.media)}</b>`
      : s._media && s._rel ? `Fichier de la clé : <b>${esc(s._rel)}</b>`
      : s.vid_url || s.img_url ? `Adresse web : <b>${esc(s.vid_url || s.img_url)}</b>`
      : `Aucun média : générez <b>${esc(s.k)}.png</b> (Fiche Flow), choisissez-en un dans la bibliothèque ou importez-le.`;
    el.innerHTML = `<div class="hd">Plan ${numPlan(i)} · ${esc(s.k || '')} <span class="meta" style="margin-left:auto;letter-spacing:0;text-transform:none">${hms(g.t0,1)} · ${g.L.toFixed(1)} s</span></div>
    <div class="st-scrollv">
      <div class="bloc"><h4>Image ou vidéo</h4>
        <div class="st-apercu">${s._media ? (s._type === 'video' ? `<video src="${s._media}" muted loop autoplay playsinline></video>` : `<img src="${s._media}">`) : 'aucun média'}</div>
        <div class="st-origine">${origine}</div>
        <div class="st-btns">
          <button class="btn small" onclick="ST.onglet='medias';stLib();toast('Cliquez une vignette de la bibliothèque')">Bibliothèque</button>
          <label class="btn small" style="margin:0;text-transform:none;letter-spacing:0">Importer…<input type="file" accept="image/*,video/*" style="display:none" onchange="stImporter(this.files,'media',true)"></label>
          <button class="btn small" onclick="stUrl()">Adresse web…</button>
          ${s.media || s.img_url || s.vid_url ? `<button class="btn small" onclick="stRetirerMedia()" title="Revenir au fichier nommé d'après la clé">Retirer le choix</button>` : ''}
        </div>
        <div><label>Mouvement de caméra (images)</label><div class="st-seg">${MOUV.map(m => `<button class="${(s.m||'in')===m?'on':''}" title="${LIB_MOUV[m]}" onclick="stChamp('m','${m}')">${ICONES[m]}</button>`).join('')}</div></div>
        <div><label>Prompt image ${persos.map(x => `<span class="pill wait">${esc(x.tag)}</span>`).join(' ')}</label><textarea data-st="p" rows="3">${esc(s.p)}</textarea></div>
        <div class="st-btns"><button class="btn small" onclick="copier(${i})">Copier le prompt</button></div>
        ${champ('vid_prompt','Prompt vidéo (si plan animé)')}
      </div>
      <div class="bloc"><h4>Texte</h4>
        <div><label>Qui parle</label><select data-st="qui">${quiOptions(s.qui)}</select></div>
        <div><label>${s.qui ? 'Réplique' : 'Narration'} · ${(s.vo||'').trim().split(/\s+/).filter(Boolean).length} mots · ${v.d.toFixed(1)} s${v.exact?'':' (estimé)'}</label><textarea data-st="vo" rows="5">${esc(s.vo)}</textarea></div>
        <div class="st-2">${champ('title','Titre à l\'écran')}${champ('min','Durée mini (s)','number','step="0.5" min="1" placeholder="4"')}</div>
      </div>
      <div class="bloc"><h4>Voix</h4>
        <div class="st-choix">
          <label class="opt ${s.voix_fichier?'':'on'}"><input type="radio" name="stv" ${s.voix_fichier?'':'checked'} onchange="stVoixSynthese()"> Synthèse <span class="det">${esc(pv.nom || '')} ${esc(pv.debit || '')} ${esc(pv.hauteur || '')}</span>
            <button class="st-rond" onclick="event.preventDefault();stEcouterPlan(${i},false)" title="Écouter">▶</button></label>
          <label class="opt ${s.voix_fichier?'on':''}"><input type="radio" name="stv" ${s.voix_fichier?'checked':''} onchange="stVoixFichier()"> Fichier audio
            <span class="det">${s.voix_fichier ? esc(s.voix_fichier.split('/').pop()) + (s._voix ? '' : ' — introuvable') : 'aucun'}</span>
            ${s.voix_fichier && s._voix ? `<button class="st-rond" onclick="event.preventDefault();stEcouterPlan(${i},true)" title="Écouter">▶</button>` : ''}</label>
        </div>
        <div class="st-btns">
          <label class="btn small" style="margin:0;text-transform:none;letter-spacing:0">Importer…<input type="file" accept="audio/*" style="display:none" onchange="stImporter(this.files,'voix',true)"></label>
          <button class="btn small ${ST.rec?'st-rec':''}" onclick="stMicro()">${ST.rec ? '■ Arrêter l\'enregistrement' : '● Enregistrer au micro'}</button>
        </div>
        <span class="meta">La voix importée sert à la version d'origine ; les versions traduites gardent la synthèse.</span>
      </div>
      ${blocMusique(s, i)}
      ${blocSons(s, i)}
    </div>`;
  }
  el.querySelectorAll('[data-st]').forEach(x => {
    x.onfocus = () => { ST.memoChamp = x.dataset.st; };
    x.oninput = () => { if(ST.memoChamp){ memo(); ST.memoChamp = null; } stChamp(x.dataset.st, x.value, true); };
  });
}
function blocMusique(s, i){
  const sec = [...ST.mus].reverse().find(x => x.t0 <= (ST.segs[i] || {t0: 0}).t0 + 0.001) || ST.mus[0];
  const libs = (ST.lib && ST.lib.musiques) || (PROJET.musiques || []).map(n => ({nom: n}));
  return `<div class="bloc"><h4>Musique</h4>
    <div class="meta">En cours sur ce plan : <b style="color:var(--text)">${esc((sec && sec.piste || 'aucune').replace(/_/g,' '))}</b></div>
    <div><label>Changer de musique à partir d'ici</label><select data-st="mus"><option value="">— la musique en cours continue</option>
      ${libs.map(m => `<option value="${esc(m.nom)}" ${m.nom === s.mus ? 'selected' : ''}>${esc(m.nom.replace(/_/g,' '))}${m.absente?' (non installée)':''}</option>`).join('')}</select></div>
    ${s.mus ? `<div class="st-2"><div><label>Début dans la piste (s)</label><input data-st="mus_off" type="number" min="0" step="1" value="${esc(s.mus_off ?? '')}" placeholder="0"></div>
      <div><label>&nbsp;</label><button class="btn small" onclick="stEcouterLib('${esc((musiqueDe(s.mus)||{}).url||'')}')">▶ Écouter la piste</button></div></div>` : ''}
    <div class="st-btns"><label class="btn small" style="margin:0;text-transform:none;letter-spacing:0">Importer une musique…<input type="file" accept="audio/*" style="display:none" onchange="stImporter(this.files,'musique',true)"></label>
      <button class="btn small" onclick="ST.onglet='musiques';stLib()">Bibliothèque</button></div>
    <span class="meta">Volume de la musique : ${PROJET.volume_musique ?? 0.47} (Projet) — elle baisse automatiquement sous la voix.</span>
  </div>`;
}
function blocSons(s, i){                          // ambiances et bruitages (sons.py) : mêmes champs que la vue Liste
  if(!SONS.sons.length && !ST.sonsDemandes){ ST.sonsDemandes = true; api('/api/sons').then(r => { SONS = r; stInsp(); stTimeline(); }).catch(()=>{}); }
  let cour = ''; EP.shots.slice(0, i).forEach(x => { if(x.amb) cour = x.amb === 'aucune' ? '' : x.amb; });
  const lib = n => ((SONS.sons.find(x => x.nom === n) || {}).libelle || n);
  return `<div class="bloc"><h4>Sons</h4>
    <div class="meta">Ambiance en cours avant ce plan : <b style="color:var(--text)">${esc(cour ? lib(cour) : 'aucune')}</b></div>
    <div><label>Ambiance à partir d'ici</label><div class="st-btns" style="flex-wrap:nowrap"><select data-st="amb">${optionsSons('ambiance', s.amb || '', cour ? '— l\'ambiance en cours continue' : '—')}</select>
      <button class="btn small" title="Écouter" onclick="ecouterSon(this.previousElementSibling.value || '${cour}')">▶</button></div></div>
    <div><label>Bruitage au début du plan</label><div class="st-btns" style="flex-wrap:nowrap"><select data-st="sfx">${optionsSons('bruitage', [].concat(s.sfx || []).join('+'), '—')}</select>
      <button class="btn small" title="Écouter" onclick="ecouterSon(this.previousElementSibling.value)">▶</button></div></div>
    <div class="st-2"><div><label>Niveau de l'ambiance</label><input data-st="amb_vol" type="number" min="0" step="0.1" placeholder="1" value="${esc(s.amb_vol ?? '')}"></div>
      ${s._type === 'video' ? `<div><label>Son de la vidéo</label><label style="margin:6px 0 0;display:flex;gap:6px;align-items:center;text-transform:none;letter-spacing:0"><input type="checkbox" style="width:auto" ${s.son_video ? 'checked' : ''} onchange="stChamp('son_video', this.checked ? true : '')"> garder</label></div>` : '<div></div>'}</div>
    <span class="meta">Volume des ambiances : ${PROJET.volume_ambiance ?? 0.8} (Projet) — fichiers ou synthèse, voir Projet › Sons et bruitages.</span>
  </div>`;
}
// modifie un champ du plan sélectionné ; texte = saisie au clavier (l'inspecteur n'est pas redessiné)
function stChamp(f, v, texte){
  const s = EP.shots[ST.sel]; if(!s) return;
  if(!texte) memo();
  if(['min', 'dur', 'mus_off', 'amb_vol'].includes(f)){ if(v === '' || v === null) delete s[f]; else s[f] = +v; }
  else if(f === 'sfx' && typeof v === 'string' && v.includes('+')) s[f] = v.split('+');
  else if(v === '' && f !== 'vo') delete s[f]; else s[f] = v;
  if(f === 'mus' && !v) delete s.mus_off;
  if(f === 'qui'){ stInsp(); if(ST.voixOn) stVoixGen(); }
  stSale(); stCalcul(); stTimeline(); ST.cur = -1; stFrame();
  if(!texte || f === 'mus') stInsp();
  if(f === 'vo'){ clearTimeout(ST.minuteur); ST.minuteur = setTimeout(() => { stInspMaj(); if(ST.voixOn) stVoixGen(); }, 1200); }
}
function stInspMaj(){ const a = document.activeElement, f = a && a.dataset && a.dataset.st, pos = f && a.selectionStart;
  stInsp(); if(f){ const x = $(`#stInsp [data-st="${f}"]`); if(x){ x.focus(); try { x.setSelectionRange(pos, pos); } catch(e){} } } }
function stVoixFichier(){ ST.onglet = 'audios'; stLib(); stInsp();
  if(!EP.shots[ST.sel].voix_fichier) toast('Choisissez un fichier dans l\'onglet Voix de la bibliothèque, importez-le ou enregistrez-le au micro'); }
function stVoixSynthese(){ const s = EP.shots[ST.sel]; if(!s.voix_fichier) return; memo(); delete s.voix_fichier; delete s._voix; stSale(); stTout(); if(ST.voixOn) stVoixGen(); }
async function stRetirerMedia(){
  const s = EP.shots[ST.sel]; memo(); delete s.media; delete s.img_url; delete s.vid_url; delete s._media; delete s._type; delete s._rel;
  try { const m = await api(`/api/media?ep=${encodeURIComponent(EP._ep)}&k=${encodeURIComponent(s.k || '')}`);
    if(m.url){ s._media = m.url; s._type = m.type; s._rel = m.rel; } } catch(e){}
  stSale(); stTout();
}
function stUrl(){
  const s = EP.shots[ST.sel], u = (prompt('Adresse web (https://…) d\'une image ou d\'une vidéo. Elle sera téléchargée au montage.', s.vid_url || s.img_url || '') || '').trim();
  if(!u) return; if(!/^https?:\/\//i.test(u)) return toast('Adresse invalide');
  memo(); delete s.media; delete s.img_url; delete s.vid_url;
  const video = /\.(mp4|mov|webm)(\?|$)/i.test(u); s[video ? 'vid_url' : 'img_url'] = u; s._media = u; s._type = video ? 'video' : 'image'; delete s._rel;
  stSale(); stTout();
}
async function stEcouterPlan(i, fichier){
  const s = EP.shots[i]; stPause();
  let url = fichier ? s._voix : ST.voixUrl[cleVoix(s)];
  if(!url && !fichier){ if(!(s.vo || '').trim()) return toast('Pas de narration sur ce plan');
    toast('Préparation de la voix…');
    try { url = await voixSynthese(s); } catch(e){ return toast(e.message); } }
  if(url){ ST.aLib.src = url; ST.aLib.currentTime = 0; ST.aLib.play().catch(()=>{}); }
}

// enregistrement au micro (navigateur) : le fichier est rangé avec les médias de l'épisode, dans voix/
async function stMicro(){
  if(ST.rec){ ST.rec.stop(); return; }
  const s = EP.shots[ST.sel]; if(!s || s.card) return;
  let flux; try { flux = await navigator.mediaDevices.getUserMedia({audio: true}); } catch(e){ return toast('Micro inaccessible : ' + e.message); }
  const morceaux = [], rec = new MediaRecorder(flux); ST.rec = rec; const i = ST.sel;
  rec.ondataavailable = e => morceaux.push(e.data);
  rec.onstop = async () => { flux.getTracks().forEach(t => t.stop()); ST.rec = null;
    const type = rec.mimeType || 'audio/webm', ext = type.includes('ogg') ? 'ogg' : type.includes('mp4') ? 'm4a' : 'webm';
    const f = new File(morceaux, `${s.k || 'plan'}_micro.${ext}`, {type}); ST.sel = i; await stImporter([f], 'voix', true); };
  rec.start(); toast('Enregistrement… cliquez « Arrêter » à la fin de la phrase'); stInsp();
}

// ---------------------------------------------------------------- voix de synthèse pour l'aperçu (mises en cache par le serveur)
async function voixSynthese(s){
  const k = cleVoix(s); if(ST.voixUrl[k]) return ST.voixUrl[k];
  const v = voixPlan(s);
  const r = await api('/api/voix/essai', {method: 'POST', body: JSON.stringify({nom: v.nom, debit: v.debit, hauteur: v.hauteur, texte: s.vo})});
  ST.voixUrl[k] = r.url; await stMesurer(r.url, k); return r.url;
}
function stMesurer(url, cle){
  return new Promise(ok => { if(!url) return ok(0); const a = new Audio(); a.preload = 'metadata';
    a.onloadedmetadata = () => { const d = isFinite(a.duration) ? a.duration : 0; if(d){ ST.voixDur[cle || url] = d; stCalcul(); stTimeline(); } ok(d); };
    a.onerror = () => ok(0); a.src = url; });
}
function stMesurerFichiers(){ EP.shots.forEach(s => { if(s._voix && !ST.voixDur[s._voix]) stMesurer(s._voix); }); }
async function stVoixGen(){
  if(ST.gen) { ST.genEncore = true; return; }
  ST.gen = true;
  do {
    ST.genEncore = false;
    const a_faire = EP.shots.filter(s => !s.card && !s.voix_fichier && (s.vo || '').trim() && !ST.voixUrl[cleVoix(s)]);
    let n = 0;
    for(const s of a_faire){
      if(!ST.ep || !$('.studio')) break;
      etat(`Voix de l'aperçu : ${++n}/${a_faire.length}…`);
      try { await voixSynthese(s); }
      catch(e){ etat('Voix de l\'aperçu indisponible (connexion internet ?) — durées estimées'); ST.gen = false; return; }
    }
  } while(ST.genEncore);
  ST.gen = false; etat(EP.shots.some(s => !s.card && (s.vo||'').trim()) ? 'Voix de l\'aperçu prêtes · durées exactes' : '');
}
const etat = t => { const e = $('#stEtat'); if(e) e.textContent = t; };

// ---------------------------------------------------------------- timeline
function pps(){ if(ST.zoom) return ST.zoom; const sc = $('#stScroll'); const w = sc ? sc.clientWidth - 30 : 1000; return Math.max(2, w / Math.max(1, ST.total)); }
function stZoom(v){ ST.zoom = v ? 2 * Math.pow(100, v / 100) : 0; stTimeline(); stSuivreTete(true); }
function stTimeline(){
  const inn = $('#stInner'); if(!inn) return;
  const p = pps(), W = Math.max(ST.total * p + 30, ($('#stScroll').clientWidth || 0));
  const pas = [1, 2, 5, 10, 15, 30, 60, 120, 300].find(x => x * p >= 64) || 600;
  let regle = ''; for(let t = 0; t <= ST.total + pas; t += pas) regle += `<i style="left:${t * p}px"></i><span style="left:${t * p}px">${hms(t)}</span>`;
  const sel = ST.sel;
  const clips = ST.segs.map(g => { const s = EP.shots[g.i], x = g.t0 * p, w = Math.max(3, g.L * p - 2);
    const fond = !s.card && s._media && s._type !== 'video' ? `;background-image:url('${s._media.replace(/'/g, "%27")}')` : '';
    const commun = `data-i="${g.i}" draggable="true" style="left:${x}px;width:${w}px${fond}"`;
    if(s.card) return `<div class="st-clip carton ${g.i===sel?'sel':''}" ${commun} title="Carton : ${esc(s.card)}"><div class="lb">◆ carton</div><div class="ct">${esc(s.card)}</div><span class="du">${g.L.toFixed(1)}s</span></div>`;
    const lb = `${numPlan(g.i)} · ${esc(s.k || '')}`;
    if(!s._media) return `<div class="st-clip manque ${g.i===sel?'sel':''}" ${commun} title="Média manquant"><div class="lb">${lb} — manquant</div><span class="du">${g.L.toFixed(1)}s</span></div>`;
    if(s._type === 'video') return `<div class="st-clip ${g.i===sel?'sel':''}" ${commun}><video src="${s._media}#t=0.5" muted preload="metadata"></video><div class="lb">🎞 ${lb}</div><span class="du">${g.L.toFixed(1)}s</span></div>`;
    return `<div class="st-clip ${g.i===sel?'sel':''}" ${commun}><div class="lb">${lb}</div><span class="du">${g.L.toFixed(1)}s</span></div>`;
  }).join('');
  const titres = ST.segs.filter(g => EP.shots[g.i].title).map(g => `<div class="st-bloc t ${g.i===sel?'sel':''}" data-i="${g.i}" style="left:${g.t0 * p}px;width:${Math.max(3, g.L * p - 2)}px" title="${esc(EP.shots[g.i].title)}">${esc(EP.shots[g.i].title)}</div>`).join('');
  const voix = ST.segs.filter(g => g.v && g.v.d).map(g => { const s = EP.shots[g.i];
    return `<div class="st-bloc a ${g.v.fichier?'fic':''} ${g.v.exact?'':'est'} ${g.i===sel?'sel':''}" data-i="${g.i}" style="left:${(g.t0 + 0.45) * p}px;width:${Math.max(3, g.v.d * p)}px" title="${esc(s.vo || '')}">${g.v.fichier ? '🎙 ' : ''}${esc((s.vo || s.voix_fichier || '').slice(0, 80))}</div>`; }).join('');
  const mus = ST.mus.map(m => { const lib = musiqueDe(m.piste); const abs = !lib || !lib.url;
    return `<div class="st-bloc m ${abs?'abs':''}" data-i="${m.i}" style="left:${m.t0 * p}px;width:${Math.max(3, (m.t1 - m.t0) * p - 2)}px" title="${esc(m.piste)}${abs?' (non installée)':''}">♫ ${esc((m.piste || 'aucune').replace(/_/g, ' '))}${m.defaut?' (par défaut)':''}${m.off?` · à ${m.off}s`:''}</div>`; }).join('');
  const libSon = n => ((SONS.sons.find(x => x.nom === n) || {}).libelle || String(n).replace(/_/g, ' '));
  const ambs = ST.amb.map(a => `<div class="st-bloc s ${a.i===sel?'sel':''}" data-i="${a.i}" style="left:${a.t0 * p}px;width:${Math.max(3, (a.t1 - a.t0) * p - 2)}px" title="Ambiance : ${esc(libSon(a.nom))} — jusqu'au prochain changement">≋ ${esc(libSon(a.nom))}${a.vol !== 1 ? ` · ${a.vol}` : ''}</div>`).join('');
  const sfx = ST.sfx.map(x => { const t = x.noms.map(libSon).join(' + ');
    return `<div class="st-sfx ${x.i===sel?'sel':''}" data-i="${x.i}" style="left:${x.t * p}px" title="Bruitage${x.noms.length > 1 ? 's' : ''} : ${esc(t)}">✦ ${esc(t)}</div>`; }).join('');
  inn.style.width = W + 'px';
  inn.innerHTML = `<div class="st-regle" id="stRegle">${regle}</div>
    <div class="st-piste v" id="stPv">${clips}</div><div class="st-piste t">${titres}</div>
    <div class="st-piste a" id="stPa">${voix}</div><div class="st-piste m" id="stPm">${mus}</div>
    <div class="st-piste s">${ambs}</div><div class="st-piste x">${sfx}</div>
    <div class="st-tete" id="stTete" style="left:${ST.t * p}px"></div>`;
  stEvenementsTimeline();
}
function stEvenementsTimeline(){
  const inn = $('#stInner'), p = pps();
  const tDe = e => (e.clientX - inn.getBoundingClientRect().left) / p;
  // clic : sélection + positionnement de la tête
  inn.querySelectorAll('[data-i]').forEach(el => el.onclick = e => { e.stopPropagation(); const i = +el.dataset.i; if(i < 0){ stAller(tDe(e)); return; }
    stChoisir(i); if(!ST.playing) stAller(el.classList.contains('st-clip') ? ST.segs[i].t0 : tDe(e)); });
  inn.onclick = e => { stAller(tDe(e)); stChoisir(indexA(ST.t)); };
  const regle = $('#stRegle');
  regle.onmousedown = e => { e.preventDefault(); e.stopPropagation(); const bouge = ev => stAller(tDe(ev)); bouge(e);
    const fin = () => { removeEventListener('mousemove', bouge); removeEventListener('mouseup', fin); if(!ST.playing) stChoisir(indexA(ST.t)); };
    addEventListener('mousemove', bouge); addEventListener('mouseup', fin); };
  // glisser-déposer : réordonner les plans, appliquer un élément de la bibliothèque
  inn.querySelectorAll('.st-clip').forEach(el => {
    el.ondragstart = e => { e.dataTransfer.setData('text/x-st-clip', el.dataset.i); e.dataTransfer.effectAllowed = 'move'; el.classList.add('drag'); };
    el.ondragend = () => el.classList.remove('drag');
    el.ondragover = e => { const t = e.dataTransfer.types; if(t.includes('text/x-st-clip') || t.includes('text/x-st-lib')){ e.preventDefault(); el.classList.add('drop'); } };
    el.ondragleave = () => el.classList.remove('drop');
    el.ondrop = e => { e.preventDefault(); e.stopPropagation(); el.classList.remove('drop'); const j = +el.dataset.i;
      const lib = e.dataTransfer.getData('text/x-st-lib');
      if(lib) return stAppliquer(lib, j);
      const i = +e.dataTransfer.getData('text/x-st-clip'); if(isNaN(i) || i === j) return;
      const r = el.getBoundingClientRect(), apres = e.clientX > r.left + r.width / 2;
      stDeplacerVers(i, apres ? j + (i < j ? 0 : 1) : j - (i < j ? 1 : 0));
    };
  });
  // piste voix / musique : déposer un fichier audio ou une musique à l'endroit voulu
  [['stPa', 'voix'], ['stPm', 'musique']].forEach(([id, sorte]) => { const pi = $('#' + id);
    pi.ondragover = e => { if(e.dataTransfer.types.includes('text/x-st-lib')){ e.preventDefault(); pi.classList.add('drop'); } };
    pi.ondragleave = () => pi.classList.remove('drop');
    pi.ondrop = e => { e.preventDefault(); pi.classList.remove('drop'); const x = JSON.parse(e.dataTransfer.getData('text/x-st-lib') || '{}');
      if(x.sorte !== sorte) return toast(sorte === 'voix' ? 'Déposez ici un fichier de l\'onglet Voix' : 'Déposez ici une musique');
      let i = indexA(tDe(e)); if(sorte === 'voix' && EP.shots[i] && EP.shots[i].card) return toast('Un carton n\'a pas de voix');
      stAppliquer(x, i); };
  });
}
function stSuivreTete(centrer){
  const sc = $('#stScroll'), x = ST.t * pps(); if(!sc) return;
  if(centrer || x < sc.scrollLeft + 20 || x > sc.scrollLeft + sc.clientWidth - 40) sc.scrollLeft = Math.max(0, x - sc.clientWidth / 3);
}

// ---------------------------------------------------------------- édition de la structure
function prochaineCle(){
  const ep = EP._ep, re = new RegExp('^' + ep.replace(/[-]/g, '\\-') + '-(\\d+)$');
  const n = Math.max(0, ...EP.shots.map(s => +((s.k || '').match(re) || [0, 0])[1]));
  return `${ep}-${String(n + 1).padStart(2, '0')}`;
}
function stAjouter(carton){
  memo(); const i = Math.min(ST.sel + 1, EP.shots.length);
  EP.shots.splice(i, 0, carton ? {card: 'TITRE', sub: '', dur: 6} : {k: prochaineCle(), vo: '', p: '', m: 'in'});
  ST.sel = i; stSale(); stTout(); stAller(ST.segs[i].t0);
  toast(carton ? 'Carton ajouté' : `Plan ${EP.shots[i].k} ajouté`);
}
function stDupliquer(){
  const s = EP.shots[ST.sel]; if(!s) return; memo();
  const c = JSON.parse(JSON.stringify(s));
  if(!c.card){ if(!c.media && c._rel) c.media = c._rel; c.k = prochaineCle(); delete c.versions; }
  EP.shots.splice(ST.sel + 1, 0, c); ST.sel++; stSale(); stTout();
}
function stDeplacer(d){ const j = ST.sel + d; if(j < 0 || j >= EP.shots.length) return; stDeplacerVers(ST.sel, j); }
function stDeplacerVers(i, j){
  j = Math.max(0, Math.min(EP.shots.length - 1, j)); if(i === j) return; memo();
  const [s] = EP.shots.splice(i, 1); EP.shots.splice(j, 0, s); ST.sel = j; stSale(); stTout(); stAller(ST.segs[j].t0);
}
function stSupprimer(){
  const s = EP.shots[ST.sel]; if(!s || EP.shots.length < 2) return;
  if(!confirm(`Supprimer ${s.card ? 'le carton « ' + s.card + ' »' : 'le plan ' + numPlan(ST.sel) + ' (' + s.k + ')'} ? Les fichiers ne sont pas effacés.`)) return;
  memo(); EP.shots.splice(ST.sel, 1); ST.sel = Math.min(ST.sel, EP.shots.length - 1); stSale(); stTout();
}
function stChoisir(i, sansInsp){
  if(i < 0 || i >= EP.shots.length) return;
  const change = ST.sel !== i; ST.sel = i;
  document.querySelectorAll('#stInner .sel').forEach(x => x.classList.remove('sel'));
  document.querySelectorAll(`#stInner [data-i="${i}"]`).forEach(x => x.classList.add('sel'));
  if(change && !sansInsp){ stInsp(); stLib(); }
}

// ---------------------------------------------------------------- aperçu : lecture
function stLecture(){ ST.playing ? stPause() : stJouer(); }
function stJouer(){
  if(!ST.segs.length) return; if(ST.t >= ST.total - 0.05) ST.t = 0;
  ST.aLib.pause(); ST.libJoue = '';
  ST.playing = true; ST.last = performance.now(); ST.voixCour = ''; ST.musCour = ''; ST.ambCour = ''; stPrechargerSons();
  ST.sfxJoues = new Set(ST.sfx.map((x, k) => x.t < ST.t - 0.05 ? k : -1));
  $('#stPlay').textContent = '❚❚'; ST.raf = requestAnimationFrame(stBoucle);
}
function stPause(){
  ST.playing = false; cancelAnimationFrame(ST.raf);
  ST.aVoix.pause(); ST.aMus.pause(); ST.aAmb.pause(); ST.ambCour = ''; const v = $('#stVid'); if(v) v.pause();
  const b = $('#stPlay'); if(b) b.textContent = '▶';
}
function stBoucle(now){
  if(!ST.playing) return;
  ST.t += (now - ST.last) / 1000; ST.last = now;
  if(ST.t >= ST.total){ ST.t = ST.total; stFrame(); stPause(); return; }
  stFrame(); stSuivreTete(); ST.raf = requestAnimationFrame(stBoucle);
}
function stAller(t){ ST.t = Math.max(0, Math.min(ST.total, t)); ST.voixCour = ''; ST.musCour = ''; ST.ambCour = '';
  ST.sfxJoues = new Set(ST.sfx.map((x, k) => x.t < ST.t - 0.05 ? k : -1)); stFrame(); }
function stVoisin(d){ const i = Math.max(0, Math.min(EP.shots.length - 1, ST.sel + d)); stChoisir(i); stAller(ST.segs[i].t0); stSuivreTete(); }
function stSync(){ ST.voixCour = ''; ST.musCour = ''; ST.ambCour = ''; if(!ST.voixOn) ST.aVoix.pause(); if(!ST.musOn) ST.aMus.pause();
  if(!ST.sonsOn) ST.aAmb.pause(); stFrame(); }

// dessine l'image à l'instant ST.t (reproduit le moteur : mouvements, titres, fondus, cartons) et cale le son
function stFrame(){
  const stage = $('#stStage'); if(!stage || !ST.segs.length) return;
  const i = indexA(ST.t), g = ST.segs[i], s = EP.shots[i], u = ST.t - g.t0, L = g.L, q = Math.min(1, Math.max(0, u / L));
  const img = $('#stImg'), vid = $('#stVid'), card = $('#stCard'), man = $('#stManque'), tit = $('#stTit');
  if(i !== ST.cur){
    ST.cur = i;
    if(ST.playing && !$('#stInsp').contains(document.activeElement)) stChoisir(i);   // la sélection suit la lecture
    $('#stBadge').textContent = s.card ? 'Carton' : `Plan ${numPlan(i)} · ${s.k || ''}`;
    card.style.display = s.card ? 'block' : 'none'; man.style.display = 'none'; img.style.display = 'none'; vid.style.display = 'none';
    if(s.card){ card.querySelector('.c1').textContent = s.card || ''; card.querySelector('.c2').textContent = s.sub || ''; }
    else if(!s._media){ man.style.display = 'flex'; man.innerHTML = `<b>${esc(s.k || '')}</b>média manquant`; }
    else if(s._type === 'video'){ vid.style.display = 'block'; if(ST.vidCour !== s._media){ ST.vidCour = s._media; vid.src = s._media; } }
    else { img.style.display = 'block'; if(img.getAttribute('src') !== s._media) img.src = s._media; }
    tit.textContent = s.card ? '' : (s.title || '');
  }
  // fondus (seulement pendant la lecture : à l'arrêt, le plan reste lisible)
  const fIn = s.card ? 0.5 : 0.35, fOut = s.card ? 0.6 : 0.35;
  const op = ST.playing ? Math.max(0, Math.min(1, u / fIn, (L - u) / fOut)) : 1;
  stage.querySelectorAll('.ly').forEach(x => x.style.opacity = op);
  // mouvement de caméra (zoompan du moteur)
  if(!s.card && s._media && s._type !== 'video'){
    const m = s.m || 'in', z = m === 'in' ? 1 + 0.12 * q : m === 'out' ? 1.12 - 0.12 * q : m === 'still' ? 1.03 : 1.12;
    const mx = (1 - 1 / z) / 2 * 100; let tx = 0, ty = 0;
    if(m === 'left') tx = -mx + 2 * mx * q; if(m === 'right') tx = mx - 2 * mx * q;
    if(m === 'up') ty = -mx + 2 * mx * q; if(m === 'down') ty = mx - 2 * mx * q;
    img.style.transform = `scale(${z}) translate(${tx}%, ${ty}%)`;
  }
  if(!s.card && s._type === 'video' && vid.readyState >= 1){
    const r = vid.duration && vid.duration < L ? vid.duration / L : 1, cible = Math.min(u * r, (vid.duration || 1e9) - 0.05);
    if(ST.playing){ vid.playbackRate = Math.max(0.25, r); if(vid.paused) vid.play().catch(()=>{}); if(Math.abs(vid.currentTime - cible) > 0.35) vid.currentTime = cible; }
    else { vid.pause(); if(Math.abs(vid.currentTime - cible) > 0.04) vid.currentTime = cible; }
  }
  // titre à l'écran : apparition 0,6–1,2 s, disparition dans les 0,8 dernières secondes
  const a = u < 0.6 ? 0 : u < 1.2 ? (u - 0.6) / 0.6 : u < L - 0.8 ? 1 : Math.max(0, (L - u - 0.2) / 0.6);
  tit.style.opacity = ST.playing ? a : 1;
  // temps
  $('#stTc').innerHTML = `${hms(ST.t, 1)} <span>/ ${hms(ST.total)}</span>`;
  const tete = $('#stTete'); if(tete) tete.style.left = ST.t * pps() + 'px';
  if(ST.playing) stSon(i, s, g, u);
}
function stSon(i, s, g, u){
  // voix
  const url = !s.card && ST.voixOn ? (s.voix_fichier ? s._voix : ST.voixUrl[cleVoix(s)]) : '';
  const cle = i + '|' + url;
  if(url && u >= 0.45){
    if(ST.voixCour !== cle){ ST.voixCour = cle; if(ST.aVoix.getAttribute('src') !== url) ST.aVoix.src = url;
      try { ST.aVoix.currentTime = Math.max(0, u - 0.45); } catch(e){} ST.aVoix.play().catch(()=>{}); }
  } else if(ST.voixCour && ST.voixCour !== cle){ ST.aVoix.pause(); ST.voixCour = ''; }
  const parle = !!url && ST.voixCour === cle && !ST.aVoix.paused;
  // musique (baisse sous la voix, comme au montage)
  const sec = ST.mus.find(m => ST.t >= m.t0 && ST.t < m.t1) || ST.mus[ST.mus.length - 1];
  const lib = sec && musiqueDe(sec.piste);
  if(ST.musOn && lib && lib.url){
    const cm = sec.i + '|' + lib.url;
    if(ST.musCour !== cm){ ST.musCour = cm; if(ST.aMus.getAttribute('src') !== lib.url) ST.aMus.src = lib.url; ST.aMus.loop = true;
      const pos = ST.t - sec.t0 + (sec.off || 0), dur = ST.aMus.duration;
      try { ST.aMus.currentTime = dur && isFinite(dur) ? pos % dur : pos; } catch(e){}
      ST.aMus.play().catch(()=>{}); }
    const vol = Math.min(1, +(PROJET.volume_musique ?? 0.47)), fin = Math.min(1, (ST.total - ST.t) / 5);
    ST.aMus.volume = Math.max(0, Math.min(1, vol * (parle ? 0.45 : 1) * fin));
  } else if(!ST.aMus.paused){ ST.aMus.pause(); ST.musCour = ''; }
  // ambiance (extrait en boucle) et bruitages, baissés sous la voix comme la musique
  const amb = ST.sonsOn && ST.amb.find(a => ST.t >= a.t0 && ST.t < a.t1), ua = amb && stUrlSon(amb.nom);
  if(ua){
    if(ST.ambCour !== ua){ ST.ambCour = ua; ST.aAmb.src = ua; ST.aAmb.loop = true; ST.aAmb.play().catch(()=>{}); }
    const fin = Math.min(1, (amb.t1 - ST.t) / 1.5, (ST.t - amb.t0) / 1.5 + 0.2);
    ST.aAmb.volume = Math.max(0, Math.min(1, +(PROJET.volume_ambiance ?? 0.8) * amb.vol * 0.6 * (parle ? 0.5 : 1) * fin));
  } else if(ST.ambCour){ ST.aAmb.pause(); ST.ambCour = ''; }
  if(ST.sonsOn) ST.sfx.forEach((x, k) => {
    if(ST.t >= x.t && ST.t < x.t + 0.4 && !ST.sfxJoues.has(k)){ ST.sfxJoues.add(k);
      x.noms.forEach(n => { const u2 = stUrlSon(n);
        if(u2){ const a = new Audio(u2); a.volume = Math.min(1, +(PROJET.volume_ambiance ?? 0.8)); a.play().catch(()=>{}); } }); }
  });
}
// extrait d'écoute d'un son (fichier du projet ou synthèse), demandé une fois au serveur puis gardé
function stUrlSon(nom){
  if(ST.sonUrl[nom] !== undefined) return ST.sonUrl[nom];
  ST.sonUrl[nom] = '';
  api('/api/sons/essai', {method: 'POST', body: JSON.stringify({nom})}).then(r => { ST.sonUrl[nom] = r.url; }).catch(() => {});
  return '';
}
function stPrechargerSons(){ ST.amb.forEach(a => stUrlSon(a.nom)); ST.sfx.forEach(x => x.noms.forEach(stUrlSon)); }

// ---------------------------------------------------------------- clavier
addEventListener('keydown', e => {
  if(!$('.studio') || !ST.ep) return;
  const champ = /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName);
  const ctrl = e.ctrlKey || e.metaKey, k = e.key.toLowerCase();
  if(ctrl && k === 's'){ e.preventDefault(); sauver(); return; }
  if(champ) return;
  if(ctrl && k === 'z'){ e.preventDefault(); e.shiftKey ? stRefaire() : stAnnuler(); return; }
  if(ctrl && k === 'y'){ e.preventDefault(); stRefaire(); return; }
  if(e.key === ' '){ e.preventDefault(); stLecture(); }
  else if(e.key === 'ArrowLeft'){ e.preventDefault(); stVoisin(-1); }
  else if(e.key === 'ArrowRight'){ e.preventDefault(); stVoisin(1); }
  else if(e.key === 'Home'){ e.preventDefault(); stAller(0); stSuivreTete(true); }
  else if(e.key === 'Delete'){ e.preventDefault(); stSupprimer(); }
});
