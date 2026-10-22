from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import urllib.parse
import json, os, re, urllib.request, urllib.error, datetime, uuid, shutil, base64

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / 'frontend'
DATA = ROOT / 'data'
MODULES = ROOT / 'modules'
PAGES = DATA / 'pages'
PORT = int(os.environ.get('PQ_PORT', '8765'))
HOST = '127.0.0.1'
REPO = os.environ.get('GITHUB_REPOSITORY', 'alexpikman/PQlocalAgentOSv3')
for p in (FRONTEND, DATA, PAGES, MODULES): p.mkdir(parents=True, exist_ok=True)
DEFAULT_SETTINGS = {'appearance': {'theme':'dark','accent':'#3b9dff','font':'Inter, Segoe UI, sans-serif','fontSize':14,'radius':12,'sidebarWidth':248,'pagePadding':28}, 'header': {'showBreadcrumbs':True,'showTitle':True,'showDescription':True,'title':'Рабочий стол','description':'Локальная платформа управления AI-системами','font':'Inter, Segoe UI, sans-serif','color':'#f2f1ff','letterSpacing':0,'transform':'none','paddingTop':24,'paddingRight':22,'paddingBottom':24}, 'navigation': {'compact':False,'menu':None}}
DEFAULT_PAGES = [{'id':'diagnostics','title':'Диагностика','description':'Проверка API, файловой системы и локальных AI-сервисов.','icon':'activity','content':'Результаты реальных проверок локального сервера.','system':True},{'id':'models','title':'Модели','description':'Состояние Ollama, доступные модели и проверочный запрос.','icon':'server','content':'Управление доступными локальными моделями.','system':True},{'id':'agents','title':'AI-агенты','description':'Реестр агентов, роли и назначенные модели.','icon':'blocks','content':'Управление агентами платформы.','system':True},{'id':'projects','title':'Проекты','description':'Рабочие пространства и пути к проектам.','icon':'files','content':'Управление проектами.','system':True},{'id':'tasks','title':'Задачи','description':'Создание задач, запуск через локальную модель и результаты.','icon':'activity','content':'Очередь задач и история выполнения.','system':True},{'id':'dashboard','title':'Рабочий стол','description':'Обзор локальной платформы и состояния системы.','icon':'layout-dashboard','content':'Добро пожаловать в PQlocalAgentOSv3. Здесь будет собираться управление локальными AI-системами.','system':True},{'id':'interface-settings','title':'Настройки интерфейса','description':'Управление общим оформлением и шапкой страниц.','icon':'sliders-horizontal','content':'Настройте оформление приложения через панель настроек.','system':True},{'id':'pages','title':'Страницы','description':'Создание и управление страницами приложения.','icon':'files','content':'Создавайте страницы без ручного редактирования файлов.','system':True},{'id':'github','title':'GitHub','description':'Состояние подключения к репозиторию.','icon':'github','content':'Подключите GitHub через переменную окружения GITHUB_TOKEN.','system':True},{'id':'system-log','title':'Журнал системы','description':'История действий и проверок.','icon':'activity','content':'Журнал событий приложения.','system':True},{'id':'menu-builder','title':'Конструктор меню','description':'Структура навигации и привязка пунктов к страницам и модулям.','icon':'list-tree','content':'Настройте меню приложения.','system':True},{'id':'modules','title':'Модули','description':'Установка, каталог и связи между модулями.','icon':'blocks','content':'Управляйте модульной системой.','system':True}]
def read_json(path, fallback):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError): return fallback
def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix+'.tmp'); tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8'); tmp.replace(path)
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
def log_event(action, detail=''):
    path=DATA/'events.json'; events=read_json(path, [])
    events.insert(0, {'time':datetime.datetime.now().astimezone().isoformat(timespec='seconds'),'action':action,'detail':str(detail)[:300]})
    write_json(path, events[:500])
OLLAMA_URL = os.environ.get('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')
DOMAIN_FILES = {'agents': DATA/'agents.json', 'projects': DATA/'projects.json', 'tasks': DATA/'tasks.json'}
AGENT_ROLES = ['MANAGER','ARCHITECT','ANALYST','DESIGNER','COPYWRITER','CODER','TESTER','DEVOPS']
def domain_items(kind):
    fallback=[{'id':'manager','name':'Менеджер проекта','role':'MANAGER','model':'','status':'idle','system':True,'description':'Координация проекта и распределение задач.'}] if kind=='agents' else []
    return read_json(DOMAIN_FILES[kind],fallback)
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
    check('Настройки интерфейса','ok' if (DATA/'settings.json').is_file() else 'warning','Файл настроек существует.' if (DATA/'settings.json').is_file() else 'Будет создан при первом сохранении.',DATA/'settings.json')
    check('Реестр страниц','ok' if (PAGES/'index.json').is_file() else 'warning','Файл страниц существует.' if (PAGES/'index.json').is_file() else 'Используются системные страницы по умолчанию.',PAGES/'index.json')
    check('Реестр модулей','ok' if (DATA/'modules.json').is_file() else 'warning','Файл реестра существует.' if (DATA/'modules.json').is_file() else 'Будет создан при первом изменении каталога.',DATA/'modules.json')
    check('Журнал событий','ok' if (DATA/'events.json').is_file() and os.access(DATA/'events.json',os.R_OK|os.W_OK) else 'warning','Журнал доступен.' if (DATA/'events.json').is_file() else 'Файл журнала появится после первого события.',DATA/'events.json')
    check('Реестр агентов','ok' if DOMAIN_FILES['agents'].is_file() else 'warning','Файл агентов существует.' if DOMAIN_FILES['agents'].is_file() else 'Будет создан при сохранении первого изменения.',DOMAIN_FILES['agents'])
    check('Реестр проектов','ok' if DOMAIN_FILES['projects'].is_file() else 'warning','Файл проектов существует.' if DOMAIN_FILES['projects'].is_file() else 'Проекты ещё не сохранялись.',DOMAIN_FILES['projects'])
    check('Реестр задач','ok' if DOMAIN_FILES['tasks'].is_file() else 'warning','Файл задач существует.' if DOMAIN_FILES['tasks'].is_file() else 'Задачи ещё не сохранялись.',DOMAIN_FILES['tasks'])
    schema_path=ROOT/'module-contract.schema.json'
    check('Контракт модулей','ok' if schema_path.is_file() else 'error','JSON-схема контракта доступна.' if schema_path.is_file() else 'Не найдена JSON-схема контракта.',schema_path)
    frontend_ok=all((FRONTEND/name).is_file() for name in ('index.html','app.js','style.css'))
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
def execute_module_graph(data):
    registry=read_json(DATA/'modules.json', {'modules':[], 'connections':[]})
    modules={m.get('id'):m for m in registry.get('modules',[]) if isinstance(m,dict) and m.get('id')}
    links=registry.get('connections',[])
    start=str(data.get('start_id','')).strip()
    if start not in modules: raise ValueError('Выберите стартовый модуль')
    outgoing={key:[] for key in modules}; incoming={key:[] for key in modules}
    for link in links:
        source=link.get('from'); target=link.get('to')
        if source in modules and target in modules:
            outgoing[source].append(target); incoming[target].append(source)
    reachable=set(); stack=[start]
    while stack:
        node=stack.pop()
        if node in reachable: continue
        reachable.add(node); stack.extend(outgoing[node])
    indegree={node:sum(1 for parent in incoming[node] if parent in reachable) for node in reachable}
    queue=[node for node in reachable if indegree[node]==0]; order=[]
    while queue:
        node=queue.pop(0); order.append(node)
        for target in outgoing[node]:
            if target in indegree:
                indegree[target]-=1
                if indegree[target]==0: queue.append(target)
    if len(order)!=len(reachable): raise ValueError('В схеме обнаружен цикл. Удалите циклическую связь.')
    if start in incoming and any(parent in reachable for parent in incoming[start]):
        raise ValueError('Стартовый модуль не может иметь входящих связей внутри выполняемой схемы')
    values={}; records=[]; prompt_input=str(data.get('input',''))[:12000]
    selected_model=str(data.get('model','')).strip()[:160]
    for module_id in order:
        module=modules[module_id]; manifest=module_runtime_manifest(module); runtime=manifest.get('runtime') if isinstance(manifest.get('runtime'),dict) else {}
        kind=str(runtime.get('kind','')).strip()
        if kind not in MODULE_RUNTIME_KINDS:
            raise ValueError('Модуль «'+str(module.get('name',module_id))+'» не имеет разрешённого встроенного типа исполнения. Внешние модули требуют отдельного адаптера.')
        parents=[parent for parent in incoming[module_id] if parent in reachable]
        incoming_value=prompt_input if module_id==start else (values[parents[0]] if len(parents)==1 else {parent:values[parent] for parent in parents})
        def to_text(value):
            if isinstance(value,str): return value
            return json.dumps(value,ensure_ascii=False,indent=2)
        if kind=='input': output=incoming_value if module_id!=start else prompt_input
        elif kind=='template':
            template=str(runtime.get('template','{input}'))[:12000]
            output=template.replace('{input}',to_text(incoming_value)).replace('{context}',str(data.get('context',''))[:8000]).replace('{task}',str(data.get('task',''))[:8000])
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
            if system_prompt: prompt='Инструкции модуля:\\n'+system_prompt+'\\n\\nВходные данные:\\n'+prompt
            result=ollama_request('/api/generate',{'model':model,'prompt':prompt,'stream':False,'options':{'num_predict':min(max(int(runtime.get('max_tokens',1024)),64),4096)}},timeout=300)
            output=result.get('response','')
        else: output=incoming_value
        values[module_id]=output
        records.append({'module_id':module_id,'name':module.get('name',module_id),'kind':kind,'status':'completed','output':output if isinstance(output,(str,int,float,bool,type(None),dict,list)) else str(output)})
    leaves=[node for node in reachable if not any(target in reachable for target in outgoing[node])]
    outputs={node:values[node] for node in leaves}
    result={'ok':True,'start_id':start,'executed':len(records),'order':order,'steps':records,'outputs':outputs,'result':next(iter(outputs.values())) if len(outputs)==1 else outputs,'finished_at':datetime.datetime.now().astimezone().isoformat(timespec='seconds')}
    log_event('module.graph.run',str(start)+' · '+str(len(records))+' модулей')
    write_json(DATA/'module-runs.json',([result]+read_json(DATA/'module-runs.json',[]))[:100])
    return result

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs): super().__init__(*args,directory=str(FRONTEND),**kwargs)
    def log_message(self, fmt, *args): pass
    def send_json(self, code, data):
        raw=json.dumps(data,ensure_ascii=False).encode(); self.send_response(code); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(raw))); self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(raw)
    def body(self):
        n=int(self.headers.get('Content-Length','0'))
        if n>1_000_000: raise ValueError('Payload too large')
        return json.loads(self.rfile.read(n).decode('utf-8') or '{}')
    def do_GET(self):
        path=urlparse(self.path).path
        if path=='/api/health': return self.send_json(200, {'ok':True,'app':'PQlocalAgentOSv3','host':HOST,'port':PORT,'time':datetime.datetime.now().astimezone().isoformat(timespec='seconds')})
        if path=='/api/diagnostics': return self.send_json(200, run_diagnostics())
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
                item.update({'role':role,'model':str(data.get('model','')).strip()[:160],'description':str(data.get('description','')).strip()[:1000],'status':'idle','system':False})
            elif kind=='projects': item.update({'path':str(data.get('path','')).strip()[:1000],'description':str(data.get('description','')).strip()[:1000],'status':'active'})
            else: item.update({'description':str(data.get('description','')).strip()[:5000],'model':str(data.get('model','')).strip()[:160],'agent_id':str(data.get('agent_id','')).strip()[:80],'status':'pending','result':'','error':''})
            items.insert(0,item); save_domain(kind,items); log_event(kind[:-1]+'.create',name)
            return self.send_json(201,item)
        if path.startswith('/api/tasks/') and path.endswith('/run'):
            task_id=path.split('/')[-2]; items=domain_items('tasks'); item=next((x for x in items if x.get('id')==task_id),None)
            if not item: return self.send_json(404, {'error':'Задача не найдена'})
            model=item.get('model') or str(data.get('model','')).strip()
            if not model: return self.send_json(400, {'error':'Укажите модель для запуска задачи'})
            item['status']='running'; item['model']=model; save_domain('tasks',items)
            agent=next((x for x in domain_items('agents') if x.get('id')==item.get('agent_id')),None)
            agent_context=('\\n\\nКонтекст назначенного агента: '+agent.get('name','')+'; роль: '+agent.get('role','')+'; описание: '+agent.get('description','')) if agent else ''
            prompt='Выполни задачу и верни результат на русском языке.'+agent_context+'\\n\\nНазвание: '+item.get('title','')+'\\n\\nОписание:\\n'+item.get('description','')
            try:
                result=ollama_request('/api/generate',{'model':model,'prompt':prompt,'stream':False,'options':{'num_predict':1024}},timeout=300)
                item['status']='completed'; item['result']=result.get('response',''); item['error']=''; item['finished_at']=datetime.datetime.now().astimezone().isoformat(timespec='seconds')
                log_event('task.completed',item.get('title','')); save_domain('tasks',items); return self.send_json(200,item)
            except Exception as e:
                item['status']='failed'; item['error']=str(e)[:300]; save_domain('tasks',items); log_event('task.failed',item.get('title',''))
                return self.send_json(502, {'error':'Не удалось выполнить задачу через Ollama: '+str(e)[:180],'task':item})
        if path.startswith('/api/agents/') or path.startswith('/api/projects/') or path.startswith('/api/tasks/'):
            parts=path.strip('/').split('/'); kind=parts[1]; item_id=parts[2] if len(parts)>2 else ''
            if kind not in DOMAIN_FILES: return self.send_json(404, {'error':'Неизвестный раздел'})
            items=domain_items(kind); item=next((x for x in items if x.get('id')==item_id),None)
            if not item: return self.send_json(404, {'error':'Запись не найдена'})
            if kind=='agents' and item.get('system'): return self.send_json(403, {'error':'Системный агент нельзя редактировать в этой версии API'})
            allowed={'agents':{'name','role','model','description'},'projects':{'name','path','description'},'tasks':{'title','description','model','agent_id'}}[kind]
            for key in allowed:
                if key in data: item[key]=str(data[key]).strip()[:5000]
            save_domain(kind,items); log_event(kind[:-1]+'.update',item.get('name',item.get('title','')))
            return self.send_json(200,item)
        if path=='/api/settings':
            allowed={'appearance','header','navigation'}; current=settings()
            for k,v in data.items():
                if k in allowed and isinstance(v,dict):
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
        if path=='/api/pages':
            title=str(data.get('title','')).strip()[:100]; desc=str(data.get('description','')).strip()[:300]; content=str(data.get('content','')).strip()[:20000]
            if not title: return self.send_json(400, {'error':'Укажите название страницы'})
            slug=re.sub(r'[^a-z0-9-]+','-',str(data.get('id') or title.lower())).strip('-')[:60] or uuid.uuid4().hex[:8]
            current=pages()
            if any(p['id']==slug for p in current): return self.send_json(409, {'error':'Страница с таким идентификатором уже существует'})
            item={'id':slug,'title':title,'description':desc,'icon':'file-text','content':content,'system':False}; current.append(item); write_json(PAGES/'index.json',current); log_event('page.create',title); return self.send_json(201,item)
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
            runtime_kind=str(data.get('runtime_kind','input')).strip()
            if runtime_kind not in MODULE_RUNTIME_KINDS: return self.send_json(400, {'error':'Неизвестный встроенный тип модуля'})
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
            manifest={'id':module_id,'name':name,'version':version,'description':description,'api_version':'1.0','inputs':inputs,'outputs':outputs,'runtime':runtime,'capabilities':[],'permissions':[],'dependencies':[]}
            folder=MODULES/module_id
            if folder.exists(): return self.send_json(409, {'error':'Папка модуля уже существует; проверьте каталог modules/'})
            folder.mkdir(parents=True,exist_ok=False)
            write_json(folder/'module.json',manifest)
            (folder/'README.md').write_text('# '+name+'\n\n'+description+'\n\nЛокальный каркас модуля PQlocalAgentOSv3. Добавьте реализацию после определения входов, выходов и разрешений. Код не запускается автоматически.\n',encoding='utf-8')
            module={'id':module_id,'name':name,'description':description,'version':version,'source':'local','url':'','stars':0,'license':'Не указана','status':'draft','trusted':False,'manifest':manifest,'note':'Локальный каркас создан. Реализация не запускается автоматически.'}
            current.setdefault('modules',[]).append(module); current.setdefault('connections',[]); write_json(DATA/'modules.json',current); log_event('module.create',module_id)
            return self.send_json(201, {'ok':True,'module':module})
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
                module={'id':module_id,'name':full_name.split('/')[-1],'description':repo_data.get('description') or 'Модуль из GitHub','source':full_name,'url':repo_data.get('html_url',''),'stars':repo_data.get('stargazers_count',0),'license':(repo_data.get('license') or {}).get('spdx_id') or 'Не указана','default_branch':repo_data.get('default_branch','main'),'status':'registered','trusted':False,'manifest':manifest,'installed_at':datetime.datetime.now().astimezone().isoformat(timespec='seconds'),'note':'Добавлен в каталог. Код не скачан и не запускается автоматически.'}
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
            except ValueError as e: return self.send_json(400, {'error':str(e)})
            except Exception as e: return self.send_json(502, {'error':'Ошибка выполнения схемы: '+str(e)[:240]})
        if path=='/api/modules/connections':
            connections=data.get('connections',[])
            if not isinstance(connections,list) or len(connections)>300: return self.send_json(400, {'error':'Некорректный список связей'})
            current=read_json(DATA/'modules.json', {'modules':[], 'connections':[]})
            ids={m.get('id') for m in current.get('modules',[])}
            seen=set()
            for link in connections:
                if not isinstance(link,dict) or link.get('from') not in ids or link.get('to') not in ids: return self.send_json(400, {'error':'Связь должна соединять зарегистрированные модули'})
                if link.get('from')==link.get('to'): return self.send_json(400, {'error':'Модуль не может быть соединён сам с собой'})
                pair=(link['from'],link['to'])
                if pair in seen: return self.send_json(400, {'error':'Повторяющаяся связь: '+pair[0]+' → '+pair[1]})
                seen.add(pair)
            adjacency={key:[] for key in ids}
            for link in connections: adjacency[link['from']].append(link['to'])
            visiting=set(); visited=set()
            def has_cycle(node):
                if node in visiting: return True
                if node in visited: return False
                visiting.add(node)
                for target in adjacency[node]:
                    if has_cycle(target): return True
                visiting.remove(node); visited.add(node); return False
            if any(has_cycle(node) for node in ids if node not in visited): return self.send_json(400, {'error':'Циклические связи запрещены. Постройте направленный ациклический граф.'})
            current['connections']=connections; write_json(DATA/'modules.json',current); log_event('module.connections','Связи модулей обновлены'); return self.send_json(200, current)
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
