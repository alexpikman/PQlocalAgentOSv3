(function () {
  'use strict';

  const state = { agents: [], agent: '', messages: [], sending: false };
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
    buildUI();
    bindShellEvents();
    bindEvents();
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