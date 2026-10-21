from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import urllib.parse
import json, os, re, urllib.request, urllib.error, datetime, uuid

ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / 'frontend'
DATA = ROOT / 'data'
PAGES = DATA / 'pages'
PORT = int(os.environ.get('PQ_PORT', '8765'))
HOST = '127.0.0.1'
REPO = os.environ.get('GITHUB_REPOSITORY', 'alexpikman/PQlocalAgentOSv3')
for p in (FRONTEND, DATA, PAGES): p.mkdir(parents=True, exist_ok=True)
DEFAULT_SETTINGS = {'appearance': {'theme':'dark','accent':'#8b7cff','font':'Inter, Segoe UI, sans-serif','fontSize':14,'radius':12,'sidebarWidth':248,'pagePadding':28}, 'header': {'showBreadcrumbs':True,'showTitle':True,'showDescription':True,'title':'Рабочий стол','description':'Локальная платформа управления AI-системами','font':'Inter, Segoe UI, sans-serif','color':'#f2f1ff','letterSpacing':0,'transform':'none','paddingTop':24,'paddingRight':22,'paddingBottom':24}, 'navigation': {'compact':False,'menu':None}}
DEFAULT_PAGES = [{'id':'dashboard','title':'Рабочий стол','description':'Обзор локальной платформы и состояния системы.','icon':'layout-dashboard','content':'Добро пожаловать в PQlocalAgentOSv3. Здесь будет собираться управление локальными AI-системами.','system':True},{'id':'interface-settings','title':'Настройки интерфейса','description':'Управление общим оформлением и шапкой страниц.','icon':'sliders-horizontal','content':'Настройте оформление приложения через панель настроек.','system':True},{'id':'pages','title':'Страницы','description':'Создание и управление страницами приложения.','icon':'files','content':'Создавайте страницы без ручного редактирования файлов.','system':True},{'id':'github','title':'GitHub','description':'Состояние подключения к репозиторию.','icon':'github','content':'Подключите GitHub через переменную окружения GITHUB_TOKEN.','system':True},{'id':'system-log','title':'Журнал системы','description':'История действий и проверок.','icon':'activity','content':'Журнал событий приложения.','system':True},{'id':'menu-builder','title':'Конструктор меню','description':'Структура навигации и привязка пунктов к страницам и модулям.','icon':'list-tree','content':'Настройте меню приложения.','system':True},{'id':'modules','title':'Модули','description':'Установка, каталог и связи между модулями.','icon':'blocks','content':'Управляйте модульной системой.','system':True}]
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
    if not p.exists(): write_json(p, DEFAULT_PAGES)
    return read_json(p, DEFAULT_PAGES)
def log_event(action, detail=''):
    path=DATA/'events.json'; events=read_json(path, [])
    events.insert(0, {'time':datetime.datetime.now().astimezone().isoformat(timespec='seconds'),'action':action,'detail':str(detail)[:300]})
    write_json(path, events[:500])
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
        if path=='/api/settings': return self.send_json(200, settings())
        if path=='/api/pages': return self.send_json(200, pages())
        if path=='/api/log': return self.send_json(200, read_json(DATA/'events.json', []))
        if path=='/api/modules':
            return self.send_json(200, read_json(DATA/'modules.json', {'modules':[], 'connections':[]}))
        if path=='/api/github/search':
            q=parse_qs(urlparse(self.path).query).get('q',[''])[0].strip()[:120]
            if len(q)<2: return self.send_json(400, {'error':'Введите минимум 2 символа для поиска'})
            try:
                result=github_request('/search/repositories?q='+urllib.parse.quote(q+' in:name,description,readme')+'&sort=stars&order=desc&per_page=12')
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
        if path=='/api/modules/install':
            full_name=str(data.get('full_name','')).strip()
            if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',full_name): return self.send_json(400, {'error':'Некорректное имя репозитория'})
            try:
                repo_data=github_request('/repos/'+full_name)
                if repo_data.get('archived') or repo_data.get('disabled'): return self.send_json(400, {'error':'Архивный или отключённый репозиторий нельзя добавить'})
                current=read_json(DATA/'modules.json', {'modules':[], 'connections':[]})
                if any(m.get('source')==full_name for m in current.get('modules',[])): return self.send_json(409, {'error':'Этот репозиторий уже добавлен'})
                module={'id':re.sub(r'[^a-z0-9_-]+','-',full_name.split('/')[-1].lower()).strip('-')[:60] or uuid.uuid4().hex[:8],'name':full_name.split('/')[-1],'description':repo_data.get('description') or 'Модуль из GitHub','source':full_name,'url':repo_data.get('html_url',''),'stars':repo_data.get('stargazers_count',0),'license':(repo_data.get('license') or {}).get('spdx_id') or 'Не указана','default_branch':repo_data.get('default_branch','main'),'status':'registered','trusted':False,'installed_at':datetime.datetime.now().astimezone().isoformat(timespec='seconds'),'note':'Добавлен в каталог. Код не скачан и не запускается автоматически.'}
                current.setdefault('modules',[]).append(module); current.setdefault('connections',[]); write_json(DATA/'modules.json',current); log_event('module.register',full_name)
                return self.send_json(201, {'ok':True,'module':module,'message':'Репозиторий добавлен в каталог. Перед установкой кода проверьте содержимое, лицензию и зависимости.'})
            except Exception as e: return self.send_json(400, {'error':str(e)})
        if path=='/api/modules/connections':
            connections=data.get('connections',[])
            if not isinstance(connections,list) or len(connections)>300: return self.send_json(400, {'error':'Некорректный список связей'})
            current=read_json(DATA/'modules.json', {'modules':[], 'connections':[]})
            ids={m.get('id') for m in current.get('modules',[])}
            for link in connections:
                if not isinstance(link,dict) or link.get('from') not in ids or link.get('to') not in ids: return self.send_json(400, {'error':'Связь должна соединять зарегистрированные модули'})
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
