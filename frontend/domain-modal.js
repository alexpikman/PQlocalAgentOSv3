(function () {
'use strict';

let context = {
  getState: () => ({}),
  api: async (path, options = {}) => {
    const response = await fetch('/api' + path, { ...options, headers: { 'Content-Type': 'application/json', ...(options.headers || {}) } });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || data.message || 'Ошибка запроса');
    return data;
  },
  esc: value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char])),
  toast: message => console.info(message),
  refresh: () => window.PQRefresh?.()
};
let editor = null;
let domainModalBound = false;
const $ = selector => document.querySelector(selector);
const esc = value => context.esc(value);
const api = (path, options) => context.api(path, options);
const refresh = async () => {
  if (typeof context.refresh === 'function') return await context.refresh();
  if (typeof window.PQRefresh === 'function') return await window.PQRefresh();
};
function domainModalMarkup(){return '<div class="modal-overlay domain-modal model-assign-modal" id="domain-modal" hidden><div class="modal-backdrop" data-domain-modal-close></div><section class="modal-card" role="dialog" aria-modal="true"><div class="section-title modal-card-head"><div><h2 id="domain-modal-title">Создать элемент</h2><p>Создание и редактирование в одном окне.</p></div><button type="button" class="btn secondary" data-domain-modal-close>Закрыть</button></div><div class="model-tabs" id="domain-modal-tabs" style="display:none;margin-bottom:12px"><button type="button" class="btn primary" data-domain-tab="profile">Профиль</button><button type="button" class="btn secondary" data-domain-tab="avatar">Аватар</button></div><div class="domain-modal-content"><form id="domain-modal-form" class="field-grid modal-card-body"></form><div id="domain-modal-avatar" style="display:none"></div></div><div id="domain-modal-status"></div><div class="modal-card-actions domain-modal-actions"><button type="submit" form="domain-modal-form" class="btn primary" id="domain-modal-save">Сохранить</button></div></section></div>'}
function ensureDomainModal(){let modal=$('#domain-modal');if(!modal){document.body.insertAdjacentHTML('beforeend',domainModalMarkup());modal=$('#domain-modal')}bindDomainModal();return modal}
function interactionPlanMarkup(rows){
  const roles=['MANAGER','ARCHITECT','ANALYST','DESIGNER','COPYWRITER','CODER','TESTER','DEVOPS'];
  const fromOptions=(value)=>['USER','ANY',...roles].map(role=>'<option value="'+role+'" '+(role===(value||'USER')?'selected':'')+'>'+role+'</option>').join('');
  const toOptions=(value)=>['USER',...roles].map(role=>'<option value="'+role+'" '+(role===(value||'USER')?'selected':'')+'>'+role+'</option>').join('');
  const fallbackOptions=(value)=>['',...roles].map(role=>'<option value="'+role+'" '+(role===(value||'')?'selected':'')+'>'+(role||'Не передавать')+'</option>').join('');
  const rowMarkup=(row={})=>'<tr data-rule-row><td><select data-rule="from" aria-label="От кого">'+fromOptions(row.from)+'</select></td><td><input data-rule="trigger" maxlength="120" value="'+esc(row.trigger||'')+'" aria-label="Тип задачи или триггер"></td><td><input data-rule="condition" maxlength="240" value="'+esc(row.condition||'')+'" aria-label="Условие или статус"></td><td><textarea data-rule="action" maxlength="1000" rows="2" aria-label="Моё действие">'+esc(row.action||'')+'</textarea></td><td><select data-rule="to" aria-label="Кому передать">'+toOptions(row.to)+'</select></td><td><select data-rule="fallback" aria-label="Fallback">'+fallbackOptions(row.fallback)+'</select></td><td><button type="button" class="rule-remove" data-rule-remove aria-label="Удалить правило" title="Удалить правило">×</button></td></tr>';
  return '<div class="system-instruction-plan"><div class="system-instruction-plan-scroll"><table><thead><tr><th>От кого</th><th>Тип задачи / триггер</th><th>Условие / статус</th><th>Моё действие</th><th>Кому передать</th><th>Fallback</th><th></th></tr></thead><tbody id="domain-interaction-plan-rows">'+(rows||[]).map(rowMarkup).join('')+'</tbody></table></div><div class="small muted" id="domain-interaction-plan-empty" '+((rows||[]).length?'hidden':'')+'>Правил пока нет.</div></div>';
}
function openDomainModal(kind,id){
  const state=context.getState?context.getState():{};
  const lists={agents:state.agents||[],projects:state.projects||[],tasks:state.tasks||[],'system-instructions':state.systemInstructions||[]};
  const item=id?lists[kind]?.find(x=>x.id===id):null;
  if(id&&!item)return;
  if(!['agents','projects','tasks','system-instructions'].includes(kind))return;
  editor={kind,id:id||null};
  const modal=ensureDomainModal(),form=$('#domain-modal-form');
  // Submit handling is explicit so hidden required profile fields can be reported on either tab.
  form.noValidate=true;
  $('#domain-modal-title').textContent=(item?'Изменить: ':'Создать: ')+({agents:'агента',projects:'проект',tasks:'задачу','system-instructions':'системную инструкцию'}[kind]);
  $('#domain-modal-save').textContent=kind==='agents'?'Сохранить':(item?'Сохранить изменения':'Создать');
  $('#domain-modal-status').innerHTML='';
  const tabsEl=$('#domain-modal-tabs'),avatarEl=$('#domain-modal-avatar');
  if(kind==='agents'){
    tabsEl.style.display='flex';avatarEl.style.display='none';form.style.display='grid';
    document.querySelectorAll('[data-domain-tab]').forEach(button=>{button.classList.toggle('primary',button.dataset.domainTab==='profile');button.classList.toggle('secondary',button.dataset.domainTab!=='profile')});
    if(item&&item.avatar){try{avatarState=Object.assign({},avatarState,JSON.parse(item.avatar))}catch(_){}}
  }else{tabsEl.style.display='none';avatarEl.style.display='none';form.style.display='grid'}
  const field=(label,key,value,type,attrs)=>'<div class="field" style="grid-column:1/-1"><label for="domain-'+key+'">'+label+'</label>'+(type==='textarea'?'<textarea id="domain-'+key+'" name="'+key+'" '+(attrs||'')+'>'+esc(value)+'</textarea>':'<input id="domain-'+key+'" name="'+key+'" type="text" value="'+esc(value)+'" '+(attrs||'')+'></div>');
  let html='';
  if(kind==='agents'){
    html=field('Название','name',item?.name||'','text','required maxlength="80"')+'<div class="field"><label for="domain-role">Роль</label><select id="domain-role" name="role">'+['MANAGER','ARCHITECT','ANALYST','DESIGNER','COPYWRITER','CODER','TESTER','DEVOPS'].map(x=>'<option '+(x===(item?.role||'ANALYST')?'selected':'')+'>'+x+'</option>').join('')+'</select></div>'+((state.models?.models||[]).length?'<div class="field"><label for="domain-model">Модель</label><select id="domain-model" name="model"><option value="">Не назначена</option>'+state.models.models.map(x=>'<option value="'+esc(x.name)+'" '+(x.name===(item?.model||'')?'selected':'')+'>'+esc(x.name)+'</option>').join('')+'</select></div>':field('Модель','model',item?.model||'','text','maxlength="160"'))+field('Краткое описание','description',item?.description||'','textarea','rows="2" maxlength="1000"')+field('Системная инструкция','system_prompt',item?.system_prompt||'','textarea','rows="4" maxlength="4000"')+field('Долговременная память','memory',item?.memory||'','textarea','rows="3" maxlength="8000"')+'<div class="field" style="grid-column:1/-1"><b>Разрешения агента</b><div class="agent-permission-list">'+[['file_loading','Чтение и поиск файлов'],['file_saving','Создание и изменение файлов'],['file_moving','Перемещение файлов'],['directory_moving','Перемещение папок'],['file_deletion','Удаление файлов'],['directory_creation','Создание папок'],['directory_deletion','Удаление пустых папок'],['github_access','Доступ к GitHub']].map(([key,label])=>'<label><input type="checkbox" name="perm_'+key+'" '+(item?.permissions?.[key]?'checked':'')+'> '+label+'</label>').join('')+'</div></div>';
  }else if(kind==='system-instructions'){
    html=field('Название инструкции','name',item?.name||'','text','required maxlength="120"')
      +'<div class="field"><label for="domain-role">Роль агента</label><select id="domain-role" name="role" required>'+['MANAGER','ARCHITECT','ANALYST','DESIGNER','COPYWRITER','CODER','TESTER','DEVOPS'].map(role=>'<option value="'+role+'" '+(role===(item?.role||'ANALYST')?'selected':'')+'>'+role+'</option>').join('')+'</select></div>'
      +field('Системная инструкция','system_prompt',item?.system_prompt||'','textarea','rows="5" maxlength="8000"')
      +'<div class="field system-instruction-reset-wrap" style="grid-column:1/-1"><button type="button" class="btn secondary" id="domain-reset-default">По умолчанию</button></div>'
      +field('Основная деятельность','activity',item?.activity||'','textarea','rows="3" maxlength="2000"')
      +'<div class="field system-instruction-plan-field" style="grid-column:1/-1"><b>План взаимодействия</b>'+interactionPlanMarkup(item?.interaction_plan||[])+'<button type="button" class="btn secondary" id="domain-add-rule" style="margin-top:8px">＋ Добавить правило</button></div>';
  }else if(kind==='projects'){
    html=field('Название','name',item?.name||'','text','required maxlength="120"')+field('Путь к рабочей папке','path',item?.path||'','text','maxlength="1000"')+field('Краткое описание','description',item?.description||'','textarea','rows="3" maxlength="1000"');
  }else{
    html=field('Название задачи','title',item?.title||'','text','required maxlength="160"')+field('Краткое описание / инструкции','description',item?.description||'','textarea','required rows="4" maxlength="5000"')+'<div class="field"><label for="domain-project_id">Проект <span class="required-mark">*</span></label><select id="domain-project_id" name="project_id" required><option value="">Выберите проект</option>'+(state.projects||[]).map(x=>'<option value="'+esc(x.id)+'" '+(x.id===(item?.project_id||'')?'selected':'')+'>'+esc(x.name)+'</option>').join('')+'</select></div><div class="field"><label for="domain-agent_id">Агент <span class="required-mark">*</span></label><select id="domain-agent_id" name="agent_id" required><option value="">Выберите агента</option>'+(state.agents||[]).map(x=>'<option value="'+esc(x.id)+'" '+(x.id===(item?.agent_id||'')?'selected':'')+'>'+esc(x.name)+'</option>').join('')+'</select></div><div class="field"><label><input type="checkbox" name="team_mode" '+(item?.team_mode?'checked':'')+'> Командный режим</label></div>';
  }
  const createdRaw=item&&(item.created_at||item.created||item.added_at);
  const createdMarkup=createdRaw?'<div class="domain-created-at">Создано · '+esc(new Date(createdRaw).toLocaleString('ru-RU',{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit'}))+'</div>':'';
  form.innerHTML=createdMarkup+html;
  modal.hidden=false;
}
async function saveDomainItem(event){
  event.preventDefault();if(!editor)return;
  const state=context.getState?context.getState():{},form=$('#domain-modal-form'),fd=new FormData(form),payload={};
  // Native constraint validation cannot focus required fields while the profile tab is hidden.
  // Disable automatic submit blocking and validate explicitly so avatar-tab saves can guide the user.
  const requiredFields=form.querySelectorAll('[required]');
  for(const field of requiredFields){
    if(!String(field.value||'').trim()){
      const profileTab=document.querySelector('[data-domain-tab="profile"]');
      if(profileTab)profileTab.click();
      field.focus();
      field.scrollIntoView({block:'center',behavior:'smooth'});
      if(typeof field.reportValidity==='function')field.reportValidity();
      return;
    }
  }
  for(const [key,value] of fd.entries())if(!key.startsWith('perm_'))payload[key]=value;
  if(editor.kind==='agents'){
    payload.avatar=JSON.stringify(avatarState);payload.permissions={};
    ['file_loading','file_saving','file_moving','directory_moving','file_deletion','directory_creation','directory_deletion','github_access'].forEach(key=>payload.permissions[key]=fd.get('perm_'+key)==='on');
  }
  if(editor.kind==='tasks')payload.team_mode=fd.get('team_mode')==='on';
  if(editor.kind==='system-instructions'){
    payload.interaction_plan=[];
    document.querySelectorAll('#domain-interaction-plan-rows tr[data-rule-row]').forEach(tr=>{
      payload.interaction_plan.push({
        from:tr.querySelector('[data-rule="from"]').value,
        trigger:tr.querySelector('[data-rule="trigger"]').value.trim(),
        condition:tr.querySelector('[data-rule="condition"]').value.trim(),
        action:tr.querySelector('[data-rule="action"]').value.trim(),
        to:tr.querySelector('[data-rule="to"]').value,
        fallback:tr.querySelector('[data-rule="fallback"]').value
      });
    });
  }
  const submit=$('#domain-modal-save');if(submit)submit.disabled=true;
  const savedKind=editor.kind,savedId=editor.id;
  try{
    const savedItem=await api('/'+savedKind+(savedId?'/'+encodeURIComponent(savedId):''),{method:'POST',body:JSON.stringify(payload)});
    $('#domain-modal').hidden=true;
    await refresh();
    if(savedKind==='system-instructions'){
      const validation=await api('/system-instructions/validate');
      const warnings=validation.warnings||[];
      if(warnings.length){
        openDomainModal('system-instructions',savedItem.id||savedId);
        const status=$('#domain-modal-status');
        if(status)status.innerHTML='<div class="system-instruction-warning"><b>План взаимодействия требует внимания</b><ul>'+warnings.map(w=>'<li>'+esc(w.from)+' → '+esc(w.to)+': '+esc(w.message)+'</li>').join('')+'</ul></div>';
      }else{
        if(typeof context.toast==='function')context.toast(savedId?'Изменения сохранены':'Инструкция создана');
        editor=null;
      }
    }else{
      if(savedKind==='agents'&&typeof window.PQOnAgentSaved==='function')await window.PQOnAgentSaved();
      if(typeof context.toast==='function')context.toast(savedId?'Изменения сохранены':'Элемент создан');editor=null;
    }
  }catch(error){$('#domain-modal-status').innerHTML='<div class="notice warning">'+esc(error.message||'Не удалось сохранить')+'</div>'}
  finally{if(submit)submit.disabled=false}
}
async function deleteDomainItem(kind,id){
  if(!kind||!id||!confirm('Удалить запись?'))return;
  try{await api('/'+kind+'/'+encodeURIComponent(id),{method:'DELETE'});await refresh();if(typeof context.toast==='function')context.toast('Запись удалена')}
  catch(error){if(typeof context.toast==='function')context.toast(error.message||'Не удалось удалить запись')}
}
function bindDomainModal(){
  if(domainModalBound)return;domainModalBound=true;
  document.addEventListener('submit',event=>{if(event.target?.matches('#domain-modal-form'))void saveDomainItem(event)});
  document.addEventListener('input',event=>{
    const field=event.target;
    if(field instanceof Element&&field.matches('#domain-modal-form [required]'))field.setCustomValidity?.('');
  });
  document.addEventListener('click',async event=>{
    const target=event.target instanceof Element?event.target:null;if(!target)return;
    const close=target.closest('[data-domain-modal-close]');if(close){const modal=$('#domain-modal');if(modal)modal.hidden=true;return}
    const tab=target.closest('[data-domain-tab]');if(tab){
      const form=$('#domain-modal-form'),avatarEl=$('#domain-modal-avatar'),isAvatar=tab.dataset.domainTab==='avatar';
      document.querySelectorAll('[data-domain-tab]').forEach(button=>{button.classList.toggle('primary',button===tab);button.classList.toggle('secondary',button!==tab)});
      if(form)form.style.display=isAvatar?'none':'grid';if(avatarEl)avatarEl.style.display=isAvatar?'block':'none';
      if(!isAvatar&&form)form.querySelectorAll('[required]').forEach(field=>field.setCustomValidity?.(''));
      if(isAvatar&&avatarEl){avatarEl.innerHTML=avatarStudioMarkup();initAvatarPickers();syncAvatarState();bindAvatarControls();updateAvatarPreview()}
      return;
    }
    const reset=target.closest('#domain-reset-default');if(reset){
      const role=$('#domain-role')?.value;
      if(!role){if(typeof context.toast==='function')context.toast('Сначала выберите роль');return}
      reset.disabled=true;
      try{const result=await api('/system-instructions/defaults');const value=result.defaults?.[role];if(!value)throw new Error('Встроенная инструкция для роли не найдена');const prompt=$('#domain-system_prompt'),activity=$('#domain-activity');if(prompt)prompt.value=value.system_prompt||'';if(activity)activity.value=value.activity||'';if(typeof context.toast==='function')context.toast('Встроенная инструкция загружена')}
      catch(error){const status=$('#domain-modal-status');if(status)status.innerHTML='<div class="notice warning">'+esc(error.message)+'</div>'}
      finally{reset.disabled=false}
      return;
    }
    const addRule=target.closest('#domain-add-rule');if(addRule){
      const rows=$('#domain-interaction-plan-rows'),empty=$('#domain-interaction-plan-empty');
      if(rows){rows.insertAdjacentHTML('beforeend',interactionPlanMarkup([{}]).replace(/^.*<tbody[^>]*>|<\/tbody>.*$/gs,''));}
      if(empty)empty.hidden=true;
      return;
    }
    const removeRule=target.closest('[data-rule-remove]');if(removeRule){
      removeRule.closest('tr[data-rule-row]')?.remove();
      const rows=$('#domain-interaction-plan-rows'),empty=$('#domain-interaction-plan-empty');
      if(empty)empty.hidden=!!rows?.querySelector('tr[data-rule-row]');
      return;
    }
    const del=target.closest('[data-domain-delete]');if(del)void deleteDomainItem(del.dataset.domainDelete,del.dataset.id);
  });
}
const PALETTES={skin:["#f0c7a6","#d9a17c","#c9a27c","#b97956","#70452f","#e6b8bd","#ffd7c2"],hairColor:["#1e1e24","#4a3728","#8d5b32","#d69f3d","#e05638","#9b7bff","#3b9dff","#6ce0a8"],clothesColor:["#258bf5","#3d2a5c","#1f4a3a","#5c2a40","#3a3d52","#f3f4f8","#ff5f56"],eyesColor:["#0e1a24","#3b9dff","#6ce0a8","#ff6b9d","#ffb84a","#9b7bff"],mouthColor:["#5a2e1a","#803434","#a0544f","#2b150c","#c94f7c"],accessoryColor:["#e6c07a","#3b9dff","#9b7bff","#6ce0a8","#ff5f56","#ffffff"],accent:["#3b9dff","#9b7bff","#6ce0a8","#ffb84a","#ff6b9d","#e6c07a","#ff5f56","#5eead4"]};
let avatarState={role:"MANAGER",head:"round",skin:"#d9a17c",eyes:"dots",eyesColor:"#0e1a24",mouth:"smile",mouthColor:"#5a2e1a",hair:"punk",hairColor:"#9b7bff",clothes:"hoodie",clothesColor:"#258bf5",accessory:"crown",accessoryColor:"#e6c07a",bg:"grad",pattern:"none",accent:"#3b9dff",talking:false};
function adjustAvColor(col,amt){let num=parseInt(col.replace("#",""),16);if(isNaN(num))return "#142b3d";let r=(num>>16)+amt,b=((num>>8)&0xff)+amt,g=(num&0xff)+amt;return "#"+(0x1000000+(r<255?r<0?0:r:255)*0x10000+(b<255?b<0?0:b:255)*0x100+(g<255?g<0?0:g:255)).toString(16).slice(1)}
function renderAvatar(s,opts){opts=opts||{};const size=opts.size||64,pulse=!!opts.pulse,blink=opts.blink!==false,talking=!!opts.talking,live=opts.live!==false;const accent=s.accent||"#3b9dff",bg2=adjustAvColor(accent,-40),bg3=adjustAvColor(accent,-60),radius=size>=100?"32px":size>=40?"11px":"8px";
const headShapes={round:'<circle cx="32" cy="32" r="17"/>',square:'<rect x="15" y="15" width="34" height="34" rx="9"/>',hex:'<path d="M32 14 L48 23 L48 41 L32 50 L16 41 L16 23 Z"/>',squircle:'<rect x="15" y="15" width="34" height="34" rx="14"/>',drop:'<path d="M32 13 Q47 13 47 28 Q47 43 32 50 Q17 43 17 28 Q17 13 32 13 Z"/>'};
const eyes={dots:'<circle cx="25" cy="30" r="2.2" fill="'+s.eyesColor+'"/><circle cx="39" cy="30" r="2.2" fill="'+s.eyesColor+'"/>',wide:'<ellipse cx="25" cy="30" rx="3.5" ry="4" fill="#fff"/><ellipse cx="39" cy="30" rx="3.5" ry="4" fill="#fff"/><circle cx="25" cy="30.5" r="1.8" fill="'+s.eyesColor+'"/><circle cx="39" cy="30.5" r="1.8" fill="'+s.eyesColor+'"/>',line:'<path d="M22 30h6M36 30h6" stroke="'+s.eyesColor+'" stroke-width="2.2" stroke-linecap="round" fill="none"/>',anime:'<ellipse cx="25" cy="30" rx="3.5" ry="4.5" fill="#fff"/><ellipse cx="39" cy="30" rx="3.5" ry="4.5" fill="#fff"/><circle cx="25.5" cy="31" r="2.2" fill="'+s.eyesColor+'"/><circle cx="39.5" cy="31" r="2.2" fill="'+s.eyesColor+'"/><circle cx="26.2" cy="29.8" r=".9" fill="#fff"/><circle cx="40.2" cy="29.8" r=".9" fill="#fff"/>',visor:'<rect x="17" y="26" width="30" height="8" rx="4" fill="#111" opacity=".9"/><path d="M19 30h26" stroke="'+s.eyesColor+'" stroke-width="2" stroke-linecap="round" stroke-dasharray="3 2"/>'};
const mouths={smile:'<path d="M26 39q6 5 12 0" stroke="'+s.mouthColor+'" stroke-width="2" stroke-linecap="round" fill="none"/>',line:'<path d="M27 40h10" stroke="'+s.mouthColor+'" stroke-width="2" stroke-linecap="round"/>',open:'<ellipse cx="32" cy="40" rx="3.5" ry="2.5" fill="'+s.mouthColor+'"/><ellipse cx="32" cy="41" rx="2" ry="1.2" fill="#e06b6b"/>',smirk:'<path d="M26 40q6 2 12 -2" stroke="'+s.mouthColor+'" stroke-width="2" stroke-linecap="round" fill="none"/>',grin:'<path d="M25 38 q7 6 14 0" fill="none" stroke="'+s.mouthColor+'" stroke-width="2" stroke-linecap="round"/><path d="M27 39 h10" stroke="#fff" stroke-width="1.5"/>'};
const hairShapes={none:"",punk:'<path d="M14 21 L20 8 L24 18 L28 6 L32 16 L36 6 L40 18 L44 8 L50 21 Q44 16 32 16 Q20 16 14 21Z" fill="'+s.hairColor+'"/>',short:'<path d="M15 22 Q16 11 32 11 Q48 11 49 22 Q44 16 32 16 Q20 16 15 22Z" fill="'+s.hairColor+'"/>',long:'<path d="M14 22 Q14 9 32 9 Q50 9 50 22 L50 44 Q46 42 45 34 L45 22 Q43 16 32 16 Q21 16 19 22 L19 34 Q18 42 14 44Z" fill="'+s.hairColor+'"/>',mohawk:'<path d="M28 8 L32 2 L36 8 L38 5 L38 18 L26 18 L26 5 Z" fill="'+s.hairColor+'"/>',bun:'<circle cx="32" cy="8" r="6" fill="'+s.hairColor+'"/><path d="M15 22 Q16 12 32 12 Q48 12 49 22 Q44 16 32 16 Q20 16 15 22Z" fill="'+s.hairColor+'"/>',afro:'<circle cx="32" cy="18" r="15" fill="'+s.hairColor+'"/><circle cx="18" cy="22" r="9" fill="'+s.hairColor+'"/><circle cx="46" cy="22" r="9" fill="'+s.hairColor+'"/>'};
const clothesShapes={hoodie:'<path d="M14 64 C14 47 18 45 32 45 C46 45 50 47 50 64 Z" fill="'+s.clothesColor+'"/><path d="M24 45 Q32 53 40 45" fill="none" stroke="#10131d" stroke-width="1.5"/>',jacket:'<path d="M14 64 C14 47 18 45 32 45 C46 45 50 47 50 64 Z" fill="'+s.clothesColor+'"/><path d="M32 45 L32 64" stroke="#10131d" stroke-width="2"/><path d="M21 47 L29 54 M43 47 L35 54" stroke="#10131d" stroke-width="1.5"/>',uniform:'<path d="M14 64 C14 47 18 45 32 45 C46 45 50 47 50 64 Z" fill="'+s.clothesColor+'"/><rect x="23" y="48" width="18" height="4" rx="1" fill="#fff" opacity=".5"/>',tshirt:'<path d="M14 64 C14 47 18 45 32 45 C46 45 50 47 50 64 Z" fill="'+s.clothesColor+'"/>'};
const accessories={none:"",glasses:'<g fill="none" stroke="'+s.accessoryColor+'" stroke-width="2"><rect x="18" y="26" width="11" height="8" rx="2.5"/><rect x="35" y="26" width="11" height="8" rx="2.5"/><path d="M29 29h6"/></g>',headphones:'<g fill="'+s.accessoryColor+'"><rect x="10" y="24" width="5" height="14" rx="2.5"/><rect x="49" y="24" width="5" height="14" rx="2.5"/><path d="M12 26 Q12 10 32 10 Q52 10 52 26" fill="none" stroke="'+s.accessoryColor+'" stroke-width="3.5" stroke-linecap="round"/></g>',crown:'<path d="M19 16 L23 6 L28 14 L32 4 L36 14 L41 6 L45 16 Z" fill="'+s.accessoryColor+'" stroke="#a88024" stroke-width="1"/><circle cx="23" cy="14" r="1" fill="#ff5f56"/><circle cx="32" cy="12" r="1" fill="#5eead4"/><circle cx="41" cy="14" r="1" fill="#ff5f56"/>',halo:'<ellipse cx="32" cy="8" rx="14" ry="3.5" fill="none" stroke="'+s.accessoryColor+'" stroke-width="2.5"/>',mask:'<path d="M20 32 Q32 28 44 32 L44 41 Q32 47 20 41 Z" fill="#151722" opacity=".95"/><path d="M24 36h16" stroke="'+s.accessoryColor+'" stroke-width="1.5" stroke-dasharray="2 2"/>',antenna:'<line x1="32" y1="14" x2="32" y2="3" stroke="'+s.accessoryColor+'" stroke-width="2"/><circle cx="32" cy="3" r="3" fill="'+s.accessoryColor+'"/>'};
const pulseClass=pulse?" av-pulse":"",talkingClass=talking?" av-talking":"",liveClass=live?" av-live":"",blinkAttr=blink?"":' style="animation:none"';
return '<div class="av'+pulseClass+talkingClass+liveClass+'" style="--av-bg:'+accent+';--av-bg2:'+bg2+';--av-bg3:'+bg3+';width:'+size+'px;height:'+size+'px;border-radius:'+radius+'"><div class="av-bg '+s.bg+'"></div>'+(s.pattern!=="none"?'<div class="av-pattern '+s.pattern+'"></div>':"")+'<div class="av-person-wrap"><svg class="av-person" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg"><g class="av-body">'+(clothesShapes[s.clothes]||clothesShapes.hoodie)+'</g><rect x="28" y="40" width="8" height="6" fill="'+s.skin+'" opacity=".85"/><g class="av-head" fill="'+s.skin+'">'+(headShapes[s.head]||headShapes.round)+'</g><g class="av-hair">'+(hairShapes[s.hair]||"")+'</g><g class="av-eye"'+blinkAttr+'>'+(eyes[s.eyes]||eyes.dots)+'</g><g class="av-mouth">'+(mouths[s.mouth]||mouths.smile)+'</g><g class="av-acc">'+(accessories[s.accessory]||"")+'</g><ellipse cx="23" cy="21" rx="4" ry="2.5" fill="#fff" opacity=".15"/></svg></div>'+(talking?'<div class="av-sound"><span></span><span></span><span></span></div>':"")+'</div>'}
function rgbToHex(rgb){if(!rgb||rgb.indexOf("rgb")!==0)return rgb;const n=rgb.match(/\d+/g);if(!n)return rgb;return "#"+((1<<24)+(+n[0]<<16)+(+n[1]<<8)+ +n[2]).toString(16).slice(1)}
function initAvatarPickers(){document.querySelectorAll(".avatar-color-picker[data-av-key]").forEach(function(container){const key=container.dataset.avKey,palette=PALETTES[key]||[];container.innerHTML="";palette.forEach(function(col){const btn=document.createElement("button");btn.type="button";btn.className="avatar-swatch"+(avatarState[key]===col?" active":"");btn.style.background=col;btn.onclick=function(){avatarState[key]=col;container.querySelectorAll(".avatar-swatch").forEach(function(b){b.classList.remove("active")});btn.classList.add("active");updateAvatarPreview()};container.appendChild(btn)});const custom=document.createElement("div");custom.className="avatar-custom-color";const inp=document.createElement("input");inp.type="color";inp.value=avatarState[key]||"#3b9dff";inp.oninput=function(e){avatarState[key]=e.target.value;container.querySelectorAll(".avatar-swatch").forEach(function(b){b.classList.remove("active")});updateAvatarPreview()};custom.appendChild(inp);container.appendChild(custom)})}
function syncAvatarState(){document.querySelectorAll("[data-av-field]").forEach(function(sel){if(avatarState[sel.dataset.avField]!==undefined)sel.value=avatarState[sel.dataset.avField]});document.querySelectorAll(".avatar-color-picker[data-av-key]").forEach(function(container){const key=container.dataset.avKey;container.querySelectorAll(".avatar-swatch").forEach(function(b){b.classList.toggle("active",b.style.backgroundColor&&rgbToHex(b.style.backgroundColor).toLowerCase()===String(avatarState[key]).toLowerCase())});const ci=container.querySelector("input[type=color]");if(ci)ci.value=avatarState[key]})}
function updateAvatarPreview(){const preview=document.getElementById("avatar-preview-big");if(preview)preview.innerHTML=renderAvatar(avatarState,{size:140,pulse:true,talking:avatarState.talking,live:true});const nameEl=document.getElementById("avatar-preview-name");const nameInput=document.getElementById("domain-name");if(nameEl)nameEl.textContent=(nameInput&&nameInput.value)||"Агент"}
function bindAvatarControls(){document.querySelectorAll("[data-av-field]").forEach(function(sel){sel.onchange=function(){avatarState[sel.dataset.avField]=sel.value;updateAvatarPreview()}});document.querySelectorAll(".avatar-tab-btn").forEach(function(btn){btn.onclick=function(){document.querySelectorAll(".avatar-tab-btn").forEach(function(b){b.classList.remove("active")});document.querySelectorAll(".avatar-tab-pane").forEach(function(p){p.classList.remove("active")});btn.classList.add("active");const pane=document.querySelector('.avatar-tab-pane[data-av-tab="'+btn.dataset.avTab+'"]');if(pane)pane.classList.add("active")}});const nameInput=document.getElementById("domain-name");if(nameInput)nameInput.addEventListener("input",updateAvatarPreview);const rand=document.getElementById("avatar-random");if(rand)rand.onclick=function(){const pick=function(a){return a[Math.floor(Math.random()*a.length)]};avatarState.head=pick(["round","square","hex","squircle","drop"]);avatarState.eyes=pick(["dots","wide","line","anime","visor"]);avatarState.mouth=pick(["smile","line","open","smirk","grin"]);avatarState.hair=pick(["none","punk","short","long","mohawk","bun","afro"]);avatarState.clothes=pick(["hoodie","jacket","uniform","tshirt"]);avatarState.accessory=pick(["none","glasses","headphones","crown","halo","mask","antenna"]);avatarState.bg=pick(["grad","radial","mesh","solid"]);avatarState.pattern=pick(["none","dots","grid","diag"]);avatarState.skin=pick(PALETTES.skin);avatarState.hairColor=pick(PALETTES.hairColor);avatarState.clothesColor=pick(PALETTES.clothesColor);avatarState.eyesColor=pick(PALETTES.eyesColor);avatarState.mouthColor=pick(PALETTES.mouthColor);avatarState.accessoryColor=pick(PALETTES.accessoryColor);avatarState.accent=pick(PALETTES.accent);syncAvatarState();initAvatarPickers();updateAvatarPreview()};const talk=document.getElementById("avatar-toggle-talk");if(talk)talk.onclick=function(){avatarState.talking=!avatarState.talking;talk.textContent=avatarState.talking?"⏸ Остановить":"🗣 Разговор";updateAvatarPreview()}}
function avatarStudioMarkup(){return '<div class="avatar-studio"><div class="avatar-preview-wrap"><div class="avatar-preview-box"><div id="avatar-preview-big"></div></div><div class="avatar-preview-name" id="avatar-preview-name">Агент</div><div class="avatar-preview-meta">Живой предпросмотр</div></div><div class="avatar-controls"><div class="avatar-tabs"><button type="button" class="avatar-tab-btn active" data-av-tab="face">Голова</button><button type="button" class="avatar-tab-btn" data-av-tab="hair">Причёска</button><button type="button" class="avatar-tab-btn" data-av-tab="body">Одежда</button><button type="button" class="avatar-tab-btn" data-av-tab="style">Стиль</button></div><div class="avatar-tab-pane active" data-av-tab="face"><div class="avatar-field-row"><label>Форма</label><select data-av-field="head"><option value="round">Круглая</option><option value="square">Квадратная</option><option value="hex">Шестиугольник</option><option value="squircle">Скруглённая</option><option value="drop">Капля</option></select></div><div class="avatar-color-group"><label>Цвет кожи</label><div class="avatar-color-picker" data-av-key="skin"></div></div><div class="avatar-field-row"><label>Глаза</label><select data-av-field="eyes"><option value="dots">Точки</option><option value="wide">Большие</option><option value="line">Полоски</option><option value="anime">Аниме</option><option value="visor">Кибер-визор</option></select></div><div class="avatar-color-group"><label>Цвет глаз</label><div class="avatar-color-picker" data-av-key="eyesColor"></div></div><div class="avatar-field-row"><label>Рот</label><select data-av-field="mouth"><option value="smile">Улыбка</option><option value="line">Линия</option><option value="open">Открытый</option><option value="smirk">Ухмылка</option><option value="grin">Зубы</option></select></div><div class="avatar-color-group"><label>Цвет рта</label><div class="avatar-color-picker" data-av-key="mouthColor"></div></div></div><div class="avatar-tab-pane" data-av-tab="hair"><div class="avatar-field-row"><label>Причёска</label><select data-av-field="hair"><option value="none">Лысый</option><option value="short">Короткие</option><option value="punk">Панк</option><option value="mohawk">Ирокез</option><option value="long">Длинные</option><option value="bun">Пучок</option><option value="afro">Афро</option></select></div><div class="avatar-color-group"><label>Цвет волос</label><div class="avatar-color-picker" data-av-key="hairColor"></div></div><div class="avatar-field-row"><label>Аксессуар</label><select data-av-field="accessory"><option value="none">Нет</option><option value="glasses">Очки</option><option value="headphones">Наушники</option><option value="crown">Корона</option><option value="halo">Нимб</option><option value="mask">Маска</option><option value="antenna">Антенна</option></select></div><div class="avatar-color-group"><label>Цвет аксессуара</label><div class="avatar-color-picker" data-av-key="accessoryColor"></div></div></div><div class="avatar-tab-pane" data-av-tab="body"><div class="avatar-field-row"><label>Одежда</label><select data-av-field="clothes"><option value="hoodie">Худи</option><option value="jacket">Пиджак</option><option value="uniform">Форма</option><option value="tshirt">Футболка</option></select></div><div class="avatar-color-group"><label>Цвет одежды</label><div class="avatar-color-picker" data-av-key="clothesColor"></div></div></div><div class="avatar-tab-pane" data-av-tab="style"><div class="avatar-field-row"><label>Фон</label><select data-av-field="bg"><option value="grad">Градиент</option><option value="radial">Радиальный</option><option value="mesh">Меш</option><option value="solid">Плоский</option></select></div><div class="avatar-field-row"><label>Узор</label><select data-av-field="pattern"><option value="none">Нет</option><option value="dots">Точки</option><option value="grid">Сетка</option><option value="diag">Диагональ</option></select></div><div class="avatar-color-group"><label>Основной цвет</label><div class="avatar-color-picker" data-av-key="accent"></div></div></div><div class="avatar-actions"><button type="button" class="btn soft-secondary" id="avatar-random">🎲 Случайный</button><button type="button" class="btn soft-secondary" id="avatar-toggle-talk">🗣 Разговор</button></div></div></div>'}
window.PQAvatar = { get state() { return avatarState; }, set state(value) { avatarState = value; }, render: renderAvatar, palettes: PALETTES };
window.PQDomainModal = {
  open: openDomainModal, markup: domainModalMarkup, bind: bindDomainModal,
  save: saveDomainItem, remove: deleteDomainItem, renderAvatar,
  getAvatarState: () => avatarState, setAvatarState: value => { avatarState = value; },
  configure: options => { context = { ...context, ...(options || {}) }; }
};
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bindDomainModal);
else if (document.getElementById('domain-modal')) bindDomainModal();

})();
