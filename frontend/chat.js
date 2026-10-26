(function () {
  'use strict';

  const STORAGE_KEY = 'pqlocalagentosv3.chat-workspace.v1';
  const state = { agents: [], agent: '', messages: [], sending: false, projects: [], conversations: [], activeConversationId: '', activeProjectId: '' };
  const elements = {};

  async function chatApi(path, options) {
    const settings = options || {};
    const response = await fetch('/api' + path, {
      ...settings,
      headers: { 'Content-Type': 'application/json', ...(settings.headers || {}) }
    });
    let data;
    try { data = await response.json(); } catch (_) { data = {}; }
    if (!response.ok) throw new Error(data.error || data.message || 'Ошибка запроса к серверу.');
    return data;
  }

  function createElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function buildUI() {
    const root = createElement('section', 'panel chat-layout');
    root.id = 'chat-root';

    const toolbar = createElement('div', 'chat-toolbar');
    const modelInfo = createElement('div', 'chat-model-info');
    const label = createElement('span', 'chat-model-label', 'Текущий агент');
    const modelName = createElement('b', 'chat-model-name', 'Загрузка агентов…');
    modelName.id = 'chat-agent-name';
    const modelAvatar = createElement('div', 'chat-current-agent-avatar', 'AI');
    modelAvatar.id = 'chat-current-agent-avatar';
    modelAvatar.setAttribute('aria-hidden', 'true');
    const agentSettings = createElement('button', 'btn soft-secondary chat-agent-settings', '');
    agentSettings.type = 'button'; agentSettings.id = 'chat-agent-settings';
    agentSettings.title = 'Настройки выбранного агента'; agentSettings.setAttribute('aria-label', 'Настройки выбранного агента');
    agentSettings.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3.2"></circle><path d="M19.4 13.5a7.6 7.6 0 0 0 0-3l1.3-1-1.6-2.8-1.6.6a7.5 7.5 0 0 0-2.6-1.5L14.6 4h-3.2l-.3 1.8a7.5 7.5 0 0 0-2.6 1.5l-1.6-.6-1.6 2.8 1.3 1a7.6 7.6 0 0 0 0 3l-1.3 1 1.6 2.8 1.6-.6a7.5 7.5 0 0 0 2.6 1.5l.3 1.8h3.2l.3-1.8a7.5 7.5 0 0 0 2.6-1.5l1.6.6 1.6-2.8z"></path></svg>';
    modelInfo.append(label, modelAvatar, modelName, agentSettings);

    const controls = createElement('div', 'chat-toolbar-controls');
    const modelSelect = document.createElement('select');
    modelSelect.id = 'chat-agent';
    modelSelect.setAttribute('aria-label', 'Выбрать агента');
    const clearButton = createElement('button', 'btn secondary', 'Очистить чат');
    clearButton.type = 'button';
    clearButton.id = 'chat-clear';
    controls.append(modelSelect, clearButton);
    toolbar.append(modelInfo, controls);

    const messages = createElement('div', 'chat-messages');
    messages.id = 'chat-messages';
    messages.setAttribute('role', 'log');
    messages.setAttribute('aria-live', 'polite');
    messages.setAttribute('aria-label', 'История сообщений');

    const composer = createElement('div', 'chat-composer');
    const typing = createElement('div', 'chat-typing');
    typing.id = 'chat-typing';
    typing.hidden = true;
    typing.append(createElement('span'), createElement('span'), createElement('span'), createElement('b', '', 'Печатает…'));

    const form = document.createElement('form');
    form.id = 'chat-form';
    form.className = 'chat-input-row';
    const input = document.createElement('textarea');
    input.id = 'chat-input';
    input.rows = 2;
    input.placeholder = 'Напишите сообщение…';
    input.setAttribute('aria-label', 'Сообщение');
    input.autocomplete = 'off';
    const send = createElement('button', 'btn primary', 'Отправить');
    send.type = 'submit';
    send.id = 'chat-send';
    form.append(input, send);
    composer.append(typing, form);

    root.append(toolbar, messages, composer);
    document.getElementById('content').replaceChildren(root);

    elements.root = root;
    elements.modelName = modelName; elements.agentSettings = agentSettings;
    elements.agent = modelSelect;
    elements.messages = messages;
    elements.form = form;
    elements.input = input;
    elements.send = send;
    elements.clear = clearButton;
    elements.typing = typing;
    buildChatWorkspace();
  }

  function readWorkspace() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      state.projects = Array.isArray(saved.projects) ? saved.projects : [];
      state.conversations = Array.isArray(saved.conversations) ? saved.conversations : [];
      state.activeConversationId = saved.activeConversationId || '';
      state.activeProjectId = saved.activeProjectId || '';
    } catch (_) {
      state.projects = [];
      state.conversations = [];
    }
  }

  function saveWorkspace() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        projects: state.projects,
        conversations: state.conversations,
        activeConversationId: state.activeConversationId,
        activeProjectId: state.activeProjectId
      }));
    } catch (_) {
      showNotice('Браузер не разрешил сохранить историю чатов. Проверьте настройки хранилища сайта.', 'warning');
    }
  }

  function activeConversation() {
    return state.conversations.find((item) => item.id === state.activeConversationId) || null;
  }

  function persistActiveConversation() {
    const conversation = activeConversation();
    if (!conversation) return;
    conversation.messages = state.messages;
    conversation.agentId = state.agent;
    conversation.updatedAt = new Date().toISOString();
    const firstUser = state.messages.find((message) => message.role === 'user');
    if (firstUser && (!conversation.title || conversation.title === 'Новый чат')) {
      conversation.title = firstUser.content.trim().replace(/\s+/g, ' ').slice(0, 48) || 'Новый чат';
    }
    saveWorkspace();
    renderChatWorkspace();
  }

  function makeId(prefix) {
    return prefix + '-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8);
  }

  function buildChatWorkspace() {
    const sidebar = document.getElementById('sidebar');
    const nav = document.getElementById('nav');
    if (!sidebar || !nav || document.getElementById('chat-workspace')) return;
    const workspace = createElement('section', 'sidebar-chat-workspace');
    workspace.id = 'chat-workspace';
    const workspaceTitle = createElement('div', 'nav-group-label sidebar-chat-workspace-title', 'РАБОЧЕЕ ПРОСТРАНСТВО');
    const workspaceNav = createElement('div', 'nav-group-items sidebar-chat-nav');
    const dashboardLink = createElement('a', 'nav-item sidebar-chat-nav-item', '');
    dashboardLink.href = '/';
    dashboardLink.append(createElement('span', 'nav-icon', '▦'), createElement('span', 'nav-label', 'Рабочий стол'));
    const chatLink = createElement('a', 'nav-item sidebar-chat-nav-item active', '');
    chatLink.href = '/chat.html';
    chatLink.setAttribute('aria-current', 'page');
    chatLink.append(createElement('span', 'nav-icon', '▤'), createElement('span', 'nav-label', 'Чат'));
    workspaceNav.append(dashboardLink, chatLink);
    const actions = createElement('div', 'sidebar-chat-actions');
    const newChat = createElement('button', 'btn primary', '＋ Новый чат');
    newChat.type = 'button';
    newChat.addEventListener('click', () => createConversation(state.activeProjectId));
    const newProject = createElement('button', 'btn secondary', '＋ Проект');
    newProject.type = 'button';
    newProject.addEventListener('click', createProject);
    actions.append(newChat, newProject);
    const projectsTitle = createElement('div', 'nav-group-label', 'ПРОЕКТЫ');
    const projectsList = createElement('div', 'sidebar-chat-list');
    projectsList.id = 'chat-project-list';
    const historyTitle = createElement('div', 'nav-group-label', 'ИСТОРИЯ ЧАТОВ');
    const historyList = createElement('div', 'sidebar-chat-list');
    historyList.id = 'chat-history-list';
    workspace.append(workspaceTitle, workspaceNav, actions, projectsTitle, projectsList, historyTitle, historyList);
    nav.replaceChildren(workspace);
    elements.workspace = workspace;
    elements.projectsList = projectsList;
    elements.historyList = historyList;
  }

  function createProject() {
    const name = window.prompt('Название проекта');
    if (!name || !name.trim()) return;
    const project = { id: makeId('project'), name: name.trim().slice(0, 80), createdAt: new Date().toISOString(), expanded: true };
    state.projects.unshift(project);
    state.activeProjectId = project.id;
    saveWorkspace();
    renderChatWorkspace();
    createConversation(project.id);
  }

  function createConversation(projectId) {
    if (state.sending) return;
    const conversation = {
      id: makeId('chat'),
      title: 'Новый чат',
      projectId: projectId || '',
      agentId: state.agent,
      messages: [],
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString()
    };
    state.conversations.unshift(conversation);
    state.activeConversationId = conversation.id;
    state.activeProjectId = conversation.projectId;
    state.messages = [];
    renderHistory();
    saveWorkspace();
    renderChatWorkspace();
    elements.input.value = '';
    resizeInput();
    elements.input.focus();
  }

  function openConversation(id) {
    if (state.sending || id === state.activeConversationId) return;
    const conversation = state.conversations.find((item) => item.id === id);
    if (!conversation) return;
    state.activeConversationId = id;
    state.activeProjectId = conversation.projectId || '';
    state.messages = Array.isArray(conversation.messages) ? conversation.messages.slice() : [];
    if (conversation.agentId && state.agents.some((agent) => agent.id === conversation.agentId)) {
      state.agent = conversation.agentId;
      elements.agent.value = state.agent;
      const selected = state.agents.find((agent) => agent.id === state.agent);
      elements.modelName.textContent = selected ? selected.name : 'Агент не выбран';
    }
    renderHistory();
    saveWorkspace();
    renderChatWorkspace();
    elements.input.value = '';
    resizeInput();
  }

  function deleteConversation(id) {
    if (state.sending) return;
    state.conversations = state.conversations.filter((item) => item.id !== id);
    if (state.activeConversationId === id) {
      state.activeConversationId = '';
      state.messages = [];
      const next = state.conversations[0];
      if (next) openConversation(next.id);
      else createConversation(state.activeProjectId);
    }
    saveWorkspace();
    renderChatWorkspace();
  }

  function renderChatWorkspace() {
    if (!elements.projectsList || !elements.historyList) return;
    elements.projectsList.replaceChildren();
    if (!state.projects.length) {
      elements.projectsList.append(createElement('div', 'sidebar-chat-empty', 'Создайте проект, чтобы группировать диалоги.'));
    }
    state.projects.forEach((project) => {
      const row = createElement('div', 'sidebar-chat-item sidebar-chat-project' + (state.activeProjectId === project.id ? ' active' : ''));
      const label = createElement('button', 'sidebar-chat-item-label', (project.expanded ? '▾ ' : '▸ ') + project.name);
      label.type = 'button';
      label.addEventListener('click', () => {
        project.expanded = !project.expanded;
        state.activeProjectId = project.id;
        saveWorkspace();
        renderChatWorkspace();
      });
      const add = createElement('button', 'sidebar-chat-item-delete', '+');
      add.type = 'button';
      add.title = 'Новый чат в проекте';
      add.setAttribute('aria-label', 'Новый чат в проекте ' + project.name);
      add.addEventListener('click', () => createConversation(project.id));
      row.append(label, add);
      elements.projectsList.append(row);
      if (project.expanded) {
        const nested = createElement('div', 'sidebar-chat-project-chats');
        state.conversations.filter((chat) => chat.projectId === project.id).forEach((chat) => {
          nested.append(makeConversationRow(chat));
        });
        if (!nested.childElementCount) nested.append(createElement('div', 'sidebar-chat-empty', 'Пока нет чатов'));
        elements.projectsList.append(nested);
      }
    });

    elements.historyList.replaceChildren();
    const ungrouped = state.conversations.filter((chat) => !chat.projectId).sort((a, b) => (b.updatedAt || '').localeCompare(a.updatedAt || ''));
    if (!ungrouped.length) elements.historyList.append(createElement('div', 'sidebar-chat-empty', 'Новые диалоги появятся здесь.'));
    ungrouped.forEach((chat) => elements.historyList.append(makeConversationRow(chat)));
  }

  function makeConversationRow(chat) {
    const row = createElement('div', 'sidebar-chat-item' + (chat.id === state.activeConversationId ? ' active' : ''));
    const label = createElement('button', 'sidebar-chat-item-label', chat.title || 'Новый чат');
    label.type = 'button';
    label.title = chat.title || 'Новый чат';
    label.addEventListener('click', () => openConversation(chat.id));
    const remove = createElement('button', 'sidebar-chat-item-delete', '×');
    remove.type = 'button';
    remove.title = 'Удалить чат';
    remove.setAttribute('aria-label', 'Удалить чат ' + (chat.title || 'Новый чат'));
    remove.addEventListener('click', () => {
      if (window.confirm('Удалить этот чат и его историю?')) deleteConversation(chat.id);
    });
    row.append(label, remove);
    return row;
  }

  function clearNotice() {
    elements.messages.querySelectorAll('.notice').forEach((notice) => notice.remove());
  }

  function showNotice(message, type) {
    clearNotice();
    const notice = createElement('div', 'notice' + (type ? ' ' + type : ''), message);
    notice.setAttribute('role', 'alert');
    elements.messages.prepend(notice);
    scrollToBottom();
  }

  function formatTime(date) {
    return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  }

  function scrollToBottom() {
    elements.messages.scrollTop = elements.messages.scrollHeight;
  }

  function renderMessage(message) {
    const isUser = message.role === 'user';
    const row = createElement('article', 'chat-msg ' + (isUser ? 'user' : 'bot'));
    const avatar = createElement('div', 'chat-msg-avatar', isUser ? 'Вы' : 'AI');
    avatar.setAttribute('aria-hidden', 'true');

    const content = createElement('div', 'chat-msg-content');
    const meta = createElement('div', 'chat-msg-meta');
    meta.append(
      createElement('span', 'chat-msg-name', isUser ? 'Вы' : 'Ассистент'),
      createElement('time', 'chat-msg-time', message.time || formatTime(new Date()))
    );

    const bubble = createElement('div', 'chat-msg-bubble', message.content);
    content.append(meta, bubble);
    row.append(avatar, content);
    elements.messages.append(row);
    scrollToBottom();
  }

  function renderHistory() {
    elements.messages.replaceChildren();
    if (!state.messages.length) {
      elements.messages.append(createElement('div', 'empty chat-empty', 'Начните диалог: задайте вопрос выбранному агенту.'));
      return;
    }
    state.messages.forEach(renderMessage);
  }

  function setSending(sending) {
    state.sending = sending;
    elements.send.disabled = sending || !state.agent;
    elements.input.disabled = sending || !state.agent;
    elements.agent.disabled = sending || !state.agents.length;
    elements.clear.disabled = sending;
    elements.send.textContent = sending ? 'Ожидайте…' : 'Отправить';
    elements.typing.hidden = !sending;
    if (sending) scrollToBottom();
  }

  function renderAgents() {
    elements.agent.replaceChildren();
    state.agents.sort((a,b) => { const rank = agent => (agent.id === 'manager' || agent.name === 'Агент №1') ? 0 : 1; return rank(a) - rank(b); });
    state.agents.forEach((agent) => {
      const option = document.createElement('option');
      option.value = agent.id;
      option.textContent = agent.name + (agent.model ? ' · ' + agent.model : ' · модель по умолчанию');
      elements.agent.append(option);
    });

    if (state.agent && state.agents.some((agent) => agent.id === state.agent)) {
      elements.agent.value = state.agent;
    } else {
      const preferred = state.agents.find((agent) => agent.id === 'manager' || agent.name === 'Агент №1');
      state.agent = preferred ? preferred.id : (state.agents.length ? state.agents[0].id : '');
      elements.agent.value = state.agent;
    }

    const selected = state.agents.find((agent) => agent.id === state.agent);
    elements.modelName.textContent = selected ? selected.name : 'Агент не выбран';
    updateCurrentAgentAvatar(selected);
    elements.agent.disabled = !state.agents.length;
    elements.send.disabled = !state.agent;
    elements.input.disabled = !state.agent;
  }

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

  function updateCurrentAgentAvatar(agent) {
    const avatar = document.getElementById('chat-current-agent-avatar');
    if (!avatar) return;
    avatar.replaceChildren();
    let config = null;
    try { config = typeof agent?.avatar === 'string' ? JSON.parse(agent.avatar) : agent?.avatar; } catch (_) {}
    if (config && typeof config === 'object') {
      avatar.innerHTML = renderAvatar(config, { size: 36, live: false, blink: false });
      avatar.classList.add('has-agent-avatar');
    } else {
      avatar.classList.remove('has-agent-avatar');
      avatar.textContent = agent ? String(agent.name || 'AI').trim().slice(0, 2).toUpperCase() : 'AI';
      avatar.style.setProperty('--agent-avatar-accent', '#3b9dff');
    }
    avatar.title = agent ? agent.name : 'Агент не выбран';
  }


  window.PQOnAgentSaved = async () => {
    try {
      const data = await chatApi('/agents', { method: 'GET', cache: 'no-store' });
      state.agents = Array.isArray(data.items) ? data.items : [];
      renderAgents();
      const selected = state.agents.find(agent => agent.id === state.agent);
      if (selected) {
        elements.modelName.textContent = selected.name || 'Агент не выбран';
        updateCurrentAgentAvatar(selected);
      }
    } catch (_) {}
  };

  async function loadAgents() {
    try {
      const data = await chatApi('/agents', { method: 'GET', cache: 'no-store' });
      state.agents = Array.isArray(data.items)
        ? data.items.filter((agent) => agent && typeof agent.id === 'string' && typeof agent.name === 'string')
        : [];
      renderAgents();
      if (!state.agents.length) {
        showNotice('Нет доступных агентов. Создайте или настройте агента в разделе «AI-агенты».', 'warning');
      } else {
        clearNotice();
      }
    } catch (error) {
      state.agents = [];
      state.agent = '';
      renderAgents();
      showNotice(error.message || 'Не удалось загрузить список агентов.', 'warning');
    }
  }

  async function sendMessage() {
    const content = elements.input.value.trim();
    if (!content || state.sending || !state.agent) return;

    clearNotice();
    const userMessage = { role: 'user', content, time: formatTime(new Date()) };
    state.messages.push(userMessage);
    persistActiveConversation();
    elements.messages.querySelector('.chat-empty')?.remove();
    renderMessage(userMessage);
    elements.input.value = '';
    resizeInput();
    setSending(true);

    try {
      const messages = state.messages.map((message) => ({
        role: message.role,
        content: message.content
      }));
      const data = await chatApi('/chat', {
        method: 'POST',
        body: JSON.stringify({ agent_id: state.agent, messages })
      });
      if (typeof data.response !== 'string') {
        throw new Error('Сервер вернул пустой или некорректный ответ модели.');
      }
      const assistantMessage = {
        role: 'assistant',
        content: data.response,
        time: formatTime(new Date())
      };
      state.messages.push(assistantMessage);
      persistActiveConversation();
      renderMessage(assistantMessage);
    } catch (error) {
      showNotice(error.message || 'Не удалось получить ответ модели.', 'warning');
    } finally {
      setSending(false);
      elements.input.focus();
    }
  }

  function resizeInput() {
    elements.input.style.height = 'auto';
    elements.input.style.height = Math.min(elements.input.scrollHeight, 200) + 'px';
  }

  function clearChat() {
    if (state.sending) return;
    state.messages = [];
    persistActiveConversation();
    clearNotice();
    renderHistory();
    elements.input.value = '';
    resizeInput();
    elements.input.focus();
  }

  function bindEvents() {
    elements.form.addEventListener('submit', (event) => {
      event.preventDefault();
      sendMessage();
    });
    elements.input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
        event.preventDefault();
        sendMessage();
      }
    });
    elements.input.addEventListener('input', resizeInput);
    elements.agent.addEventListener('change', () => {
      state.agent = elements.agent.value;
      const selected = state.agents.find((agent) => agent.id === state.agent);
      elements.modelName.textContent = selected ? selected.name : 'Агент не выбран';
      updateCurrentAgentAvatar(selected);
      elements.send.disabled = state.sending || !state.agent; elements.input.disabled = state.sending || !state.agent; persistActiveConversation();
    });
    elements.agentSettings.addEventListener('click', () => {
      if (!state.agent) {
        showNotice('Сначала выберите агента.', 'warning');
        return;
      }
      if (window.PQDomainModal?.open) {
        window.PQDomainModal.open('agents', state.agent);
      } else {
        showNotice('Модалка настроек недоступна.', 'warning');
      }
    });
    elements.clear.addEventListener('click', clearChat);
  }


  function bindShellEvents() {
    const shell = document.querySelector('.app-shell');
    const left = document.getElementById('toggle-left-panel');
    const right = document.getElementById('toggle-right-panel');
    if (!shell) return;

    if (left) {
      left.addEventListener('click', () => {
        shell.classList.toggle('left-hidden');
        left.setAttribute('aria-expanded', String(!shell.classList.contains('left-hidden')));
      });
    }
    if (right) {
      right.addEventListener('click', () => {
        shell.classList.toggle('right-hidden');
        right.setAttribute('aria-expanded', String(!shell.classList.contains('right-hidden')));
      });
    }
  }

  async function applySidebarWidthFromApi() {
    let panelWidth = 322;
    try {
      const settings = await chatApi('/settings');
      const configuredWidth = Number(settings?.appearance?.sidebarWidth);
      if (Number.isFinite(configuredWidth) && configuredWidth > 0) panelWidth = Math.round(configuredWidth);
    } catch (_) {
      // Keep the shared 322px default if settings cannot be loaded.
    }
    const root = document.documentElement;
    if (window.matchMedia('(max-width:720px)').matches) {
      root.style.removeProperty('--sidebar');
      root.style.removeProperty('--right-sidebar');
      return;
    }
    root.style.setProperty('--sidebar', panelWidth + 'px');
    root.style.setProperty('--right-sidebar', panelWidth + 'px');
  }

  async function init() {
    const content = document.getElementById('content');
    if (!content || document.getElementById('chat-root')) return;
    readWorkspace();
    await applySidebarWidthFromApi();
    const chatSidebarWidthMediaQuery = window.matchMedia('(max-width:720px)');
    chatSidebarWidthMediaQuery.addEventListener('change', () => { void applySidebarWidthFromApi(); });
    buildUI();
    bindShellEvents();
    bindEvents();
    renderChatWorkspace();
    const existing = state.conversations.find((item) => item.id === state.activeConversationId);
    if (existing) {
      state.messages = Array.isArray(existing.messages) ? existing.messages.slice() : [];
      state.agent = existing.agentId || '';
    } else {
      createConversation('');
    }
    renderHistory();
    loadAgents();
  }

  if (window.PQDomainModal?.configure) {
    window.PQDomainModal.configure({
      getState: () => ({ agents: state.agents, models: state.models || { models: [] }, projects: [], tasks: [] }),
      api: chatApi,
      esc: value => String(value ?? '').replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char])),
      toast: message => showNotice(message, 'info'),
      refresh: async () => {}
    });
  }

  window.ChatPage = { init };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();