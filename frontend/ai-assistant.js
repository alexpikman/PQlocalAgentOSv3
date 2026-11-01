import { ChatTransport } from '/chat-transport.js';
import { ChatRenderer } from '/chat-renderer.js';

(() => {
  'use strict';

  const $ = (selector) => document.querySelector(selector);
  const state = {
    agents: [], agentId: '', models: [], selectedModel: '', conversationId: '',
    transport: null, renderer: null, busy: false, events: [], files: [],
    role: 'general', requestStartedAt: 0, generatedTokens: 0, lastStats: null
  };

  const roles = {
    general: { name: 'GENERALIST', label: 'Универсальный помощник', symbol: '✳', caption: 'Ассистент ожидает', detail: 'Все системы в режиме ожидания' },
    architect: { name: 'ARCHITECT', label: 'Архитектура и проектирование систем', symbol: '⌗', caption: 'Проектирует архитектуру', detail: 'Структурирование и проектирование' },
    developer: { name: 'DEVELOPER', label: 'Разработка и инженерия ПО', symbol: '⌘', caption: 'Работает с кодом', detail: 'Разработка и анализ исходников' },
    analyst: { name: 'ANALYST', label: 'Анализ и диагностика', symbol: '⌁', caption: 'Анализирует данные', detail: 'Поиск закономерностей и проблем' },
    designer: { name: 'DESIGNER', label: 'UI/UX и визуальные системы', symbol: '✧', caption: 'Проектирует интерфейс', detail: 'Визуальные решения и UX' },
    devops: { name: 'DEVOPS', label: 'Инфраструктура и эксплуатация', symbol: '⇄', caption: 'Работает с инфраструктурой', detail: 'Системы, окружения и деплой' },
    writer: { name: 'WRITER', label: 'Тексты и документация', symbol: '≡', caption: 'Работает с текстом', detail: 'Структура и редактура материалов' },
    researcher: { name: 'RESEARCHER', label: 'Исследования и поиск', symbol: '◎', caption: 'Исследует тему', detail: 'Сбор и проверка информации' }
  };

  const rolePrompt = {
    general: 'Работай как универсальный профессиональный ассистент. Выбирай подходящую дисциплину под задачу.',
    architect: 'ТВОЯ ТЕКУЩАЯ РОЛЬ: СИСТЕМНЫЙ АРХИТЕКТОР. Проектируй архитектуру, границы модулей, контракты, потоки данных, отказоустойчивость и миграции. Сначала выясняй ограничения, затем предлагай проверяемое решение. Не меняй код без понимания архитектурных последствий.',
    developer: 'ТВОЯ ТЕКУЩАЯ РОЛЬ: ВЕДУЩИЙ РАЗРАБОТЧИК. Работай инженерно: изучай существующий код, соблюдай стиль проекта, делай минимальные согласованные изменения, проверяй результат тестами. Не выдумывай API и не утверждай об успехе без проверки.',
    analyst: 'ТВОЯ ТЕКУЩАЯ РОЛЬ: СИСТЕМНЫЙ АНАЛИТИК. Разделяй факты, гипотезы и выводы. Проверяй источники данных, ищи противоречия, оценивай риски и формулируй проверяемые рекомендации.',
    designer: 'ТВОЯ ТЕКУЩАЯ РОЛЬ: UI/UX ДИЗАЙНЕР. Уделяй внимание визуальной иерархии, сетке, типографике, доступности, адаптивности и согласованности дизайн-системы. Не добавляй случайные стили и дублирующие правила.',
    devops: 'ТВОЯ ТЕКУЩАЯ РОЛЬ: DEVOPS-ИНЖЕНЕР. Учитывай безопасность, воспроизводимость, наблюдаемость, права доступа, резервирование и откат. Перед потенциально опасными операциями объясняй последствия и требуй подтверждение.',
    writer: 'ТВОЯ ТЕКУЩАЯ РОЛЬ: ТЕХНИЧЕСКИЙ РЕДАКТОР. Пиши ясно, точно и структурно, сохраняй смысл, терминологию и тон документа. Не добавляй неподтверждённые факты.',
    researcher: 'ТВОЯ ТЕКУЩАЯ РОЛЬ: ИССЛЕДОВАТЕЛЬ. Формулируй вопросы, проверяй гипотезы, отделяй первичные данные от интерпретаций, указывай ограничения и степень уверенности.'
  };

  async function api(path, options = {}) {
    const response = await fetch('/api' + path, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      cache: options.cache || 'no-store'
    });
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(data.error || data.message || 'Ошибка API: ' + response.status);
    return data;
  }

  function toast(message) {
    const node = $('#toast');
    node.textContent = message;
    node.classList.add('show');
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => node.classList.remove('show'), 3200);
  }

  function setCore(mode, title, detail) {
    const core = $('#neural-core');
    core.dataset.state = mode || 'idle';
    $('#core-state').textContent = ({ idle: 'STANDBY', thinking: 'THINKING', streaming: 'GENERATING', tool: 'TOOL ACTIVE', approval: 'APPROVAL', error: 'ERROR', success: 'COMPLETE' })[mode] || 'ACTIVE';
    $('#core-caption-title').textContent = title || 'Ассистент ожидает';
    $('#core-caption-detail').textContent = detail || '';
    $('#chat-status').dataset.state = ['thinking', 'streaming', 'tool', 'approval'].includes(mode) ? 'busy' : 'idle';
    $('#chat-status').innerHTML = '<i></i> ' + (mode === 'thinking' ? 'АНАЛИЗИРУЕТ' : mode === 'streaming' ? 'ГЕНЕРИРУЕТ ОТВЕТ' : mode === 'tool' ? 'ВЫПОЛНЯЕТ ДЕЙСТВИЕ' : mode === 'approval' ? 'ОЖИДАЕТ ПОДТВЕРЖДЕНИЯ' : mode === 'error' ? 'ОШИБКА' : mode === 'success' ? 'ЗАВЕРШЕНО' : 'ГОТОВ К РАБОТЕ');
  }

  function updateRole(role) {
    const next = roles[role] ? role : 'general';
    state.role = next;
    try { localStorage.setItem('pq-ai-assistant.role', next); } catch (_) {}
    const item = roles[next];
    $('#persona-symbol').classList.add('is-changing');
    $('#role-select').value = next;
    $('#persona-symbol').textContent = item.symbol;
    $('#persona-name').textContent = item.name;
    $('#persona-description').textContent = item.label;
    $('#core-glyph').textContent = item.symbol;
    if (!state.busy) setCore('idle', item.caption, item.detail);
    setTimeout(() => $('#persona-symbol').classList.remove('is-changing'), 380);
  }

  function escapeText(value) {
    return String(value ?? '').replace(/[&<>"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[char]);
  }

  function renderHistory(items) {
    const list = $('#history-list');
    list.replaceChildren();
    if (!items.length) {
      list.innerHTML = '<div class="history-empty">Пока нет диалогов.</div>';
      return;
    }
    items.slice(0, 40).forEach((item) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'history-item' + (item.id === state.conversationId ? ' active' : '');
      button.innerHTML = '<i>◌</i><span></span>';
      button.querySelector('span').textContent = item.title || 'Новый диалог';
      button.title = item.title || 'Новый диалог';
      button.addEventListener('click', () => openConversation(item.id));
      list.append(button);
    });
  }

  async function loadHistoryList() {
    const data = await api('/chat/conversations');
    renderHistory(data.items || []);
  }

  function eventDescription(event) {
    const payload = event.payload || {};
    const tool = String(payload.name || payload.tool_name || '');
    const args = payload.arguments || {};
    const path = args.path || args.file_path || args.cwd || args.command || '';
    const labels = {
      thinking: ['Анализ задачи', 'Ассистент изучает запрос', 'thinking'],
      assistant_delta: ['Генерация ответа', 'Поступает текст ответа', 'work'],
      assistant_message: ['Ответ сформирован', 'Сообщение добавлено в диалог', 'success'],
      user_message: ['Новое сообщение', 'Получен запрос пользователя', 'work'],
      tool_call: [tool ? 'Инструмент: ' + tool : 'Запуск инструмента', path ? String(path) : 'Вызов инструмента', 'work'],
      tool_result: ['Результат инструмента', payload.status || 'Операция завершена', payload.status === 'error' ? 'error' : 'success'],
      approval_required: ['Требуется подтверждение', payload.tool_name || 'Ожидается решение пользователя', 'work'],
      approval_resolved: ['Подтверждение обработано', payload.decision === 'approved' ? 'Разрешено' : 'Отклонено', 'success'],
      turn_completed: ['Задача завершена', payload.status || 'completed', 'success'],
      turn_cancelled: ['Выполнение остановлено', 'Задача отменена', 'error'],
      error: ['Ошибка', payload.message || 'Ошибка выполнения', 'error'],
      turn_state: [({ thinking: 'Анализ запроса', streaming: 'Генерация ответа', tool_running: 'Выполнение инструмента', waiting_approval: 'Ожидание подтверждения' })[payload.state] || 'Состояние агента', payload.state || '', 'work']
    };
    return labels[event.type] || [event.type || 'Событие', '', 'work'];
  }

  function addTimelineEvent(event) {
    const list = $('#timeline-list');
    const empty = list.querySelector('.timeline-empty');
    if (empty) empty.remove();
    const [title, detail, kind] = eventDescription(event);
    const row = document.createElement('div');
    row.className = 'timeline-item';
    row.dataset.kind = kind;
    const dot = document.createElement('span');
    dot.className = 'timeline-dot';
    const content = document.createElement('div');
    const heading = document.createElement('b');
    heading.textContent = title;
    const note = document.createElement('small');
    note.textContent = detail;
    const time = document.createElement('time');
    time.textContent = event.created_at ? new Date(event.created_at).toLocaleTimeString('ru-RU') : 'сейчас';
    content.append(heading, note, time);
    row.append(dot, content);
    list.prepend(row);
    while (list.children.length > 30) list.lastElementChild.remove();
    $('#activity-count').textContent = list.children.length + ' EVENTS';
  }

  function onEvent(event) {
    state.events.push(event);
    addTimelineEvent(event);
    state.renderer.apply(event);
    const payload = event.payload || {};
    if (event.type === 'assistant_delta' && typeof payload.text === 'string') {
      state.generatedTokens += Math.max(1, Math.ceil(payload.text.length / 4));
      const elapsed = Math.max(0.2, (performance.now() - state.requestStartedAt) / 1000);
      $('#runtime-tokens').textContent = '~' + state.generatedTokens.toLocaleString('ru-RU');
      $('#runtime-speed').textContent = '~' + (state.generatedTokens / elapsed).toFixed(1) + ' tok/s';
    }
    if (event.type === 'thinking' || (event.type === 'turn_state' && payload.state === 'thinking')) setCore('thinking', 'Анализирует задачу', 'Изучает запрос и контекст');
    else if (event.type === 'assistant_delta' || (event.type === 'turn_state' && payload.state === 'streaming')) setCore('streaming', 'Формирует ответ', 'Генерация текста моделью');
    else if (event.type === 'tool_call') {
      const name = String(payload.name || payload.tool_name || 'инструмент');
      setCore('tool', 'Выполняет действие', name);
      $('#chat-activity-label').textContent = 'Выполняет: ' + name;
      $('#chat-activity-detail').textContent = payload.arguments?.path || payload.arguments?.command || '';
      $('#chat-activity').hidden = false;
    } else if (event.type === 'approval_required') {
      setCore('approval', 'Ожидает подтверждения', payload.tool_name || 'Инструмент');
    } else if (event.type === 'error') {
      setCore('error', 'Возникла ошибка', payload.message || 'Ошибка выполнения');
    } else if (event.type === 'turn_completed' || event.type === 'turn_cancelled') {
      state.busy = false;
      $('#send-button').disabled = false;
      $('#chat-activity').hidden = true;
      const success = event.type === 'turn_completed' && ['completed', 'success'].includes(String(payload.status || 'completed'));
      setCore(success ? 'success' : 'error', success ? 'Задача завершена' : 'Выполнение остановлено', success ? 'Операции завершены' : (payload.reason || 'Проверьте журнал действий'));
      if (success) setTimeout(() => { if (!state.busy) setCore('idle', roles[state.role].caption, roles[state.role].detail); }, 2600);
      loadHistoryList().catch(() => {});
    }
  }

  async function setupConversation(id) {
    state.conversationId = id;
    state.renderer.reset();
    $('#welcome-state')?.remove();
    $('#timeline-list').replaceChildren();
    $('#activity-count').textContent = '0 EVENTS';
    $('#chat-activity').hidden = true;
    const history = await state.transport.loadHistory(0);
    (history.events || []).forEach(addTimelineEvent);
    state.renderer.applyMany(history.events || []);
    const lastSequence = (history.events || []).reduce((max, event) => Math.max(max, Number(event.sequence) || 0), 0);
    state.transport.connect({ lastSequence, epoch: history.meta?.epoch ?? null });
    state.transportConversationId = id;
    renderHistory((await api('/chat/conversations')).items || []);
  }

  async function openConversation(id) {
    try {
      if (!state.transport || state.conversationId !== id) {
        state.transport?.close();
        state.conversationId = id;
        state.transport = new ChatTransport({ conversationId: id, onEvent, onStatus: updateTransportStatus });
        await setupConversation(id);
      }
    } catch (error) { toast('Не удалось открыть диалог: ' + error.message); }
  }

  function updateTransportStatus(status) {
    if (status === 'connected') $('#connection-label').textContent = 'События чата подключены';
    else if (status === 'reconnecting') $('#connection-label').textContent = 'Переподключение…';
    else $('#connection-label').textContent = 'Ожидание событий';
  }

  async function newConversation() {
    try {
      state.transport?.close();
      const data = await api('/chat/conversations', { method: 'POST', body: JSON.stringify({ title: 'Новый диалог' }) });
      state.transport = new ChatTransport({ conversationId: data.conversation_id, onEvent, onStatus: updateTransportStatus });
      state.renderer = state.renderer || new ChatRenderer($('#chat-messages'), () => ({ agentName: 'AI Assistant · ' + roles[state.role].name, modelName: state.selectedModel || 'Ollama' }));
      state.conversationId = data.conversation_id;
      state.renderer.reset();
      const welcome = document.createElement('div');
      welcome.className = 'welcome-state';
      welcome.id = 'welcome-state';
      welcome.innerHTML = '<div class="welcome-core"><div class="core-orbit orbit-one"></div><div class="core-orbit orbit-two"></div><div class="core-orbit orbit-three"></div><div class="core-center">AI</div></div><div class="welcome-kicker">SYSTEM ONLINE · LOCAL INTELLIGENCE</div><h2>Чем займёмся?</h2><p>Опишите задачу. Я изучу контекст, предложу план и покажу каждое действие.</p>';
      $('#chat-messages').append(welcome);
      const history = await state.transport.loadHistory(0);
      state.transport.connect({ lastSequence: 0, epoch: history.meta?.epoch ?? null });
      renderHistory((await api('/chat/conversations')).items || []);
      $('#message-input').focus();
    } catch (error) { toast('Не удалось создать диалог: ' + error.message); }
  }

  async function sendMessage() {
    const input = $('#message-input');
    const text = input.value.trim();
    if ((!text && !state.files.length) || state.busy) return;
    if (!state.agentId) { toast('В системе нет агента с назначенной моделью. Сначала настройте AI-агента в PQlocalAgentOS.'); return; }
    if (!state.conversationId) await newConversation();
    if (!state.conversationId || !state.transport) return;
    let attachmentContext = '';
    if (state.files.length) {
      const chunks = [];
      let totalChars = 0;
      for (const file of state.files) {
        const content = await file.text();
        const remaining = Math.max(0, 160000 - totalChars);
        const excerpt = content.slice(0, Math.min(remaining, 50000));
        totalChars += excerpt.length;
        chunks.push('\\n\\n--- FILE: ' + file.name + ' ---\\n' + excerpt + (excerpt.length < content.length ? '\\n[Файл обрезан по лимиту размера]' : ''));
        if (totalChars >= 160000) break;
      }
      attachmentContext = '\\n\\nПРИКРЕПЛЁННЫЕ ТЕКСТОВЫЕ ФАЙЛЫ:' + chunks.join('');
    }
    const messageText = text + attachmentContext;
    const commandId = crypto.randomUUID ? crypto.randomUUID() : 'cmd-' + Date.now();
    state.files = [];
    $('#attachment-strip').replaceChildren();
    $('#attachment-strip').hidden = true;
    state.busy = true;
    state.requestStartedAt = performance.now();
    state.generatedTokens = 0;
    $('#send-button').disabled = true;
    input.value = '';
    input.style.height = 'auto';
    $('#welcome-state')?.remove();
    $('#chat-activity').hidden = false;
    $('#chat-activity-label').textContent = 'Анализирует запрос…';
    $('#chat-activity-detail').textContent = roles[state.role].name;
    setCore('thinking', 'Анализирует задачу', roles[state.role].label);
    try {
      const response = await fetch('/api/chat/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: state.conversationId,
          text: messageText,
          command_id: commandId,
          agent_id: state.agentId,
          project_id: '',
          mode: 'chat',
          persona: state.role,
          model: state.selectedModel
        })
      });
      let result = {};
      try { result = await response.json(); } catch (_) {}
      if (!response.ok) throw new Error(result.error || 'HTTP ' + response.status);
    } catch (error) {
      state.busy = false;
      $('#send-button').disabled = false;
      $('#chat-activity').hidden = true;
      state.renderer.showLocalUserMessage(text, commandId, 'error');
      setCore('error', 'Не удалось отправить запрос', error.message);
      toast(error.message);
    }
  }

  function findNumber(root, patterns, depth = 0) {
    if (!root || typeof root !== 'object' || depth > 5) return null;
    for (const [key, value] of Object.entries(root)) {
      if (patterns.some((pattern) => pattern.test(key)) && typeof value === 'number' && Number.isFinite(value)) return { value, key };
    }
    for (const value of Object.values(root)) {
      if (value && typeof value === 'object') {
        const found = findNumber(value, patterns, depth + 1);
        if (found) return found;
      }
    }
    return null;
  }

  function formatBytes(value) {
    if (!Number.isFinite(value)) return '—';
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let size = value;
    let index = 0;
    while (size >= 1024 && index < units.length - 1) { size /= 1024; index += 1; }
    return size.toFixed(index > 1 ? 1 : 0) + ' ' + units[index];
  }

  function setMetric(prefix, percent, detail, extra) {
    const safe = Number.isFinite(percent) ? Math.max(0, Math.min(100, percent)) : null;
    $('#' + prefix + '-value').textContent = safe === null ? '—' : safe.toFixed(0) + '%';
    $('#' + prefix + '-bar').style.width = (safe ?? 0) + '%';
    $('#' + prefix + '-detail').textContent = detail || 'Нет данных';
    $('#' + prefix + '-extra').textContent = extra || '';
  }

  async function updateTelemetry() {
    try {
      const data = await api('/system/stats');
      state.lastStats = data;
      const cpu = data.cpu || {};
      const ram = data.ram || {};
      const gpu = data.gpu || {};
      setMetric('cpu', cpu.percent, cpu.name || 'CPU utilization', cpu.logicalCores ? cpu.logicalCores + ' threads' : '');
      setMetric('ram', ram.percent, Number.isFinite(ram.used) && Number.isFinite(ram.total) ? ram.used.toFixed(1) + ' / ' + ram.total.toFixed(1) + ' GB' : 'ОЗУ');
      setMetric('gpu', gpu.percent, gpu.name || (gpu.pending ? 'Сбор данных GPU…' : 'GPU utilization'), Number.isFinite(gpu.temperatureC) ? gpu.temperatureC + ' °C' : '');
      setMetric('vram', Number.isFinite(gpu.vramUsed) && Number.isFinite(gpu.vramTotal) && gpu.vramTotal > 0 ? gpu.vramUsed / gpu.vramTotal * 100 : null,
        Number.isFinite(gpu.vramUsed) && Number.isFinite(gpu.vramTotal) ? gpu.vramUsed.toFixed(0) + ' / ' + gpu.vramTotal.toFixed(0) + ' MB' : 'Видеопамять');
    } catch (_) {
      $('#cpu-detail').textContent = 'Телеметрия недоступна';
      $('#ram-detail').textContent = 'Телеметрия недоступна';
      $('#gpu-detail').textContent = 'Телеметрия недоступна';
      $('#vram-detail').textContent = 'Телеметрия недоступна';
    }
  }

  async function loadResources() {
    const [agentsResult, modelsResult] = await Promise.all([
      api('/agents').catch(() => ({ items: [] })),
      api('/models').catch(() => ({ models: [], connected: false, error: 'Ollama недоступна' }))
    ]);
    state.agents = agentsResult.items || [];
    state.models = modelsResult.models || [];
    const ollamaNames = new Set(state.models.map((item) => String(item.name || '')));
    const agent = state.agents.find((item) => item && item.enabled !== false && ollamaNames.has(String(item.model || item.model_name || '')))
      || state.agents.find((item) => item && ollamaNames.has(String(item.model || item.model_name || '')));
    if (agent) {
      state.agentId = agent.id;
      state.selectedModel = String(agent.model || agent.model_name || '');
    }
    const select = $('#model-select');
    select.replaceChildren();
    if (!modelsResult.connected) {
      select.add(new Option('Ollama не подключена', ''));
      $('#ollama-state').textContent = 'OFFLINE';
      $('#ollama-state').classList.remove('is-online');
      $('#connection-label').textContent = 'Ollama не подключена';
    } else {
      $('#ollama-state').textContent = 'CONNECTED';
      $('#ollama-state').classList.add('is-online');
      $('#connection-label').textContent = 'Ollama подключена';
      if (!state.models.length) select.add(new Option('Нет загруженных моделей', ''));
      state.models.forEach((model) => select.add(new Option(model.name, model.name)));
      if (state.selectedModel && !state.models.some((item) => item.name === state.selectedModel)) select.add(new Option(state.selectedModel + ' · назначена агенту', state.selectedModel));
      let rememberedModel = '';
      try { rememberedModel = localStorage.getItem('pq-ai-assistant.model') || ''; } catch (_) {}
      select.value = rememberedModel && state.models.some((item) => item.name === rememberedModel) ? rememberedModel : (state.selectedModel || state.models[0]?.name || '');
      state.selectedModel = select.value;
    }
    $('#runtime-model').textContent = state.selectedModel || 'Не назначена';
    $('#composer-model-label').textContent = state.selectedModel ? 'Ollama · ' + state.selectedModel : 'Ollama · модель не выбрана';
    if (!agent) toast('Не найден AI-агент с назначенной моделью. Создайте или настройте одного агента в основном интерфейсе.');
    select.addEventListener('change', () => {
      state.selectedModel = select.value;
      try { localStorage.setItem('pq-ai-assistant.model', state.selectedModel); } catch (_) {}
      $('#runtime-model').textContent = state.selectedModel || 'Не назначена';
      $('#composer-model-label').textContent = state.selectedModel ? 'Ollama · ' + state.selectedModel : 'Ollama · модель не выбрана';
    });
  }

  function setupComposer() {
    const input = $('#message-input');
    input.addEventListener('input', () => {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 150) + 'px';
    });
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendMessage(); }
    });
    $('#send-button').addEventListener('click', sendMessage);
    $('#new-chat').addEventListener('click', newConversation);
    $('#refresh-history').addEventListener('click', () => loadHistoryList().catch((error) => toast(error.message)));
    $('#clear-view').addEventListener('click', () => { state.renderer.reset(); toast('Экран очищен. История диалога сохранена.'); });
    $('#role-select').addEventListener('change', (event) => updateRole(event.target.value));
    $('#open-settings').addEventListener('click', () => { window.location.href = '/?page=interface-settings'; });
    document.querySelectorAll('[data-prompt]').forEach((button) => button.addEventListener('click', () => { input.value = button.dataset.prompt; input.focus(); }));
    $('#attach-file').addEventListener('click', () => $('#file-input').click());
    const showAttachments = () => {
      const strip = $('#attachment-strip');
      strip.replaceChildren();
      state.files.forEach((file, index) => {
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.className = 'attachment-chip';
        chip.textContent = file.name + ' · ' + formatBytes(file.size) + ' ×';
        chip.title = 'Убрать вложение';
        chip.addEventListener('click', () => { state.files.splice(index, 1); showAttachments(); });
        strip.append(chip);
      });
      strip.hidden = state.files.length === 0;
    };
    const acceptFiles = (files) => {
      const allowed = [...files].filter((file) => /^(text\/|application\/(json|xml|javascript|yaml|x-yaml))/.test(file.type) || /\.(txt|md|py|js|mjs|cjs|ts|tsx|jsx|html|css|json|xml|ya?ml|toml|ini|cfg|sql|sh|bat|ps1|log|csv)$/i.test(file.name));
      const rejected = [...files].length - allowed.length;
      state.files = [...state.files, ...allowed].slice(0, 8);
      showAttachments();
      if (rejected) toast('Прикреплены только текстовые файлы. Бинарные файлы и изображения пока не поддерживаются.');
    };
    $('#file-input').addEventListener('change', (event) => {
      acceptFiles(event.target.files);
      event.target.value = '';
    });
    const composer = $('.composer');
    composer.addEventListener('dragover', (event) => { event.preventDefault(); composer.classList.add('is-dragging'); });
    composer.addEventListener('dragleave', (event) => { if (!composer.contains(event.relatedTarget)) composer.classList.remove('is-dragging'); });
    composer.addEventListener('drop', (event) => {
      event.preventDefault();
      composer.classList.remove('is-dragging');
      if (event.dataTransfer?.files?.length) acceptFiles(event.dataTransfer.files);
    });
  }

  async function init() {
    state.renderer = new ChatRenderer($('#chat-messages'), () => ({
      agentName: 'AI Assistant · ' + roles[state.role].name,
      modelName: state.selectedModel || 'Ollama'
    }));
    setupComposer();
    let savedRole = 'general';
    try { savedRole = localStorage.getItem('pq-ai-assistant.role') || 'general'; } catch (_) {}
    updateRole(savedRole);
    try {
      await loadResources();
      await loadHistoryList();
      const conversations = (await api('/chat/conversations')).items || [];
      if (conversations.length) await openConversation(conversations[0].id);
      else await newConversation();
    } catch (error) {
      toast('Ошибка инициализации: ' + error.message);
      setCore('error', 'Не удалось подключиться', error.message);
    }
    updateTelemetry();
    setInterval(updateTelemetry, 2500);
  }

  init();
})();