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
    modelInfo.append(label, modelName);

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
    elements.modelName = modelName;
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
      conversation.title = firstUser.content.trim().replace(/\\s+/g, ' ').slice(0, 48) || 'Новый чат';
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
    const actions = createElement('div', 'sidebar-chat-actions');
    const newChat = createElement('button', '', '＋ Новый чат');
    newChat.type = 'button';
    newChat.addEventListener('click', () => createConversation(state.activeProjectId));
    const newProject = createElement('button', '', '＋ Проект');
    newProject.type = 'button';
    newProject.addEventListener('click', createProject);
    actions.append(newChat, newProject);
    const projectsTitle = createElement('div', 'sidebar-chat-section-title', 'Проекты');
    const projectsList = createElement('div', 'sidebar-chat-list');
    projectsList.id = 'chat-project-list';
    const historyTitle = createElement('div', 'sidebar-chat-section-title', 'История чатов');
    const historyList = createElement('div', 'sidebar-chat-list');
    historyList.id = 'chat-history-list';
    workspace.append(actions, projectsTitle, projectsList, historyTitle, historyList);
    nav.insertAdjacentElement('afterend', workspace);
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
    elements.agent.disabled = !state.agents.length;
    elements.send.disabled = !state.agent;
    elements.input.disabled = !state.agent;
  }

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
      elements.send.disabled = state.sending || !state.agent;
      elements.input.disabled = state.sending || !state.agent;
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

  function init() {
    const content = document.getElementById('content');
    if (!content || document.getElementById('chat-root')) return;
    readWorkspace();
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

  window.ChatPage = { init };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();