from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import urllib.parse
import json, os, re, urllib.request, urllib.error, datetime, uuid, shutil, base64, threading, hashlib, hmac, secrets
from http.cookies import SimpleCookie

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / 'frontend'
ICONS_DIR = FRONTEND / 'icons'
DATA = ROOT / 'data'
MODULES = ROOT / 'modules'
PAGES = DATA / 'pages'
PORT = int(os.environ.get('PQ_PORT', '8765'))
HOST = '127.0.0.1'
REPO = os.environ.get('GITHUB_REPOSITORY', 'alexpikman/PQlocalAgentOSv3')
for p in (FRONTEND, DATA, PAGES, MODULES, ICONS_DIR): p.mkdir(parents=True, exist_ok=True)
DEFAULT_SETTINGS = {'appearance': {'theme':'light','accent':'#3b9dff','font':'Inter, Segoe UI, sans-serif','fontSize':14,'radius':12,'sidebarWidth':248,'pagePadding':28}, 'header': {'showBreadcrumbs':True,'showTitle':True,'showDescription':True,'title':'Рабочий стол','description':'Локальная платформа управления AI-системами','font':'Inter, Segoe UI, sans-serif','color':'#f2f1ff','letterSpacing':0,'transform':'none','paddingTop':24,'paddingRight':22,'paddingBottom':24}, 'navigation': {'compact':False,'menu':None}, 'icons': {}}
DEFAULT_PAGES = [{'id':'diagnostics','title':'Диагностика','description':'Проверка API, файловой системы и локальных AI-сервисов.','icon':'activity','content':'Результаты реальных проверок локального сервера.','system':True},{'id':'models','title':'Модели','description':'Состояние Ollama, доступные модели и проверочный запрос.','icon':'server','content':'Управление доступными локальными моделями.','system':True},{'id':'agents','title':'AI-агенты','description':'Реестр агентов, роли и назначенные модели.','icon':'blocks','content':'Управление агентами платформы.','system':True},{'id':'projects','title':'Проекты','description':'Рабочие пространства и пути к проектам.','icon':'files','content':'Управление проектами.','system':True},{'id':'tasks','title':'Задачи','description':'Создание задач, запуск через локальную модель и результаты.','icon':'activity','content':'Очередь задач и история выполнения.','system':True},{'id':'dashboard','title':'Рабочий стол','description':'Обзор локальной платформы и состояния системы.','icon':'layout-dashboard','content':'Добро пожаловать в PQlocalAgentOSv3. Здесь будет собираться управление локальными AI-системами.','system':True},{'id':'chat','title':'Чат','description':'Общение с локальными моделями Ollama.','icon':'file-text','content':'Диалог с выбранной локальной моделью.','system':True},{'id':'interface-settings','title':'Настройки интерфейса','description':'Управление общим оформлением и шапкой страниц.','icon':'sliders-horizontal','content':'Настройте оформление приложения через панель настроек.','system':True},{'id':'pages','title':'Страницы','description':'Создание и управление страницами приложения.','icon':'files','content':'Создавайте страницы без ручного редактирования файлов.','system':True},{'id':'github','title':'GitHub','description':'Состояние подключения к репозиторию.','icon':'github','content':'Подключите GitHub через переменную окружения GITHUB_TOKEN.','system':True},{'id':'system-log','title':'Журнал системы','description':'История действий и проверок.','icon':'activity','content':'Журнал событий приложения.','system':True},{'id':'menu-builder','title':'Конструктор меню','description':'Структура навигации и привязка пунктов к страницам и модулям.','icon':'list-tree','content':'Настройте меню приложения.','system':True},{'id':'modules','title':'Модули','description':'Установка, каталог и связи между модулями.','icon':'blocks','content':'Управляйте модульной системой.','system':True},{'id':'permissions','title':'Разрешения','description':'Управление доступом AI-агентов к локальным папкам и GitHub.','icon':'shield-check','content':'Настройте права доступа агентов.','system':True}]
def read_json(path, fallback):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError): return fallback
def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix+'.tmp'); tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8'); tmp.replace(path)
AUTH_FILE = DATA/'auth.json'
AUTH_ENABLED = os.environ.get('PQ_AUTH_ENABLED', '0').strip().lower() in ('1', 'true', 'yes', 'on')
AUTH_ITERATIONS = 310000
AUTH_SESSIONS = {}
AUTH_SESSIONS_LOCK = threading.Lock()

def _password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, AUTH_ITERATIONS).hex()

def _ensure_auth_config():
    if AUTH_FILE.exists():
        current = read_json(AUTH_FILE, None)
        if not isinstance(current, dict) or not all(k in current for k in ('username', 'salt', 'password_hash', 'iterations')):
            raise RuntimeError('Файл data/auth.json повреждён или имеет неверный формат; восстановите его из резервной копии.')
        return
    salt = secrets.token_bytes(16)
    write_json(AUTH_FILE, {
        'username': 'root',
        'salt': salt.hex(),
        'password_hash': _password_hash('IamRootUser', salt),
        'iterations': AUTH_ITERATIONS,
        'must_change_password': True
    })

_ensure_auth_config()

def settings():
    p=DATA/'settings.json'
    if not p.exists(): write_json(p, DEFAULT_SETTINGS)
    return read_json(p, DEFAULT_SETTINGS)
def pages():
    p=PAGES/'index.json'
    current=read_json(p, DEFAULT_PAGES)
    known={item.get('id') for item in current if isinstance(item,dict)}
    changed=False
    for item in DEFAULT_PAGES:
        if item.get('system') and item.get('id') not in known:
            current.append(item.copy()); known.add(item.get('id')); changed=True
    if changed or not p.exists(): write_json(p, current)
    return current
PROVIDER_FILE = DATA/'providers.json'
CLOUD_PROVIDER_CATALOG = [
 {'id':'openai','name':'OpenAI','kind':'cloud','base_url':'https://api.openai.com/v1','format':'openai','access_format':'OpenAI-compatible REST API','builtin':True},
 {'id':'anthropic','name':'Anthropic','kind':'cloud','base_url':'https://api.anthropic.com/v1','format':'anthropic','access_format':'Anthropic Messages API','builtin':True},
 {'id':'google-gemini','name':'Google Gemini','kind':'cloud','base_url':'https://generativelanguage.googleapis.com/v1beta','format':'gemini','access_format':'Google Gemini API','builtin':True},
 {'id':'openrouter','name':'OpenRouter','kind':'cloud','base_url':'https://openrouter.ai/api/v1','format':'openai','access_format':'OpenAI-compatible API','builtin':True},
 {'id':'groq','name':'Groq','kind':'cloud','base_url':'https://api.groq.com/openai/v1','format':'openai','access_format':'OpenAI-compatible API','builtin':True}
]
def provider_items():
    defaults=[{'id':'ollama','name':'Ollama','kind':'local','base_url':OLLAMA_URL,'format':'ollama','builtin':True},{'id':'lm-studio','name':'LM Studio','kind':'local','base_url':'http://127.0.0.1:1234/v1','format':'openai','builtin':True}]
    saved=read_json(PROVIDER_FILE,[]); saved=saved if isinstance(saved,list) else []
    by_id={x.get('id'):x for x in saved if isinstance(x,dict)}
    items=[{**p,**by_id.get(p['id'],{}),'builtin':True} for p in defaults+CLOUD_PROVIDER_CATALOG]
    for p in saved:
        if isinstance(p,dict) and p.get('id') not in {x['id'] for x in items}: items.append(p)
    return items
def provider_models(p):
    base=str(p.get('base_url','')).rstrip('/'); fmt=p.get('format','openai'); headers={'User-Agent':'PQlocalAgentOSv3'}
    key=str(p.get('api_key','')).strip()
    if key: headers['Authorization']='Bearer '+key
    if fmt=='ollama':
        req=urllib.request.Request(base+'/api/tags',headers=headers)
        with urllib.request.urlopen(req,timeout=4) as r: raw=json.loads(r.read())
        return [{'name':x.get('name',''),'size':x.get('size',0),'parameter_size':(x.get('details') or {}).get('parameter_size','—')} for x in raw.get('models',[]) if x.get('name')]
    if fmt=='anthropic':
        if not key: return []
        headers.update({'x-api-key':key,'anthropic-version':'2023-06-01'})
        req=urllib.request.Request(base+'/models',headers=headers)
        with urllib.request.urlopen(req,timeout=5) as r: raw=json.loads(r.read())
        return [{'name':x.get('id','')} for x in raw.get('data',[]) if x.get('id')]
    if fmt=='gemini':
        if not key: return []
        req=urllib.request.Request(base+'/models?key='+urllib.parse.quote(key),headers=headers)
        with urllib.request.urlopen(req,timeout=5) as r: raw=json.loads(r.read())
        return [{'name':x.get('name','').removeprefix('models/')} for x in raw.get('models',[]) if x.get('name') and 'generateContent' in x.get('supportedGenerationMethods',[])]
    req=urllib.request.Request(base+'/models',headers=headers)
    with urllib.request.urlopen(req,timeout=4) as r: raw=json.loads(r.read())
    return [{'name':x.get('id','')} for x in raw.get('data',[]) if x.get('id')]
def public_provider(p):
    return {k:v for k,v in p.items() if k!='api_key'} | {'api_key_set':bool(p.get('api_key'))}
def permission_settings():
    current=read_json(DATA/'permissions.json', {'local_files':False,'roots':[]})
    if not isinstance(current,dict): current={'local_files':False,'roots':[]}
    current['local_files']=bool(current.get('local_files',False))
    current['roots']=current.get('roots',[]) if isinstance(current.get('roots',[]),list) else []
    return current
def log_event(action, detail=''):
    path=DATA/'events.json'; events=read_json(path, [])
    events.insert(0, {'time':datetime.datetime.now().astimezone().isoformat(timespec='seconds'),'action':action,'detail':str(detail)[:300]})
    write_json(path, events[:500])
OLLAMA_URL = os.environ.get('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')
DOMAIN_FILES = {'agents': DATA/'agents.json', 'projects': DATA/'projects.json', 'tasks': DATA/'tasks.json'}
AGENT_ROLES = ['MANAGER','ARCHITECT','ANALYST','DESIGNER','COPYWRITER','CODER','TESTER','DEVOPS']
AGENT_PERMISSION_KEYS = {'file_loading','file_saving','file_moving','file_deletion','directory_creation','directory_deletion','directory_moving','github_access'}
DEFAULT_AGENT_PERMISSIONS = {key:False for key in AGENT_PERMISSION_KEYS}
AGENT_ROLE_PROMPTS = {
    'MANAGER':'Ты менеджер проекта. Разбей цель на этапы, уточни критерии результата, риски и зависимости. Дай приоритетный план и явно обозначь, что не выполнено.',
    'ARCHITECT':'Ты системный архитектор. Проектируй модульную структуру, контракты, потоки данных, ограничения и точки отказа. Не выдумывай существующие API.',
    'ANALYST':'Ты аналитик. Разделяй факты, предположения и рекомендации; проверяй полноту требований и формулируй выводы структурированно.',
    'DESIGNER':'Ты продуктовый и интерфейсный дизайнер. Учитывай сценарии пользователя, доступность, адаптивность, визуальную иерархию и единообразие компонентов.',
    'COPYWRITER':'Ты редактор и технический автор. Пиши ясно, конкретно, на языке пользователя; сохраняй смысл и не выдумывай факты.',
    'CODER':'Ты инженер-программист. Предлагай проверяемые решения, учитывай ошибки, безопасность, тесты и сопровождение. Не утверждай, что код запущен, если это не так.',
    'TESTER':'Ты инженер по тестированию. Ищи граничные случаи, регрессии, ошибки обработки данных, безопасность и воспроизводимые критерии приёмки.',
    'DEVOPS':'Ты инженер инфраструктуры. Учитывай воспроизводимые сборки, конфигурацию окружения, логи, мониторинг, откат и минимальные привилегии.'
}
def domain_items(kind):
    fallback=[{'id':'manager','name':'Агент №1','role':'MANAGER','model':'','status':'idle','system':True,'description':'Координация проекта и распределение задач.'}] if kind=='agents' else []
    items = read_json(DOMAIN_FILES[kind],fallback)
    if kind == 'agents' and isinstance(items, list):
        changed = False
        for item in items:
            if isinstance(item, dict) and item.get('id') == 'manager' and item.get('name') == 'Менеджер проекта':
                item['name'] = 'Агент №1'
                changed = True
        if changed:
            write_json(DOMAIN_FILES[kind], items)
    return items
def save_domain(kind, items): write_json(DOMAIN_FILES[kind],items)
def ollama_request(path, payload=None, timeout=8):
    req=urllib.request.Request(OLLAMA_URL+path,data=json.dumps(payload).encode() if payload is not None else None,method='POST' if payload is not None else 'GET',headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=timeout) as response: return json.loads(response.read().decode('utf-8'))
def run_diagnostics():
    checks=[]
    def check(name,status,message,detail=''):
        checks.append({'name':name,'status':status,'message':message,'detail':str(detail)[:240]})
    check('HTTP API','ok','Сервер обработал диагностический запрос.','PQlocalAgentOSv3')
    check('Каталог данных','ok' if os.access(DATA,os.R_OK|os.W_OK) else 'error','Проверены права чтения и записи.',DATA)
    check('Интерпретатор Python','ok','Интерпретатор доступен.',__import__('sys').version.split()[0])
    check('Каталог модулей','ok' if MODULES.is_dir() and os.access(MODULES,os.R_OK|os.W_OK) else 'error','Проверен каталог модулей.',MODULES)
    check('Runtime-инструменты агентов','ok' if (ROOT/'agent_tools.py').is_file() else 'error','Проверен модуль разрешённых инструментов агентов.',ROOT/'agent_tools.py')
    access=permission_settings()
    check('Файловые разрешения','ok' if access.get('local_files') and access.get('roots') else 'warning','Локальные файловые инструменты включены.' if access.get('local_files') and access.get('roots') else 'Доступ к локальным файлам выключен или не заданы разрешённые папки. Это безопасное значение по умолчанию.',DATA/'permissions.json')
    check('Настройки интерфейса','ok' if (DATA/'settings.json').is_file() else 'warning','Файл настроек существует.' if (DATA/'settings.json').is_file() else 'Будет создан при первом сохранении.',DATA/'settings.json')
    check('Реестр страниц','ok' if (PAGES/'index.json').is_file() else 'warning','Файл страниц существует.' if (PAGES/'index.json').is_file() else 'Используются системные страницы по умолчанию.',PAGES/'index.json')
    check('Реестр модулей','ok' if (DATA/'modules.json').is_file() else 'warning','Файл реестра существует.' if (DATA/'modules.json').is_file() else 'Будет создан при первом изменении каталога.',DATA/'modules.json')
    check('Журнал событий','ok' if (DATA/'events.json').is_file() and os.access(DATA/'events.json',os.R_OK|os.W_OK) else 'warning','Журнал доступен.' if (DATA/'events.json').is_file() else 'Файл журнала появится после первого события.',DATA/'events.json')
    check('Реестр агентов','ok' if DOMAIN_FILES['agents'].is_file() else 'warning','Файл агентов существует.' if DOMAIN_FILES['agents'].is_file() else 'Будет создан при сохранении первого изменения.',DOMAIN_FILES['agents'])
    check('Реестр проектов','ok' if DOMAIN_FILES['projects'].is_file() else 'warning','Файл проектов существует.' if DOMAIN_FILES['projects'].is_file() else 'Проекты ещё не сохранялись.',DOMAIN_FILES['projects'])
    check('Реестр задач','ok' if DOMAIN_FILES['tasks'].is_file() else 'warning','Файл задач существует.' if DOMAIN_FILES['tasks'].is_file() else 'Задачи ещё не сохранялись.',DOMAIN_FILES['tasks'])
    schema_path=ROOT/'module-contract.schema.json'
    check('Контракт модулей','ok' if schema_path.is_file() else 'error','JSON-схема контракта доступна.' if schema_path.is_file() else 'Не найдена JSON-схема контракта.',schema_path)
    frontend_ok=all((FRONTEND/name).is_file() for name in ('index.html','app.js','style.css','components.css'))
    check('Frontend-ресурсы','ok' if frontend_ok else 'error','HTML, JavaScript и CSS доступны.' if frontend_ok else 'Не хватает одного или нескольких файлов frontend.',FRONTEND)
    try:
        models=ollama_request('/api/tags',timeout=3).get('models',[])
        check('Сервис Ollama','ok','Локальный сервис моделей отвечает.',OLLAMA_URL)
        check('Доступность моделей','ok' if models else 'warning',f'Доступно моделей: {len(models)}.' if models else 'В Ollama пока нет установленных моделей.',', '.join(x.get('name','') for x in models[:8]) or 'Нет моделей')
    except Exception as exc:
        check('Сервис Ollama','warning','Локальный сервис моделей не отвечает.',str(exc)[:180])
        check('Доступность моделей','warning','Список моделей недоступен без работающей Ollama.',OLLAMA_URL)
    lm_url=os.environ.get('LM_STUDIO_BASE_URL','http://127.0.0.1:1234/v1').rstrip('/')
    try:
        with urllib.request.urlopen(lm_url+'/models',timeout=2.5) as response:
            status=response.status
        check('Сервис LM Studio','ok' if 200<=status<300 else 'warning',f'Локальный сервис вернул HTTP {status}.',lm_url)
    except Exception as exc:
        check('Сервис LM Studio','warning','LM Studio не запущена или недоступна; это необязательный сервис.',str(exc)[:180])
    return {'checked_at':datetime.datetime.now().astimezone().isoformat(timespec='seconds'),'checks':checks,'summary':{'total':len(checks),'ok':sum(x['status']=='ok' for x in checks),'warning':sum(x['status']=='warning' for x in checks),'error':sum(x['status']=='error' for x in checks)}}

def github_request(path, method='GET', payload=None):
    token=os.environ.get('GITHUB_TOKEN')
    if not token: raise RuntimeError('Задайте GITHUB_TOKEN в окружении и перезапустите сервер.')
    raw=json.dumps(payload).encode() if payload is not None else None
    req=urllib.request.Request('https://api.github.com'+path,data=raw,method=method,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','User-Agent':'PQlocalAgentOSv3','X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json'})
    try:
        with urllib.request.urlopen(req,timeout=12) as res:
            body=res.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        message='GitHub API вернул HTTP '+str(e.code)
        try: message += ': '+json.loads(e.read()).get('message','')
        except Exception: pass
        raise RuntimeError(message)

def github_public_request(path):
    req=urllib.request.Request('https://api.github.com'+path,headers={'Accept':'application/vnd.github+json','User-Agent':'PQlocalAgentOSv3','X-GitHub-Api-Version':'2022-11-28'})
    try:
        with urllib.request.urlopen(req,timeout=10) as res:
            body=res.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        message='GitHub API вернул HTTP '+str(e.code)
        try: message += ': '+json.loads(e.read()).get('message','')
        except Exception: pass
        raise RuntimeError(message)


MODULE_RUNTIME_KINDS = {'input','template','ollama','transform','output'}
def module_runtime_manifest(module):
    manifest=module.get('manifest') if isinstance(module.get('manifest'),dict) else {}
    if not manifest and (MODULES/module.get('id','')/'module.json').is_file():
        manifest=read_json(MODULES/module['id']/'module.json',{})
    return manifest if isinstance(manifest,dict) else {}

def validate_module_connections(current, connections):
    if not isinstance(connections,list) or len(connections)>300: raise ValueError('Некорректный список связей')
    modules={m.get('id'):m for m in current.get('modules',[]) if isinstance(m,dict) and isinstance(m.get('id'),str)}
    ids=set(modules); normalized=[]; seen_edges=set(); occupied_inputs=set(); adjacency={key:[] for key in ids}
    for raw in connections:
        if not isinstance(raw,dict) or not isinstance(raw.get('from'),str) or not isinstance(raw.get('to'),str) or raw.get('from') not in ids or raw.get('to') not in ids:
            raise ValueError('Связь должна соединять зарегистрированные модули')
        link=dict(raw); source=modules[link['from']]; target=modules[link['to']]
        if link['from']==link['to']: raise ValueError('Модуль не может быть соединён сам с собой')
        source_manifest=module_runtime_manifest(source); target_manifest=module_runtime_manifest(target)
        source_ports=source_manifest.get('outputs') if isinstance(source_manifest.get('outputs'),list) else []
        target_ports=target_manifest.get('inputs') if isinstance(target_manifest.get('inputs'),list) else []
        if not source_ports: link['from_port']='output'
        elif not isinstance(link.get('from_port'),str) or not link.get('from_port'): link['from_port']=source_ports[0].get('name','output')
        if not target_ports: link['to_port']='input'
        elif not isinstance(link.get('to_port'),str) or not link.get('to_port'): link['to_port']=target_ports[0].get('name','input')
        source_port=next((p for p in source_ports if isinstance(p,dict) and p.get('name')==link['from_port']),None)
        target_port=next((p for p in target_ports if isinstance(p,dict) and p.get('name')==link['to_port']),None)
        if source_ports and not source_port: raise ValueError('Выходной порт не найден в модуле '+str(source.get('name',link['from'])))
        if target_ports and not target_port: raise ValueError('Входной порт не найден в модуле '+str(target.get('name',link['to'])))
        if source_port and target_port:
            source_type=source_port.get('type','text'); target_type=target_port.get('type','text')
            if source_type!=target_type and 'any' not in {source_type,target_type}: raise ValueError('Несовместимые типы портов: '+str(source_type)+' → '+str(target_type))
        edge=(link['from'],link['from_port'],link['to'],link['to_port'])
        if edge in seen_edges: raise ValueError('Повторяющаяся связь между портами')
        slot=(link['to'],link['to_port'])
        if slot in occupied_inputs: raise ValueError('Входной порт '+link['to_port']+' уже подключён')
        seen_edges.add(edge); occupied_inputs.add(slot); normalized.append(link); adjacency[link['from']].append(link['to'])
    visiting=set(); visited=set()
    def has_cycle(node):
        if node in visiting: return True
        if node in visited: return False
        visiting.add(node)
        for target in adjacency[node]:
            if has_cycle(target): return True
        visiting.remove(node); visited.add(node); return False
    if any(has_cycle(node) for node in ids if node not in visited): raise ValueError('Циклические связи запрещены. Постройте направленный ациклический граф.')
    return normalized

def execute_module_graph(data):
    registry=read_json(DATA/'modules.json', {'modules':[], 'connections':[]})
    modules={m.get('id'):m for m in registry.get('modules',[]) if isinstance(m,dict) and m.get('id')}
    links=registry.get('connections',[])
    links=validate_module_connections(registry,links)
    start=str(data.get('start_id','')).strip()
    if start not in modules: raise ValueError('Выберите стартовый модуль')
    outgoing={key:[] for key in modules}; incoming={key:[] for key in modules}
    for link in links:
        source=link.get('from'); target=link.get('to')
        if source in modules and target in modules:
            outgoing[source].append(target); incoming[target].append(link)
    reachable=set(); stack=[start]
    while stack:
        node=stack.pop()
        if node in reachable: continue
        reachable.add(node); stack.extend(outgoing[node])
    indegree={node:sum(1 for edge in incoming[node] if edge.get('from') in reachable) for node in reachable}
    queue=[node for node in reachable if indegree[node]==0]; order=[]
    while queue:
        node=queue.pop(0); order.append(node)
        for target in outgoing[node]:
            if target in indegree:
                indegree[target]-=1
                if indegree[target]==0: queue.append(target)
    if len(order)!=len(reachable): raise ValueError('В схеме обнаружен цикл. Удалите циклическую связь.')
    if start in incoming and any(edge.get('from') in reachable for edge in incoming[start]):
        raise ValueError('Стартовый модуль не может иметь входящих связей внутри выполняемой схемы')
    values={}; port_values={}; records=[]; prompt_input=str(data.get('input',''))[:12000]
    selected_model=str(data.get('model','')).strip()[:160]
    for module_id in order:
        module=modules[module_id]; manifest=module_runtime_manifest(module); runtime=manifest.get('runtime') if isinstance(manifest.get('runtime'),dict) else {}
        kind=str(runtime.get('kind','')).strip()
        if kind not in MODULE_RUNTIME_KINDS:
            raise ValueError('Модуль «'+str(module.get('name',module_id))+'» не имеет разрешённого встроенного типа исполнения. Внешние модули требуют отдельного адаптера.')
        edges=[edge for edge in incoming[module_id] if edge.get('from') in reachable]
        if module_id==start: incoming_value=prompt_input
        elif len(edges)==1:
            edge=edges[0]; parent=edge['from']; parent_manifest=module_runtime_manifest(modules[parent]); parent_ports=parent_manifest.get('outputs') if isinstance(parent_manifest.get('outputs'),list) else []
            source_port=str(edge.get('from_port') or (parent_ports[0].get('name') if parent_ports else 'output'))
            target_port=str(edge.get('to_port') or ((manifest.get('inputs') or [{}])[0].get('name') if manifest.get('inputs') else 'input'))
            source_value=port_values.get(parent,{}).get(source_port,values[parent])
            incoming_value=source_value if target_port=='input' and len(manifest.get('inputs') or [])<=1 else {target_port:source_value}
        else:
            incoming_value={}
            for edge in edges:
                parent=edge['from']; parent_manifest=module_runtime_manifest(modules[parent]); parent_ports=parent_manifest.get('outputs') if isinstance(parent_manifest.get('outputs'),list) else []
                source_port=str(edge.get('from_port') or (parent_ports[0].get('name') if parent_ports else 'output'))
                target_port=str(edge.get('to_port') or 'input')
                incoming_value[target_port]=port_values.get(parent,{}).get(source_port,values[parent])
        def to_text(value):
            if isinstance(value,str): return value
            return json.dumps(value,ensure_ascii=False,indent=2)
        if kind=='input': output=incoming_value if module_id!=start else prompt_input
        elif kind=='template':
            template=str(runtime.get('template','{input}'))[:12000]
            output=template.replace('{input}',to_text(incoming_value)).replace('{context}',str(data.get('context',''))[:8000]).replace('{task}',str(data.get('task',''))[:8000])
            if isinstance(incoming_value,dict):
                for port_name,port_value in incoming_value.items(): output=output.replace('{input.'+str(port_name)+'}',to_text(port_value))
        elif kind=='transform':
            operation=str(runtime.get('operation','strip'))
            value=to_text(incoming_value)
            if operation=='uppercase': output=value.upper()
            elif operation=='lowercase': output=value.lower()
            elif operation=='strip': output=value.strip()
            elif operation=='json_parse':
                try: output=json.loads(value)
                except ValueError: raise ValueError('Модуль «'+str(module.get('name',module_id))+'»: вход не является корректным JSON')
            elif operation=='json_pretty':
                try: output=json.dumps(json.loads(value),ensure_ascii=False,indent=2)
                except ValueError: raise ValueError('Модуль «'+str(module.get('name',module_id))+'»: вход не является корректным JSON')
            else: raise ValueError('Неизвестная операция преобразования: '+operation)
        elif kind=='ollama':
            model=str(runtime.get('model') or selected_model or module.get('model') or '').strip()[:160]
            if not model: raise ValueError('Для модуля «'+str(module.get('name',module_id))+'» выберите модель Ollama')
            prompt=to_text(incoming_value)
            system_prompt=str(runtime.get('system_prompt','')).strip()[:4000]
            if system_prompt: prompt='Инструкции модуля:\n'+system_prompt+'\n\nВходные данные:\n'+prompt
            result=ollama_request('/api/generate',{'model':model,'prompt':prompt,'stream':False,'options':{'num_predict':min(max(int(runtime.get('max_tokens',1024)),64),4096)}},timeout=300)
            output=result.get('response','')
        else: output=incoming_value
        values[module_id]=output
        output_ports=manifest.get('outputs') if isinstance(manifest.get('outputs'),list) else []
        if not output_ports: port_values[module_id]={'output':output}
        elif isinstance(output,dict): port_values[module_id]={str(port.get('name','output')):output.get(str(port.get('name','output')),output) for port in output_ports}
        else: port_values[module_id]={str(port.get('name','output')):output for port in output_ports}
        records.append({'module_id':module_id,'name':module.get('name',module_id),'kind':kind,'status':'completed','output':output if isinstance(output,(str,int,float,bool,type(None),dict,list)) else str(output)})
    leaves=[node for node in reachable if not any(target in reachable for target in outgoing[node])]
    outputs={node:values[node] for node in leaves}
    result={'ok':True,'start_id':start,'executed':len(records),'order':order,'steps':records,'outputs':outputs,'result':next(iter(outputs.values())) if len(outputs)==1 else outputs,'finished_at':datetime.datetime.now().astimezone().isoformat(timespec='seconds')}
    log_event('module.graph.run',str(start)+' · '+str(len(records))+' модулей')
    write_json(DATA/'module-runs.json',([result]+read_json(DATA/'module-runs.json',[]))[:100])
    return result


def run_agent_task(model, task, agent=None, project=None):
    from agent_tools import effective_tools, execute_tool
    permissions=permission_settings()
    role=(agent or {}).get('role','ANALYST')
    system_prompt=(agent or {}).get('system_prompt') or AGENT_ROLE_PROMPTS.get(role,AGENT_ROLE_PROMPTS['ANALYST'])
    if agent:
        system_prompt += '\n\nПрофиль агента: '+str(agent.get('name',''))+'\nНазначение: '+str(agent.get('description',''))[:1000]
        memory=str(agent.get('memory','')).strip()
        if memory: system_prompt += '\n\nДолговременная память агента (пользовательские заметки):\n'+memory[:8000]
    system_prompt += '\n\nТы работаешь в локальной платформе PQlocalAgentOSv3. Отвечай по-русски. Используй только инструменты, переданные в текущем запросе. Не запускай команды, PowerShell, SSH, программы или произвольный код. Не утверждай, что действие выполнено, пока инструмент не вернул успех.'
    if permissions.get('local_files') and permissions.get('roots'):
        system_prompt += '\n\nРазрешённые корневые папки для файловых инструментов:\n'+'\n'.join(str(root) for root in permissions['roots'][:50])+'\nИспользуй только эти пути. Доступ за пределами этих папок будет отклонён.'
    if (agent or {}).get('permissions',{}).get('github_access') and os.environ.get('GITHUB_TOKEN'):
        system_prompt += '\n\nДоступен только чтение настроенного репозитория GitHub: '+REPO+'.'
    prompt='Выполни задачу. Разделяй факты и предположения; сообщи о том, что не удалось проверить.\n\nНазвание задачи: '+str(task.get('title',''))+'\n\nИнструкция:\n'+str(task.get('description',''))
    if project:
        prompt += '\n\nКонтекст проекта:\nНазвание: '+str(project.get('name',''))+'\nОписание: '+str(project.get('description',''))+'\nПуть (справочная информация; не открывай автоматически): '+str(project.get('path',''))
    available=effective_tools(agent or {},permissions) if agent else []
    if not available:
        result=ollama_request('/api/generate',{'model':model,'system':system_prompt,'prompt':prompt,'stream':False,'options':{'num_predict':2048}},timeout=300)
        return {'response':result.get('response',''),'tool_calls':0,'model':result.get('model',model)}
    messages=[{'role':'system','content':system_prompt},{'role':'user','content':prompt}]
    names={tool['function']['name'] for tool in available}
    total=0; last={}
    for _ in range(12):
        try:
            payload=ollama_request('/api/chat',{'model':model,'messages':messages,'tools':available,'stream':False,'think':False,'keep_alive':'5m','options':{'num_predict':1024}},timeout=240)
        except urllib.error.HTTPError as exc:
            if total==0 and exc.code in {400,404,422}:
                result=ollama_request('/api/generate',{'model':model,'system':system_prompt,'prompt':prompt,'stream':False,'options':{'num_predict':2048}},timeout=300)
                return {'response':result.get('response',''),'tool_calls':0,'model':result.get('model',model),'warning':'Модель не поддерживает вызов инструментов; выполнен обычный запрос без инструментов.'}
            raise
        last=payload
        message=payload.get('message')
        if not isinstance(message,dict): break
        calls=message.get('tool_calls')
        if not isinstance(calls,list) or not calls:
            return {'response':message.get('content','') if isinstance(message.get('content',''),str) else '', 'tool_calls':total,'model':payload.get('model',model)}
        messages.append(message)
        for call in calls:
            total+=1
            if total>24:
                messages.append({'role':'tool','content':'Остановлено: достигнут лимит 24 вызова инструмента.'})
                break
            function=call.get('function',{}) if isinstance(call,dict) else {}
            name=function.get('name') if isinstance(function,dict) else None
            args=function.get('arguments',{}) if isinstance(function,dict) else {}
            if isinstance(args,str):
                try: args=json.loads(args)
                except ValueError: args={}
            if not isinstance(args,dict) or not isinstance(name,str) or name not in names:
                result={'error':'Некорректный или недоступный инструмент.'}; name=str(name or 'unknown')
            else:
                result=execute_tool(name,args,agent,permissions)
            log_event('agent.tool_called',str((agent or {}).get('id',''))+' · '+name+' · '+('error' if 'error' in result else 'ok'))
            messages.append({'role':'tool','tool_name':name,'content':json.dumps(result,ensure_ascii=False)[:12000]})
        if total>24: break
    message=last.get('message',{}) if isinstance(last,dict) else {}
    return {'response':message.get('content','') if isinstance(message,dict) and isinstance(message.get('content',''),str) else '', 'tool_calls':total,'model':last.get('model',model) if isinstance(last,dict) else model,'warning':'Достигнут лимит циклов вызова инструментов.'}


def run_agent_team(model, task, agent=None, project=None):
    """Run a bounded manager -> specialist -> reviewer workflow."""
    base_description=str(task.get('description',''))
    manager_agent={'id':None,'name':'Менеджер команды','role':'MANAGER','system_prompt':AGENT_ROLE_PROMPTS['MANAGER'],'permissions':{}}
    manager_task={'title':str(task.get('title',''))+' — планирование','description':base_description+'\n\nСоставь краткий план выполнения, критерии готовности и риски. Не выполняй саму работу.'}
    manager=run_agent_task(model,manager_task,manager_agent,project)
    specialist=agent or {'id':None,'name':'Специалист','role':'ANALYST','system_prompt':AGENT_ROLE_PROMPTS['ANALYST'],'permissions':{}}
    specialist_task={'title':str(task.get('title',''))+' — выполнение','description':base_description+'\n\nПлан менеджера:\n'+str(manager.get('response',''))+'\n\nВыполни задачу по плану. Если план содержит ошибочные предположения, исправь их.'}
    specialist_model=str((agent or {}).get('model') or model)
    specialist_result=run_agent_task(specialist_model,specialist_task,specialist,project)
    reviewer={'id':None,'name':'Контролёр качества','role':'TESTER','system_prompt':AGENT_ROLE_PROMPTS['TESTER'],'permissions':{}}
    review_task={'title':str(task.get('title',''))+' — проверка результата','description':'Исходная задача:\n'+base_description+'\n\nПлан менеджера:\n'+str(manager.get('response',''))+'\n\nРезультат специалиста:\n'+str(specialist_result.get('response',''))+'\n\nПроверь соответствие исходной задаче, найди неподтверждённые утверждения и недостающие части. Верни итоговый результат и явно перечисли ограничения. Не утверждай, что запускал проверки, если этого не делал.'}
    review=run_agent_task(model,review_task,reviewer,project)
    stages=[
        {'role':'MANAGER','name':'Менеджер','model':manager.get('model',model),'response':manager.get('response',''),'tool_calls':manager.get('tool_calls',0),'warning':manager.get('warning','')},
        {'role':specialist.get('role','ANALYST'),'name':specialist.get('name','Специалист'),'model':specialist_result.get('model',specialist_model),'response':specialist_result.get('response',''),'tool_calls':specialist_result.get('tool_calls',0),'warning':specialist_result.get('warning','')},
        {'role':'TESTER','name':'Контроль качества','model':review.get('model',model),'response':review.get('response',''),'tool_calls':review.get('tool_calls',0),'warning':review.get('warning','')}
    ]
    return {'response':review.get('response',''),'team_result':stages,'tool_calls':sum(int(x.get('tool_calls',0) or 0) for x in stages),'model':model}


def _filetime_value(value):
    return (value.dwHighDateTime << 32) | value.dwLowDateTime

def _windows_cpu_times():
    import ctypes
    from ctypes import wintypes
    idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
    if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
        raise OSError('GetSystemTimes failed')
    return (_filetime_value(idle), _filetime_value(kernel), _filetime_value(user))

def _cpu_usage():
    try:
        before = _windows_cpu_times()
        import time
        time.sleep(0.12)
        after = _windows_cpu_times()
        idle = after[0] - before[0]
        total = (after[1] - before[1]) + (after[2] - before[2])
        return round(max(0.0, min(100.0, (1 - idle / total) * 100)), 1) if total > 0 else None
    except Exception:
        try:
            import psutil
            return round(psutil.cpu_percent(interval=0.12), 1)
        except Exception:
            return None

def _memory_stats():
    try:
        import ctypes
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong),
                        ('ullTotalPhys', ctypes.c_ulonglong), ('ullAvailPhys', ctypes.c_ulonglong),
                        ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                        ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong),
                        ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
        status = MEMORYSTATUSEX()
        status.dwLength = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)) and status.ullTotalPhys:
            total = status.ullTotalPhys / (1024 ** 3)
            available = status.ullAvailPhys / (1024 ** 3)
            page_total = status.ullTotalPageFile / (1024 ** 3)
            page_available = status.ullAvailPageFile / (1024 ** 3)
            return {'available': True, 'percent': round((total - available) / total * 100, 1),
                    'used': round(total - available, 2), 'total': round(total, 2),
                    'free': round(available, 2), 'pagefile': {
                        'total': round(page_total, 2), 'available': round(page_available, 2),
                        'used': round(max(0, page_total - page_available), 2)}}
    except Exception:
        pass
    try:
        import psutil
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {'available': True, 'percent': mem.percent, 'used': round(mem.used / (1024 ** 3), 2),
                'total': round(mem.total / (1024 ** 3), 2), 'free': round(mem.available / (1024 ** 3), 2),
                'pagefile': {'total': round(swap.total / (1024 ** 3), 2),
                             'available': round((swap.total - swap.used) / (1024 ** 3), 2),
                             'used': round(swap.used / (1024 ** 3), 2)}}
    except Exception:
        return {'available': False, 'percent': None, 'used': None, 'total': None, 'free': None, 'pagefile': None}

def _cpu_name():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
            return str(winreg.QueryValueEx(key, 'ProcessorNameString')[0]).strip()
    except Exception:
        try:
            import platform
            return platform.processor() or None
        except Exception:
            return None

def _gpu_stats():
    import subprocess
    from pathlib import Path
    candidates = ['nvidia-smi']
    program_files = os.environ.get('ProgramFiles', r'C:\Program Files')
    candidates.append(str(Path(program_files) / 'NVIDIA Corporation' / 'NVSMI' / 'nvidia-smi.exe'))
    fields = ['name', 'utilization.gpu', 'memory.used', 'memory.total', 'temperature.gpu',
              'power.draw', 'power.limit', 'clocks.gr', 'clocks.mem', 'fan.speed']
    query = ','.join(fields)
    for command in candidates:
        try:
            result = subprocess.run([command, '--query-gpu=' + query, '--format=csv,noheader,nounits'],
                                    capture_output=True, text=True, timeout=3, check=True,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            line = next((line.strip() for line in result.stdout.splitlines() if line.strip()), '')
            parts = [part.strip() for part in line.split(',')]
            if len(parts) < len(fields):
                raise ValueError('Incomplete nvidia-smi output')
            def number(index):
                try:
                    value = parts[index].strip()
                    return None if not value or value.lower() in ('[n/a]', 'n/a', 'not supported') else float(value)
                except (ValueError, IndexError):
                    return None
            used_mb, total_mb = number(2), number(3)
            return {'available': True, 'name': parts[0] or None, 'percent': number(1),
                    'vramUsed': round(used_mb / 1024, 2) if used_mb is not None else None,
                    'vramTotal': round(total_mb / 1024, 2) if total_mb is not None else None,
                    'temperatureC': number(4), 'powerW': number(5), 'powerLimitW': number(6),
                    'coreClockMHz': number(7), 'memoryClockMHz': number(8), 'fanPercent': number(9),
                    'raw': {'memoryUsedMiB': used_mb, 'memoryTotalMiB': total_mb}}
        except Exception:
            # Driver versions may not expose every optional field; retry the stable base query.
            try:
                result = subprocess.run([command, '--query-gpu=name,utilization.gpu,memory.used,memory.total',
                                         '--format=csv,noheader,nounits'], capture_output=True, text=True,
                                        timeout=2, check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                parts = [part.strip() for part in next((x.strip() for x in result.stdout.splitlines() if x.strip()), '').split(',')]
                if len(parts) >= 4:
                    return {'available': True, 'name': ','.join(parts[:-3]).strip() or None,
                            'percent': float(parts[-3]), 'vramUsed': round(float(parts[-2]) / 1024, 2),
                            'vramTotal': round(float(parts[-1]) / 1024, 2), 'temperatureC': None,
                            'powerW': None, 'powerLimitW': None, 'coreClockMHz': None,
                            'memoryClockMHz': None, 'fanPercent': None}
            except Exception:
                continue
    return {'available': False, 'name': None, 'percent': None, 'vramUsed': None, 'vramTotal': None,
            'temperatureC': None, 'powerW': None, 'powerLimitW': None, 'coreClockMHz': None,
            'memoryClockMHz': None, 'fanPercent': None}

def _disk_stats():
    disks = []
    try:
        import ctypes
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        for index in range(26):
            if not (mask & (1 << index)):
                continue
            mount = chr(65 + index) + ':\\'
            try:
                drive_type = ctypes.windll.kernel32.GetDriveTypeW(mount)
                if drive_type not in (2, 3, 6):
                    continue
                usage = shutil.disk_usage(mount)
                total = usage.total / (1024 ** 3)
                used = (usage.total - usage.free) / (1024 ** 3)
                if total <= 0:
                    continue
                label_buffer = ctypes.create_unicode_buffer(261)
                fs_buffer = ctypes.create_unicode_buffer(261)
                try:
                    ctypes.windll.kernel32.GetVolumeInformationW(mount, label_buffer, len(label_buffer), None, None, None, fs_buffer, len(fs_buffer))
                    label, filesystem = label_buffer.value or None, fs_buffer.value or None
                except Exception:
                    label, filesystem = None, None
                disks.append({'mount': mount, 'available': True, 'driveType': drive_type,
                              'label': label, 'filesystem': filesystem, 'percent': round(used / total * 100, 1),
                              'used': round(used, 2), 'free': round(usage.free / (1024 ** 3), 2),
                              'total': round(total, 2), 'totalBytes': usage.total, 'freeBytes': usage.free})
            except (OSError, PermissionError):
                continue
    except Exception:
        try:
            usage = shutil.disk_usage(str(ROOT))
            total = usage.total / (1024 ** 3)
            used = (usage.total - usage.free) / (1024 ** 3)
            if total:
                disks.append({'mount': str(ROOT.anchor or ROOT), 'available': True,
                              'percent': round(used / total * 100, 1), 'used': round(used, 2),
                              'free': round(usage.free / (1024 ** 3), 2), 'total': round(total, 2),
                              'totalBytes': usage.total, 'freeBytes': usage.free})
        except Exception:
            pass
    return disks

def _network_stats():
    try:
        import psutil
        counters = psutil.net_io_counters(pernic=True)
        addresses = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        adapters = []
        for name, counter in counters.items():
            status = stats.get(name)
            addr_items = addresses.get(name, [])
            adapters.append({
                'name': name, 'isUp': bool(status.isup) if status else None,
                'speedMbps': status.speed if status else None,
                'mtu': status.mtu if status else None,
                'bytesSent': counter.bytes_sent, 'bytesReceived': counter.bytes_recv,
                'packetsSent': counter.packets_sent, 'packetsReceived': counter.packets_recv,
                'errorsIn': counter.errin, 'errorsOut': counter.errout,
                'dropsIn': counter.dropin, 'dropsOut': counter.dropout,
                'addresses': [{'family': str(a.family), 'address': a.address, 'netmask': a.netmask}
                              for a in addr_items if a.address and not a.address.startswith('fe80::')]
            })
        totals = psutil.net_io_counters()
        return {'available': True, 'bytesSent': totals.bytes_sent, 'bytesReceived': totals.bytes_recv,
                'packetsSent': totals.packets_sent, 'packetsReceived': totals.packets_recv, 'adapters': adapters,
                'note': 'Network counters are cumulative since system start or adapter reset.'}
    except Exception as exc:
        return {'available': False, 'bytesSent': None, 'bytesReceived': None, 'adapters': [],
                'reason': 'Install psutil to expose per-adapter counters.'}

def _process_stats():
    try:
        import psutil
        processes=[]
        for proc in psutil.process_iter(['pid','ppid','name','exe','username','status','memory_info','memory_full_info','cpu_percent','create_time','num_threads','nice','io_counters']):
            try:
                info=proc.info; mem=info.get('memory_info'); full=info.get('memory_full_info'); io=info.get('io_counters')
                started=info.get('create_time')
                processes.append({'pid':info.get('pid'),'parentPid':info.get('ppid'),'name':info.get('name'),'path':info.get('exe'),'user':info.get('username'),'status':info.get('status'),'memoryBytes':getattr(mem,'rss',None),'virtualMemoryBytes':getattr(mem,'vms',None),'privateMemoryBytes':getattr(full,'private',None),'peakWorkingSetBytes':getattr(full,'peak_wset',None),'cpuPercent':info.get('cpu_percent'),'startedAt':datetime.datetime.fromtimestamp(started).astimezone().isoformat(timespec='seconds') if started else None,'threads':info.get('num_threads'),'priority':info.get('nice'),'diskReadBytes':getattr(io,'read_bytes',None),'diskWriteBytes':getattr(io,'write_bytes',None),'diskReadOps':getattr(io,'read_count',None),'diskWriteOps':getattr(io,'write_count',None),'diskReadBytesPerSec':_rate_snapshot('proc-read-'+str(info.get('pid')),getattr(io,'read_bytes',0)) if io else None,'diskWriteBytesPerSec':_rate_snapshot('proc-write-'+str(info.get('pid')),getattr(io,'write_bytes',0)) if io else None,'gpuPercent':None,'gpuMemoryBytes':None,'exitCode':None})
            except (OSError,PermissionError,psutil.Error):
                continue
        by_memory=sorted(processes,key=lambda p:p.get('memoryBytes') or 0,reverse=True)
        by_cpu=sorted(processes,key=lambda p:p.get('cpuPercent') or 0,reverse=True)
        by_read=sorted(processes,key=lambda p:p.get('diskReadBytesPerSec') or 0,reverse=True)
        by_write=sorted(processes,key=lambda p:p.get('diskWriteBytesPerSec') or 0,reverse=True)
        return {'available':True,'count':len(processes),'items':processes,'topMemory':by_memory[:30],'topCpu':by_cpu[:30],'topDiskRead':by_read[:20],'topDiskWrite':by_write[:20],
                'note':'Per-process network and GPU counters are driver/ETW dependent and are null unless a supported collector is installed.'}
    except Exception as exc:
        return {'available':False,'count':None,'items':[],'topMemory':[],'topCpu':[],'topDiskRead':[],'topDiskWrite':[],'reason':'Detailed process metrics unavailable: '+str(exc)[:160]}

def _battery_stats():
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery is None:
            return {'available': False, 'present': False, 'percent': None, 'plugged': None, 'secondsLeft': None}
        return {'available': True, 'present': True, 'percent': battery.percent, 'plugged': battery.power_plugged,
                'secondsLeft': battery.secsleft if battery.secsleft >= 0 else None}
    except Exception:
        return {'available': False, 'present': None, 'percent': None, 'plugged': None, 'secondsLeft': None}

def _local_services():
    import urllib.request
    services = [
        {'id': 'ollama', 'name': 'Ollama', 'base': 'http://127.0.0.1:11434'},
        {'id': 'lm-studio', 'name': 'LM Studio', 'base': 'http://127.0.0.1:1234'}
    ]
    result = []
    for service in services:
        item = {'id': service['id'], 'name': service['name'], 'available': False, 'baseUrl': service['base'],
                'models': None, 'modelCount': None}
        endpoints = ['/api/tags'] if service['id'] == 'ollama' else ['/v1/models']
        for endpoint in endpoints:
            try:
                request = urllib.request.Request(service['base'] + endpoint, headers={'Accept': 'application/json'})
                with urllib.request.urlopen(request, timeout=0.65) as response:
                    payload = json.loads(response.read(1_000_000).decode('utf-8'))
                item['available'] = True
                if service['id'] == 'ollama':
                    models = payload.get('models', []) if isinstance(payload, dict) else []
                    item['models'] = [{'name': m.get('name'), 'sizeBytes': m.get('size'),
                                       'modifiedAt': m.get('modified_at')} for m in models if isinstance(m, dict)]
                else:
                    models = payload.get('data', []) if isinstance(payload, dict) else []
                    item['models'] = [{'id': m.get('id'), 'ownedBy': m.get('owned_by')} for m in models if isinstance(m, dict)]
                item['modelCount'] = len(item['models'])
                break
            except Exception:
                continue
        result.append(item)
    return result


# Extended telemetry helpers. Optional Windows counters return null when unavailable.
_TELEMETRY_PREVIOUS = {}
_FOLDER_SIZE_CACHE = {}
_FOLDER_SIZE_CACHE_AT = 0
_WINDOWS_CACHE = None
_WINDOWS_CACHE_AT = 0
_TELEMETRY_HISTORY = []
# Кэшируем только выбранные системные показатели, чтобы не собирать снимок при каждом опросе.
_TELEMETRY_CACHE = None
_TELEMETRY_CACHE_AT = 0.0
_TELEMETRY_CACHE_LOCK = threading.Lock()
def _rate_snapshot(key, current):
    import time
    now=time.monotonic(); old=_TELEMETRY_PREVIOUS.get(key); _TELEMETRY_PREVIOUS[key]=(now,current)
    if not old or now<=old[0]: return None
    return round(max(0,current-old[1])/(now-old[0]),2)

def _extended_cpu():
    result={'perCorePercent':[],'manufacturer':None,'baseMHz':None,'queueLength':None,'temperatureC':None,'powerW':None,'systemCpuTimeSeconds':None,'processesTopCpu':[]}
    try:
        import psutil
        result['perCorePercent']=psutil.cpu_percent(interval=0.05,percpu=True)
        result['systemCpuTimeSeconds']=round(sum(psutil.cpu_times()._asdict().values()),2)
        try:
            q=psutil.cpu_stats()
            result['contextSwitches']=q.ctx_switches; result['interrupts']=q.interrupts
        except Exception: pass
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'HARDWARE\DESCRIPTION\System\CentralProcessor\0') as key:
                result['manufacturer']=str(winreg.QueryValueEx(key,'VendorIdentifier')[0]).strip()
                mhz=winreg.QueryValueEx(key,'~MHz')[0]; result['baseMHz']=float(mhz) if mhz else None
        except Exception: pass
        procs=[]
        for p in psutil.process_iter(['pid','name','cpu_percent','status','num_threads']):
            try:
                i=p.info; procs.append({'pid':i.get('pid'),'name':i.get('name'),'cpuPercent':i.get('cpu_percent'),'status':i.get('status'),'threads':i.get('num_threads')})
            except Exception: pass
        result['processesTopCpu']=sorted(procs,key=lambda x:x.get('cpuPercent') or 0,reverse=True)[:20]
    except Exception as exc: result['error']=str(exc)[:180]
    # Temperature sensors are not consistently exposed by Windows/psutil.
    result['temperatureNote']='Температура CPU и мощность доступны только при наличии поддерживаемого датчика/драйвера.'
    return result

def _extended_memory():
    out={'cachedGB':None,'buffersGB':None,'availableGB':None,'processesTopMemory':[],'processesTopVirtual':[],'peakWorkingSetAvailable':False,'readWriteBytesPerSec':None,'hardwareReservedGB':None}
    try:
        import psutil
        m=psutil.virtual_memory()
        out.update({'availableGB':round(m.available/1024**3,2),'cachedGB':round(getattr(m,'cached',0)/1024**3,2) if hasattr(m,'cached') else None,'buffersGB':round(getattr(m,'buffers',0)/1024**3,2) if hasattr(m,'buffers') else None})
        rows=[]
        for p in psutil.process_iter(['pid','name','memory_info','memory_full_info']):
            try:
                i=p.info; mi=i.get('memory_info'); full=i.get('memory_full_info')
                rows.append({'pid':i.get('pid'),'name':i.get('name'),'rssBytes':getattr(mi,'rss',None),'vmsBytes':getattr(mi,'vms',None),'privateBytes':getattr(full,'private',None)})
            except Exception: pass
        out['processesTopMemory']=sorted(rows,key=lambda x:x.get('rssBytes') or 0,reverse=True)[:20]
        out['processesTopVirtual']=sorted(rows,key=lambda x:x.get('vmsBytes') or 0,reverse=True)[:20]
    except Exception as exc: out['error']=str(exc)[:180]
    return out

def _extended_gpu():
    import subprocess
    out={'adapters':[],'engines':None,'processes':[],'activeGpuCount':None,'note':'Engine-level utilization and per-process VRAM depend on the installed NVIDIA driver and nvidia-smi support.'}
    command=shutil.which('nvidia-smi')
    if not command:
        p=os.environ.get('ProgramFiles',r'C:\Program Files')
        candidate=str(Path(p)/'NVIDIA Corporation'/'NVSMI'/'nvidia-smi.exe')
        if Path(candidate).is_file(): command=candidate
    if not command: return out
    def run(args,timeout=2):
        return subprocess.run([command]+args,capture_output=True,text=True,timeout=timeout,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)).stdout
    try:
        raw=run(['--query-gpu=index,name,uuid,utilization.gpu,utilization.memory,memory.used,memory.total,temperature.gpu,power.draw,clocks.gr,clocks.mem,pstate,clocks_throttle_reasons.active','--format=csv,noheader,nounits'])
        for line in raw.splitlines():
            p=[x.strip() for x in line.split(',')]
            if len(p)>=13:
                def n(i):
                    try:return float(p[i]) if p[i] and p[i].lower() not in ('n/a','[n/a]','not supported') else None
                    except Exception:return None
                out['adapters'].append({'index':n(0),'name':p[1],'uuid':p[2],'gpuPercent':n(3),'memoryPercent':n(4),'vramUsedMiB':n(5),'vramTotalMiB':n(6),'temperatureC':n(7),'powerW':n(8),'coreClockMHz':n(9),'memoryClockMHz':n(10),'performanceState':p[11],'throttleReasons':p[12]})
        out['activeGpuCount']=len(out['adapters'])
    except Exception as exc: out['queryError']=str(exc)[:180]
    try:
        raw=run(['--query-compute-apps=gpu_uuid,pid,process_name,used_memory','--format=csv,noheader,nounits'])
        for line in raw.splitlines():
            p=[x.strip() for x in line.split(',',3)]
            if len(p)>=4: out['processes'].append({'gpuUuid':p[0],'pid':p[1],'name':p[2],'vramMiB':p[3]})
    except Exception: pass
    try:
        raw=run(['dmon','-c','1','-s','u'])
        lines=[x.split() for x in raw.splitlines() if x.strip() and not x.lstrip().startswith('#')]
        if len(lines)>1: out['engines']={'header':lines[0],'sample':lines[-1]}
    except Exception: pass
    return out

def _extended_disks():
    import time
    global _FOLDER_SIZE_CACHE_AT
    result={'io':None,'physicalDevices':[],'projectFolders':[],'note':'SMART, drive temperature and controller write endurance require vendor/driver support.'}
    try:
        import psutil
        io=psutil.disk_io_counters(perdisk=True)
        entries=[]
        for name,c in io.items():
            read_rate=_rate_snapshot('disk-read-'+name,c.read_bytes); write_rate=_rate_snapshot('disk-write-'+name,c.write_bytes)
            entries.append({'device':name,'readBytes':c.read_bytes,'writeBytes':c.write_bytes,'readBytesPerSec':read_rate,'writeBytesPerSec':write_rate,'readMBps':round(read_rate/1024**2,3) if read_rate is not None else None,'writeMBps':round(write_rate/1024**2,3) if write_rate is not None else None,'readCount':c.read_count,'writeCount':c.write_count,'readIOPS':_rate_snapshot('disk-readops-'+name,c.read_count),'writeIOPS':_rate_snapshot('disk-writeops-'+name,c.write_count),'readTimeMs':c.read_time,'writeTimeMs':c.write_time,'busyTimeMs':getattr(c,'busy_time',None)})
        result['io']=entries
    except Exception as exc: result['error']=str(exc)[:180]
    for name,path in [('Project root',ROOT),('Models (Ollama default)',Path.home()/'.ollama'/'models'),('LM Studio models',Path.home()/'.lmstudio'/'models'),('ComfyUI W drive',Path('W:/--Comfy')),('Hugging Face cache',Path.home()/'.cache'/'huggingface')]:
        try:
            if path.exists():
                cache_key=str(path)
                cached=_FOLDER_SIZE_CACHE.get(cache_key)
                if cached and time.monotonic()-_FOLDER_SIZE_CACHE_AT<300:
                    total,files,partial=cached
                else:
                    total=0; files=0; partial=False
                    for base,dirs,names in os.walk(path):
                        dirs[:]=[d for d in dirs if d not in {'.git','node_modules','.venv','venv','__pycache__'}]
                        for fn in names:
                            try: total+=os.path.getsize(os.path.join(base,fn)); files+=1
                            except OSError: pass
                            if files>=5000: partial=True; break
                        if partial: break
                    _FOLDER_SIZE_CACHE[cache_key]=(total,files,partial)
                    _FOLDER_SIZE_CACHE_AT=time.monotonic()
                result['projectFolders'].append({'name':name,'path':str(path),'sizeBytes':total,'filesScanned':files,'partialScan':partial,'cacheSeconds':300})
            else: result['projectFolders'].append({'name':name,'path':str(path),'exists':False})
        except Exception: pass
    try:
        import subprocess
        ps=r"$ErrorActionPreference='Stop'; Get-PhysicalDisk | Select-Object FriendlyName,MediaType,BusType,Size,HealthStatus,OperationalStatus | ConvertTo-Json -Compress"
        run=subprocess.run(['powershell','-NoProfile','-Command',ps],capture_output=True,text=True,timeout=2.2,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if run.returncode==0 and run.stdout.strip():
            data=json.loads(run.stdout); result['physicalDevices']=data if isinstance(data,list) else [data]
    except Exception: pass
    return result

def _extended_network():
    import time
    out={'rates':[],'defaultGateways':[],'dnsServers':[],'internet':None,'tcpConnections':None,'serviceChecks':[],'note':'Per-process network accounting is not provided by psutil on Windows without ETW/WFP-based collection.'}
    try:
        import psutil
        counters=psutil.net_io_counters(pernic=True)
        for name,c in counters.items():
            rx=_rate_snapshot('net-rx-'+name,c.bytes_recv); tx=_rate_snapshot('net-tx-'+name,c.bytes_sent)
            out['rates'].append({'adapter':name,'receiveBytesPerSec':rx,'sendBytesPerSec':tx,'receiveMbps':round(rx*8/1e6,3) if rx is not None else None,'sendMbps':round(tx*8/1e6,3) if tx is not None else None})
        out['tcpConnections']=len(psutil.net_connections(kind='tcp'))
    except Exception as exc: out['error']=str(exc)[:180]
    try:
        import subprocess
        cmd="Get-NetIPConfiguration | Where-Object {$_.NetAdapter.Status -eq 'Up'} | Select-Object InterfaceAlias,@{n='IPv4Gateway';e={$_.IPv4DefaultGateway.NextHop -join ','}},@{n='DNSServers';e={$_.DNSServer.ServerAddresses -join ','}} | ConvertTo-Json -Compress"
        run=subprocess.run(['powershell','-NoProfile','-Command',cmd],capture_output=True,text=True,timeout=2.2,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if run.returncode==0 and run.stdout.strip():
            data=json.loads(run.stdout); data=data if isinstance(data,list) else [data]
            for x in data:
                if x.get('IPv4Gateway'): out['defaultGateways'].append({'adapter':x.get('InterfaceAlias'),'gateway':x.get('IPv4Gateway')})
                if x.get('DNSServers'): out['dnsServers'].append({'adapter':x.get('InterfaceAlias'),'servers':x.get('DNSServers')})
    except Exception: pass
    checks=[('Ollama','http://127.0.0.1:11434/api/tags'),('LM Studio','http://127.0.0.1:1234/v1/models'),('GitHub API','https://api.github.com')]
    import urllib.request
    for name,url in checks:
        started=time.monotonic()
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'PQlocalAgentOSv3-telemetry'})
            with urllib.request.urlopen(req,timeout=1.2) as response: status=response.status
            out['serviceChecks'].append({'name':name,'available':200<=status<400,'statusCode':status,'latencyMs':round((time.monotonic()-started)*1000,1),'checkedAt':datetime.datetime.now().astimezone().isoformat(timespec='seconds')})
        except Exception as exc: out['serviceChecks'].append({'name':name,'available':False,'error':str(exc)[:140],'latencyMs':round((time.monotonic()-started)*1000,1),'checkedAt':datetime.datetime.now().astimezone().isoformat(timespec='seconds')})
    try:
        req=urllib.request.Request('https://www.msftconnecttest.com/connecttest.txt',headers={'User-Agent':'PQlocalAgentOSv3-telemetry'})
        with urllib.request.urlopen(req,timeout=1.5) as response: out['internet']={'available':response.status==200,'statusCode':response.status}
    except Exception as exc: out['internet']={'available':False,'error':str(exc)[:140]}
    return out

def _windows_details():
    import time
    global _WINDOWS_CACHE, _WINDOWS_CACHE_AT
    if _WINDOWS_CACHE is not None and time.monotonic()-_WINDOWS_CACHE_AT<60:
        return _WINDOWS_CACHE
    out={'timezone':datetime.datetime.now().astimezone().tzname(),'localTime':datetime.datetime.now().astimezone().isoformat(timespec='seconds'),'startupItems':[],'services':[],'events':[],'security':{},'recentShutdowns':[],'powerPlan':None,'drivers':[],'note':'Windows event logs, Defender and driver inventory may require additional permissions.'}
    try:
        import subprocess
        ps=r"$ErrorActionPreference='SilentlyContinue'; $s=@{}; $s.edition=(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').EditionID; $s.build=(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').CurrentBuild; $s.displayVersion=(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion').DisplayVersion; $s.services=(Get-CimInstance Win32_Service | Where-Object {$_.State -eq 'Running'} | Select-Object -First 80 Name,DisplayName,StartMode,State); $s.startup=(Get-CimInstance Win32_StartupCommand | Select-Object -First 80 Name,Command,Location,User); $s.power=(powercfg /getactivescheme); $s.security=@{firewall=(Get-NetFirewallProfile | Select-Object Name,Enabled); defender=(Get-MpComputerStatus | Select-Object AntivirusEnabled,RealTimeProtectionEnabled,AntivirusSignatureLastUpdated)}; $s.events=(Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2,3;StartTime=(Get-Date).AddHours(-24)} -MaxEvents 30 -ErrorAction SilentlyContinue | Select-Object TimeCreated,Id,LevelDisplayName,ProviderName,Message); $s.shutdowns=(Get-WinEvent -FilterHashtable @{LogName='System';Id=41,1074,6006,6008;StartTime=(Get-Date).AddDays(-14)} -MaxEvents 20 -ErrorAction SilentlyContinue | Select-Object TimeCreated,Id,ProviderName,Message); $s | ConvertTo-Json -Depth 5 -Compress"
        run=subprocess.run(['powershell','-NoProfile','-Command',ps],capture_output=True,text=True,timeout=5,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if run.returncode==0 and run.stdout.strip():
            data=json.loads(run.stdout)
            out.update({'edition':data.get('edition'),'build':data.get('build'),'displayVersion':data.get('displayVersion'),'services':data.get('services') or [],'startupItems':data.get('startup') or [],'powerPlan':data.get('power'),'security':data.get('security') or {},'events':data.get('events') or [],'recentShutdowns':data.get('shutdowns') or []})
    except Exception as exc: out['collectionError']=str(exc)[:180]
    _WINDOWS_CACHE=out
    _WINDOWS_CACHE_AT=time.monotonic()
    return out

def _ai_runtime_stats():
    out={'ollamaRunningModels':None,'ollamaApiLatencyMs':None,'agents':{},'tasks':{},'recentPlatformEvents':[]}
    started=__import__('time').monotonic()
    try:
        req=urllib.request.Request(OLLAMA_URL+'/api/ps')
        with urllib.request.urlopen(req,timeout=1.2) as response: data=json.loads(response.read())
        out['ollamaRunningModels']=data.get('models',[])
        out['ollamaApiLatencyMs']=round((__import__('time').monotonic()-started)*1000,1)
    except Exception as exc: out['ollamaError']=str(exc)[:160]
    for kind in ('agents','tasks'):
        try:
            items=domain_items(kind)
            statuses={}
            for item in items:
                status=str(item.get('status','unknown')).lower(); statuses[status]=statuses.get(status,0)+1
            out[kind]={'total':len(items),'statuses':statuses,'items':[{'id':x.get('id'),'name':x.get('name',x.get('title')),'status':x.get('status'),'model':x.get('model'),'provider':x.get('provider'),'updated_at':x.get('updated_at'),'created_at':x.get('created_at')} for x in items[:100]]}
        except Exception as exc: out[kind]={'error':str(exc)[:120]}
    try: out['recentPlatformEvents']=read_json(DATA/'events.json',[])[:30]
    except Exception: pass
    return out



def _telemetry_snapshot():
    import time
    global _TELEMETRY_CACHE, _TELEMETRY_CACHE_AT
    # Один сбор раз в 2 секунды; блокировка не даёт параллельным запросам дублировать сбор.
    with _TELEMETRY_CACHE_LOCK:
        now = time.monotonic()
        if _TELEMETRY_CACHE is not None and now - _TELEMETRY_CACHE_AT < 2:
            return _TELEMETRY_CACHE
        data = system_stats()
        sample = {'timestamp': data.get('timestamp'),
                  'cpuPercent': (data.get('cpu') or {}).get('percent'),
                  'ramPercent': (data.get('ram') or {}).get('percent'),
                  'gpuPercent': (data.get('gpu') or {}).get('percent'),
                  'gpuTemperatureC': (data.get('gpu') or {}).get('temperatureC'),
                  'ramUsedGB': (data.get('ram') or {}).get('used')}
        _TELEMETRY_HISTORY.append(sample)
        del _TELEMETRY_HISTORY[:-360]
        _TELEMETRY_CACHE = data
        _TELEMETRY_CACHE_AT = time.monotonic()
        return data

def _telemetry_schema_node(value, path=''):
    if isinstance(value,dict):
        return {'type':'object','properties':{str(k):_telemetry_schema_node(v,path+'.'+str(k)) for k,v in value.items()}}
    if isinstance(value,list):
        item_schema=_telemetry_schema_node(value[0],path+'[]') if value else {'type':'unknown','description':'Пустой массив; схема элемента определяется по фактическому ответу API.'}
        return {'type':'array','items':item_schema}
    if value is None: return {'type':'null','nullable':True}
    if isinstance(value,bool): return {'type':'boolean'}
    if isinstance(value,int): return {'type':'integer'}
    if isinstance(value,float): return {'type':'number'}
    return {'type':'string'}

def _telemetry_api_schema():
    sample=system_stats()
    return {'ok':True,'apiVersion':'1.0','service':'PQlocalAgentOSv3 system telemetry',
            'description':'Возвращаются только CPU, RAM/файл подкачки, GPU, операционная система и среда Python. Недоступные значения обозначаются null или available=false.',
            'endpoints':[
                {'method':'GET','path':'/api/system/stats','description':'Снимок только выбранных показателей: CPU, RAM/файл подкачки, GPU, ОС и среда Python. Снимок кэшируется на 5 секунд.'},
                {'method':'GET','path':'/api/system/stats/schema','description':'JSON Schema-подобное описание структуры полей полного ответа.'},
                {'method':'GET','path':'/api/system/stats/history?limit=60','description':'История снятых образцов телеметрии; до 360 последних образцов в памяти текущего процесса сервера.'}
            ],
            'refreshHintSeconds':5,'historyMaxSamples':360,'schema':_telemetry_schema_node(sample)}


def _telemetry_unavailable_fields():
    checked=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
    def unavailable(source,reason):
        return {'value':None,'available':False,'source':source,'checkedAt':checked,'reason':reason}
    return {
      'cpu':{
        'temperatureC':unavailable('Windows hardware sensors','Нет универсального CPU temperature API в Windows; нужен поддерживаемый датчик/LibreHardwareMonitor.'),
        'powerW':unavailable('Hardware power sensor','Мощность CPU не предоставляется стандартным счётчиком на этом оборудовании.'),
        'perCoreFrequencyMHz':unavailable('CPU frequency counters','Частота каждого ядра не предоставлена текущим системным API/драйвером.'),
        'processorQueueLength':unavailable('Windows Performance Counters','Очередь процессора не удалось получить надёжным системным счётчиком.'),
        'baseFrequencyMHz':unavailable('CPU firmware/registry','Базовая частота не гарантируется для всех CPU; используйте cpuDetails.baseMHz если доступна.')
      },
      'ram':{
        'hardwareReservedGB':unavailable('Windows memory counters','Windows API, используемый приложением, не возвращает отдельный объём аппаратно зарезервированной RAM.'),
        'readBytesPerSec':unavailable('Windows memory performance counters','Скорость чтения RAM не является стандартным счётчиком psutil.'),
        'writeBytesPerSec':unavailable('Windows memory performance counters','Скорость записи RAM не является стандартным счётчиком psutil.'),
        'peakWorkingSetPerProcess':unavailable('Per-process memory counters','Пиковый working set зависит от доступных прав и Windows API; текущие рабочие наборы доступны в processes.')
      },
      'gpu':{
        'engine3DPercent':unavailable('Windows GPU engine counters','Счётчики 3D движка не предоставлены драйвером в доступном формате.'),
        'engineComputePercent':unavailable('Windows GPU engine counters','Счётчики Compute движка не предоставлены драйвером в доступном формате.'),
        'engineCopyPercent':unavailable('Windows GPU engine counters','Счётчики Copy движка не предоставлены драйвером в доступном формате.'),
        'engineVideoEncodePercent':unavailable('Windows GPU engine counters','Счётчики Video Encode движка не предоставлены драйвером в доступном формате.'),
        'engineVideoDecodePercent':unavailable('Windows GPU engine counters','Счётчики Video Decode движка не предоставлены драйвером в доступном формате.'),
        'fanRPM':unavailable('NVIDIA/board sensor','Доступен только процент вентилятора, если его возвращает nvidia-smi; RPM не предоставлены.'),
        'totalSystemPowerW':unavailable('Hardware power meter','Общая мощность ноутбука требует аппаратного измерителя/производительского API.'),
        'throttleReasonTemperature':unavailable('NVIDIA driver','Отдельная причина температурного троттлинга зависит от поддержки драйвером.'),
        'throttleReasonPower':unavailable('NVIDIA driver','Отдельная причина ограничения мощности зависит от поддержки драйвером.')
      },
      'disks':{
        'averageResponseMs':unavailable('Windows disk performance counters','Среднее время отклика не получено отдельным счётчиком.'),
        'queueLength':unavailable('Windows disk performance counters','Очередь диска не получена отдельным счётчиком.'),
        'activePercent':unavailable('Windows disk performance counters','Процент активности требует доступного Performance Counter.'),
        'temperatureC':unavailable('SMART/vendor storage driver','Температура диска не доступна через стандартный API; зависит от контроллера/SMART.'),
        'smartHealth':unavailable('SMART/vendor storage driver','SMART-состояние не доступно универсально через стандартный API Windows.'),
        'powerOnHours':unavailable('SMART/vendor storage driver','Часы работы накопителя зависят от SMART/производителя.'),
        'totalBytesWritten':unavailable('SMART/vendor storage driver','Объём записи накопителя зависит от SMART/производителя.')
      },
      'network':{
        'packetLossPercent':unavailable('ICMP probe','Потери пакетов требуют регулярных проверок конкретного узла; однократный запрос не является надёжной статистикой.'),
        'latencyMs':unavailable('ICMP probe','Постоянная задержка требует заданного целевого узла и периодических измерений.'),
        'internetSpeedMbps':unavailable('Bandwidth test','Тест скорости интернета не выполняется автоматически, чтобы не создавать лишний трафик.'),
        'perProcessTraffic':unavailable('ETW/WFP network collector','Трафик отдельных процессов требует ETW/WFP или отдельного сетевого коллектора.'),
        'subnetAndGatewayByAdapter':unavailable('Windows IP configuration','Сведения шлюза/DNS могут отсутствовать для отключённых или виртуальных адаптеров.')
      },
      'windows':{
        'windowsUpdateStatus':unavailable('Windows Update API','Состояние обновлений не подтверждено через Windows Update API.'),
        'driverHealth':unavailable('Device Manager/PnP','Общее состояние драйверов не подтверждено отдельной проверкой устройств.'),
        'recentApplicationCrashes':unavailable('Windows Application event log','Полный список сбоев приложений требует отдельного чтения журнала Application.'),
        'shutdownReason':unavailable('Windows System event log','Причина доступна только если Windows записала соответствующее событие.'),
        'defenderStatus':unavailable('Windows Defender cmdlets','Если PowerShell-команда недоступна или нет прав, состояние Defender не подтверждено.')
      },
      'processes':{
        'networkBytesPerSec':unavailable('ETW/WFP network collector','psutil не предоставляет универсальный учёт сети по процессам в Windows.'),
        'gpuPercentPerProcess':unavailable('Windows GPU engine/NVIDIA telemetry','GPU-процент процесса зависит от драйвера и счётчиков GPU Engine.'),
        'gpuMemoryBytesPerProcess':unavailable('NVIDIA driver / Windows GPU counters','VRAM по процессам доступна не для всех типов процессов/драйверов.'),
        'exitCode':unavailable('Process lifecycle monitor','Код завершения доступен только для процессов, завершение которых приложение отслеживало заранее.')
      },
      'aiRuntime':{
        'modelContextLength':unavailable('Provider model metadata','Размер контекста доступен только если конкретный провайдер/model API предоставляет это поле.'),
        'tokensPerSecond':unavailable('Inference request instrumentation','Скорость токенов появится для запросов, выполняемых через инструментированный runtime платформы.'),
        'inputOutputTokenCounts':unavailable('Inference request instrumentation','Количество токенов доступно только если API/модель возвращает usage или runtime его считает.'),
        'modelLoadDurationMs':unavailable('Inference request instrumentation','Время загрузки модели требует измерения вокруг команды загрузки/первого запроса.'),
        'perModelGpuMemory':unavailable('NVIDIA process mapping','Связать VRAM с конкретной моделью можно только при сопоставлении PID процесса и модели.'),
        'taskQueueLength':unavailable('Task scheduler instrumentation','Число ожидающих задач требует отдельного состояния очереди планировщика.'),
        'successfulRunCount':unavailable('Persisted task run history','История успешных запусков доступна только если исполнитель сохраняет каждую попытку.'),
        'failedRunCount':unavailable('Persisted task run history','История неуспешных запусков требует сохранения каждого результата исполнения.'),
        'averageTaskDurationMs':unavailable('Persisted task run history','Средняя длительность рассчитывается после сохранения времён начала и завершения запусков.'),
        'taskRetryCounts':unavailable('Task execution history','Счётчик повторов зависит от сохранения попыток в исполнительном контуре задач.'),
        'taskFailureReasons':unavailable('Task execution history','Причины ошибок доступны из сохранённых результатов и журналов конкретных запусков.'),
        'currentTaskStage':unavailable('Task execution instrumentation','Этап задачи обновляется только при инструментировании исполнителя на каждом шаге.'),
        'lastSuccessfulModelCall':unavailable('Inference request instrumentation','Последний успешный вызов модели требует журнала вызовов провайдера.'),
        'perTaskProviderAndModel':unavailable('Task execution history','Провайдер и модель на каждую задачу должны фиксироваться при запуске.'),
        'perTaskTokenUsage':unavailable('Inference request instrumentation','Токены на задачу требуют учёта usage со стороны модели или runtime.')
      }
    }

def system_stats():
    import platform
    import time
    # Собираем только CPU, RAM/файл подкачки, GPU, ОС и среду Python.
    cpu_percent = _cpu_usage()
    memory = _memory_stats()
    gpu = _gpu_stats()
    try:
        import psutil
        cpu_frequency = psutil.cpu_freq()
        boot_timestamp = psutil.boot_time()
        cpu_physical = psutil.cpu_count(logical=False)
        cpu_logical = psutil.cpu_count(logical=True)
        cpu_frequency_data = {'currentMHz': round(cpu_frequency.current, 1) if cpu_frequency else None,
                              'minMHz': round(cpu_frequency.min, 1) if cpu_frequency else None,
                              'maxMHz': round(cpu_frequency.max, 1) if cpu_frequency else None}
        uptime_seconds = max(0, int(time.time() - boot_timestamp))
        process_count = len(psutil.pids())
        thread_count = None
        try:
            thread_count = sum(p.info.get('num_threads') or 0 for p in psutil.process_iter(['num_threads']))
        except Exception:
            pass
    except Exception:
        cpu_physical = None
        cpu_logical = os.cpu_count()
        cpu_frequency_data = {'currentMHz': None, 'minMHz': None, 'maxMHz': None}
        uptime_seconds = None
        process_count = None
        thread_count = None
    os_data = {'system': platform.system(), 'release': platform.release(), 'version': platform.version(),
               'edition': platform.win32_edition() if hasattr(platform, 'win32_edition') else None,
               'architecture': platform.architecture()[0], 'machine': platform.machine(),
               'hostname': platform.node(), 'pythonVersion': platform.python_version(),
               'pythonImplementation': platform.python_implementation()}
    try:
        uptime_ms = __import__('ctypes').windll.kernel32.GetTickCount64()
        uptime_seconds = int(uptime_ms / 1000)
    except Exception:
        pass
    try:
        boot_time = datetime.datetime.now().astimezone() - datetime.timedelta(seconds=uptime_seconds) if uptime_seconds is not None else None
        boot_iso = boot_time.isoformat(timespec='seconds') if boot_time else None
    except Exception:
        boot_iso = None
    cpu = {'available': cpu_percent is not None, 'percent': cpu_percent, 'name': _cpu_name(),
           'physicalCores': cpu_physical, 'logicalCores': cpu_logical, 'frequency': cpu_frequency_data,
           'processCount': process_count, 'threadCount': thread_count}
    return {
        'ok': True,
        'timestamp': datetime.datetime.now().astimezone().isoformat(timespec='seconds'),
        'collection': {'source':'local Windows host','optionalDependency':'psutil + optional NVIDIA nvidia-smi; unavailable hardware sensors are returned as null','refreshHintSeconds':5},
        'cpu': cpu, 'ram': memory, 'gpu': gpu,
        'system': {'os':os_data,'uptimeSeconds':uptime_seconds,'bootTime':boot_iso,'processCount':process_count,'threadCount':thread_count}
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(FRONTEND),**kwargs)
    def log_message(self, fmt, *args): pass
    def send_json(self, code, data, headers=None):
        raw=json.dumps(data,ensure_ascii=False).encode(); self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(raw))); self.send_header('Cache-Control','no-store')
        for key, value in (headers or {}).items(): self.send_header(key, value)
        self.end_headers(); self.wfile.write(raw)
    def auth_session(self):
        cookie = SimpleCookie()
        try: cookie.load(self.headers.get('Cookie', ''))
        except Exception: return None
        morsel = cookie.get('pq_session')
        if not morsel: return None
        token = morsel.value
        now = datetime.datetime.now(datetime.timezone.utc)
        with AUTH_SESSIONS_LOCK:
            session = AUTH_SESSIONS.get(token)
            if not session: return None
            if session['expires'] <= now:
                AUTH_SESSIONS.pop(token, None)
                return None
            return session
    def require_auth(self):
        if not AUTH_ENABLED: return True
        if self.auth_session(): return True
        self.send_json(401, {'error':'Требуется вход в систему', 'auth_required':True})
        return False
    def auth_cookie(self, token, max_age):
        return {'Set-Cookie': 'pq_session=' + token + '; Path=/; HttpOnly; SameSite=Strict; Max-Age=' + str(max_age)}
    def body(self):
        n=int(self.headers.get('Content-Length','0'))
        if n>1_000_000: raise ValueError('Payload too large')
        return json.loads(self.rfile.read(n).decode('utf-8') or '{}')
    def do_GET(self):
        path=urlparse(self.path).path
        if path == '/api/auth/status':
            session = self.auth_session()
            config = read_json(AUTH_FILE, {})
            return self.send_json(200, {'auth_enabled':AUTH_ENABLED, 'authenticated':bool(session), 'username':session.get('username') if session else None, 'must_change_password':bool(config.get('must_change_password', False)) if session else False})
        if path=='/api/health': return self.send_json(200, {'ok':True,'app':'PQlocalAgentOSv3','host':HOST,'port':PORT,'time':datetime.datetime.now().astimezone().isoformat(timespec='seconds')})
        if path.startswith('/api/') and not self.require_auth(): return
        if path=='/api/diagnostics': return self.send_json(200, run_diagnostics())
        if path=='/api/system/stats':
            try:
                return self.send_json(200, _telemetry_snapshot())
            except Exception as exc:
                return self.send_json(500, {'ok':False,'error':str(exc),'errorType':type(exc).__name__})
        if path=='/api/system/stats/schema':
            try:
                return self.send_json(200, _telemetry_api_schema())
            except Exception as exc:
                return self.send_json(500, {'ok':False,'error':str(exc),'errorType':type(exc).__name__})
        if path=='/api/system/stats/history':
            try:
                query=parse_qs(urlparse(self.path).query)
                limit=max(1,min(360,int(query.get('limit',['60'])[0])))
                return self.send_json(200, {'ok':True,'count':min(limit,len(_TELEMETRY_HISTORY)),'maxSamples':360,'samples':_TELEMETRY_HISTORY[-limit:]})
            except (ValueError,TypeError) as exc:
                return self.send_json(400, {'ok':False,'error':'Параметр limit должен быть числом от 1 до 360','detail':str(exc)[:120]})
        if path=='/api/providers':
            items=provider_items(); models=[]
            for p in items:
                found=[]; connected=False
                if p.get('kind')=='local' or p.get('api_key'):
                    try: found=provider_models(p); connected=True
                    except Exception: pass
                p['connected']=connected; p['model_count']=len(found); p['api_key_set']=bool(p.get('api_key'))
                for m in found: models.append({'provider':p.get('name',''),'provider_id':p.get('id'),'kind':p.get('kind','local'),'name':m.get('name',''),'parameter_size':m.get('parameter_size','—'),'size':m.get('size',0),'connected':connected})
            return self.send_json(200, {'providers':[public_provider(p) for p in items], 'models':models})
        if path=='/api/models':
            try:
                payload=ollama_request('/api/tags',timeout=4)
                models=[{'name':m.get('name',''),'size':m.get('size',0),'modified_at':m.get('modified_at','')} for m in payload.get('models',[]) if isinstance(m,dict) and m.get('name')]
                return self.send_json(200, {'provider':'ollama','base_url':OLLAMA_URL,'connected':True,'models':models,'error':None})
            except Exception as e: return self.send_json(200, {'provider':'ollama','base_url':OLLAMA_URL,'connected':False,'models':[],'error':'Не удалось подключиться к Ollama: '+str(e)[:180]})
        if path in ('/api/agents','/api/projects','/api/tasks'):
            kind=path.split('/')[-1]; items=domain_items(kind)
            return self.send_json(200, {'items':items,'total':len(items)})
        if path=='/api/settings': return self.send_json(200, settings())
        if path=='/api/pages': return self.send_json(200, pages())
        if path=='/api/log': return self.send_json(200, read_json(DATA/'events.json', []))
        if path=='/api/modules':
            return self.send_json(200, read_json(DATA/'modules.json', {'modules':[], 'connections':[]}))
        if path=='/api/modules/runs':
            return self.send_json(200, read_json(DATA/'module-runs.json', []))
        if path=='/api/permissions': return self.send_json(200, permission_settings())
        if path=='/api/github/search':
            q=parse_qs(urlparse(self.path).query).get('q',[''])[0].strip()[:120]
            if len(q)<2: return self.send_json(400, {'error':'Введите минимум 2 символа для поиска'})
            try:
                result=github_public_request('/search/repositories?q='+urllib.parse.quote(q+' in:name,description,readme')+'&sort=stars&order=desc&per_page=12')
                items=[{'full_name':x.get('full_name',''),'description':x.get('description') or 'Без описания','html_url':x.get('html_url',''),'stars':x.get('stargazers_count',0),'language':x.get('language') or 'Не указан','license':(x.get('license') or {}).get('spdx_id') or 'Не указана','updated_at':x.get('updated_at','')} for x in result.get('items',[])]
                return self.send_json(200, {'items':items,'total_count':result.get('total_count',0)})
            except Exception as e: return self.send_json(400, {'error':str(e)})
        if path=='/api/github': return self.send_json(200, {'repository':REPO,'configured':bool(os.environ.get('GITHUB_TOKEN')),'connected':False,'message':'Токен не задан' if not os.environ.get('GITHUB_TOKEN') else 'Токен задан; нажмите «Проверить подключение»'})
        if path=='/api/github/check':
            token=os.environ.get('GITHUB_TOKEN')
            if not token: return self.send_json(200, {'ok':False,'message':'Задайте GITHUB_TOKEN в окружении перед запуском сервера.'})
            req=urllib.request.Request('https://api.github.com/repos/'+REPO,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','User-Agent':'PQlocalAgentOSv3'})
            try:
                with urllib.request.urlopen(req,timeout=8) as res: data=json.loads(res.read())
                log_event('github.check',REPO); return self.send_json(200, {'ok':True,'message':'Подключение успешно','repository':data.get('full_name',REPO),'private':data.get('private'),'default_branch':data.get('default_branch')})
            except urllib.error.HTTPError as e: return self.send_json(200, {'ok':False,'message':'GitHub вернул HTTP '+str(e.code)+'. Проверьте токен и доступ к репозиторию.'})
            except Exception as e: return self.send_json(200, {'ok':False,'message':'Не удалось подключиться к GitHub: '+str(e)[:180]})
        if path=='/api/github/files':
            try:
                repo=github_request('/repos/'+REPO)
                tree=github_request('/repos/'+REPO+'/git/trees/'+repo.get('default_branch','main')+'?recursive=1')
                files=[{'path':x['path'],'size':x.get('size',0)} for x in tree.get('tree',[]) if x.get('type')=='blob'][:500]
                return self.send_json(200, {'repository':REPO,'branch':repo.get('default_branch','main'),'files':files})
            except Exception as e: return self.send_json(400, {'error':str(e)})
        if path=='/api/github/file':
            file_path=parse_qs(urlparse(self.path).query).get('path',[''])[0]
            if not file_path or file_path.startswith('/') or '..' in Path(file_path).parts: return self.send_json(400, {'error':'Некорректный путь файла'})
            try:
                f=github_request('/repos/'+REPO+'/contents/'+urllib.parse.quote(file_path,safe='/'))
                import base64
                content=base64.b64decode(f.get('content','')).decode('utf-8',errors='replace')
                return self.send_json(200, {'path':file_path,'content':content,'sha':f.get('sha'),'size':f.get('size',0)})
            except Exception as e: return self.send_json(400, {'error':str(e)})
        return super().do_GET()
    def do_POST(self):
        path=urlparse(self.path).path
        try: data=self.body()
        except Exception as e: return self.send_json(400, {'error':str(e)})
        if path == '/api/auth/login':
            config = read_json(AUTH_FILE, {})
            username = str(data.get('username', '')).strip()
            password = str(data.get('password', ''))
            try:
                salt = bytes.fromhex(config.get('salt', ''))
                supplied = _password_hash(password, salt)
            except Exception:
                supplied = ''
            if username != config.get('username') or not hmac.compare_digest(supplied, str(config.get('password_hash', ''))):
                return self.send_json(401, {'error':'Неверный логин или пароль'})
            token = secrets.token_urlsafe(32)
            with AUTH_SESSIONS_LOCK:
                AUTH_SESSIONS[token] = {'username':config['username'], 'expires':datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(hours=8)}
            log_event('auth.login', config['username'])
            return self.send_json(200, {'ok':True,'username':config['username'],'must_change_password':bool(config.get('must_change_password', False))}, self.auth_cookie(token, 28800))
        if path == '/api/auth/logout':
            session = self.auth_session()
            if session:
                cookie = SimpleCookie()
                try:
                    cookie.load(self.headers.get('Cookie', ''))
                    token = cookie.get('pq_session').value if cookie.get('pq_session') else ''
                    with AUTH_SESSIONS_LOCK: AUTH_SESSIONS.pop(token, None)
                except Exception: pass
            return self.send_json(200, {'ok':True}, self.auth_cookie('', 0))
        if path == '/api/auth/change-password':
            if not self.require_auth(): return
            new_password = str(data.get('new_password', ''))
            if len(new_password) < 12:
                return self.send_json(400, {'error':'Новый пароль должен содержать не менее 12 символов'})
            config = read_json(AUTH_FILE, {})
            salt = secrets.token_bytes(16)
            config.update({'salt':salt.hex(),'password_hash':_password_hash(new_password, salt),'iterations':AUTH_ITERATIONS,'must_change_password':False})
            write_json(AUTH_FILE, config)
            log_event('auth.password_change', config.get('username', 'root'))
            return self.send_json(200, {'ok':True,'must_change_password':False})
        if path.startswith('/api/') and not self.require_auth(): return
        if path == '/api/chat':
            agent_id = str(data.get('agent_id', '')).strip()[:160]
            model = str(data.get('model', '')).strip()[:160]
            messages = data.get('messages')
            agent = None
            if agent_id:
                agent = next((x for x in domain_items('agents') if isinstance(x, dict) and x.get('id') == agent_id), None)
                if not agent: return self.send_json(404, {'error':'Выбранный агент не найден'})
                model = str(agent.get('model', '')).strip()[:160] or model
            if not model:
                try:
                    available = ollama_request('/api/tags', timeout=4).get('models', [])
                    model = next((str(x.get('name','')).strip() for x in available if isinstance(x,dict) and x.get('name')), '')
                except Exception:
                    model = ''
            if not model:
                return self.send_json(400, {'error': 'У выбранного агента не назначена модель, а локальные модели недоступны. Откройте настройки агента и назначьте модель.'})
            if not isinstance(messages, list) or not messages:
                return self.send_json(400, {'error': 'Передайте историю сообщений'})
            validated_messages = []
            for message in messages:
                if not isinstance(message, dict):
                    return self.send_json(400, {'error': 'Некорректный формат сообщения'})
                role = str(message.get('role', '')).strip()
                content = message.get('content')
                if role not in ('system', 'user', 'assistant') or not isinstance(content, str):
                    return self.send_json(400, {'error': 'У сообщения некорректная роль или содержимое'})
                validated_messages.append({'role': role, 'content': content})
            if agent:
                system_prompt = str(agent.get('system_prompt', '')).strip()
                role_prompt = {
                    'MANAGER':'Ты Агент №1 — координатор проекта. Помогай пользователю управлять проектом, уточняй цели и предлагай проверяемые следующие шаги.',
                    'ARCHITECT':'Ты системный архитектор. Учитывай структуру, зависимости, масштабируемость и безопасность.',
                    'ANALYST':'Ты аналитик. Разделяй факты и предположения, проверяй данные и объясняй выводы.',
                    'DESIGNER':'Ты дизайнер интерфейсов. Учитывай доступность, адаптивность, иерархию и единообразие.',
                    'COPYWRITER':'Ты редактор и технический автор. Пиши ясно, конкретно и без выдуманных фактов.',
                    'CODER':'Ты инженер-программист. Предлагай проверяемые решения и учитывай безопасность, тесты и сопровождение.',
                    'TESTER':'Ты инженер по тестированию. Ищи граничные случаи, регрессии и воспроизводимые критерии приёмки.',
                    'DEVOPS':'Ты инженер инфраструктуры. Учитывай конфигурацию, логи, мониторинг и откат.'
                }.get(str(agent.get('role','')).upper(), '')
                instruction = system_prompt or role_prompt
                if instruction and not any(m.get('role') == 'system' for m in validated_messages):
                    validated_messages.insert(0, {'role':'system','content':instruction})
            request_body = json.dumps({
                'model': model,
                'messages': validated_messages,
                'stream': False
            }, ensure_ascii=False).encode('utf-8')
            request = urllib.request.Request(
                'http://127.0.0.1:11434/api/chat',
                data=request_body,
                headers={'Content-Type': 'application/json'},
                method='POST'
            )
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    result = json.loads(response.read().decode('utf-8'))
                answer = result.get('message', {}).get('content')
                if not isinstance(answer, str):
                    return self.send_json(500, {'error': 'Ollama вернула ответ без текста модели.'})
                log_event('chat.message', model)
                return self.send_json(200, {'response': answer})
            except urllib.error.HTTPError as exc:
                try:
                    error_payload = json.loads(exc.read().decode('utf-8'))
                    detail = error_payload.get('error')
                except Exception:
                    detail = None
                return self.send_json(500, {'error': 'Ошибка Ollama: ' + str(detail or exc.reason)[:240]})
            except TimeoutError:
                return self.send_json(500, {'error': 'Ollama не ответила за 120 секунд. Попробуйте ещё раз.'})
            except (urllib.error.URLError, ConnectionError, OSError) as exc:
                return self.send_json(500, {'error': 'Ollama недоступна. Запустите ollama serve.'})
            except Exception as exc:
                return self.send_json(500, {'error': 'Не удалось получить ответ Ollama: ' + str(exc)[:180]})
        if path=='/api/providers':
            pid=str(data.get('id','')).strip(); name=str(data.get('name','')).strip()[:80]; kind=str(data.get('kind','local')).strip(); base=str(data.get('base_url','')).strip().rstrip('/'); fmt=str(data.get('format','openai')).strip()
            if not name or not base or kind not in ('local','cloud'): return self.send_json(400, {'error':'Укажите имя, тип и адрес провайдера'})
            if not re.match(r'^https?://',base): return self.send_json(400, {'error':'Адрес должен начинаться с http:// или https://'})
            if fmt not in ('ollama','openai','anthropic','gemini'): return self.send_json(400, {'error':'Неподдерживаемый формат доступа'})
            items=read_json(PROVIDER_FILE,[]); items=items if isinstance(items,list) else []; existing=next((x for x in items if x.get('id')==pid),None) if pid else None
            if not pid: pid=re.sub(r'[^a-z0-9-]+','-',name.lower()).strip('-')[:48]+'-'+uuid.uuid4().hex[:6]
            builtin=pid in {'ollama','lm-studio','openai','anthropic','google-gemini','openrouter','groq'}
            old=existing or next((x for x in provider_items() if x.get('id')==pid),{})
            if existing is None and builtin and pid not in {x.get('id') for x in provider_items()}: return self.send_json(400, {'error':'Неизвестный встроенный провайдер'})
            item={'id':pid,'name':name,'kind':kind,'base_url':base,'format':fmt,'builtin':builtin,'created_at':(old or {}).get('created_at') or (datetime.datetime.now().astimezone().isoformat(timespec='seconds') if not existing and not builtin else '')}
            key=str(data.get('api_key','')).strip()
            if key: item['api_key']=key
            elif old.get('api_key'): item['api_key']=old['api_key']
            if existing: items=[item if x.get('id')==pid else x for x in items]
            else: items.append(item)
            write_json(PROVIDER_FILE,items); log_event('provider.save',name)
            return self.send_json(200, {'ok':True,'provider':public_provider(item)})
        if path=='/api/providers/assign':
            aid=str(data.get('agent_id','')); pid=str(data.get('provider_id','')); model=str(data.get('model','')).strip()[:200]
            agents=domain_items('agents'); agent=next((x for x in agents if x.get('id')==aid),None); prov=next((x for x in provider_items() if x.get('id')==pid),None)
            if not agent or not prov or not model: return self.send_json(400, {'error':'Не удалось определить агента, провайдера или модель'})
            agent['model']=model; agent['provider_id']=pid; save_domain('agents',agents); log_event('model.assign',agent.get('name','')+' ← '+prov.get('name','')+'/'+model)
            return self.send_json(200, {'ok':True})
        if path=='/api/models/test':
            model=str(data.get('model','')).strip()[:160]; prompt=str(data.get('prompt','Проверь, что модель отвечает.')).strip()[:4000]
            if not model: return self.send_json(400, {'error':'Выберите модель'})
            try:
                result=ollama_request('/api/generate',{'model':model,'prompt':prompt,'stream':False,'options':{'num_predict':256}},timeout=180)
                log_event('model.test',model)
                return self.send_json(200, {'ok':True,'model':result.get('model',model),'response':result.get('response',''),'done':bool(result.get('done',False))})
            except Exception as e: return self.send_json(502, {'error':'Ошибка запроса к локальной модели: '+str(e)[:200]})
        if path in ('/api/agents','/api/projects','/api/tasks'):
            kind=path.split('/')[-1]; items=domain_items(kind); field='title' if kind=='tasks' else 'name'
            name=str(data.get(field,'')).strip()[:160]
            if not name: return self.send_json(400, {'error':'Укажите название'})
            item={'id':uuid.uuid4().hex[:12],field:name,'created_at':datetime.datetime.now().astimezone().isoformat(timespec='seconds')}
            if kind=='agents':
                role=str(data.get('role','ANALYST')).upper()
                if role not in AGENT_ROLES: return self.send_json(400, {'error':'Неизвестная роль агента'})
                item.update({'role':role,'model':str(data.get('model','')).strip()[:160],'description':str(data.get('description','')).strip()[:1000],'system_prompt':str(data.get('system_prompt') or AGENT_ROLE_PROMPTS[role]).strip()[:4000],'memory':str(data.get('memory','')).strip()[:8000],'permissions':{**DEFAULT_AGENT_PERMISSIONS,**{k:bool(v) for k,v in data.get('permissions',{}).items() if k in AGENT_PERMISSION_KEYS}} if isinstance(data.get('permissions',{}),dict) else DEFAULT_AGENT_PERMISSIONS.copy(),'status':'idle','system':False})
            elif kind=='projects': item.update({'path':str(data.get('path','')).strip()[:1000],'description':str(data.get('description','')).strip()[:1000],'status':'active'})
            else: item.update({'description':str(data.get('description','')).strip()[:5000],'model':str(data.get('model','')).strip()[:160],'agent_id':str(data.get('agent_id','')).strip()[:80],'project_id':str(data.get('project_id','')).strip()[:80],'team_mode':bool(data.get('team_mode',False)),'status':'pending','result':'','error':'','team_result':[]})
            items.insert(0,item); save_domain(kind,items); log_event(kind[:-1]+'.create',name)
            return self.send_json(201,item)
        if path.startswith('/api/tasks/') and (path.endswith('/run') or path.endswith('/run-team')):
            task_id=path.split('/')[-2]; items=domain_items('tasks'); item=next((x for x in items if x.get('id')==task_id),None)
            if not item: return self.send_json(404, {'error':'Задача не найдена'})
            agents=domain_items('agents')
            agent=next((x for x in agents if x.get('id')==item.get('agent_id')),None)
            model=item.get('model') or (agent or {}).get('model') or str(data.get('model','')).strip()
            if not model: return self.send_json(400, {'error':'Укажите модель для запуска задачи или назначьте модель агенту'})
            project=next((x for x in domain_items('projects') if x.get('id')==item.get('project_id')),None)
            item['status']='running'; item['model']=model; item['started_at']=datetime.datetime.now().astimezone().isoformat(timespec='seconds'); save_domain('tasks',items)
            role=(agent or {}).get('role','ANALYST')
            system_prompt=(agent or {}).get('system_prompt') or AGENT_ROLE_PROMPTS.get(role,AGENT_ROLE_PROMPTS['ANALYST'])
            if agent:
                system_prompt += '\n\nПрофиль агента: '+str(agent.get('name',''))+'\nНазначение: '+str(agent.get('description',''))[:1000]
                memory=str(agent.get('memory','')).strip()
                if memory: system_prompt += '\n\nДолговременная память агента (пользовательские заметки):\n'+memory[:8000]
            prompt='Выполни задачу. Отвечай на русском языке. Разделяй подтверждённые факты и предположения. Если не хватает данных, явно укажи ограничения.\n\nНазвание задачи: '+item.get('title','')+'\n\nОписание и инструкции:\n'+item.get('description','')
            if project:
                prompt += '\n\nКонтекст проекта:\nНазвание: '+str(project.get('name',''))+'\nОписание: '+str(project.get('description',''))+'\nРабочий путь (справочная информация, не открывай файлы автоматически): '+str(project.get('path',''))
            try:
                team_mode=path.endswith('/run-team') or bool(item.get('team_mode'))
                result=run_agent_team(model,item,agent,project) if team_mode else run_agent_task(model,item,agent,project)
                item['status']='completed'; item['result']=result.get('response',''); item['tool_calls']=result.get('tool_calls',0); item['warning']=result.get('warning',''); item['team_result']=result.get('team_result',[]); item['error']=''; item['finished_at']=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
                if agent:
                    agent['last_task_id']=task_id; agent['last_task_at']=item['finished_at']; save_domain('agents',agents)
                log_event('task.completed',item.get('title','')); save_domain('tasks',items); return self.send_json(200,item)
            except Exception as e:
                item['status']='failed'; item['error']=str(e)[:300]; item['finished_at']=datetime.datetime.now().astimezone().isoformat(timespec='seconds'); save_domain('tasks',items); log_event('task.failed',item.get('title',''))
                return self.send_json(502, {'error':'Не удалось выполнить задачу через Ollama: '+str(e)[:180],'task':item})
        if path.startswith('/api/agents/') or path.startswith('/api/projects/') or path.startswith('/api/tasks/'):
            parts=path.strip('/').split('/'); kind=parts[1]; item_id=parts[2] if len(parts)>2 else ''
            if kind not in DOMAIN_FILES: return self.send_json(404, {'error':'Неизвестный раздел'})
            items=domain_items(kind); item=next((x for x in items if x.get('id')==item_id),None)
            if not item: return self.send_json(404, {'error':'Запись не найдена'})
            allowed={'agents':{'name','role','model','description','system_prompt','memory','permissions','avatar'},'projects':{'name','path','description'},'tasks':{'title','description','model','agent_id','project_id','team_mode'}}[kind]
            for key in allowed:
                if key not in data: continue
                if kind=='agents' and key=='permissions':
                    if not isinstance(data[key],dict) or set(data[key])-AGENT_PERMISSION_KEYS: return self.send_json(400, {'error':'Некорректные разрешения агента'})
                    item[key]={**DEFAULT_AGENT_PERMISSIONS,**{k:bool(v) for k,v in data[key].items()}}
                elif kind=='agents' and key in {'system_prompt','memory'}: item[key]=str(data[key]).strip()[:(4000 if key=='system_prompt' else 8000)]
                elif kind=='tasks' and key=='team_mode': item[key]=bool(data[key])
                else: item[key]=str(data[key]).strip()[:5000]
            save_domain(kind,items); log_event(kind[:-1]+'.update',item.get('name',item.get('title','')))
            return self.send_json(200,item)
        if path=='/api/permissions':
            current=permission_settings()
            if 'local_files' in data:
                if not isinstance(data.get('local_files'),bool): return self.send_json(400, {'error':'local_files должен быть логическим значением'})
                current['local_files']=data['local_files']
            if current['local_files'] and not current['roots']: return self.send_json(409, {'error':'Сначала добавьте хотя бы одну разрешённую папку.'})
            write_json(DATA/'permissions.json',current); log_event('permissions.global',str(current['local_files']))
            return self.send_json(200,current)
        if path=='/api/permissions/roots':
            current=permission_settings(); raw_path=str(data.get('path','')).strip().strip('"'); action=str(data.get('action','add'))
            if action=='remove':
                current['roots']=[p for p in current['roots'] if p!=raw_path]
                if not current['roots']: current['local_files']=False
                write_json(DATA/'permissions.json',current); log_event('permissions.root.remove',raw_path); return self.send_json(200,current)
            if action!='add' or not raw_path: return self.send_json(400, {'error':'Укажите путь к папке'})
            try:
                from agent_tools import _contains_reparse
                raw_root=Path(raw_path).expanduser()
                if _contains_reparse(raw_root): return self.send_json(400, {'error':'Символические ссылки и junction нельзя добавлять в разрешённые папки.'})
                root=raw_root.resolve(strict=True)
                if not root.is_dir() or root.parent==root or _contains_reparse(root): return self.send_json(400, {'error':'Нужно выбрать существующую папку, не корень диска и без символических ссылок.'})
            except Exception as e: return self.send_json(400, {'error':'Папка недоступна: '+str(e)[:160]})
            normalized=str(root)
            if normalized not in current['roots']: current['roots'].append(normalized)
            write_json(DATA/'permissions.json',current); log_event('permissions.root.add',normalized)
            return self.send_json(200,current)
        if path=='/api/settings':
            allowed={'appearance','header','navigation','icons'}; current=settings()
            for k,v in data.items():
                if k in allowed and isinstance(v,dict):
                    if k=='icons':
                        cleaned={}
                        for key,val in list(v.items())[:100]:
                            if not isinstance(key,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}',key): continue
                            if not isinstance(val,dict): continue
                            try: size=int(val.get('size'))
                            except (TypeError,ValueError): continue
                            if size<12 or size>64: continue
                            cleaned[key]={'size':size}
                        current['icons']=cleaned
                        continue
                    if k=='navigation' and isinstance(v.get('menu'),list):
                        menu=[]
                        for item in v['menu'][:100]:
                            if not isinstance(item,dict): continue
                            pid=str(item.get('page_id','')).strip()[:80]
                            if pid and not re.fullmatch(r'[a-zA-Z0-9_-]+',pid): continue
                            menu.append({'id':str(item.get('id') or uuid.uuid4().hex[:10])[:40],'label':str(item.get('label') or '')[:100],'icon':str(item.get('icon') or 'file-text')[:40],'page_id':pid,'visible':item.get('visible') is not False,'parent_id':str(item.get('parent_id') or '')[:40]})
                        v={**v,'menu':menu}
                    current[k]={**current.get(k,{}),**v}
            write_json(DATA/'settings.json',current); log_event('settings.save','Настройки интерфейса сохранены'); return self.send_json(200,current)
        if path == '/api/icons':
            icon_id = str(data.get('id', '')).strip()
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', icon_id):
                return self.send_json(400, {'error': 'Некорректный id иконки'})
            if icon_id in {'cpu', 'hdd', 'monitor', 'ram', 'video'}:
                return self.send_json(403, {'error': 'Эта иконка зарезервирована для системной телеметрии'})
            svg = data.get('svg')
            if not isinstance(svg, str) or not svg.strip():
                return self.send_json(400, {'error': 'Пустой SVG'})
            if len(svg.encode('utf-8')) > 256 * 1024:
                return self.send_json(413, {'error': 'SVG слишком большой (макс. 256 КБ)'})
            svg_lower = svg.lower()
            forbidden = [
                '<!doctype', '<?xml', '<script', '<iframe', '<object',
                '<embed', '<foreignobject', 'javascript:', 'data:text/html'
            ]
            for token in forbidden:
                if token in svg_lower:
                    return self.send_json(400, {'error': 'SVG содержит запрещённые элементы'})
            if re.search(r'\son[a-z]+\s*=', svg_lower):
                return self.send_json(400, {'error': 'SVG содержит inline-обработчики'})
            stripped = svg.lstrip()
            if not stripped.lower().startswith('<svg') or not re.match(r'<svg(?:\s|>)', stripped, re.IGNORECASE):
                return self.send_json(400, {'error': 'Файл не является SVG'})
            target = ICONS_DIR / f'{icon_id}.svg'
            try:
                target.write_text(svg, encoding='utf-8')
            except OSError as e:
                return self.send_json(500, {'error': f'Не удалось сохранить: {e}'})
            saved_size = None
            size = data.get('size')
            if size is not None:
                try:
                    parsed_size = int(size)
                except (TypeError, ValueError):
                    parsed_size = None
                if parsed_size is not None and 12 <= parsed_size <= 64:
                    current = settings()
                    icons = current.get('icons')
                    if not isinstance(icons, dict):
                        icons = {}
                    icons[icon_id] = {'size': parsed_size}
                    current['icons'] = icons
                    write_json(DATA / 'settings.json', current)
                    saved_size = parsed_size
            log_event('icons.upload', f'Иконка {icon_id} сохранена')
            return self.send_json(200, {
                'ok': True,
                'id': icon_id,
                'path': f'/icons/{icon_id}.svg',
                'size': saved_size
            })
        if path=='/api/pages':
            title=str(data.get('title','')).strip()[:100]; desc=str(data.get('description','')).strip()[:300]; content=str(data.get('content','')).strip()[:20000]
            if not title: return self.send_json(400, {'error':'Укажите название страницы'})
            slug=re.sub(r'[^a-z0-9-]+','-',str(data.get('id') or title.lower())).strip('-')[:60] or uuid.uuid4().hex[:8]
            current=pages()
            if any(p['id']==slug for p in current): return self.send_json(409, {'error':'Страница с таким идентификатором уже существует'})
            item={'id':slug,'title':title,'description':desc,'icon':'file-text','content':content,'system':False,'created_at':datetime.datetime.now().astimezone().isoformat(timespec='seconds')}; current.append(item); write_json(PAGES/'index.json',current); log_event('page.create',title); return self.send_json(201,item)
        if path.startswith('/api/pages/') and path.endswith('/update'):
            pid=path.split('/')[-2]; current=pages(); item=next((p for p in current if p['id']==pid),None)
            if not item: return self.send_json(404, {'error':'Страница не найдена'})
            for k,limit in [('title',100),('description',300),('content',20000)]:
                if k in data: item[k]=str(data[k]).strip()[:limit]
            write_json(PAGES/'index.json',current); log_event('page.update',item['title']); return self.send_json(200,item)
        if path=='/api/modules':
            raw_id=str(data.get('id','')).strip().lower()
            module_id=re.sub(r'[^a-z0-9._-]+','-',raw_id).strip('-')[:80]
            name=str(data.get('name','')).strip()[:120]
            description=str(data.get('description','')).strip()[:1000]
            version=str(data.get('version','1.0.0')).strip()[:40] or '1.0.0'
            if not module_id or not re.fullmatch(r'[a-z0-9][a-z0-9._-]{1,79}',module_id): return self.send_json(400, {'error':'ID: 2–80 символов, латиница, цифры, точка, дефис или подчёркивание'})
            if not name: return self.send_json(400, {'error':'Укажите название модуля'})
            current=read_json(DATA/'modules.json', {'modules':[], 'connections':[]})
            if any(m.get('id')==module_id for m in current.get('modules',[])): return self.send_json(409, {'error':'Модуль с таким ID уже существует'})
            inputs=[{'name':x.strip(),'type':'text','required':False} for x in str(data.get('inputs','')).split(',') if x.strip()][:30]
            outputs=[{'name':x.strip(),'type':'text'} for x in str(data.get('outputs','')).split(',') if x.strip()][:30]
            if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',p['name']) for p in inputs+outputs): return self.send_json(400, {'error':'Имена портов должны содержать латинские буквы, цифры, точку, дефис или подчёркивание.'})
            if len({p['name'] for p in inputs})!=len(inputs) or len({p['name'] for p in outputs})!=len(outputs): return self.send_json(400, {'error':'Имена портов должны быть уникальными.'})
            runtime_kind=str(data.get('runtime_kind','input')).strip()
            if runtime_kind not in MODULE_RUNTIME_KINDS: return self.send_json(400, {'error':'Неизвестный встроенный тип модуля'})
            runtime={'kind':runtime_kind}
            if runtime_kind=='template': runtime['template']=str(data.get('template') or '{input}')[:12000]
            if runtime_kind=='transform':
                operation=str(data.get('operation','strip'))
                if operation not in {'uppercase','lowercase','strip','json_parse','json_pretty'}: return self.send_json(400, {'error':'Неизвестная операция преобразования'})
                runtime['operation']=operation
            if runtime_kind=='ollama':
                runtime['system_prompt']=str(data.get('system_prompt',''))[:4000]
                runtime['model']=str(data.get('model',''))[:160]
                try: max_tokens=int(data.get('max_tokens',1024))
                except (TypeError,ValueError): max_tokens=1024
                runtime['max_tokens']=min(max(max_tokens,64),4096)
            manifest={'id':module_id,'name':name,'version':version,'description':description,'api_version':'1.0','inputs':inputs,'outputs':outputs,'runtime':runtime,'capabilities':[],'permissions':[],'dependencies':[]}
            folder=MODULES/module_id
            if folder.exists(): return self.send_json(409, {'error':'Папка модуля уже существует; проверьте каталог modules/'})
            folder.mkdir(parents=True,exist_ok=False)
            write_json(folder/'module.json',manifest)
            (folder/'README.md').write_text('# '+name+'\n\n'+description+'\n\nЛокальный каркас модуля PQlocalAgentOSv3. Добавьте реализацию после определения входов, выходов и разрешений. Код не запускается автоматически.\n',encoding='utf-8')
            module={'id':module_id,'name':name,'description':description,'version':version,'source':'local','url':'','stars':0,'license':'Не указана','status':'draft','trusted':False,'manifest':manifest,'created_at':datetime.datetime.now().astimezone().isoformat(timespec='seconds'),'note':'Локальный каркас создан. Реализация не запускается автоматически.'}
            current.setdefault('modules',[]).append(module); current.setdefault('connections',[]); write_json(DATA/'modules.json',current); log_event('module.create',module_id)
            return self.send_json(201, {'ok':True,'module':module})
        if path=='/api/modules/update':
            module_id=str(data.get('id','')).strip()
            current=read_json(DATA/'modules.json', {'modules':[], 'connections':[]})
            module=next((m for m in current.get('modules',[]) if m.get('id')==module_id),None)
            if not module: return self.send_json(404, {'error':'Модуль не найден'})
            if module.get('source')!='local': return self.send_json(403, {'error':'Редактирование runtime доступно для локальных модулей. Для GitHub-модулей нужен проверенный адаптер.'})
            runtime_kind=str(data.get('runtime_kind','')).strip()
            if runtime_kind not in MODULE_RUNTIME_KINDS: return self.send_json(400, {'error':'Неизвестный встроенный тип модуля'})
            def parse_port_names(raw):
                names=[x.strip() for x in str(raw or '').split(',') if x.strip()][:30]
                if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}',name) for name in names): raise ValueError('Имена портов должны содержать латинские буквы, цифры, точку, дефис или подчёркивание.')
                if len(names)!=len(set(names)): raise ValueError('Имена портов должны быть уникальными.')
                return names
            try:
                input_names=parse_port_names(data.get('inputs','')); output_names=parse_port_names(data.get('outputs',''))
            except ValueError as e: return self.send_json(400, {'error':str(e)})
            manifest=module_runtime_manifest(module).copy()
            runtime={'kind':runtime_kind}
            if runtime_kind=='template': runtime['template']=str(data.get('template','{input}'))[:12000]
            if runtime_kind=='transform':
                operation=str(data.get('operation','strip'))
                if operation not in {'uppercase','lowercase','strip','json_parse','json_pretty'}: return self.send_json(400, {'error':'Неизвестная операция преобразования'})
                runtime['operation']=operation
            if runtime_kind=='ollama':
                runtime['system_prompt']=str(data.get('system_prompt',''))[:4000]
                runtime['model']=str(data.get('model',''))[:160]
                try: max_tokens=int(data.get('max_tokens',1024))
                except (TypeError,ValueError): max_tokens=1024
                runtime['max_tokens']=min(max(max_tokens,64),4096)
            manifest.update({'inputs':[{'name':name,'type':'text','required':False} for name in input_names],'outputs':[{'name':name,'type':'text'} for name in output_names],'runtime':runtime})
            manifest['version']=str(data.get('version',module.get('version','1.0.0')).strip()[:40] or '1.0.0')
            manifest['description']=str(data.get('description',module.get('description','')).strip()[:1000])
            folder=MODULES/module_id
            if not folder.is_dir() or folder.resolve().parent!=MODULES.resolve(): return self.send_json(400, {'error':'Не найдена локальная папка модуля'})
            previous_manifest=module_runtime_manifest(module)
            module.update({'version':manifest['version'],'description':manifest['description'],'manifest':manifest,'status':'draft','note':'Настройки runtime сохранены. Модуль выполняется только через встроенный безопасный исполнитель.'})
            try: current['connections']=validate_module_connections(current,current.get('connections',[]))
            except ValueError as e:
                module['manifest']=previous_manifest; module['version']=previous_manifest.get('version',module.get('version','1.0.0')); module['description']=previous_manifest.get('description',module.get('description',''))
                return self.send_json(400, {'error':'Изменение портов нарушит существующие связи: '+str(e)})
            write_json(folder/'module.json',manifest)
            write_json(DATA/'modules.json',current); log_event('module.update',module_id)
            return self.send_json(200, {'ok':True,'module':module})
        if path=='/api/modules/install':
            full_name=str(data.get('full_name','')).strip()
            if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',full_name): return self.send_json(400, {'error':'Некорректное имя репозитория'})
            try:
                repo_data=github_public_request('/repos/'+full_name)
                if repo_data.get('archived') or repo_data.get('disabled'): return self.send_json(400, {'error':'Архивный или отключённый репозиторий нельзя добавить'})
                current=read_json(DATA/'modules.json', {'modules':[], 'connections':[]})
                if any(m.get('source')==full_name for m in current.get('modules',[])): return self.send_json(409, {'error':'Этот репозиторий уже добавлен'})
                module_id=re.sub(r'[^a-z0-9_-]+','-',full_name.split('/')[-1].lower()).strip('-')[:60] or uuid.uuid4().hex[:8]
                if len(module_id)<2: module_id='m-'+module_id
                if any(m.get('id')==module_id for m in current.get('modules',[])): return self.send_json(409, {'error':'ID модуля уже занят другим источником'})
                manifest={'id':module_id,'name':full_name.split('/')[-1],'version':'0.0.0','description':repo_data.get('description') or 'Модуль из GitHub','author':full_name.split('/')[0],'license':(repo_data.get('license') or {}).get('spdx_id') or 'Не указана','repository':repo_data.get('html_url',''),'api_version':'1.0','inputs':[],'outputs':[],'capabilities':[],'permissions':[],'dependencies':[]}
                module={'id':module_id,'name':full_name.split('/')[-1],'description':repo_data.get('description') or 'Модуль из GitHub','created_at':datetime.datetime.now().astimezone().isoformat(timespec='seconds'),'source':full_name,'url':repo_data.get('html_url',''),'stars':repo_data.get('stargazers_count',0),'license':(repo_data.get('license') or {}).get('spdx_id') or 'Не указана','default_branch':repo_data.get('default_branch','main'),'status':'registered','trusted':False,'manifest':manifest,'installed_at':datetime.datetime.now().astimezone().isoformat(timespec='seconds'),'note':'Добавлен в каталог. Код не скачан и не запускается автоматически.'}
                current.setdefault('modules',[]).append(module); current.setdefault('connections',[]); write_json(DATA/'modules.json',current); write_json(MODULES/module['id']/'module.json',manifest); log_event('module.register',full_name)
                return self.send_json(201, {'ok':True,'module':module,'message':'Репозиторий добавлен в каталог. Перед установкой кода проверьте содержимое, лицензию и зависимости.'})
            except Exception as e: return self.send_json(400, {'error':str(e)})
        if path=='/api/modules/download':
            module_id=str(data.get('id','')).strip()
            current=read_json(DATA/'modules.json', {'modules':[], 'connections':[]})
            module=next((m for m in current.get('modules',[]) if m.get('id')==module_id),None)
            if not module: return self.send_json(404, {'error':'Модуль не найден'})
            source=str(module.get('source',''))
            if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',source): return self.send_json(400, {'error':'Для этого локального модуля исходники из GitHub недоступны'})
            request_github=github_request if os.environ.get('GITHUB_TOKEN') else github_public_request
            try:
                branch=str(module.get('default_branch') or 'main')
                tree=request_github('/repos/'+source+'/git/trees/'+urllib.parse.quote(branch,safe='')+'?recursive=1')
                if tree.get('truncated'): return self.send_json(400, {'error':'Репозиторий слишком велик для безопасной загрузки одним запросом'})
                allowed={'.py','.js','.mjs','.cjs','.ts','.json','.md','.txt','.yaml','.yml','.toml','.html','.css','.sh','.bat','.ps1','.go','.rs','.java','.c','.h','.cpp','.xml','.svg'}
                blocked={'node_modules','.git','.github','.venv','venv','dist','build','vendor','__pycache__'}
                candidates=[]
                for entry in tree.get('tree',[]):
                    rel=entry.get('path',''); parts=Path(rel).parts
                    if entry.get('type')!='blob' or not rel or len(parts)>8 or any(part in blocked for part in parts) or '..' in parts or rel.startswith('/') or any(re.search(r'[<>:"|?*]',part) or part.split('.')[0].upper() in {'CON','PRN','AUX','NUL','COM1','COM2','COM3','COM4','COM5','COM6','COM7','COM8','COM9','LPT1','LPT2','LPT3','LPT4','LPT5','LPT6','LPT7','LPT8','LPT9'} for part in parts): continue
                    if Path(rel).suffix.lower() not in allowed or int(entry.get('size',0))>200000: continue
                    candidates.append(entry)
                if len(candidates)>100: return self.send_json(400, {'error':'В репозитории больше 100 текстовых файлов-кандидатов; загрузка ограничена'})
                if sum(int(entry.get('size',0)) for entry in candidates)>2_000_000: return self.send_json(400, {'error':'Исходники превышают лимит загрузки 2 МБ'})
                folder=(MODULES/module_id/'source').resolve(); folder.mkdir(parents=True,exist_ok=True)
                total=0; saved=[]
                for entry in candidates:
                    blob=request_github('/repos/'+source+'/git/blobs/'+entry['sha'])
                    if blob.get('encoding')!='base64': continue
                    raw=base64.b64decode(blob.get('content',''))
                    total+=len(raw)
                    if total>2_000_000: return self.send_json(400, {'error':'Исходники превышают лимит загрузки 2 МБ'})
                    try: text_content=raw.decode('utf-8')
                    except UnicodeDecodeError: continue
                    target=(folder/entry['path']).resolve()
                    if not target.is_relative_to(folder): continue
                    target.parent.mkdir(parents=True,exist_ok=True); target.write_text(text_content,encoding='utf-8'); saved.append(entry['path'])
                module['status']='downloaded_unverified'; module['downloaded_files']=len(saved); module['note']='Исходники скачаны в папку source и не запускаются. Проверьте код, зависимости, лицензию и разрешения.'
                write_json(DATA/'modules.json',current); log_event('module.download',source)
                return self.send_json(200, {'ok':True,'module':module,'files':saved,'total_bytes':total,'message':'Исходники загружены и оставлены неисполняемыми для проверки.'})
            except Exception as e: return self.send_json(400, {'error':str(e)})
        if path=='/api/modules/run':
            try: return self.send_json(200, execute_module_graph(data))
            except ValueError as e:
                failed={'ok':False,'start_id':str(data.get('start_id','')),'error':str(e),'finished_at':datetime.datetime.now().astimezone().isoformat(timespec='seconds')}
                runs=read_json(DATA/'module-runs.json',[]); runs=runs if isinstance(runs,list) else []; write_json(DATA/'module-runs.json',([failed]+runs)[:100]); log_event('module.graph.failed',str(e))
                return self.send_json(400, {'error':str(e),'run':failed})
            except Exception as e:
                failed={'ok':False,'start_id':str(data.get('start_id','')),'error':str(e)[:240],'finished_at':datetime.datetime.now().astimezone().isoformat(timespec='seconds')}
                runs=read_json(DATA/'module-runs.json',[]); runs=runs if isinstance(runs,list) else []; write_json(DATA/'module-runs.json',([failed]+runs)[:100]); log_event('module.graph.failed',str(e))
                return self.send_json(502, {'error':'Ошибка выполнения схемы: '+str(e)[:240],'run':failed})
        if path=='/api/modules/connections':
            current=read_json(DATA/'modules.json', {'modules':[], 'connections':[]})
            try: current['connections']=validate_module_connections(current,data.get('connections',[]))
            except ValueError as e: return self.send_json(400, {'error':str(e)})
            write_json(DATA/'modules.json',current); log_event('module.connections','Связи модулей обновлены'); return self.send_json(200,current)
        if path=='/api/github/file':
            file_path=str(data.get('path','')).strip(); content=str(data.get('content','')); message=str(data.get('message','').strip() or 'Update '+file_path)[:200]
            if not file_path or file_path.startswith('/') or '..' in Path(file_path).parts: return self.send_json(400, {'error':'Некорректный путь файла'})
            if len(content)>800000: return self.send_json(400, {'error':'Файл слишком большой (максимум 800 КБ)'})
            try:
                existing=github_request('/repos/'+REPO+'/contents/'+urllib.parse.quote(file_path,safe='/'))
                expected_sha=str(data.get('sha',''))
                if expected_sha and expected_sha != existing.get('sha'): return self.send_json(409, {'error':'Файл изменился в GitHub после загрузки. Перечитайте его перед сохранением.'})
                import base64
                branch=github_request('/repos/'+REPO).get('default_branch','main')
                result=github_request('/repos/'+REPO+'/contents/'+urllib.parse.quote(file_path,safe='/'),'PUT',{'message':message,'content':base64.b64encode(content.encode()).decode(),'sha':existing['sha'],'branch':branch})
                log_event('github.file.save',file_path)
                return self.send_json(200, {'ok':True,'path':file_path,'commit':result.get('commit',{}).get('html_url'),'message':'Изменения сохранены в GitHub'})
            except Exception as e: return self.send_json(400, {'error':str(e)})
        if path=='/api/github/check':
            self.path='/api/github/check'; return self.do_GET()
        return self.send_json(404, {'error':'API endpoint not found'})
    def do_DELETE(self):
        path=urlparse(self.path).path
        if path.startswith('/api/') and not self.require_auth(): return
        if path.startswith('/api/icons/'):
            icon_id = urllib.parse.unquote(path[len('/api/icons/'):])
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,40}', icon_id):
                return self.send_json(400, {'error': 'Некорректный id'})
            if icon_id in {'cpu', 'hdd', 'monitor', 'ram', 'video'}:
                return self.send_json(403, {'error': 'Эта иконка зарезервирована для системной телеметрии'})
            target = ICONS_DIR / f'{icon_id}.svg'
            if target.exists():
                try:
                    target.unlink()
                except OSError as e:
                    return self.send_json(500, {'error': f'Не удалось удалить: {e}'})
            current = settings()
            icons = current.get('icons')
            if isinstance(icons, dict) and icon_id in icons:
                del icons[icon_id]
                current['icons'] = icons
                write_json(DATA / 'settings.json', current)
            log_event('icons.delete', f'Иконка {icon_id} удалена')
            return self.send_json(200, {'ok': True, 'id': icon_id})
        if path.startswith('/api/providers/'):
            pid=urllib.parse.unquote(path.split('/')[-1]); protected={'ollama','lm-studio','openai','anthropic','google-gemini','openrouter','groq'}
            if pid in protected: return self.send_json(403, {'error':'Встроенный провайдер не удаляется; его можно настроить'})
            items=read_json(PROVIDER_FILE,[]); items=items if isinstance(items,list) else []; updated=[x for x in items if x.get('id')!=pid]
            if len(updated)==len(items): return self.send_json(404, {'error':'Провайдер не найден'})
            write_json(PROVIDER_FILE,updated); log_event('provider.delete',pid); return self.send_json(200, {'ok':True})

        if path.startswith('/api/agents/') or path.startswith('/api/projects/') or path.startswith('/api/tasks/'):
            parts=path.strip('/').split('/'); kind=parts[1]; item_id=parts[2] if len(parts)>2 else ''
            if kind not in DOMAIN_FILES: return self.send_json(404, {'error':'Неизвестный раздел'})
            items=domain_items(kind); item=next((x for x in items if x.get('id')==item_id),None)
            if not item: return self.send_json(404, {'error':'Запись не найдена'})
            if kind=='agents' and item.get('system'): return self.send_json(403, {'error':'Системного агента нельзя удалить'})
            items.remove(item); save_domain(kind,items); log_event(kind[:-1]+'.delete',item.get('name',item.get('title','')))
            return self.send_json(200, {'ok':True})
        if path.startswith('/api/modules/'):
            module_id=path.split('/')[-1]
            if not re.fullmatch(r'[a-z0-9][a-z0-9._-]{1,79}',module_id): return self.send_json(400, {'error':'Некорректный ID модуля'})
            current=read_json(DATA/'modules.json', {'modules':[], 'connections':[]})
            item=next((m for m in current.get('modules',[]) if m.get('id')==module_id),None)
            if not item: return self.send_json(404, {'error':'Модуль не найден'})
            current['modules']=[m for m in current.get('modules',[]) if m.get('id')!=module_id]
            current['connections']=[x for x in current.get('connections',[]) if x.get('from')!=module_id and x.get('to')!=module_id]
            write_json(DATA/'modules.json',current)
            folder=MODULES/module_id
            if folder.exists() and folder.resolve().parent==MODULES.resolve(): shutil.rmtree(folder)
            log_event('module.remove',module_id); return self.send_json(200, {'ok':True})
        if path.startswith('/api/pages/'):
            pid=path.split('/')[-1]; current=pages(); item=next((p for p in current if p['id']==pid),None)
            if not item: return self.send_json(404, {'error':'Страница не найдена'})
            if item.get('system'): return self.send_json(403, {'error':'Системные страницы нельзя удалить'})
            write_json(PAGES/'index.json',[p for p in current if p['id']!=pid]); log_event('page.delete',item['title']); return self.send_json(200, {'ok':True})
        return self.send_json(404, {'error':'API endpoint not found'})
    def do_GET_HEAD(self): pass
if __name__=='__main__':
    settings(); pages(); log_event('server.start',f'http://{HOST}:{PORT}')
    server=ThreadingHTTPServer((HOST,PORT),Handler)
    print(f'PQlocalAgentOSv3: http://{HOST}:{PORT}  (Ctrl+C to stop)')
    try: server.serve_forever()
    except KeyboardInterrupt: print('\nServer stopped')
    finally: server.server_close()
