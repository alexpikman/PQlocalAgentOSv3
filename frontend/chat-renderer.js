/* Рендерер событий чата. Не вставляет данные модели через innerHTML. */
export class ChatRenderer {
  constructor(container, getContext) {
    this.container=container; this.nodes=new Map(); this.seen=new Set();
    this.status=document.getElementById('chat-task-status');
    this.getContext=typeof getContext==='function'?getContext:()=>({});
    this.turnStartedAt=null; this.lastTurnStatus='completed'; this.userSendStatuses=new Map();
    container?.addEventListener('click',async event=>{
      const action=event.target.closest('[data-chat-message-action]'); if(!action)return;
      const row=action.closest('.chat-msg'); if(!row)return;
      if(action.dataset.chatMessageAction==='copy'){
        try{await navigator.clipboard.writeText(row.querySelector('.chat-msg-bubble')?.textContent||'');action.title='Скопировано';}
        catch(_){action.title='Не удалось скопировать';}
      } else if(action.dataset.chatMessageAction==='retry') {
        let userRow=row.classList.contains('user')?row:row.previousElementSibling;
        while(userRow&&!userRow.classList.contains('user'))userRow=userRow.previousElementSibling;
        window.dispatchEvent(new CustomEvent('pq-chat-retry',{detail:{text:userRow?.querySelector('.chat-msg-bubble')?.textContent||''}}));
      }
    });
    window.addEventListener('pq-chat-user-send-status',event=>{
      const detail=event.detail||{};
      this.setUserMessageStatus(detail.commandId,detail.status);
    });
    container?.addEventListener('click',async event=>{
      const button=event.target.closest('[data-approval-decision]'); if(!button)return;
      const card=button.closest('[data-approval-id]'); if(!card)return;
      button.disabled=true;
      try {
        const transport=window.PQChatTransport;
        if(!transport)throw new Error('Транспорт чата не подключён');
        await transport.approveTool(card.dataset.approvalId,button.dataset.approvalDecision);
      } catch(error) {
        let note=card.querySelector('.chat-approval-error');
        if(!note){note=document.createElement('p');note.className='chat-approval-error';card.append(note);}
        note.textContent=error.message;button.disabled=false;
      }
    });
  }
  reset(){this.container.replaceChildren();this.nodes.clear();this.seen.clear();}
  startTurn(timestamp=Date.now()){this.turnStartedAt=Number(timestamp)||Date.now();}
  setUserMessageStatus(commandId,status){
    if(!commandId||!status)return;
    this.userSendStatuses.set(String(commandId),status);
    const row=[...this.container.querySelectorAll('.chat-msg.user')].find(item=>item.dataset.commandId===String(commandId));
    if(row)this._applyUserStatus(row,status);
  }
  _applyUserStatus(row,status){
    row.dataset.sendStatus=status;
    const badge=row.querySelector('.chat-msg-result-status');if(!badge)return;
    badge.classList.remove('is-pending','is-success','is-error');
    badge.classList.add(status==='success'?'is-success':status==='error'?'is-error':'is-pending');
    badge.title=status==='success'?'Сообщение отправлено':status==='error'?'Ошибка отправки сообщения':'Отправка сообщения';
    badge.setAttribute('aria-label',badge.title);
  }
  showLocalUserMessage(text,commandId,status='error'){
    if(commandId&&[...this.container.querySelectorAll('.chat-msg.user')].some(row=>row.dataset.commandId===String(commandId)))return;
    const event={event_id:'local-'+String(commandId||Date.now()),created_at:new Date().toISOString(),payload:{text,command_id:commandId}};
    this._message('user',text,event);
    const row=this.container.lastElementChild;
    if(row)this._applyUserStatus(row,status);
  }
  _el(tag,cls,text){const el=document.createElement(tag);if(cls)el.className=cls;if(text!==undefined)el.textContent=String(text);return el;}
  _normalizeAssistantText(text) {
    const raw = String(text ?? '');
    if (!raw.trimStart().startsWith('{')) return { text: raw, toolCall: null };
    try {
      const value = JSON.parse(raw.trim());
      if (!value || typeof value !== 'object' || Array.isArray(value)) return { text: raw, toolCall: null };
      const type = String(value.type || '').toLowerCase();
      if (type === 'message' || type === 'assistant_message') return { text: String(value.text ?? value.content ?? ''), toolCall: null };
      if (type === 'tool_call' || type === 'tool-call' || (typeof value.name === 'string' && ('parameters' in value || 'arguments' in value))) {
        const args = value.parameters ?? value.arguments ?? {};
        return { text: '', toolCall: typeof value.name === 'string' && args && typeof args === 'object' ? { name: value.name, arguments: args } : null };
      }
      if (typeof value.text === 'string') return { text: value.text, toolCall: null };
      return { text: 'Получен структурированный ответ без распознанного текста.', toolCall: null };
    } catch (_) { return { text: raw, toolCall: null }; }
  }
  applyMany(events){for(const event of events||[])this.apply(event);}
  apply(event){
    if(!event||typeof event!=='object'||!event.event_id||this.seen.has(event.event_id))return;
    this.updateActivity(event);
    this.updateHeaderIndicators(event);
    this.seen.add(event.event_id);const p=event.payload||{};
    switch(event.type){
      case 'user_message':this._message('user',p.text||'',event);break;
      case 'assistant_delta':this._assistantDelta(event.message_id,p.text||'');break;
      case 'assistant_message':this._assistantFinal(event.message_id,p.content||'');break;
      case 'thinking':this._status('Думает…');break;
      case 'turn_state':if(p.state==='thinking'&&!this.turnStartedAt)this.turnStartedAt=event.created_at?new Date(event.created_at).getTime():Date.now();this._status(({thinking:'Генерирует ответ…',streaming:'Генерирует ответ…',tool_running:'Выполняет инструмент…',waiting_approval:'Ожидает подтверждения',idle:''})[p.state]||p.state||'');break;
      case 'tool_call':this._status('Выполняет инструмент: '+(p.name||p.tool_name||'инструмент'));this._toolCall(event.tool_call_id,p);break;
      case 'tool_result':this._status(p.status==='error'?'Ошибка инструмента':'Получен результат инструмента');this._toolResult(event.tool_call_id,p);break;
      case 'approval_required':this._status('Ожидает подтверждения');this._approval(p);break;
      case 'approval_resolved':this._status(p.decision==='approved'?'Возобновляет выполнение…':'Продолжает после отказа…');this._approvalResolved(p);break;
      case 'error':this._status('Ошибка');this.container.append(this._el('div','chat-event-error',p.message||'Ошибка агента'));break;
      case 'turn_completed':this.lastTurnStatus=(p.status==='completed'||p.status==='success')?'completed':'error';this._finishTurn(event);this._status('');window.dispatchEvent(new CustomEvent('pq-chat-turn-completed',{detail:event}));break;
      case 'turn_cancelled':this.lastTurnStatus='error';this._finishTurn(event);this._status('');window.dispatchEvent(new CustomEvent('pq-chat-turn-cancelled',{detail:event}));break;
    }
  }
  _message(role,text,event){
    const isUser=role==='user';
    const row=this._el('article','chat-msg '+(isUser?'user':'bot'));row.dataset.eventId=event.event_id;
    const payload=event.payload||{};
    if(payload.command_id)row.dataset.commandId=String(payload.command_id);
    row.append(this._el('div','chat-msg-avatar',isUser?'Вы':'AI'));
    const content=this._el('div','chat-msg-content'),meta=this._el('div','chat-msg-meta');
    const context=this.getContext()||{};
    const agentName=String(context.agentName||'Агент');
    const modelName=String(context.modelName||'Модель по умолчанию');
    meta.append(this._el('span','chat-msg-name',isUser?'Вы':(agentName+' | '+modelName)));
    const time=this._el('time','chat-msg-time',event.created_at?new Date(event.created_at).toLocaleTimeString():'');
    meta.append(time);const bubble=this._el('div','chat-msg-bubble',text);content.append(meta,bubble);
    const actions=this._el('div','chat-msg-actions');
    const retry=this._el('button','chat-msg-action','↻');retry.type='button';retry.dataset.chatMessageAction='retry';retry.title=isUser?'Повторить отправку сообщения':'Повторить запрос';retry.setAttribute('aria-label',retry.title);
    const copy=this._el('button','chat-msg-action','⧉');copy.type='button';copy.dataset.chatMessageAction='copy';copy.title='Скопировать текст';copy.setAttribute('aria-label','Скопировать текст');
    const status=this._el('span','chat-msg-result-status is-pending','✓');status.title=isUser?'Отправка сообщения':'Ответ ещё не завершён';status.setAttribute('aria-label',status.title);
    actions.append(retry,copy,status);content.append(actions);
    if(isUser){
      const knownStatus=this.userSendStatuses.get(String(payload.command_id||''));
      this._applyUserStatus(row,knownStatus||'pending');
    }else{
      row.dataset.turnStatus='pending';
      row.dataset.agentName=agentName;
      row.dataset.modelName=modelName;
    }
    row.dataset.createdAt=event.created_at||new Date().toISOString();row.append(content);
    this.container.append(row);this._scroll();
  }
  _assistantDelta(id,text){
    if(!id)return;let node=this.nodes.get(id);
    if(!node){this._message('assistant','',{event_id:'assistant-'+id});node=this.container.lastElementChild;node.dataset.messageId=id;node.dataset.rawAssistantText='';this.nodes.set(id,node);}
    node.dataset.rawAssistantText=(node.dataset.rawAssistantText||'')+String(text||'');
    const bubble=node.querySelector('.chat-msg-bubble'),raw=node.dataset.rawAssistantText;
    if(raw.trimStart().startsWith('{')){bubble.textContent='';return;}
    bubble.textContent=raw;this._scroll();
  }
  _assistantFinal(id,text){
    if(!id)return;let node=this.nodes.get(id);
    if(!node){this._assistantDelta(id,'');node=this.nodes.get(id);}
    const normalized=this._normalizeAssistantText(text);
    node.querySelector('.chat-msg-bubble').textContent=normalized.text;
    if(normalized.toolCall)this._toolCall('legacy-'+id,normalized.toolCall);
    this._scroll();
  }
  updateHeaderIndicators(event){
    const payload=event.payload||{};
    const set=(kind,state,title)=>{
      const el=document.querySelector('[data-chat-indicator="'+kind+'"]');if(!el)return;
      el.classList.remove('is-idle','is-active','is-error','is-read','is-write','is-delete','is-remote');
      el.classList.add(state);if(title)el.title=title;
    };
    const resetIndicators=()=>{
      set('error','is-idle','Нет активной ошибки');
      set('files','is-idle','Нет активной операции с файлами');
      set('approval','is-idle','Нет ожидающего подтверждения');
      set('remote','is-idle','Нет активного удалённого подключения');
    };
    if(event.type==='tool_call'){
      const name=String(payload.name||payload.tool_name||'').toLowerCase();
      if(name==='read_file'||/^(list_files|search_files|github_read_file|github_list_files)$/.test(name)){
        set('files','is-read','Чтение файла');
      }else if(name==='write_file'||name==='create_directory'){
        set('files','is-write','Запись или создание файла/папки');
      }else if(name==='delete'||name==='delete_file'||name==='delete_directory'||name==='move_file'){
        set('files','is-delete','Удаление или перемещение');
      }
      if(/^(ssh_|github_)/i.test(name))set('remote','is-remote','Удалённый инструмент SSH/GitHub');
    }else if(event.type==='approval_required'){
      set('approval','is-active','Ожидается подтверждение пользователя');
    }else if(event.type==='approval_resolved'){
      set('approval','is-idle','Подтверждение обработано');
    }else if(event.type==='error'||event.type==='turn_completed'||event.type==='turn_cancelled'){
      resetIndicators();
    }
  }
  _finishTurn(event){
    const completedAt=event?.created_at?new Date(event.created_at).getTime():Date.now();
    const startAt=this.turnStartedAt;
    const seconds=startAt?Math.max(0,(completedAt-startAt)/1000):0;
    const rows=[...this.container.querySelectorAll('.chat-msg.bot')];
    const row=rows.reverse().find(item=>item.dataset.turnStatus==='pending')||rows[0];
    if(row){
      row.dataset.turnStatus=this.lastTurnStatus;
      row.dataset.durationSeconds=seconds.toFixed(1);
      const status=row.querySelector('.chat-msg-result-status');
      if(status){status.classList.remove('is-pending');status.classList.add(this.lastTurnStatus==='completed'?'is-success':'is-error');status.title=this.lastTurnStatus==='completed'?'Ответ завершён':'Ход завершился с ошибкой';}
      const meta=row.querySelector('.chat-msg-name');
      if(meta)meta.textContent=String(row.dataset.agentName||'Агент')+' | '+String(row.dataset.modelName||'Модель по умолчанию')+' | '+seconds.toFixed(1)+' с';
    }
    this.turnStartedAt=null;
  }
  _toolCall(id,p){
    const row=this.nodes.size?[...this.nodes.values()].at(-1):null;
    const parent=row?.querySelector('.chat-msg-content')||this.container;
    let list=parent.querySelector('.chat-tool-calls');
    if(!list){list=this._el('div','chat-tool-calls');parent.append(list);}
    const card=this._el('section','chat-tool-card');card.dataset.toolCallId=id||'';
    card.append(this._el('span','chat-tool-badge','Инструмент: '+(p.name||'неизвестно')));
    card.append(this._el('pre','',JSON.stringify(p.arguments||{},null,2)));list.append(card);this._scroll();
  }
  _toolResult(id,p){
    const card=[...this.container.querySelectorAll('[data-tool-call-id]')].find(el=>el.dataset.toolCallId===id);
    if(!card)return;
    let result=p.result??p.message??p.error??'Готово';
    try {
      const parsed=typeof result==='string'?JSON.parse(result):result;
      if(parsed&&typeof parsed==='object'&&parsed.error)result='Ошибка: '+String(parsed.message||parsed.error);
      else if(parsed&&typeof parsed==='object'&&typeof parsed.content==='string')result=parsed.content;
      else if(parsed&&typeof parsed==='object'&&Array.isArray(parsed.items))result=parsed.items.length
        ? parsed.items.map(item=>typeof item==='string'?item:String(item.name||item.path||item.title||JSON.stringify(item))).join('\n')
        : 'Список пуст.';
      else if(parsed&&typeof parsed==='object'&&typeof parsed.message==='string')result=parsed.message;
      else if(parsed&&typeof parsed==='object')result=Object.entries(parsed).map(([key,value])=>key+': '+(typeof value==='string'?value:JSON.stringify(value))).join('\n');
    } catch (_) {}
    card.append(this._el('pre','chat-tool-result',result));
    if(p.status==='error'||p.status==='denied'||p.error)card.dataset.status='error';
  }
  _approval(p){
    const card=this._el('section','chat-approval-card');card.dataset.approvalId=p.approval_id||'';
    card.append(this._el('p','',p.description||'Требуется подтверждение: '+(p.tool_name||'инструмент')));
    for(const [decision,label] of [['approved','Разрешить'],['rejected','Отклонить']]){
      const button=this._el('button','btn secondary',label);button.type='button';button.dataset.approvalDecision=decision;card.append(button);
    }
    this.container.append(card);this._scroll();
  }
  _approvalResolved(p){
    const card=[...this.container.querySelectorAll('[data-approval-id]')].find(el=>el.dataset.approvalId===p.approval_id);
    if(card){card.append(this._el('p','',p.decision==='approved'?'Разрешено':'Отклонено'));card.querySelectorAll('button').forEach(button=>button.disabled=true);}
  }
  _status(text){if(this.status){this.status.textContent=text;const center=this.status.closest('.chat-header-center');if(center)center.classList.toggle('is-active',/генер|думает|инструмент|возобновляет|продолжает/i.test(String(text||'')));}}
  _scroll(){this.container.scrollTop=this.container.scrollHeight;}
  updateActivity(event) {
    const el = document.getElementById("chat-activity");
    if (!el) return;
    const label = document.getElementById("chat-activity-label");
    const detail = document.getElementById("chat-activity-detail");
    if (!label || !detail) return;

    const type = event.type;
    const payload = event.payload || {};

    const show = (state, text, detailText) => {
      el.hidden = false;
      el.dataset.state = state;
      label.textContent = text;
      detail.textContent = detailText || "";
    };
    const hide = () => {
      el.hidden = true;
      el.dataset.state = "";
      label.textContent = "";
      detail.textContent = "";
    };

    switch (type) {
      case "turn_state": {
        const s = payload.state || payload.status || "";
        if (s === "thinking") show("thinking", "Думает…", "");
        else if (s === "streaming") show("streaming", "Печатает…", "");
        else if (s === "tool_running") show("tool", "Выполняет инструмент…", "");
        else if (s === "waiting_approval") show("approval", "Ждёт подтверждения", "");
        else if (s === "idle") hide();
        break;
      }
      case "assistant_delta":
        show("streaming", "Печатает…", "");
        break;
      case "tool_call": {
        const name = payload.name || payload.tool_name || "tool";
        const args = payload.arguments ? JSON.stringify(payload.arguments).slice(0, 80) : "";
        show("tool", "Инструмент: " + name, args);
        break;
      }
      case "tool_result": {
        const status = payload.status || "done";
        if (status === "denied") show("failed", "Отклонено", "allowed_paths");
        else show("tool", "Результат получен", "");
        break;
      }
      case "approval_required":
        show("approval", "Ждёт вашего подтверждения", payload.tool_name || "");
        break;
      case "approval_resolved":
        show("tool", "Подтверждение принято", payload.decision || "");
        break;
      case "verification": {
        const ok = payload.verified;
        show(ok ? "completed" : "failed", ok ? "Проверено" : "Проверка не пройдена", "");
        break;
      }
      case "turn_completed": {
        const status = String(payload.status || "success").toLowerCase();
        const ok = status === "success" || status === "completed";
        show(ok ? "completed" : "failed", ok ? "Готово" : "Ошибка", payload.reason || "");
        if (ok) setTimeout(() => { if (el.dataset.state === "completed") hide(); }, 3000);
        break;
      }
      case "turn_cancelled":
        show("failed", "Отменено", "");
        setTimeout(hide, 3000);
        break;
      case "error":
        show("failed", "Ошибка", payload.message || "");
        break;
    }
  }

}
