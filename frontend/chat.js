(function () {
  'use strict';

  const state = {
    models: [],
    model: '',
    messages: [],
    sending: false
  };

  const elements = {};

  async function chatApi(path, options) {
    const settings = options || {};
    const response = await fetch('/api' + path, {
      ...settings,
      headers: {
        'Content-Type': 'application/json',
        ...(settings.headers || {})
      }
    });

    let data;
    try {
      data = await response.json();
    } catch (_) {
      data = {};
    }

    if (!response.ok) {
      throw new Error(data.error || data.message || 'Ошибка запроса к серверу.');
    }

    return data;
  }

  function createElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function showNotice(message, type) {
    clearNotice();
    const notice = createElement('div', 'notice' + (type ? ' ' + type : ''), message);
    notice.setAttribute('role', 'alert');
    elements.messages.prepend(notice);
  }

  function clearNotice() {
    elements.messages.querySelectorAll('.chat-notice').forEach((notice) => notice.remove());
    elements.messages.querySelectorAll('.notice').forEach((notice) => notice.remove());
  }

  function formatTime(date) {
    return date.toLocaleTimeString('ru-RU', {
      hour: '2-digit',
      minute: '2-digit'
    });
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
    const name = createElement('span', 'chat-msg-name', isUser ? 'Вы' : 'Ассистент');
    const time = createElement('time', 'chat-msg-time', message.time || formatTime(new Date()));
    meta.append(name, time);

    const bubble = createElement('div', 'chat-msg-bubble');
    bubble.textContent = message.content;
    content.append(meta, bubble);
    row.append(avatar, content);
    elements.messages.append(row);
    scrollToBottom();
  }

  function renderHistory() {
    elements.messages.replaceChildren();
    if (!state.messages.length) {
      const empty = createElement('div', 'empty chat-empty', 'Начните диалог: задайте вопрос локальной модели.');
      elements.messages.append(empty);
      return;
    }
    state.messages.forEach(renderMessage);
  }

  function setSending(sending) {
    state.sending = sending;
    elements.send.disabled = sending || !state.model;
    elements.input.disabled = sending || !state.model;
    elements.model.disabled = sending || !state.models.length;
    elements.clear.disabled = sending;
    elements.send.textContent = sending ? 'Ожидайте…' : 'Отправить';
    elements.typing.hidden = !sending;
    if (sending) scrollToBottom();
  }

  function renderModels() {
    elements.model.replaceChildren();
    state.models.forEach((model) => {
      const option = document.createElement('option');
      option.value = model.name;
      option.textContent = model.name;
      elements.model.append(option);
    });

    if (state.model && state.models.some((model) => model.name === state.model)) {
      elements.model.value = state.model;
    } else {
      state.model = state.models.length ? state.models[0].name : '';
      elements.model.value = state.model;
    }

    elements.modelName.textContent = state.model || 'Модель не выбрана';
    elements.model.disabled = !state.models.length;
    elements.send.disabled = !state.model;
    elements.input.disabled = !state.model;
  }

  async function loadModels() {
    try {
      const data = await chatApi('/models', { method: 'GET', cache: 'no-store' });
      state.models = Array.isArray(data.models)
        ? data.models.filter((model) => model && typeof model.name === 'string' && model.name.trim())
        : [];
      renderModels();

      if (!state.models.length) {
        showNotice('Нет доступных моделей. Подключите Ollama в разделе «Модели».', 'warning');
      } else {
        clearNotice();
      }
    } catch (error) {
      state.models = [];
      state.model = '';
      renderModels();
      showNotice(error.message || 'Не удалось загрузить список моделей.', 'warning');
    }
  }

  async function sendMessage() {
    const content = elements.input.value.trim();
    if (!content || state.sending || !state.model) return;

    clearNotice();
    const userMessage = {
      role: 'user',
      content,
      time: formatTime(new Date())
    };

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
        body: JSON.stringify({
          model: state.model,
          messages
        })
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

    elements.model.addEventListener('change', () => {
      state.model = elements.model.value;
      elements.modelName.textContent = state.model || 'Модель не выбрана';
      elements.send.disabled = state.sending || !state.model;
      elements.input.disabled = state.sending || !state.model;
    });

    elements.clear.addEventListener('click', clearChat);
  }

  function init() {
    elements.root = document.getElementById('chat-root');
    if (!elements.root || elements.root.dataset.initialized === 'true') return;
    elements.root.dataset.initialized = 'true';

    elements.modelName = document.getElementById('chat-model-name');
    elements.model = document.getElementById('chat-model');
    elements.messages = document.getElementById('chat-messages');
    elements.form = document.getElementById('chat-form');
    elements.input = document.getElementById('chat-input');
    elements.send = document.getElementById('chat-send');
    elements.clear = document.getElementById('chat-clear');
    elements.typing = document.getElementById('chat-typing');

    bindEvents();
    renderHistory();
    loadModels();
  }

  window.ChatPage = { init: init };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();