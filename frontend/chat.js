(function () {
  'use strict';

  const STORAGE_KEY = 'pqlocalagentosv3.chat-workspace.v1';
  const state = { agents: [], agent: '', messages: [], sending: false, projects: [], systemProjects: [], conversations: [], chatGroups: [], activeConversationId: '', activeProjectId: '', modelAvailable: false, loadingChats: false };
  const elements = {};
  let chatSaveQueue = Promise.resolve();

  async function chatApi(path, options) {
    const settings = options || {};
    const response = await fetch('/api' + path, {
      ...settings,
      headers: { ...(settings.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...(settings.headers || {}) }
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
    modelAvatar.style.cursor = 'pointer';
    modelAvatar.title = 'Настройки агента';
    modelAvatar.addEventListener('click', () => {
      if (!state.agent) return;
      window.location.href = '/?edit_agent=' + encodeURIComponent(state.agent) + '&return_to_chat=1';
    });
    const availability = createElement('span', 'chat-model-availability is-unavailable');
    availability.id = 'chat-model-availability';availability.title = 'Доступность модели не проверена';availability.setAttribute('role','status');availability.setAttribute('aria-label','Доступность модели не проверена');
    modelInfo.append(label, modelAvatar, modelName, availability);

    const workingDir = createElement('button', 'btn secondary', 'Указать рабочую папку'); workingDir.type = 'button'; workingDir.id = 'chat-working-dir'; workingDir.title = 'Путь будет добавлен в разрешённые папки для локальных файловых инструментов';
    modelInfo.append(workingDir);
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
    const attach = createElement('button', 'btn secondary chat-attach', 'Прикрепить файл'); attach.type = 'button'; attach.id = 'chat-attach';
    const fileInput = document.createElement('input'); fileInput.type = 'file'; fileInput.id = 'chat-file-input'; fileInput.hidden = true;
    const input = document.createElement('textarea');
    input.id = 'chat-input';
    input.rows = 2;
    input.placeholder = 'Напишите сообщение…';
    input.setAttribute('aria-label', 'Сообщение');
    input.autocomplete = 'off';
    const send = createElement('button', 'btn primary', 'Отправить');
    send.type = 'submit';
    send.id = 'chat-send';
    form.append(attach, input, send, fileInput);
    composer.append(typing, form);

    root.append(toolbar, messages, composer);
    document.getElementById('content').replaceChildren(root);

    elements.root = root;
    elements.modelName = modelName; elements.availability = availability;
    elements.agent = modelSelect;
    elements.messages = messages;
    elements.form = form;
    elements.input = input;
    elements.send = send;
    elements.clear = clearButton;
    elements.typing = typing; elements.workingDir = workingDir; elements.attach = attach; elements.fileInput = fileInput;
    buildChatWorkspace();
  }

  function readWorkspace() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      state.activeConversationId = saved.activeConversationId || '';
      state.activeProjectId = saved.activeProjectId || '';
    } catch (_) {
      state.activeConversationId = '';
      state.activeProjectId = '';
    }
  }

  function saveWorkspace() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        activeConversationId: state.activeConversationId,
        activeProjectId: state.activeProjectId,
        projectExpansion: state.projects.filter(p => p.expanded).map(p => p.id),
        groupExpansion: state.chatGroups.filter(g => g.expanded).map(g => g.id)
      }));
    } catch (_) {}
  }

  function activeConversation() {
    return state.conversations.find((item) => item.id === state.activeConversationId) || null;
  }

  function normalizeChat(chat) {
    return {
      ...chat,
      id: String(chat.id || ''),
      title: chat.title || 'Новый чат',
      projectId: String(chat.project_id || chat.projectId || ''),
      groupId: String(chat.group_id || chat.groupId || ''),
      agentId: String(chat.agent_id || chat.agentId || ''),
      workingDir: String(chat.working_dir || chat.workingDir || ''),
      messages: Array.isArray(chat.messages) ? chat.messages : [],
      createdAt: chat.created_at || chat.createdAt || new Date().toISOString(),
      updatedAt: chat.updated_at || chat.updatedAt || chat.created_at || chat.createdAt || new Date().toISOString()
    };
  }

  function saveConversation(conversation) {
    if (!conversation) return Promise.resolve();
    const payload = {
      id: conversation.id, title: conversation.title || 'Новый чат',
      project_id: conversation.projectId || '', group_id: conversation.groupId || '',
      agent_id: conversation.agentId || '', working_dir: conversation.workingDir || '',
      messages: Array.isArray(conversation.messages) ? conversation.messages : [],
      created_at: conversation.createdAt || new Date().toISOString(),
      updated_at: conversation.updatedAt || new Date().toISOString()
    };
    chatSaveQueue = chatSaveQueue.catch(() => {}).then(async () => {
      try {
        const result = await chatApi('/chats', { method: 'POST', body: JSON.stringify(payload) });
        if (result.chat) Object.assign(conversation, normalizeChat(result.chat));
        rebuildProjectTree();
        return true;
      } catch (error) {
        showNotice('Не удалось сохранить историю на сервере: ' + error.message, 'warning');
        return false;
      }
    });
    return chatSaveQueue;
  }

  function persistActiveConversation() {
    const conversation = activeConversation();
    if (!conversation) return;
    conversation.messages = state.messages;
    conversation.agentId = state.agent;
    conversation.updatedAt = new Date().toISOString();
    const firstUser = state.messages.find((message) => message.role === 'user' && message.content);
    if (firstUser && (!conversation.title || conversation.title === 'Новый чат')) {
      conversation.title = firstUser.content.trim().replace(/\s+/g, ' ').split(' ').slice(0, 3).join(' ').slice(0, 48) || 'Новый чат';
    }
    saveWorkspace();
    renderChatWorkspace();
    void saveConversation(conversation);
  }

  function makeId(prefix) {
    return prefix + '-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 8);
  }

  function buildChatWorkspace() {
    const nav = document.getElementById('nav');
    if (!nav || document.getElementById('chat-workspace')) return;
    const workspace = createElement('section', 'sidebar-chat-workspace'); workspace.id = 'chat-workspace';
    const group = createElement('section', 'nav-group nav-group-fixed'); group.dataset.navGroup = 'group-0';
    const title = createElement('div', 'nav-group-label', 'РАБОЧЕЕ ПРОСТРАНСТВО');
    const items = createElement('div', 'nav-group-items');
    const dashboard = createElement('button', 'nav-item', ''); dashboard.type = 'button'; dashboard.dataset.go = 'dashboard';
    dashboard.insertAdjacentHTML('beforeend', '<span class="nav-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><rect x="3" y="3" width="8" height="8" rx="1"/><rect x="13" y="3" width="8" height="5" rx="1"/><rect x="13" y="10" width="8" height="11" rx="1"/><rect x="3" y="13" width="8" height="8" rx="1"/></svg></span>');
    dashboard.append(createElement('span', 'nav-label', 'Рабочий стол'));
    const chatLink = createElement('button', 'nav-item active', ''); chatLink.type = 'button'; chatLink.dataset.go = 'chat'; chatLink.setAttribute('aria-current', 'page');
    chatLink.insertAdjacentHTML('beforeend', '<span class="nav-icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z"/><path d="M4 5.5v15M8 7h8M8 11h8"/></svg></span>');
    chatLink.append(createElement('span', 'nav-label', 'Чат'));
    dashboard.onclick = () => { window.location.href = '/'; }; chatLink.onclick = () => { window.location.href = '/chat.html'; };
    items.append(dashboard, chatLink); group.append(title, items);

    const actions = createElement('div', 'sidebar-chat-actions');
    const newChat = createElement('button', 'btn primary', '+ Новый чат');
    const newProject = createElement('button', 'btn secondary', '+ Проект');
    const newGroup = createElement('button', 'btn secondary', '+ Папка');
    [newChat, newProject, newGroup].forEach(button => { button.type = 'button'; });
    newChat.onclick = openNewChatModal; newProject.onclick = openProjectModal; newGroup.onclick = () => { void createChatGroup(); };
    actions.append(newChat, newProject, newGroup);

    const projectsTitle = createElement('div', 'nav-group-label', 'ПРОЕКТЫ');
    const projectsList = createElement('div', 'sidebar-chat-list'); projectsList.id = 'chat-project-list';
    const groupsTitle = createElement('div', 'nav-group-label', 'ПАПКИ');
    const groupsList = createElement('div', 'sidebar-chat-list'); groupsList.id = 'chat-group-list';
    const historyToggle = createElement('button', 'btn secondary chat-history-toggle', '');
    historyToggle.type = 'button'; historyToggle.id = 'chat-history-toggle';
    historyToggle.innerHTML = '<span>ЧАТЫ БЕЗ ПРОЕКТА</span><svg class="nav-group-chevron" viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4"></path></svg>';
    const historyList = createElement('div', 'sidebar-chat-list'); historyList.id = 'chat-history-list';
    historyToggle.setAttribute('aria-expanded', 'true');
    historyToggle.onclick = () => { const open = historyToggle.getAttribute('aria-expanded') === 'true'; historyToggle.setAttribute('aria-expanded', String(!open)); historyToggle.classList.toggle('is-collapsed', open); historyList.hidden = open; };
    workspace.append(group, actions, projectsTitle, projectsList, groupsTitle, groupsList, historyToggle, historyList);
    workspace.insertAdjacentHTML('beforeend', '<div class="modal-overlay" id="chat-new-modal" hidden><div class="modal-backdrop" data-chat-new-close></div><section class="modal-card" role="dialog" aria-modal="true" aria-labelledby="chat-new-title"><div class="section-title modal-card-head"><div><h2 id="chat-new-title">Новый чат</h2><p>Выберите проект или папку. Можно оставить чат в корне.</p></div><button type="button" class="btn secondary" data-chat-new-close>Закрыть</button></div><div class="modal-card-body"><div class="field"><label for="chat-new-project">Проект</label><select id="chat-new-project"><option value="">Без проекта</option></select></div><div class="field"><label for="chat-new-group">Папка для чатов</label><select id="chat-new-group"><option value="">Без папки</option><option value="__new_group__">+ Создать папку…</option></select></div><div class="notice" id="chat-new-status" hidden></div></div><div class="modal-card-actions"><button type="button" class="btn secondary" data-chat-new-close>Отмена</button><button type="button" class="btn primary" id="chat-new-submit">Создать чат</button></div></section></div>');
    workspace.insertAdjacentHTML('beforeend', '<div class="modal-overlay" id="chat-project-modal" hidden><div class="modal-backdrop" data-chat-project-close></div><section class="modal-card" role="dialog" aria-modal="true" aria-labelledby="chat-project-title"><div class="section-title modal-card-head"><div><h2 id="chat-project-title">Создать проект</h2><p>Проект появится в дереве после добавления в него чата.</p></div><button type="button" class="btn secondary" data-chat-project-close>Закрыть</button></div><div class="modal-card-body"><div class="field"><label for="chat-project-name">Название проекта</label><input id="chat-project-name" maxlength="120" placeholder="Название проекта"></div><div class="field"><label for="chat-project-path">Рабочий путь (необязательно)</label><input id="chat-project-path" maxlength="1000" placeholder="C:\\Projects\\MyProject"></div><div class="field"><label for="chat-project-description">Описание (необязательно)</label><textarea id="chat-project-description" rows="2" maxlength="1000"></textarea></div><div class="notice" id="chat-project-status" hidden></div></div><div class="modal-card-actions"><button type="button" class="btn secondary" data-chat-project-close>Отмена</button><button type="button" class="btn primary" id="chat-project-submit">Создать проект и чат</button></div></section></div>');
    document.body.append(document.getElementById('chat-new-modal'), document.getElementById('chat-project-modal'));
    nav.replaceChildren(workspace);
    elements.workspace = workspace; elements.projectsList = projectsList; elements.groupsList = groupsList; elements.historyList = historyList;
    bindNewChatModal(); bindProjectModal();
  }

  async function openNewChatModal() {
    const modal = document.getElementById('chat-new-modal');
    const projects = document.getElementById('chat-new-project');
    const groups = document.getElementById('chat-new-group');
    const status = document.getElementById('chat-new-status');
    status.hidden = true; status.textContent = '';
    projects.replaceChildren(new Option('Без проекта', ''));
    state.systemProjects.forEach(project => projects.add(new Option(project.name || 'Без названия', project.id)));
    groups.replaceChildren(new Option('Без папки', ''), new Option('+ Создать папку…', '__new_group__'));
    state.chatGroups.forEach(group => groups.add(new Option(group.name, group.id)));
    projects.value = state.activeProjectId || '';
    modal.hidden = false;
    document.getElementById('chat-new-submit').focus();
  }

  function bindNewChatModal() {
    const modal = document.getElementById('chat-new-modal');
    modal.querySelectorAll('[data-chat-new-close]').forEach(button => button.onclick = () => { modal.hidden = true; });
    document.getElementById('chat-new-submit').onclick = async () => {
      let projectId = document.getElementById('chat-new-project').value;
      let groupId = document.getElementById('chat-new-group').value;
      const status = document.getElementById('chat-new-status');
      const submit = document.getElementById('chat-new-submit');
      status.hidden = true; submit.disabled = true;
      try {
        if (groupId === '__new_group__') {
          const name = window.prompt('Название новой папки');
          if (name === null) return;
          const result = await chatApi('/chat-groups', { method: 'POST', body: JSON.stringify({ name }) });
          if (result.group) state.chatGroups.unshift({ ...result.group, expanded: true });
          groupId = result.group?.id || '';
        }
        if (groupId) projectId = '';
        modal.hidden = true;
        await createConversation(projectId, groupId);
      } catch (error) {
        status.textContent = error.message || 'Не удалось создать чат.';
        status.hidden = false;
      } finally { submit.disabled = false; }
    };
  }

  async function openProjectModal() {
    const modal = document.getElementById('chat-project-modal');
    const status = document.getElementById('chat-project-status');
    status.hidden = true; status.textContent = '';
    modal.hidden = false;
    document.getElementById('chat-project-name').focus();
  }

  function bindProjectModal() {
    const modal = document.getElementById('chat-project-modal');
    modal.querySelectorAll('[data-chat-project-close]').forEach(button => button.onclick = () => { modal.hidden = true; });
    document.getElementById('chat-project-submit').onclick = async () => {
      const nameInput = document.getElementById('chat-project-name');
      const pathInput = document.getElementById('chat-project-path');
      const descInput = document.getElementById('chat-project-description');
      const status = document.getElementById('chat-project-status');
      const submit = document.getElementById('chat-project-submit');
      status.hidden = true; submit.disabled = true;
      try {
        const name = nameInput.value.trim();
        if (!name) throw new Error('Укажите название проекта.');
        const result = await chatApi('/projects', { method: 'POST', body: JSON.stringify({ name, path: pathInput.value.trim(), description: descInput.value.trim() }) });
        const project = result.item || result.project || result;
        if (!project.id) throw new Error('Сервер не вернул созданный проект.');
        state.systemProjects = [project, ...state.systemProjects.filter(item => item.id !== project.id)];
        modal.hidden = true; nameInput.value = ''; pathInput.value = ''; descInput.value = '';
        await createConversation(project.id, '');
      } catch (error) {
        status.textContent = error.message || 'Не удалось создать проект.';
        status.hidden = false;
      } finally { submit.disabled = false; }
    };
  }

  async function createChatGroup() {
    const name = window.prompt('Название папки для чатов');
    if (name === null) return;
    const result = await chatApi('/chat-groups', { method: 'POST', body: JSON.stringify({ name }) });
    if (result.group) state.chatGroups.unshift({ ...result.group, expanded: true });
    saveWorkspace(); renderChatWorkspace();
  }

  async function createConversation(projectId, groupId) {
    if (state.sending) return;
    const conversation = {
      id: makeId('chat'), title: 'Новый чат', projectId: projectId || '', groupId: projectId ? '' : (groupId || ''),
      agentId: state.agent, messages: [], createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(), workingDir: ''
    };
    state.conversations.unshift(conversation);
    state.activeConversationId = conversation.id; state.activeProjectId = conversation.projectId;
    state.messages = []; renderHistory(); saveWorkspace(); renderChatWorkspace();
    try { await saveConversation(conversation); } catch (_) {}
    elements.input.value = ''; resizeInput(); elements.input.focus();
  }

  async function openConversation(id) {
    if (state.sending) return;
    try {
      const result = await chatApi('/chats/' + encodeURIComponent(id), { cache: 'no-store' });
      const conversation = normalizeChat(result.chat || {});
      const index = state.conversations.findIndex(item => item.id === conversation.id);
      if (index >= 0) state.conversations[index] = conversation; else state.conversations.unshift(conversation);
      state.activeConversationId = conversation.id; state.activeProjectId = conversation.projectId;
      elements.workingDir.textContent = conversation.workingDir ? 'Рабочая папка: ' + conversation.workingDir : 'Указать рабочую папку';
      elements.workingDir.title = conversation.workingDir || 'Путь будет добавлен в разрешённые папки для локальных файловых инструментов';
      state.messages = conversation.messages.slice();
      if (conversation.agentId && state.agents.some(agent => agent.id === conversation.agentId)) {
        state.agent = conversation.agentId; elements.agent.value = state.agent;
        const selected = state.agents.find(agent => agent.id === state.agent);
        elements.modelName.textContent = selected ? selected.name : 'Агент не выбран';
        updateCurrentAgentAvatar(selected); void updateModelAvailability(selected);
      }
      renderHistory(); saveWorkspace(); renderChatWorkspace();
      elements.input.value = ''; resizeInput();
    } catch (error) { showNotice('Не удалось загрузить историю чата: ' + error.message, 'warning'); }
  }

  async function renameConversation(id) {
    const conversation = state.conversations.find(item => item.id === id); if (!conversation) return;
    const next = window.prompt('Название чата', conversation.title || 'Новый чат'); if (next === null) return;
    const title = next.trim().replace(/\s+/g, ' ').slice(0, 120);
    if (!title) { showNotice('Название чата не может быть пустым.', 'warning'); return; }
    conversation.title = title; conversation.updatedAt = new Date().toISOString();
    await saveConversation(conversation); renderChatWorkspace();
  }

  async function syncProjectChatMemory(conversation) {
    if (!conversation?.projectId) return;
    try {
      const projectChats = state.conversations.filter(item => item.projectId === conversation.projectId).sort((a, b) => (b.updatedAt || '').localeCompare(a.updatedAt || '')).slice(0, 40).map(item => ({ id: item.id, title: item.title || 'Новый чат', updated_at: item.updatedAt || '', agent_id: item.agentId || '', messages: (item.messages || []).slice(-30).map(m => ({ role: m.role, content: String(m.content || '').slice(0, 3000), time: m.time || '' })) }));
      await chatApi('/projects/' + encodeURIComponent(conversation.projectId) + '/memory', { method: 'POST', body: JSON.stringify({ chats: projectChats }) });
    } catch (_) {}
  }

  async function deleteConversation(id) {
    if (state.sending) return;
    try { await chatApi('/chats/' + encodeURIComponent(id), { method: 'DELETE' }); }
    catch (error) { showNotice('Не удалось удалить чат: ' + error.message, 'warning'); return; }
    state.conversations = state.conversations.filter(item => item.id !== id);
    if (state.activeConversationId === id) {
      state.activeConversationId = ''; state.messages = [];
      if (state.conversations.length) await openConversation(state.conversations[0].id);
      else await createConversation('', '');
    }
    saveWorkspace(); renderChatWorkspace();
  }

  function rebuildProjectTree() {
    const projectIds = new Set(state.conversations.map(chat => chat.projectId).filter(Boolean));
    const expanded = new Map(state.projects.map(project => [project.id, !!project.expanded]));
    state.projects = state.systemProjects.filter(project => projectIds.has(project.id)).map(project => ({ id: project.id, name: project.name || 'Без названия', createdAt: project.created_at || '', expanded: expanded.has(project.id) ? expanded.get(project.id) : true }));
    renderChatWorkspace();
  }

  async function loadChatWorkspaceFromServer() {
    let saved = {};
    try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); } catch (_) {}
    let [chatsResult, groupsResult, projectsResult] = await Promise.all([
      chatApi('/chats', { cache: 'no-store' }),
      chatApi('/chat-groups', { cache: 'no-store' }),
      chatApi('/projects', { cache: 'no-store' })
    ]);
    state.systemProjects = Array.isArray(projectsResult.items) ? projectsResult.items : [];
    const serverChats = Array.isArray(chatsResult.items) ? chatsResult.items : [];
    const knownIds = new Set(serverChats.map(chat => String(chat.id)));
    const legacyChats = Array.isArray(saved.conversations) ? saved.conversations : [];
    for (const legacy of legacyChats) {
      if (!legacy || !legacy.id || knownIds.has(String(legacy.id))) continue;
      const chat = normalizeChat(legacy);
      const payload = {
        id: chat.id, title: chat.title, project_id: chat.projectId, group_id: chat.groupId,
        agent_id: chat.agentId, working_dir: chat.workingDir, messages: chat.messages,
        created_at: chat.createdAt, updated_at: chat.updatedAt
      };
      await chatApi('/chats', { method: 'POST', body: JSON.stringify(payload) });
      knownIds.add(chat.id);
    }
    if (legacyChats.some(chat => chat && chat.id && !serverChats.some(item => String(item.id) === String(chat.id)))) {
      chatsResult = await chatApi('/chats', { cache: 'no-store' });
    }
    const expandedProjects = new Set(saved.projectExpansion || []);
    const expandedGroups = new Set(saved.groupExpansion || []);
    state.conversations = (Array.isArray(chatsResult.items) ? chatsResult.items : []).map(normalizeChat);
    state.chatGroups = (Array.isArray(groupsResult.items) ? groupsResult.items : []).map(group => ({ ...group, expanded: expandedGroups.size ? expandedGroups.has(group.id) : true }));
    state.projects = [];
    rebuildProjectTree();
    state.projects.forEach(project => { if (expandedProjects.size) project.expanded = expandedProjects.has(project.id); });
    if (!state.conversations.some(chat => chat.id === state.activeConversationId)) state.activeConversationId = state.conversations[0]?.id || '';
    return state.conversations;
  }

  function renderChatWorkspace() {
    if (!elements.projectsList || !elements.historyList || !elements.groupsList) return;
    rebuildProjectTreeShallow();
    elements.projectsList.replaceChildren();
    if (!state.projects.length) elements.projectsList.append(createElement('div', 'sidebar-chat-empty', 'Проекты появятся после добавления в них чата.'));
    state.projects.forEach(project => {
      const row = createElement('div', 'sidebar-chat-project-row' + (state.activeProjectId === project.id ? ' active' : ''));
      const label = createElement('button', 'sidebar-chat-project-label', '');
      label.type = 'button'; label.title = project.name; label.draggable = true;
      label.insertAdjacentHTML('beforeend', '<svg class="chat-tree-chevron" viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4"/></svg><svg class="chat-tree-folder" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7.5a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>');
      label.append(createElement('span', 'sidebar-chat-item-title', project.name));
      label.classList.toggle('is-expanded', !!project.expanded);
      label.onclick = () => { project.expanded = !project.expanded; state.activeProjectId = project.id; saveWorkspace(); renderChatWorkspace(); };
      label.ondragover = event => event.preventDefault();
      label.ondrop = event => { event.preventDefault(); void moveChat(event.dataTransfer.getData('text/plain'), project.id, ''); };
      const add = createElement('button', 'icon-btn sidebar-project-add', '+'); add.type = 'button'; add.title = 'Новый чат в проекте'; add.onclick = () => { void createConversation(project.id, ''); };
      row.append(label, add); elements.projectsList.append(row);
      if (project.expanded) {
        const nested = createElement('div', 'sidebar-chat-project-chats');
        state.conversations.filter(chat => chat.projectId === project.id).sort((a,b)=>(b.updatedAt||'').localeCompare(a.updatedAt||'')).forEach(chat => nested.append(makeConversationRow(chat)));
        if (!nested.childElementCount) nested.append(createElement('div', 'sidebar-chat-empty', 'Пока нет чатов'));
        nested.ondragover = event => event.preventDefault();
        nested.ondrop = event => { event.preventDefault(); void moveChat(event.dataTransfer.getData('text/plain'), project.id, ''); };
        elements.projectsList.append(nested);
      }
    });

    elements.groupsList.replaceChildren();
    if (!state.chatGroups.length) elements.groupsList.append(createElement('div', 'sidebar-chat-empty', 'Создайте папку, чтобы группировать чаты.'));
    state.chatGroups.forEach(group => {
      const row = createElement('div', 'sidebar-chat-project-row');
      const label = createElement('button', 'sidebar-chat-project-label', '');
      label.type = 'button'; label.title = group.name; label.classList.toggle('is-expanded', !!group.expanded);
      label.insertAdjacentHTML('beforeend', '<svg class="chat-tree-chevron" viewBox="0 0 16 16" aria-hidden="true"><path d="m4 6 4 4 4-4"/></svg><svg class="chat-tree-folder" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7.5a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>');
      label.append(createElement('span', 'sidebar-chat-item-title', group.name));
      label.onclick = () => { group.expanded = !group.expanded; saveWorkspace(); renderChatWorkspace(); };
      label.ondragover = event => event.preventDefault();
      label.ondrop = event => { event.preventDefault(); void moveChat(event.dataTransfer.getData('text/plain'), '', group.id); };
      const remove = createElement('button', 'icon-btn sidebar-project-add', '×'); remove.type = 'button'; remove.title = 'Удалить папку'; remove.onclick = async () => { if (!window.confirm('Удалить папку? Чаты останутся и переместятся в корень.')) return; try { await chatApi('/chat-groups/' + encodeURIComponent(group.id), { method: 'DELETE' }); state.chatGroups = state.chatGroups.filter(item => item.id !== group.id); state.conversations.forEach(chat => { if (chat.groupId === group.id) chat.groupId = ''; }); renderChatWorkspace(); } catch (error) { showNotice(error.message, 'warning'); } };
      row.append(label, remove); elements.groupsList.append(row);
      if (group.expanded) {
        const nested = createElement('div', 'sidebar-chat-project-chats');
        state.conversations.filter(chat => !chat.projectId && chat.groupId === group.id).sort((a,b)=>(b.updatedAt||'').localeCompare(a.updatedAt||'')).forEach(chat => nested.append(makeConversationRow(chat)));
        if (!nested.childElementCount) nested.append(createElement('div', 'sidebar-chat-empty', 'Перетащите сюда чат'));
        nested.ondragover = event => event.preventDefault();
        nested.ondrop = event => { event.preventDefault(); void moveChat(event.dataTransfer.getData('text/plain'), '', group.id); };
        elements.groupsList.append(nested);
      }
    });

    elements.historyList.replaceChildren();
    elements.historyList.ondragover = event => event.preventDefault();
    elements.historyList.ondrop = event => { event.preventDefault(); void moveChat(event.dataTransfer.getData('text/plain'), '', ''); };
    const ungrouped = state.conversations.filter(chat => !chat.projectId && !chat.groupId).sort((a,b)=>(b.updatedAt||'').localeCompare(a.updatedAt||''));
    if (!ungrouped.length) elements.historyList.append(createElement('div', 'sidebar-chat-empty', 'Новые диалоги появятся здесь.'));
    ungrouped.forEach(chat => elements.historyList.append(makeConversationRow(chat)));
  }

  function rebuildProjectTreeShallow() {
    const projectIds = new Set(state.conversations.map(chat => chat.projectId).filter(Boolean));
    const known = new Map(state.projects.map(project => [project.id, project]));
    state.projects = state.systemProjects.filter(project => projectIds.has(project.id)).map(project => ({ ...project, name: project.name || 'Без названия', expanded: known.has(project.id) ? known.get(project.id).expanded : true }));
  }

  function makeConversationRow(chat) {
    const row = createElement('div', 'sidebar-chat-item' + (chat.id === state.activeConversationId ? ' active' : ''));
    row.draggable = true; row.dataset.chatId = chat.id;
    row.ondragstart = event => { event.dataTransfer.setData('text/plain', chat.id); event.dataTransfer.effectAllowed = 'move'; };
    const label = createElement('button', 'sidebar-chat-item-label', chat.title || 'Новый чат');
    label.type = 'button'; label.title = chat.title || 'Новый чат'; label.onclick = () => { void openConversation(chat.id); };
    const actions = createElement('div', 'sidebar-chat-item-actions');
    const rename = createElement('button', 'sidebar-chat-item-action', ''); rename.type = 'button'; rename.title = 'Переименовать чат'; rename.setAttribute('aria-label', 'Переименовать чат');
    rename.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 16.5-.8 4.3 4.3-.8L19.7 7.8a2.2 2.2 0 0 0-3.1-3.1z"/><path d="m14.9 6.4 3.1 3.1"/></svg>';
    rename.onclick = () => { void renameConversation(chat.id); };
    const remove = createElement('button', 'sidebar-chat-item-action is-danger', ''); remove.type = 'button'; remove.title = 'Удалить чат'; remove.setAttribute('aria-label', 'Удалить чат');
    remove.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3m-9 0 1 13h10l1-13M10 11v5m4-5v5"/></svg>';
    remove.onclick = () => { if (window.confirm('Удалить этот чат и его историю?')) void deleteConversation(chat.id); };
    actions.append(rename, remove); row.append(label, actions); return row;
  }

  async function moveChat(chatId, projectId, groupId) {
    const chat = state.conversations.find(item => item.id === chatId); if (!chat) return;
    chat.projectId = projectId || ''; chat.groupId = projectId ? '' : (groupId || '');
    chat.updatedAt = new Date().toISOString();
    if (chat.id === state.activeConversationId) state.activeProjectId = chat.projectId;
    await saveConversation(chat); saveWorkspace(); renderChatWorkspace();
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

    const bubble = createElement('div', 'chat-msg-bubble', message.content || '');
    content.append(meta, bubble);
    if (message.attachment && typeof message.attachment === 'object') {
      const attachment = message.attachment;
      const link = createElement('a', 'chat-message-attachment', attachment.name || 'Вложение');
      link.href = attachment.url || '#'; link.target = '_blank'; link.rel = 'noopener';
      link.title = (attachment.type || 'Файл') + ' · ' + String(attachment.size || 0) + ' байт';
      bubble.append(link);
    }
    if (!isUser && Array.isArray(message.tool_calls) && message.tool_calls.length) {
      const toolsDiv = createElement('div', 'chat-tool-calls');
      message.tool_calls.forEach((tc) => {
        if (!tc || typeof tc.name !== 'string') return;
        toolsDiv.append(createElement('span', 'chat-tool-badge', '🛠 ' + tc.name + (tc.status === 'error' ? ' · ошибка' : '')));
      });
      if (toolsDiv.childElementCount) content.append(toolsDiv);
    }
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
    updateCurrentAgentAvatar(selected);void updateModelAvailability(selected);
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

  async function updateModelAvailability(agent) {
    if(!elements.availability)return;elements.availability.classList.remove('is-available','is-unavailable');elements.availability.classList.add('is-unavailable');
    if(!agent||!agent.model){elements.availability.title='У агента не назначена модель';elements.availability.setAttribute('aria-label','Модель не назначена');return}
    try{const [modelsResult,providersResult]=await Promise.all([chatApi('/models',{cache:'no-store'}),chatApi('/providers',{cache:'no-store'})]);const found=(modelsResult.models||[]).some(m=>m.name===agent.model)||(providersResult.models||[]).some(m=>m.name===agent.model&&m.connected);state.modelAvailable=!!found;elements.availability.classList.toggle('is-available',!!found);elements.availability.classList.toggle('is-unavailable',!found);elements.availability.title=found?'Модель доступна':'Модель не найдена или провайдер недоступен';elements.availability.setAttribute('aria-label',found?'Модель доступна':'Модель недоступна')}catch(_){state.modelAvailable=false;elements.availability.title='Не удалось проверить доступность модели';elements.availability.setAttribute('aria-label','Доступность модели не подтверждена')}
  }

  async function loadAgents() {
    try {
      const data = await chatApi('/agents', { method: 'GET', cache: 'no-store' });
      state.agents = Array.isArray(data.items)
        ? data.items.filter((agent) => agent && typeof agent.id === 'string' && typeof agent.name === 'string')
        : [];
      const urlParams = new URLSearchParams(window.location.search);
      const requestedAgentId = urlParams.get('agent_id');
      if (requestedAgentId && state.agents.some((agent) => agent.id === requestedAgentId)) {
        state.agent = requestedAgentId;
        if (elements.agent) elements.agent.value = requestedAgentId;
      }
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
        content: message.content || (message.attachment ? '[Вложение: ' + message.attachment.name + ']' : '')
      })).filter(message => message.content);
      await syncProjectChatMemory(activeConversation());
      const startTime = performance.now();
      const data = await chatApi('/chat', {
        method: 'POST',
        body: JSON.stringify({ agent_id: state.agent, project_id: activeConversation()?.projectId || '', conversation_id: state.activeConversationId, messages })
      });
      if (typeof data.response !== 'string') {
        throw new Error('Сервер вернул пустой или некорректный ответ модели.');
      }
      const duration = ((performance.now() - startTime) / 1000).toFixed(1);
      const assistantMessage = {
        role: 'assistant',
        content: data.response,
        tool_calls: Array.isArray(data.tool_calls) ? data.tool_calls : [],
        time: formatTime(new Date()) + ' · ⏱ ' + duration + ' сек'
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

  async function uploadChatFile(file) {
    if (!state.activeConversationId) return;
    if (file.size > 20 * 1024 * 1024) { showNotice('Максимальный размер файла — 20 МБ.', 'warning'); return; }
    const form = new FormData(); form.append('file', file, file.name);
    elements.attach.disabled = true;
    try {
      const result = await chatApi('/chats/' + encodeURIComponent(state.activeConversationId) + '/files', { method: 'POST', body: form });
      if (result.chat) {
        const saved = normalizeChat(result.chat);
        const index = state.conversations.findIndex(chat => chat.id === saved.id);
        if (index >= 0) state.conversations[index] = saved;
        state.messages = saved.messages.slice();
        renderHistory(); renderChatWorkspace(); saveWorkspace();
      }
      showNotice('Файл загружен: ' + file.name, 'info');
    } catch (error) { showNotice('Не удалось прикрепить файл: ' + error.message, 'warning'); }
    finally { elements.attach.disabled = false; }
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
      updateCurrentAgentAvatar(selected);void updateModelAvailability(selected);
      elements.send.disabled = state.sending || !state.agent; elements.input.disabled = state.sending || !state.agent; persistActiveConversation();
    });
    elements.clear.addEventListener('click', clearChat);
    elements.attach.addEventListener('click', () => { if (!state.activeConversationId) { showNotice('Сначала создайте чат.', 'warning'); return; } elements.fileInput.click(); });
    elements.fileInput.addEventListener('change', async () => {
      const file = elements.fileInput.files?.[0];
      elements.fileInput.value = '';
      if (file) await uploadChatFile(file);
    });
    elements.workingDir.addEventListener('click', async () => {
      const conversation = activeConversation(); if (!conversation) return;
      const value = window.prompt('Полный путь к рабочей папке', conversation.workingDir || '');
      if (value === null) return;
      const path = value.trim();
      if (!path) { showNotice('Укажите полный путь к рабочей папке.', 'warning'); return; }
      conversation.workingDir = path;
      try {
        const saved = await saveConversation(conversation);
        if (!saved) return;
        elements.workingDir.textContent = 'Рабочая папка: ' + path;
        elements.workingDir.title = path + ' — добавлено в разрешённые папки';
        showNotice('Рабочая папка сохранена и добавлена в разрешённые пути.', 'info');
      } catch (error) { showNotice(error.message, 'warning'); }
    });
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
    buildUI();
    bindShellEvents();
    bindEvents();
    void applySidebarWidthFromApi();
    const chatSidebarWidthMediaQuery = window.matchMedia('(max-width:720px)');
    chatSidebarWidthMediaQuery.addEventListener('change', () => { void applySidebarWidthFromApi(); });
    try {
      await loadChatWorkspaceFromServer();
    } catch (error) {
      showNotice('Не удалось загрузить серверную историю чатов: ' + error.message, 'warning');
      state.conversations = [];
    }
    const existing = state.conversations.find(item => item.id === state.activeConversationId);
    if (existing) {
      state.messages = existing.messages.slice();
      state.agent = existing.agentId || '';
      state.activeProjectId = existing.projectId || '';
      if (existing.workingDir) {
        elements.workingDir.textContent = 'Рабочая папка: ' + existing.workingDir;
        elements.workingDir.title = existing.workingDir;
      }
    }
    renderChatWorkspace();
    renderHistory();
    await loadAgents();
    if (!existing && !state.conversations.length) await createConversation('', '');
    else if (!existing && state.conversations.length) await openConversation(state.conversations[0].id);
    state.conversations.filter(chat => chat.projectId).slice(0, 10).forEach(chat => { void syncProjectChatMemory(chat); });
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