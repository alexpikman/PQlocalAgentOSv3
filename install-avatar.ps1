# ─────────────────────────────────────────────────────────────
# PQ Avatar Installer — one-click
# ─────────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"
$root = "C:\PROJECT\PQlocalAgentOSv3"
$js   = Join-Path $root "frontend\app.js"
$css  = Join-Path $root "frontend\styles\06-patterns.css"

Write-Host "`n=== PQ Avatar Installer ===`n" -ForegroundColor Cyan

# ── 0. Проверка путей ──
if (-not (Test-Path $js))  { Write-Host "Не найден: $js" -ForegroundColor Red; exit 1 }
if (-not (Test-Path $css)) { Write-Host "Не найден: $css" -ForegroundColor Red; exit 1 }

# ── 1. Бэкап ──
$ts = Get-Date -Format "yyyyMMdd-HHmmss"
Copy-Item $js  "$js.bak-$ts"  -Force
Copy-Item $css "$css.bak-$ts" -Force
Write-Host "[1/8] Бэкап: app.js.bak-$ts, 06-patterns.css.bak-$ts" -ForegroundColor Green

# ── 2. CSS: аватар + модалка + фиксы ──
$cssBlock = @'

/* ═══ AVATAR (installed) ═══ */
.av{position:relative;overflow:hidden;display:grid;place-items:center;flex-shrink:0;transition:transform .3s cubic-bezier(.34,1.56,.64,1),box-shadow .3s;box-shadow:0 4px 14px #17243715,inset 0 1px 0 #fff5;user-select:none}
.av:hover{transform:translateY(-2px) scale(1.02)}
.av-bg{position:absolute;inset:0;z-index:0}
.av-bg.grad{background:linear-gradient(135deg,var(--av-bg),var(--av-bg2))}
.av-bg.radial{background:radial-gradient(circle at 35% 25%,var(--av-bg2),var(--av-bg) 75%)}
.av-bg.mesh{background:radial-gradient(circle at 20% 20%,var(--av-bg2),transparent 45%),radial-gradient(circle at 80% 80%,var(--av-bg3),transparent 50%),var(--av-bg)}
.av-bg.solid{background:var(--av-bg)}
.av-pattern{position:absolute;inset:0;z-index:1;opacity:.3;pointer-events:none}
.av-pattern.dots{background-image:radial-gradient(#fff8 1.2px,transparent 1.2px);background-size:8px 8px}
.av-pattern.grid{background-image:linear-gradient(#fff4 1px,transparent 1px),linear-gradient(90deg,#fff4 1px,transparent 1px);background-size:10px 10px}
.av-pattern.diag{background:repeating-linear-gradient(45deg,#fff3 0 1px,transparent 1px 7px)}
.av-person-wrap{position:relative;z-index:2;width:100%;height:100%;display:block;transform-origin:center 70%}
.av-person{position:relative;z-index:2;width:100%;height:100%;display:block}
.av-pulse::before{content:"";position:absolute;inset:-6px;z-index:0;border:2px solid var(--av-bg);border-radius:inherit;opacity:0;animation:avPulse 2.2s ease-out infinite}
@keyframes avPulse{0%{opacity:.8;transform:scale(.98)}100%{opacity:0;transform:scale(1.18)}}
.av-eye{transform-origin:center;transform-box:fill-box;animation:avBlink 4.2s infinite}
@keyframes avBlink{0%,90%,100%{transform:scaleY(1)}94%{transform:scaleY(.08)}}
@keyframes avSwaySoft{0%,100%{transform:translateY(0) translateX(0)}25%{transform:translateY(-1.5px) translateX(-1px)}50%{transform:translateY(0) translateX(0)}75%{transform:translateY(1.5px) translateX(1px)}}
@keyframes avBreathe{0%,100%{transform:scale(1)}50%{transform:scale(1.012)}}
.av-live .av-person-wrap{animation:avSwaySoft 5s ease-in-out infinite,avBreathe 4s ease-in-out infinite alternate}
.av-talking .av-mouth{animation:avTalk .22s ease-in-out infinite alternate;transform-origin:32px 41px}
@keyframes avTalk{0%{transform:scaleY(.4) scaleX(.9)}100%{transform:scaleY(1.4) scaleX(1.1)}}
.av-sound{position:absolute;inset:0;z-index:3;pointer-events:none;opacity:0;transition:opacity .3s;display:grid;place-items:center}
.av-talking .av-sound{opacity:1}
.av-sound span{position:absolute;top:50%;left:50%;width:28%;height:22%;border-radius:50%;border:2px solid var(--av-bg);transform:translate(-50%,-50%) rotate(0deg);animation:avWave 1.6s ease-out infinite;box-sizing:border-box}
.av-sound span:nth-child(2){animation-delay:.53s;animation-duration:1.8s}
.av-sound span:nth-child(3){animation-delay:1.06s;animation-duration:2s}
@keyframes avWave{0%{opacity:.9;width:28%;height:22%;transform:translate(-50%,-50%) rotate(0deg) scale(1)}33%{width:55%;height:48%;transform:translate(-50%,-50%) rotate(6deg) scale(1.02)}66%{width:80%;height:76%;transform:translate(-50%,-50%) rotate(-4deg) scale(1.03)}100%{opacity:0;width:110%;height:108%;transform:translate(-50%,-50%) rotate(2deg) scale(1.04)}}

/* Avatar Studio (в модалке) */
.avatar-studio{display:grid;grid-template-columns:170px minmax(0,1fr);gap:14px;align-items:start}
@media(max-width:560px){.avatar-studio{grid-template-columns:1fr;justify-items:center}}
.avatar-preview-wrap{display:grid;gap:6px;justify-items:center;text-align:center}
.avatar-preview-box{padding:14px;background:var(--panel2);border:1px solid var(--line);border-radius:14px;display:grid;place-items:center;position:relative;overflow:hidden;width:100%}
.avatar-preview-name{font-size:12px;font-weight:600}
.avatar-preview-meta{font-size:10px;color:var(--muted)}
.avatar-tabs{display:flex;gap:4px;background:var(--panel2);padding:4px;border-radius:10px;border:1px solid var(--line);margin-bottom:6px}
.avatar-tab-btn{flex:1;padding:6px 8px;border:0;background:transparent;color:var(--muted);font-size:11px;font-weight:600;border-radius:7px;transition:.15s;cursor:pointer}
.avatar-tab-btn:hover{color:var(--text)}
.avatar-tab-btn.active{background:var(--panel);color:var(--text);box-shadow:0 1px 3px #17243710}
.avatar-tab-pane{display:none}
.avatar-tab-pane.active{display:grid;gap:8px}
.avatar-field-row{display:grid;grid-template-columns:100px minmax(0,1fr);gap:8px;align-items:center}
.avatar-field-row label{font-size:11px;color:var(--muted);font-weight:600}
.avatar-field-row select{width:100%;min-width:0;background:var(--bg);border:1px solid var(--line);border-radius:7px;padding:6px 9px;color:var(--text);font-size:11px;outline:none;cursor:pointer;transition:border-color .15s;font-family:inherit}
.avatar-field-row select:focus{border-color:var(--accent);box-shadow:0 0 0 3px #2785e820}
.avatar-color-group{display:grid;gap:4px}
.avatar-color-group>label{font-size:11px;color:var(--muted);font-weight:600}
.avatar-color-picker{display:flex;align-items:center;gap:4px;flex-wrap:wrap}
.avatar-swatch{width:18px;height:18px;border-radius:5px;border:2px solid transparent;cursor:pointer;transition:transform .15s,border-color .15s;padding:0;box-shadow:inset 0 1px 0 #fff5,0 1px 3px #17243715}
.avatar-swatch:hover{transform:scale(1.12)}
.avatar-swatch.active{border-color:var(--text);transform:scale(1.12)}
.avatar-custom-color{position:relative;width:18px;height:18px;border-radius:5px;border:1px dashed var(--muted);background:transparent;display:flex;align-items:center;justify-content:center;overflow:hidden}
.avatar-custom-color input[type=color]{position:absolute;opacity:0;inset:-10px;cursor:pointer;width:40px;height:40px}
.avatar-custom-color::after{content:"+";font-size:10px;color:var(--muted);font-weight:700}
.avatar-actions{display:flex;gap:6px;flex-wrap:wrap;margin-top:4px}

/* Модалка не прыгает */
.domain-modal .modal-card{min-height:520px;max-height:calc(100vh - 40px)}
#domain-modal-form,#domain-modal-avatar{min-height:400px}

/* Аватар в списке агентов */
.entity-row[data-search-row="agents"]{grid-template-columns:32px minmax(0,1fr) auto}
.entity-row[data-search-row="agents"] > .av{width:28px;height:28px;flex:0 0 28px}
'@
Add-Content -Path $css -Value $cssBlock -Encoding UTF8
Write-Host "[2/8] CSS: аватар + модалка + фикс списка" -ForegroundColor Green

# ── 3. JS: блок 1 — PALETTES, avatarState, функции ──
$jsBlock1 = @'

/* ═══ AVATAR (installed) ═══ */
const PALETTES={skin:["#f0c7a6","#d9a17c","#c9a27c","#b97956","#70452f","#e6b8bd","#ffd7c2"],hairColor:["#1e1e24","#4a3728","#8d5b32","#d69f3d","#e05638","#9b7bff","#3b9dff","#6ce0a8"],clothesColor:["#258bf5","#3d2a5c","#1f4a3a","#5c2a40","#3a3d52","#f3f4f8","#ff5f56"],eyesColor:["#0e1a24","#3b9dff","#6ce0a8","#ff6b9d","#ffb84a","#9b7bff"],mouthColor:["#5a2e1a","#803434","#a0544f","#2b150c","#c94f7c"],accessoryColor:["#e6c07a","#3b9dff","#9b7bff","#6ce0a8","#ff5f56","#ffffff"],accent:["#3b9dff","#9b7bff","#6ce0a8","#ffb84a","#ff6b9d","#e6c07a","#ff5f56","#5eead4"]};
let avatarState={role:"MANAGER",head:"round",skin:"#d9a17c",eyes:"dots",eyesColor:"#0e1a24",mouth:"smile",mouthColor:"#5a2e1a",hair:"punk",hairColor:"#9b7bff",clothes:"hoodie",clothesColor:"#258bf5",accessory:"crown",accessoryColor:"#e6c07a",bg:"grad",pattern:"none",accent:"#3b9dff",talking:false};
function adjustAvColor(c,a){let n=parseInt(c.replace("#",""),16);if(isNaN(n))return "#142b3d";let r=(n>>16)+a,b=((n>>8)&255)+a,g=(n&255)+a;return "#"+(0x1000000+(r<255?r<0?0:r:255)*0x10000+(b<255?b<0?0:b:255)*0x100+(g<255?g<0?0:g:255)).toString(16).slice(1)}
function renderAvatar(s,o){o=o||{};var size=o.size||64,pulse=!!o.pulse,blink=o.blink!==false,talking=!!o.talking,live=o.live!==false;
var accent=s.accent||"#3b9dff",bg2=adjustAvColor(accent,-40),bg3=adjustAvColor(accent,-60),radius=size>=100?"32px":size>=40?"11px":"8px";
var headShapes={round:'<circle cx="32" cy="32" r="17"/>',square:'<rect x="15" y="15" width="34" height="34" rx="9"/>',hex:'<path d="M32 14 L48 23 L48 41 L32 50 L16 41 L16 23 Z"/>',squircle:'<rect x="15" y="15" width="34" height="34" rx="14"/>',drop:'<path d="M32 13 Q47 13 47 28 Q47 43 32 50 Q17 43 17 28 Q17 13 32 13 Z"/>'};
var eyes={dots:'<circle cx="25" cy="30" r="2.2" fill="'+s.eyesColor+'"/><circle cx="39" cy="30" r="2.2" fill="'+s.eyesColor+'"/>',wide:'<ellipse cx="25" cy="30" rx="3.5" ry="4" fill="#fff"/><ellipse cx="39" cy="30" rx="3.5" ry="4" fill="#fff"/><circle cx="25" cy="30.5" r="1.8" fill="'+s.eyesColor+'"/><circle cx="39" cy="30.5" r="1.8" fill="'+s.eyesColor+'"/>',line:'<path d="M22 30h6M36 30h6" stroke="'+s.eyesColor+'" stroke-width="2.2" stroke-linecap="round" fill="none"/>',anime:'<ellipse cx="25" cy="30" rx="3.5" ry="4.5" fill="#fff"/><ellipse cx="39" cy="30" rx="3.5" ry="4.5" fill="#fff"/><circle cx="25.5" cy="31" r="2.2" fill="'+s.eyesColor+'"/><circle cx="39.5" cy="31" r="2.2" fill="'+s.eyesColor+'"/><circle cx="26.2" cy="29.8" r=".9" fill="#fff"/><circle cx="40.2" cy="29.8" r=".9" fill="#fff"/>',visor:'<rect x="17" y="26" width="30" height="8" rx="4" fill="#111" opacity=".9"/><path d="M19 30h26" stroke="'+s.eyesColor+'" stroke-width="2" stroke-linecap="round" stroke-dasharray="3 2"/>'};
var mouths={smile:'<path d="M26 39q6 5 12 0" stroke="'+s.mouthColor+'" stroke-width="2" stroke-linecap="round" fill="none"/>',line:'<path d="M27 40h10" stroke="'+s.mouthColor+'" stroke-width="2" stroke-linecap="round"/>',open:'<ellipse cx="32" cy="40" rx="3.5" ry="2.5" fill="'+s.mouthColor+'"/><ellipse cx="32" cy="41" rx="2" ry="1.2" fill="#e06b6b"/>',smirk:'<path d="M26 40q6 2 12 -2" stroke="'+s.mouthColor+'" stroke-width="2" stroke-linecap="round" fill="none"/>',grin:'<path d="M25 38 q7 6 14 0" fill="none" stroke="'+s.mouthColor+'" stroke-width="2" stroke-linecap="round"/><path d="M27 39 h10" stroke="#fff" stroke-width="1.5"/>'};
var hairShapes={none:"",punk:'<path d="M14 21 L20 8 L24 18 L28 6 L32 16 L36 6 L40 18 L44 8 L50 21 Q44 16 32 16 Q20 16 14 21Z" fill="'+s.hairColor+'"/>',short:'<path d="M15 22 Q16 11 32 11 Q48 11 49 22 Q44 16 32 16 Q20 16 15 22Z" fill="'+s.hairColor+'"/>',long:'<path d="M14 22 Q14 9 32 9 Q50 9 50 22 L50 44 Q46 42 45 34 L45 22 Q43 16 32 16 Q21 16 19 22 L19 34 Q18 42 14 44Z" fill="'+s.hairColor+'"/>',mohawk:'<path d="M28 8 L32 2 L36 8 L38 5 L38 18 L26 18 L26 5 Z" fill="'+s.hairColor+'"/>',bun:'<circle cx="32" cy="8" r="6" fill="'+s.hairColor+'"/><path d="M15 22 Q16 12 32 12 Q48 12 49 22 Q44 16 32 16 Q20 16 15 22Z" fill="'+s.hairColor+'"/>',afro:'<circle cx="32" cy="18" r="15" fill="'+s.hairColor+'"/><circle cx="18" cy="22" r="9" fill="'+s.hairColor+'"/><circle cx="46" cy="22" r="9" fill="'+s.hairColor+'"/>'};
var clothesShapes={hoodie:'<path d="M14 64 C14 47 18 45 32 45 C46 45 50 47 50 64 Z" fill="'+s.clothesColor+'"/><path d="M24 45 Q32 53 40 45" fill="none" stroke="#10131d" stroke-width="1.5"/>',jacket:'<path d="M14 64 C14 47 18 45 32 45 C46 45 50 47 50 64 Z" fill="'+s.clothesColor+'"/><path d="M32 45 L32 64" stroke="#10131d" stroke-width="2"/><path d="M21 47 L29 54 M43 47 L35 54" stroke="#10131d" stroke-width="1.5"/>',uniform:'<path d="M14 64 C14 47 18 45 32 45 C46 45 50 47 50 64 Z" fill="'+s.clothesColor+'"/><rect x="23" y="48" width="18" height="4" rx="1" fill="#fff" opacity=".5"/>',tshirt:'<path d="M14 64 C14 47 18 45 32 45 C46 45 50 47 50 64 Z" fill="'+s.clothesColor+'"/>'};
var accessories={none:"",glasses:'<g fill="none" stroke="'+s.accessoryColor+'" stroke-width="2"><rect x="18" y="26" width="11" height="8" rx="2.5"/><rect x="35" y="26" width="11" height="8" rx="2.5"/><path d="M29 29h6"/></g>',headphones:'<g fill="'+s.accessoryColor+'"><rect x="10" y="24" width="5" height="14" rx="2.5"/><rect x="49" y="24" width="5" height="14" rx="2.5"/><path d="M12 26 Q12 10 32 10 Q52 10 52 26" fill="none" stroke="'+s.accessoryColor+'" stroke-width="3.5" stroke-linecap="round"/></g>',crown:'<path d="M19 16 L23 6 L28 14 L32 4 L36 14 L41 6 L45 16 Z" fill="'+s.accessoryColor+'" stroke="#a88024" stroke-width="1"/><circle cx="23" cy="14" r="1" fill="#ff5f56"/><circle cx="32" cy="12" r="1" fill="#5eead4"/><circle cx="41" cy="14" r="1" fill="#ff5f56"/>',halo:'<ellipse cx="32" cy="8" rx="14" ry="3.5" fill="none" stroke="'+s.accessoryColor+'" stroke-width="2.5"/>',mask:'<path d="M20 32 Q32 28 44 32 L44 41 Q32 47 20 41 Z" fill="#151722" opacity=".95"/><path d="M24 36h16" stroke="'+s.accessoryColor+'" stroke-width="1.5" stroke-dasharray="2 2"/>',antenna:'<line x1="32" y1="14" x2="32" y2="3" stroke="'+s.accessoryColor+'" stroke-width="2"/><circle cx="32" cy="3" r="3" fill="'+s.accessoryColor+'"/>'};
var pc=pulse?" av-pulse":"",tc=talking?" av-talking":"",lc=live?" av-live":"",ba=blink?"":' style="animation:none"';
return '<div class="av'+pc+tc+lc+'" style="--av-bg:'+accent+';--av-bg2:'+bg2+';--av-bg3:'+bg3+';width:'+size+'px;height:'+size+'px;border-radius:'+radius+'"><div class="av-bg '+s.bg+'"></div>'+(s.pattern!=="none"?'<div class="av-pattern '+s.pattern+'"></div>':"")+'<div class="av-person-wrap"><svg class="av-person" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg"><g class="av-body">'+(clothesShapes[s.clothes]||clothesShapes.hoodie)+'</g><rect x="28" y="40" width="8" height="6" fill="'+s.skin+'" opacity=".85"/><g class="av-head" fill="'+s.skin+'">'+(headShapes[s.head]||headShapes.round)+'</g><g class="av-hair">'+(hairShapes[s.hair]||"")+'</g><g class="av-eye"'+ba+'>'+(eyes[s.eyes]||eyes.dots)+'</g><g class="av-mouth">'+(mouths[s.mouth]||mouths.smile)+'</g><g class="av-acc">'+(accessories[s.accessory]||"")+'</g><ellipse cx="23" cy="21" rx="4" ry="2.5" fill="#fff" opacity=".15"/></svg></div>'+(talking?'<div class="av-sound"><span></span><span></span><span></span></div>':"")+'</div>'}
function rgbToHex(r){if(!r||r.indexOf("rgb")!==0)return r;var n=r.match(/\d+/g);if(!n)return r;return "#"+((1<<24)+(+n[0]<<16)+(+n[1]<<8)+ +n[2]).toString(16).slice(1)}
function initAvatarPickers(){document.querySelectorAll(".avatar-color-picker[data-av-key]").forEach(function(c){var key=c.dataset.avKey,p=PALETTES[key]||[];c.innerHTML="";p.forEach(function(col){var b=document.createElement("button");b.type="button";b.className="avatar-swatch"+(avatarState[key]===col?" active":"");b.style.background=col;b.onclick=function(){avatarState[key]=col;c.querySelectorAll(".avatar-swatch").forEach(function(x){x.classList.remove("active")});b.classList.add("active");updateAvatarPreview()};c.appendChild(b)});var cu=document.createElement("div");cu.className="avatar-custom-color";var inp=document.createElement("input");inp.type="color";inp.value=avatarState[key]||"#3b9dff";inp.oninput=function(e){avatarState[key]=e.target.value;c.querySelectorAll(".avatar-swatch").forEach(function(x){x.classList.remove("active")});updateAvatarPreview()};cu.appendChild(inp);c.appendChild(cu)})}
function syncAvatarState(){document.querySelectorAll("[data-av-field]").forEach(function(s){if(avatarState[s.dataset.avField]!==undefined)s.value=avatarState[s.dataset.avField]});document.querySelectorAll(".avatar-color-picker[data-av-key]").forEach(function(c){var key=c.dataset.avKey;c.querySelectorAll(".avatar-swatch").forEach(function(b){b.classList.toggle("active",b.style.backgroundColor&&rgbToHex(b.style.backgroundColor).toLowerCase()===String(avatarState[key]).toLowerCase())});var ci=c.querySelector("input[type=color]");if(ci)ci.value=avatarState[key]})}
function updateAvatarPreview(){var p=document.getElementById("avatar-preview-big");if(p)p.innerHTML=renderAvatar(avatarState,{size:140,pulse:true,talking:avatarState.talking,live:true});var n=document.getElementById("avatar-preview-name"),ni=document.getElementById("domain-name");if(n)n.textContent=(ni&&ni.value)||"Агент"}
function bindAvatarControls(){document.querySelectorAll("[data-av-field]").forEach(function(s){s.onchange=function(){avatarState[s.dataset.avField]=s.value;updateAvatarPreview()}});document.querySelectorAll(".avatar-tab-btn").forEach(function(b){b.onclick=function(){document.querySelectorAll(".avatar-tab-btn").forEach(function(x){x.classList.remove("active")});document.querySelectorAll(".avatar-tab-pane").forEach(function(x){x.classList.remove("active")});b.classList.add("active");var pane=document.querySelector('.avatar-tab-pane[data-av-tab="'+b.dataset.avTab+'"]');if(pane)pane.classList.add("active")}});var ni=document.getElementById("domain-name");if(ni)ni.addEventListener("input",updateAvatarPreview);var r=document.getElementById("avatar-random");if(r)r.onclick=function(){var pick=function(a){return a[Math.floor(Math.random()*a.length)]};avatarState.head=pick(["round","square","hex","squircle","drop"]);avatarState.eyes=pick(["dots","wide","line","anime","visor"]);avatarState.mouth=pick(["smile","line","open","smirk","grin"]);avatarState.hair=pick(["none","punk","short","long","mohawk","bun","afro"]);avatarState.clothes=pick(["hoodie","jacket","uniform","tshirt"]);avatarState.accessory=pick(["none","glasses","headphones","crown","halo","mask","antenna"]);avatarState.bg=pick(["grad","radial","mesh","solid"]);avatarState.pattern=pick(["none","dots","grid","diag"]);avatarState.skin=pick(PALETTES.skin);avatarState.hairColor=pick(PALETTES.hairColor);avatarState.clothesColor=pick(PALETTES.clothesColor);avatarState.eyesColor=pick(PALETTES.eyesColor);avatarState.mouthColor=pick(PALETTES.mouthColor);avatarState.accessoryColor=pick(PALETTES.accessoryColor);avatarState.accent=pick(PALETTES.accent);syncAvatarState();initAvatarPickers();updateAvatarPreview()};var t=document.getElementById("avatar-toggle-talk");if(t)t.onclick=function(){avatarState.talking=!avatarState.talking;t.textContent=avatarState.talking?"⏸ Остановить":"🗣 Разговор";updateAvatarPreview()}}
function avatarStudioMarkup(){return '<div class="avatar-studio"><div class="avatar-preview-wrap"><div class="avatar-preview-box"><div id="avatar-preview-big"></div></div><div class="avatar-preview-name" id="avatar-preview-name">Агент</div><div class="avatar-preview-meta">Живой предпросмотр</div></div><div class="avatar-controls"><div class="avatar-tabs"><button type="button" class="avatar-tab-btn active" data-av-tab="face">Голова</button><button type="button" class="avatar-tab-btn" data-av-tab="hair">Причёска</button><button type="button" class="avatar-tab-btn" data-av-tab="body">Одежда</button><button type="button" class="avatar-tab-btn" data-av-tab="style">Стиль</button></div><div class="avatar-tab-pane active" data-av-tab="face"><div class="avatar-field-row"><label>Форма</label><select data-av-field="head"><option value="round">Круглая</option><option value="square">Квадратная</option><option value="hex">Шестиугольник</option><option value="squircle">Скруглённая</option><option value="drop">Капля</option></select></div><div class="avatar-color-group"><label>Цвет кожи</label><div class="avatar-color-picker" data-av-key="skin"></div></div><div class="avatar-field-row"><label>Глаза</label><select data-av-field="eyes"><option value="dots">Точки</option><option value="wide">Большие</option><option value="line">Полоски</option><option value="anime">Аниме</option><option value="visor">Кибер-визор</option></select></div><div class="avatar-color-group"><label>Цвет глаз</label><div class="avatar-color-picker" data-av-key="eyesColor"></div></div><div class="avatar-field-row"><label>Рот</label><select data-av-field="mouth"><option value="smile">Улыбка</option><option value="line">Линия</option><option value="open">Открытый</option><option value="smirk">Ухмылка</option><option value="grin">Зубы</option></select></div><div class="avatar-color-group"><label>Цвет рта</label><div class="avatar-color-picker" data-av-key="mouthColor"></div></div></div><div class="avatar-tab-pane" data-av-tab="hair"><div class="avatar-field-row"><label>Причёска</label><select data-av-field="hair"><option value="none">Лысый</option><option value="short">Короткие</option><option value="punk">Панк</option><option value="mohawk">Ирокез</option><option value="long">Длинные</option><option value="bun">Пучок</option><option value="afro">Афро</option></select></div><div class="avatar-color-group"><label>Цвет волос</label><div class="avatar-color-picker" data-av-key="hairColor"></div></div><div class="avatar-field-row"><label>Аксессуар</label><select data-av-field="accessory"><option value="none">Нет</option><option value="glasses">Очки</option><option value="headphones">Наушники</option><option value="crown">Корона</option><option value="halo">Нимб</option><option value="mask">Маска</option><option value="antenna">Антенна</option></select></div><div class="avatar-color-group"><label>Цвет аксессуара</label><div class="avatar-color-picker" data-av-key="accessoryColor"></div></div></div><div class="avatar-tab-pane" data-av-tab="body"><div class="avatar-field-row"><label>Одежда</label><select data-av-field="clothes"><option value="hoodie">Худи</option><option value="jacket">Пиджак</option><option value="uniform">Форма</option><option value="tshirt">Футболка</option></select></div><div class="avatar-color-group"><label>Цвет одежды</label><div class="avatar-color-picker" data-av-key="clothesColor"></div></div></div><div class="avatar-tab-pane" data-av-tab="style"><div class="avatar-field-row"><label>Фон</label><select data-av-field="bg"><option value="grad">Градиент</option><option value="radial">Радиальный</option><option value="mesh">Меш</option><option value="solid">Плоский</option></select></div><div class="avatar-field-row"><label>Узор</label><select data-av-field="pattern"><option value="none">Нет</option><option value="dots">Точки</option><option value="grid">Сетка</option><option value="diag">Диагональ</option></select></div><div class="avatar-color-group"><label>Основной цвет</label><div class="avatar-color-picker" data-av-key="accent"></div></div></div><div class="avatar-actions"><button type="button" class="btn soft-secondary" id="avatar-random">🎲 Случайный</button><button type="button" class="btn soft-secondary" id="avatar-toggle-talk">🗣 Разговор</button></div></div></div>'}
'@
Add-Content -Path $js -Value $jsBlock1 -Encoding UTF8
Write-Host "[3/8] JS: функции аватара добавлены в конец app.js" -ForegroundColor Green

# ── 4. JS: заменить domainModalMarkup ──
$c = Get-Content $js -Raw -Encoding UTF8
$newDM = 'function domainModalMarkup(){return ''<div class="modal-overlay domain-modal model-assign-modal" id="domain-modal" hidden><div class="modal-backdrop" data-domain-modal-close></div><section class="modal-card" role="dialog" aria-modal="true"><div class="section-title modal-card-head"><div><h2 id="domain-modal-title">Создать элемент</h2><p>Создание и редактирование в одном окне.</p></div><button type="button" class="btn secondary" data-domain-modal-close>Закрыть</button></div><div class="model-tabs" id="domain-modal-tabs" style="display:none;margin-bottom:12px"><button type="button" class="btn primary" data-domain-tab="profile">Профиль</button><button type="button" class="btn secondary" data-domain-tab="avatar">Аватар</button></div><form id="domain-modal-form" class="field-grid modal-card-body"></form><div id="domain-modal-avatar" style="display:none"></div><div class="modal-card-actions" id="domain-modal-footer" style="display:none;margin-top:12px;padding-top:12px;border-top:1px solid var(--line)"><button type="button" class="btn primary" id="domain-modal-save-btn">Сохранить</button></div><div id="domain-modal-status"></div></section></div>''}'
$sDM = $c.IndexOf("function domainModalMarkup(")
$sODM = $c.IndexOf("function openDomainModal(")
if ($sDM -lt 0 -or $sODM -lt 0) { Write-Host "[4/8] Якорь domainModalMarkup не найден" -ForegroundColor Red }
else {
  $c = $c.Substring(0,$sDM) + $newDM + "`n" + $c.Substring($sODM)
  Set-Content -Path $js -Value $c -Encoding UTF8 -NoNewline
  Write-Host "[4/8] domainModalMarkup заменён (вкладки + футер)" -ForegroundColor Green
}

# ── 5. JS: заменить openDomainModal ──
$c = Get-Content $js -Raw -Encoding UTF8
$newODM = @'
function openDomainModal(kind,id){const lists={agents:state.agents||[],projects:state.projects||[],tasks:state.tasks||[]},item=id?lists[kind].find(x=>x.id===id):null;if(id&&!item)return;state.domainEditor={kind:kind,id:id||null};const form=document.getElementById("domain-modal-form");document.getElementById("domain-modal-title").textContent=(item?"Изменить: ":"Создать: ")+({agents:"агента",projects:"проект",tasks:"задачу"}[kind]);document.getElementById("domain-modal-status").innerHTML="";const tabsEl=document.getElementById("domain-modal-tabs"),avatarEl=document.getElementById("domain-modal-avatar"),footer=document.getElementById("domain-modal-footer");if(kind==="agents"){tabsEl.style.display="flex";avatarEl.style.display="none";form.style.display="grid";if(item&&item.avatar){try{avatarState=Object.assign({},avatarState,typeof item.avatar==="string"?JSON.parse(item.avatar):item.avatar)}catch(e){}}document.querySelectorAll("[data-domain-tab]").forEach(b=>{b.onclick=()=>{document.querySelectorAll("[data-domain-tab]").forEach(x=>{x.classList.remove("primary");x.classList.add("secondary")});b.classList.remove("secondary");b.classList.add("primary");const isAvatar=b.dataset.domainTab==="avatar";form.style.display=isAvatar?"none":"grid";avatarEl.style.display=isAvatar?"block":"none";if(isAvatar){avatarEl.innerHTML=avatarStudioMarkup();initAvatarPickers();syncAvatarState();bindAvatarControls();updateAvatarPreview()}}})}else{tabsEl.style.display="none";avatarEl.style.display="none";form.style.display="grid"}const field=(label,key,value,type,attrs)=>'<div class="field" style="grid-column:1/-1"><label for="domain-'+key+'">'+label+'</label>'+(type==="textarea"?'<textarea id="domain-'+key+'" name="'+key+'" '+(attrs||"")+'>'+esc(value)+'</textarea>':'<input id="domain-'+key+'" name="'+key+'" type="text" value="'+esc(value)+'" '+(attrs||"")+'>')+'</div>';let html="";if(kind==="agents"){html=field("Название","name",item?.name||"","text",'required maxlength="80"')+'<div class="field"><label for="domain-role">Роль</label><select id="domain-role" name="role">'+["MANAGER","ARCHITECT","ANALYST","DESIGNER","COPYWRITER","CODER","TESTER","DEVOPS"].map(x=>'<option '+(x===(item?.role||"ANALYST")?"selected":"")+'>'+x+'</option>').join("")+'</select></div><div class="field"><label for="domain-model">Модель</label><select id="domain-model" name="model"><option value="">Не назначена</option>'+(state.models.models||[]).map(x=>'<option value="'+esc(x.name)+'" '+(x.name===(item?.model||"")?"selected":"")+'>'+esc(x.name)+'</option>').join("")+'</select></div>'+field("Краткое описание","description",item?.description||"","textarea",'rows="2" maxlength="1000"')+field("Системная инструкция","system_prompt",item?.system_prompt||"","textarea",'rows="4" maxlength="4000"')+field("Долговременная память","memory",item?.memory||"","textarea",'rows="3" maxlength="8000"')+'<div class="field" style="grid-column:1/-1"><b>Разрешения агента</b><div class="agent-permission-list">'+[["file_loading","Чтение и поиск файлов"],["file_saving","Создание и изменение файлов"],["file_moving","Перемещение файлов"],["directory_moving","Перемещение папок"],["file_deletion","Удаление файлов"],["directory_creation","Создание папок"],["directory_deletion","Удаление пустых папок"],["github_access","Доступ к GitHub"]].map(([key,label])=>'<label><input type="checkbox" name="perm_'+key+'" '+(item?.permissions?.[key]?"checked":"")+'> '+label+'</label>').join("")+'</div></div>'}else if(kind==="projects"){html=field("Название","name",item?.name||"","text",'required maxlength="120"')+field("Путь к рабочей папке","path",item?.path||"","text",'maxlength="1000"')+field("Краткое описание","description",item?.description||"","textarea",'rows="3" maxlength="1000"')}else{html=field("Название задачи","title",item?.title||"","text",'required maxlength="160"')+field("Краткое описание / инструкции","description",item?.description||"","textarea",'required rows="4" maxlength="5000"')+'<div class="field"><label for="domain-project_id">Проект <span class="required-mark">*</span></label><select id="domain-project_id" name="project_id" required><option value="">Выберите проект</option>'+(state.projects||[]).map(x=>'<option value="'+esc(x.id)+'" '+(x.id===(item?.project_id||"")?"selected":"")+'>'+esc(x.name)+'</option>').join("")+'</select></div><div class="field"><label for="domain-agent_id">Агент <span class="required-mark">*</span></label><select id="domain-agent_id" name="agent_id" required><option value="">Выберите агента</option>'+(state.agents||[]).map(x=>'<option value="'+esc(x.id)+'" '+(x.id===(item?.agent_id||"")?"selected":"")+'>'+esc(x.name)+'</option>').join("")+'</select></div><div class="field"><label><input type="checkbox" name="team_mode" '+(item?.team_mode?"checked":"")+'> Командный режим</label></div>'}const createdRaw=item&&(item.created_at||item.created||item.added_at);const createdMarkup=createdRaw?'<div class="domain-created-at">Создано · '+esc(new Date(createdRaw).toLocaleString("ru-RU",{day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit"}))+'</div>':"";form.innerHTML=createdMarkup+html;footer.style.display=(kind==="agents")?"flex":"none";const saveBtn=document.getElementById("domain-modal-save-btn");if(saveBtn){saveBtn.textContent=(item?"Сохранить изменения":"Создать");saveBtn.onclick=()=>{form.requestSubmit()}}document.getElementById("domain-modal").hidden=false}
'@
$sODM = $c.IndexOf("function openDomainModal(")
$sER  = $c.IndexOf("function entityRow(")
if ($sODM -lt 0 -or $sER -lt 0) { Write-Host "[5/8] Якорь openDomainModal не найден" -ForegroundColor Red }
else {
  $c = $c.Substring(0,$sODM) + $newODM + "`n" + $c.Substring($sER)
  Set-Content -Path $js -Value $c -Encoding UTF8 -NoNewline
  Write-Host "[5/8] openDomainModal заменён (вкладки + футер + безопасный парсер)" -ForegroundColor Green
}

# ── 6. JS: payload.avatar + fix class в new-task ──
$c = Get-Content $js -Raw -Encoding UTF8
$o1 = "if(cfg.kind==='agents'){payload.permissions={};"
$n1 = "if(cfg.kind==='agents'){payload.avatar=JSON.stringify(avatarState);payload.permissions={};"
if ($c.Contains($o1)) { $c = $c.Replace($o1,$n1); Write-Host "[6/8] payload.avatar добавлен" -ForegroundColor Green }
else { Write-Host "[6/8] Якорь payload.avatar не найден" -ForegroundColor Yellow }

# fix двойной class= в new-task
$o2 = '<button class="btn primary" id="new-task" class="entity-create-button">'
$n2 = '<button class="btn primary entity-create-button" id="new-task">'
if ($c.Contains($o2)) { $c = $c.Replace($o2,$n2); Write-Host "[6b/8] Фикс двойного class= в new-task" -ForegroundColor Green }

Set-Content -Path $js -Value $c -Encoding UTF8 -NoNewline

# ── 7. JS: мини-аватар в agentsView ──
$c = Get-Content $js -Raw -Encoding UTF8
$o3 = "entityRow(x,{kind:'agents',title:x.name,description:x.description,extra:"
$n3 = "entityRow(x,{kind:'agents',title:x.name,description:x.description,marker:(x.avatar?(function(){try{var a=typeof x.avatar==='string'?JSON.parse(x.avatar):x.avatar;return renderAvatar(a,{size:28,live:false})}catch(e){return domainInfo(x,x.description).replace('domain-info','entity-row-info domain-info')}})():(domainInfo(x,x.description).replace('domain-info','entity-row-info domain-info'))),extra:"
if ($c.Contains($o3)) { $c = $c.Replace($o3,$n3); Write-Host "[7/8] Мини-аватар в списке агентов" -ForegroundColor Green }
else { Write-Host "[7/8] Якорь agentsView не найден" -ForegroundColor Yellow }
Set-Content -Path $js -Value $c -Encoding UTF8 -NoNewline

# ── 8. Проверка ──
Write-Host "[8/8] Проверка синтаксиса app.js..." -ForegroundColor Cyan
try {
  $node = Get-Command node -ErrorAction SilentlyContinue
  if ($node) {
    node -c $js 2>&1 | Out-String | Write-Host
    if ($LASTEXITCODE -eq 0) { Write-Host "Синтаксис OK" -ForegroundColor Green }
    else { Write-Host "ОШИБКА синтаксиса — откатываю бэкап" -ForegroundColor Red; Copy-Item "$js.bak-$ts" $js -Force; exit 1 }
  } else {
    Write-Host "node не установлен — пропускаю. Откройте сайт, F12 → Console." -ForegroundColor Yellow
  }
} catch { Write-Host "Проверка не удалась: $_" -ForegroundColor Yellow }

Write-Host "`n=== ГОТОВО ===" -ForegroundColor Cyan
Write-Host "Бэкап: app.js.bak-$ts, 06-patterns.css.bak-$ts" -ForegroundColor Gray
Write-Host "`nЧто проверить:" -ForegroundColor White
Write-Host "  1. F5 в браузере (жёсткая перезагрузка: Ctrl+Shift+R)"
Write-Host "  2. AI-агенты → Создать агента → вкладка 'Аватар'"
Write-Host "  3. Модалка не должна прыгать между вкладками"
Write-Host "  4. Кнопка 'Сохранить' внизу — всегда видна"
Write-Host "  5. После сохранения — в списке слева должен быть аватар 28×28"
Write-Host "`nЕсли что-то сломалось — откат:" -ForegroundColor Yellow
Write-Host "  Copy-Item `"$js.bak-$ts`" `"$js`" -Force" -ForegroundColor Gray
Write-Host "  Copy-Item `"$css.bak-$ts`" `"$css`" -Force" -ForegroundColor Gray