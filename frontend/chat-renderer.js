/* Безопасный рендерер событий. Все внешние данные вставляются только через textContent. */
export class ChatRenderer {
  constructor(container) {
    this.container=container;this.nodes=new Map();this.seen=new Set();
    this.status=document.getElementById('chat-task-status');
    container?.addEventListener('click',async e=>{
      const button=e.target.closest('[data-approval-decision]');if(!button)return;
      const card=button.closest('[data-approval-id]');if(!card)return;
      button.disabled=true;
      try{
        const transport=window.PQChatTransport;
        if(!transport)throw new Error('Транспорт чата не подключён');
        await transport.approveTool(card.dataset.approvalId,button.dataset.approvalDecision);
      }catch(err){const note=card.querySelector('.chat-approval-error')||document.createElement('p');note.className='chat-approval-error';note.textContent=err.message;card.append(note);button.disabled=false;}
    });
  }
  _el(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=String(text);return e;}
  applyMany(events){for(const event of events||[])this.apply(event);}
  apply(event){
    if(!event||typeof event!=='object'||!event.event_id||this.seen.has(event.event_id))return;
    this.seen.add(event.event_id);const p=event.payload||{};
    switch(event.type){
      case 'user_message': this._message('user',p.text||'',event);break;
      case 'assistant_delta': this._assistantDelta(event.message_id,p.text||'');break;
      case 'assistant_message': this._assistantFinal(event.message_id,p.content||'');break;
      case 'thinking': this._status('Думает…');break;
      case 'turn_state': this._status(({thinking:'Думает…',streaming:'Генерирует ответ…',waiting_approval:'Ожидает подтверждения',idle:'Готово'})[p.state]||p.state||'');break;
      case 'tool_call': this._toolCall(event.tool_call_id,p);break;
      case 'tool_result': this._toolResult(event.tool_call_id,p);break;
      case 'approval_required': this._approval(p);break;
      case 'approval_resolved': this._approvalResolved(p);break;
      case 'error': this.container.append(this._el('div','chat-event-error',p.message||'Ошибка агента'));break;
      case 'turn_completed': this._status('');window.dispatchEvent(new CustomEvent('pq-chat-turn-completed',{detail:event}));break;
      case 'turn_cancelled': this._status('');window.dispatchEvent(new CustomEvent('pq-chat-turn-cancelled',{detail:event}));break;
    }
  }
  _message(role,text,event){
    const node=this._el('article','chat-message chat-message-'+role);
    node.dataset.eventId=event.event_id;node.append(this._el('div','chat-message-content',text));this.container.append(node);
  }
  _assistantDelta(id,text){
    if(!id)return;let node=this.nodes.get(id);
    if(!node){node=this._el('article','chat-message chat-message-assistant');node.append(this._el('div','chat-message-content',''));node.dataset.messageId=id;this.nodes.set(id,node);this.container.append(node);}
    const body=node.querySelector('.chat-message-content');body.textContent+=text;
  }
  _assistantFinal(id,text){
    if(!id)return;let node=this.nodes.get(id);
    if(!node){this._assistantDelta(id,'');node=this.nodes.get(id);}
    node.querySelector('.chat-message-content').textContent=text;
  }
  _toolCall(id,p){
    const card=this._el('section','chat-tool-card');card.dataset.toolCallId=id||'';
    card.append(this._el('b','',p.name||'Инструмент'));
    const args=this._el('pre','',JSON.stringify(p.arguments||{},null,2));card.append(args);
    this.container.append(card);
  }
  _toolResult(id,p){
    const card=[...this.container.querySelectorAll('[data-tool-call-id]')].find(x=>x.dataset.toolCallId===id);
    if(!card)return;card.append(this._el('pre','chat-tool-result',p.result??p.message??p.error??'Готово'));
  }
  _approval(p){
    const card=this._el('section','chat-approval-card');card.dataset.approvalId=p.approval_id||'';
    card.append(this._el('p','',p.description||'Требуется подтверждение: '+(p.tool_name||'инструмент')));
    for(const [decision,label] of [['approved','Разрешить'],['rejected','Отклонить']]){
      const b=this._el('button','btn secondary',label);b.type='button';b.dataset.approvalDecision=decision;card.append(b);
    }
    this.container.append(card);
  }
  _approvalResolved(p){
    const card=[...this.container.querySelectorAll('[data-approval-id]')].find(x=>x.dataset.approvalId===p.approval_id);
    if(card){card.append(this._el('p','',p.decision==='approved'?'Разрешено':'Отклонено'));card.querySelectorAll('button').forEach(b=>b.disabled=true);}
  }
  _status(text){if(this.status)this.status.textContent=text;}
}
