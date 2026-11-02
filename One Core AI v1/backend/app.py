from __future__ import annotations
import base64,ipaddress,json,mimetypes,os,queue,re,shutil,socket,subprocess,threading,time,urllib.request,uuid
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,parse_qs,quote_plus
ROOT=Path(__file__).resolve().parent.parent; WEB=ROOT/"frontend"; DATA=ROOT/"data"; CFG=ROOT/"config"/"settings.json"; HISTORY=DATA/"conversations.json"; AUDIT=DATA/"operations.jsonl"; PLUGINS=ROOT/"plugins"; TEMP=DATA/"temp"; TASKS=TEMP/"tasks.json"; TASK_HISTORY=TEMP/"creation_history.jsonl"
DEFAULT={"provider":"ollama","base_url":"http://127.0.0.1:11434","model":"","temperature":0.7,"model_parameters":{"top_p":0.9,"num_ctx":8192,"num_predict":2048,"repeat_penalty":1.1,"top_k":40,"min_p":0.05,"repeat_last_n":64,"num_thread":0,"num_gpu":-1,"seed":-1,"mirostat":0},"system_prompt":"Ты — полезный AI-ассистент. Отвечай точно и структурированно на языке пользователя.","behavior":{"role":"Универсальный AI-ассистент","verbosity":"balanced","language":"auto","reasoning":"deep","memory":True,"auto_plan":True,"ask_before_tools":True,"verify_changes":True,"max_steps":20},"appearance":{"font_family":"Manrope","font_size":14,"font_color":"#30435e"},"workspace":{"path":str(Path.home())},"tools":{"files":True,"terminal":False,"github":False,"ssh":False,"browser":True,"web_search":True,"git":True,"plugins":True},"remote":{"ssh_profiles":[]},"runtime":{"ollama_executable":""}}
CATALOG=[{"id":"files","name":"Файловая система","description":"Чтение и контекст рабочей папки, вложения.","risk":"read_write"},{"id":"terminal","name":"PowerShell","description":"Команды Windows и системная диагностика.","risk":"critical"},{"id":"git","name":"Git","description":"Статус, diff и операции с репозиторием.","risk":"write"},{"id":"github","name":"GitHub CLI","description":"Репозитории, issues, pull requests и workflows через gh.","risk":"remote"},{"id":"ssh","name":"SSH","description":"Удалённые серверы через OpenSSH и ключи.","risk":"critical"},{"id":"browser","name":"Виртуальный браузер","description":"Просмотр сайтов и браузерная автоматизация через Playwright.","risk":"network"},{"id":"web_search","name":"Поиск в интернете","description":"Поиск через поисковые сайты в браузере.","risk":"network"},{"id":"plugins","name":"Плагины","description":"Локальные расширения и декларативные разрешения.","risk":"write"}]
def read(p,f):
 try:return json.loads(p.read_text(encoding="utf-8"))
 except (OSError,json.JSONDecodeError):return f
def write(p,v):
 p.parent.mkdir(parents=True,exist_ok=True); t=p.with_suffix(p.suffix+".tmp"); t.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding="utf-8"); t.replace(p)
def config():
 c=DEFAULT.copy()
 for k,v in read(CFG,{}).items(): c[k]={**c[k],**v} if isinstance(c.get(k),dict) and isinstance(v,dict) else v
 return c
def redact(value):
 text=str(value)
 text=re.sub(r"(?i)(token|password|secret|api[_-]?key)(\s*[:=]\s*)([^\s,;]+)",r"\1\2[REDACTED]",text)
 text=re.sub(r"(?i)(--token|--password|--api-key)\s+\S+",r"\1 [REDACTED]",text)
 return text[:30000]
def audit(action,status="ok",details=None):
 DATA.mkdir(parents=True,exist_ok=True)
 with AUDIT.open("a",encoding="utf-8") as f:f.write(json.dumps({"id":str(uuid.uuid4()),"time":datetime.now(timezone.utc).isoformat(),"action":action,"status":status,"details":details or {}},ensure_ascii=False)+"\n")
def http(url,payload=None,headers=None,timeout=30):
 data=None if payload is None else json.dumps(payload,ensure_ascii=False).encode()
 h={"Content-Type":"application/json"} if data is not None else {};h.update(headers or {})
 return urllib.request.urlopen(urllib.request.Request(url,data=data,headers=h,method="GET" if data is None else "POST"),timeout=timeout)
def plugins():
 PLUGINS.mkdir(parents=True,exist_ok=True); return [read(p,{}) for p in sorted(PLUGINS.glob("*.json"))]
def project_context(root):
 try:
  root=root.expanduser().resolve();excluded={".git","node_modules",".venv","venv","__pycache__",".idea",".vscode","dist","build","logs","cache"};blocked=(".env","secret","token","credential","password","id_rsa","id_ed25519",".pem",".key","settings","auth","vault","private");allowed={".py",".js",".mjs",".cjs",".html",".css",".json",".md",".txt",".yml",".yaml",".toml",".ini",".bat",".ps1",".sh",".sql"};lines=[];total=0
  if not root.is_dir():return "Рабочая папка недоступна."
  for current,dirs,names in os.walk(root):
   dirs[:]=[d for d in dirs if d not in excluded and not d.startswith(".")]
   for name in names:
    path=Path(current)/name;rel=path.relative_to(root)
    if path.suffix.lower() not in allowed or any(x in name.lower() for x in blocked):continue
    try:
     if path.stat().st_size>30000:continue
     content=path.read_text(encoding="utf-8")
    except (OSError,UnicodeDecodeError):continue
    chunk="\n--- FILE: "+str(rel)+" ---\n"+content[:12000]
    if total+len(chunk)>70000:return "Корень: "+str(root)+"\nФайловый контекст ограничен 25 текстовыми файлами / 70k символов.\n"+"".join(lines)
    lines.append(chunk);total+=len(chunk)
    if len(lines)>=25:break
   if len(lines)>=25:break
  return "Корень: "+str(root)+"\nФайловый контекст ограничен 25 текстовыми файлами / 70k символов.\n"+"".join(lines) if lines else "В выбранной папке нет подходящих текстовых файлов."
 except Exception as e:return "Не удалось прочитать контекст проекта: "+str(e)
def task_data():
 tasks=read(TASKS,[])
 history=[]
 if TASK_HISTORY.exists():
  for line in TASK_HISTORY.read_text(encoding="utf-8").splitlines()[-1000:]:
   try:history.append(json.loads(line))
   except json.JSONDecodeError:pass
 return {"tasks":list(reversed(tasks)),"history":list(reversed(history))}
def complete_task(task_id):
 items=read(TASKS,[]);task=next((x for x in items if x.get("id")==task_id),None)
 if task is None:raise ValueError("Задача не найдена в журнале.")
 task["status"]="done";task["updated_at"]=datetime.now(timezone.utc).isoformat();write(TASKS,items)
 with TASK_HISTORY.open("a",encoding="utf-8") as stream:stream.write(json.dumps({"event":"status","id":task_id,"title":task["title"],"status":"done","created_at":task["updated_at"]},ensure_ascii=False)+"\n")
 audit("task.status",details={"id":task_id,"status":"done","source":"assistant"})
 return {"ok":True,"status":"done","task_id":task_id}
def logs():
 out=[]
 if AUDIT.exists():
  for line in AUDIT.read_text(encoding="utf-8").splitlines()[-500:]:
   try:out.append(json.loads(line))
   except json.JSONDecodeError:pass
 return list(reversed(out))
class Browser:
 def __init__(self):
  self.commands=queue.Queue();self.thread=threading.Thread(target=self.worker,daemon=True);self.thread.start()
 def call(self,method,*args,timeout=60):
  event=threading.Event();box={};self.commands.put((method,args,event,box))
  if not event.wait(timeout):raise TimeoutError("Браузер не ответил вовремя.")
  if "error" in box:raise RuntimeError(box["error"])
  return box.get("result")
 def worker(self):
  pw=browser=page=None
  while True:
   method,args,event,box=self.commands.get()
   try:
    if method=="navigate":
     url=args[0]
     if not re.match(r"^https?://",url,re.I):raise ValueError("Разрешены только http:// и https://")
     host=urlparse(url).hostname
     if not host:raise ValueError("Некорректный адрес.")
     try: addresses=[ipaddress.ip_address(host)]
     except ValueError: addresses=[ipaddress.ip_address(x[4][0]) for x in socket.getaddrinfo(host,None)]
     if any(not ip.is_global for ip in addresses):raise PermissionError("Виртуальный браузер может открывать только публичные адреса.")
     if not browser:
      from playwright.sync_api import sync_playwright
      pw=sync_playwright().start();browser=pw.chromium.launch(headless=True);page=browser.new_page(viewport={"width":1440,"height":900})
     page.goto(url,wait_until="domcontentloaded",timeout=45000);box["result"]={"running":True,"url":page.url,"title":page.title()}
    elif method=="status":box["result"]={"running":bool(page),"url":page.url if page else None,"title":page.title() if page else None}
    elif method=="screenshot":box["result"]=base64.b64encode(page.screenshot(type="jpeg",quality=65)).decode() if page else None
    elif method=="text":box["result"]=(page.locator("body").inner_text(timeout=10000)[:12000] if page else "")
    elif method=="close":
     if browser:browser.close()
     if pw:pw.stop()
     browser=page=pw=None;box["result"]={"ok":True}
    elif method=="stop": 
     if browser:browser.close()
     if pw:pw.stop()
     box["result"]={"ok":True};event.set();break
   except Exception as exc:box["error"]=str(exc)
   finally:event.set()
 def navigate(self,url):return self.call("navigate",url,timeout=60)
 def status(self):return self.call("status")
 def screenshot(self):return self.call("screenshot",timeout=30)
 def text(self):return self.call("text",timeout=30)
 def close(self):return self.call("close",timeout=30)
BROWSER=Browser()
class Handler(BaseHTTPRequestHandler):
 server_version="OneCoreAI/1.1"
 def log_message(self,fmt,*args):print("[%s] %s"%(time.strftime("%H:%M:%S"),fmt%args))
 def host_ok(self):
  if self.headers.get("Host") not in ("127.0.0.1:9001","localhost:9001"):self.send_error(403);return False
  return True
 def json(self,obj,status=200):
  raw=json.dumps(obj,ensure_ascii=False).encode();self.send_response(status);self.send_header("Content-Type","application/json; charset=utf-8");self.send_header("Content-Length",str(len(raw)));self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(raw)
 def body(self):
  n=int(self.headers.get("Content-Length","0"))
  if n>8_000_000:raise ValueError("Запрос больше 8 МБ")
  return json.loads(self.rfile.read(n).decode()) if n else {}
 def do_GET(self):
  if not self.host_ok():return
  path=urlparse(self.path).path
  try:
   if path=="/api/status":return self.json({"ok":True,"version":"0.2.0","port":9001})
   if path in ("/api/config","/api/settings"):
    c=config();c.pop("api_key",None);return self.json(c)
   if path=="/api/history":return self.json(read(HISTORY,[]))
   if path=="/api/tasks":return self.json(task_data())
   if path=="/api/models":return self.models()
   if path=="/api/tools":return self.json(CATALOG)
   if path=="/api/plugins":return self.json(plugins())
   if path=="/api/logs":return self.json(logs())
   if path=="/api/workspace":return self.workspace()
   if path=="/api/runtime/status":return self.runtime_status()
   if path=="/api/github/status":return self.github_status()
   if path=="/api/ssh/profiles":return self.json(config()["remote"].get("ssh_profiles",[]))
   if path=="/api/browser/status":return self.json(BROWSER.status())
   if path=="/api/browser/screenshot":return self.json({"image":BROWSER.screenshot(),"status":BROWSER.status()})
   rel="index.html" if path=="/" else path.lstrip("/"); target=(WEB/rel).resolve()
   if WEB.resolve() not in target.parents or not target.is_file():return self.send_error(404)
   raw=target.read_bytes();typ=mimetypes.guess_type(target.name)[0] or "application/octet-stream"
   if typ.startswith("text/") or target.suffix in (".js",".css"):typ+="; charset=utf-8"
   self.send_response(200);self.send_header("Content-Type",typ);self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
  except Exception as e:self.json({"error":str(e)},500)
 def do_POST(self):
  if not self.host_ok():return
  path=urlparse(self.path).path
  try:
   d=self.body()
   if path in ("/api/config","/api/settings"):
    c=config()
    for k in ("provider","base_url","model","temperature","system_prompt","model_parameters","behavior","appearance","workspace","tools","remote","runtime"):
     if k in d:c[k]=d[k]
    c["base_url"]=str(c["base_url"]).rstrip("/")
    
    write(CFG,c);audit("settings.save",details={"sections":list(d)});return self.json({"ok":True})
   if path=="/api/history":
    item=d.get("conversation")
    if not isinstance(item,dict) or not item.get("id"):return self.json({"error":"Некорректный диалог"},400)
    items=[x for x in read(HISTORY,[]) if x.get("id")!=item["id"]];items.insert(0,item);write(HISTORY,items[:200]);return self.json({"ok":True})
   if path=="/api/chat":return self.chat(d)
   if path=="/api/tasks/update":
    task_id=str(d.get("id",""));status=str(d.get("status",""))
    if status not in ("open","done","verified","failed"):return self.json({"error":"Недопустимый статус проверки."},400)
    items=read(TASKS,[]);item=next((x for x in items if x.get("id")==task_id),None)
    if not item:return self.json({"error":"Задача не найдена."},404)
    item["status"]=status;item["updated_at"]=datetime.now(timezone.utc).isoformat();write(TASKS,items)
    TEMP.mkdir(parents=True,exist_ok=True)
    with TASK_HISTORY.open("a",encoding="utf-8") as stream:stream.write(json.dumps({"event":"status","id":task_id,"title":item["title"],"status":status,"created_at":item["updated_at"]},ensure_ascii=False)+"\n")
    audit("task.status",details={"id":task_id,"status":status})
    return self.json({"ok":True,"task":item})
   if path=="/api/tasks":
    title=str(d.get("title","")).strip()[:160];description=str(d.get("description","")).strip()[:12000]
    if not title:return self.json({"error":"Укажи название задачи."},400)
    TEMP.mkdir(parents=True,exist_ok=True)
    item={"id":str(uuid.uuid4()),"title":title,"description":description,"status":"open","created_at":datetime.now(timezone.utc).isoformat()}
    items=read(TASKS,[]);items.append(item);write(TASKS,items)
    with TASK_HISTORY.open("a",encoding="utf-8") as stream:stream.write(json.dumps(item,ensure_ascii=False)+"\n")
    audit("task.created",details={"id":item["id"],"title":title})
    return self.json({"ok":True,"task":item},201)
   if path=="/api/models/pull":return self.pull(d)
   if path=="/api/models/delete":return self.delete_model(d)
   if path=="/api/models/load":return self.load_model(d)
   if path=="/api/models/unload":return self.unload_model(d)
   if path=="/api/runtime/start":return self.start_runtime()
   if path=="/api/workspace":return self.set_workspace(d)
   if path=="/api/terminal/run":return self.terminal(d)
   if path=="/api/ssh/profile":return self.ssh_profile(d)
   if path=="/api/ssh/run":return self.ssh_run(d)
   if path=="/api/github/run":return self.github_run(d)
   if path=="/api/git/run":return self.git_run(d)
   if path=="/api/browser/navigate":
    if not config()["tools"].get("browser"):return self.json({"error":"Браузер отключён в библиотеке возможностей."},403)
    return self.json(BROWSER.navigate(str(d.get("url",""))))
   if path=="/api/browser/close":BROWSER.close();audit("browser.close");return self.json({"ok":True})
   if path=="/api/plugins":return self.plugin_create(d)
   if path=="/api/plugins/toggle":return self.plugin_toggle(d)
   if path=="/api/tools/toggle":return self.tool_toggle(d)
   if path=="/api/shutdown":self.json({"ok":True});threading.Thread(target=self.server.shutdown,daemon=True).start();return
   return self.json({"error":"Маршрут не найден"},404)
  except (BrokenPipeError,ConnectionResetError):return
  except Exception as e:
   audit(path,"error",{"error":str(e)})
   try:self.json({"error":str(e)},500)
   except (BrokenPipeError,ConnectionResetError):pass
 def models(self):
  c=config();q=parse_qs(urlparse(self.path).query);provider=q.get("provider",[c["provider"]])[0];base=q.get("base_url",[c["base_url"]])[0].rstrip("/")
  try:
   if provider=="ollama":
    with http(base+"/api/tags") as r:items=json.loads(r.read()).get("models",[])
    models=[{"id":x["name"],"name":x["name"],"size":x.get("size")} for x in items]
   else:
    with http(base+"/models",headers={"Authorization":"Bearer "+c.get("api_key","lm-studio")}) as r:items=json.loads(r.read()).get("data",[])
    models=[{"id":x["id"],"name":x["id"]} for x in items]
   return self.json({"ok":True,"models":models,"provider":provider})
  except Exception as e:return self.json({"ok":False,"models":[],"error":str(e)},502)
 def events(self,fn):
  self.send_response(200);self.send_header("Content-Type","text/event-stream; charset=utf-8");self.send_header("Cache-Control","no-cache");self.send_header("Connection","keep-alive");self.end_headers()
  def emit(x):self.wfile.write(("data: "+json.dumps(x,ensure_ascii=False)+"\n\n").encode());self.wfile.flush()
  try:fn(emit)
  except Exception as e:
   audit("stream","error",{"error":str(e)})
   try:emit({"type":"error","message":str(e)})
   except (BrokenPipeError,ConnectionResetError):pass
  finally:
   try:emit({"type":"done"})
   except (BrokenPipeError,ConnectionResetError):pass
 def chat(self,d):
  c=config();model=str(d.get("model") or c["model"]).strip();messages=d.get("messages",[])
  if not model:return self.json({"error":"Выбери модель в настройках ИИ."},400)
  if not messages:return self.json({"error":"Пустое сообщение."},400)
  started=time.perf_counter()
  def run(emit):
   system=c["system_prompt"]+"\n\nПараметры поведения агента: "+json.dumps(c["behavior"],ensure_ascii=False)
   if c["tools"].get("files") and c.get("workspace",{}).get("include_files",True):system+="\n\nКОНТЕКСТ ВЫБРАННОГО ПРОЕКТА:\n"+project_context(Path(c["workspace"]["path"]))
   full=[{"role":"system","content":system}]+messages
   if c["provider"]=="ollama":
    available=[]
    if c["tools"].get("browser"):
     available.append({"type":"function","function":{"name":"browser_open","description":"Открыть публичную веб-страницу в виртуальном браузере. Пользователь видит текущую страницу в Live Monitor.","parameters":{"type":"object","properties":{"url":{"type":"string","description":"Полный URL с http:// или https://"}},"required":["url"]}}})
    if c["tools"].get("web_search"):
     available.append({"type":"function","function":{"name":"browser_search","description":"Найти информацию в интернете через поисковую систему. Открой результаты в виртуальном браузере и прочитай видимый текст страницы.","parameters":{"type":"object","properties":{"query":{"type":"string","description":"Поисковый запрос"}},"required":["query"]}}})
    available.append({"type":"function","function":{"name":"task_mark_done","description":"Отметить задачу из интерактивного журнала как выполненную после фактического выполнения и проверки результата.","parameters":{"type":"object","properties":{"task_id":{"type":"string"}},"required":["task_id"]}}})
    max_steps=max(1,min(30,int(c["behavior"].get("max_steps",20))))
    for step in range(max_steps):
     payload={"model":model,"messages":full,"stream":True,"options":{"temperature":float(c["temperature"]),**c.get("model_parameters",{})}}
     if available:payload["tools"]=available
     req=urllib.request.Request(c["base_url"]+"/api/chat",data=json.dumps(payload,ensure_ascii=False).encode(),headers={"Content-Type":"application/json"})
     tool_calls=[];assistant_text=""
     with urllib.request.urlopen(req,timeout=600) as r:
      for line in r:
       if not line.strip():continue
       x=json.loads(line);msg=x.get("message",{});token=msg.get("content","")
       if token:assistant_text+=token;emit({"type":"token","text":token})
       if msg.get("tool_calls"):tool_calls.extend(msg["tool_calls"])
       if x.get("done"):
        n=x.get("eval_count");dur=x.get("eval_duration")
        emit({"type":"metrics","model":model,"prompt_tokens":x.get("prompt_eval_count"),"completion_tokens":n,"tokens_per_second":round(n/(dur/1e9),2) if n and dur else None,"latency_ms":round((time.perf_counter()-started)*1000)})
     if not tool_calls:break
     full.append({"role":"assistant","content":assistant_text,"tool_calls":tool_calls})
     for call in tool_calls:
      fn=call.get("function",{});name=fn.get("name","");args=fn.get("arguments",{})
      if isinstance(args,str):
       try:args=json.loads(args)
       except json.JSONDecodeError:args={}
      emit({"type":"tool_start","tool":name,"args":args})
      try:
       if name=="browser_open":url=str(args.get("url",""))
       elif name=="browser_search":url="https://html.duckduckgo.com/html/?q="+quote_plus(str(args.get("query","")))
       else:raise ValueError("Инструмент не разрешён.")
       if not c["tools"].get("browser"):raise PermissionError("Виртуальный браузер выключен.")
       BROWSER.navigate(url);page_text=BROWSER.text()
       result={"url":BROWSER.status()["url"],"title":BROWSER.status()["title"],"page_text":page_text[:10000]}
       emit({"type":"tool_result","tool":name,"url":result["url"],"title":result["title"]})
      except Exception as exc:result={"error":str(exc)}
      full.append({"role":"tool","content":json.dumps(result,ensure_ascii=False),"tool_name":name})
    audit("ai.chat",details={"provider":c["provider"],"model":model,"browser_tools_enabled":bool(available)})
   else:
    payload={"model":model,"messages":full,"temperature":float(c["temperature"]),"top_p":float(c.get("model_parameters",{}).get("top_p",0.9)),"max_tokens":int(c.get("model_parameters",{}).get("num_predict",2048)),"frequency_penalty":max(0,min(2,float(c.get("model_parameters",{}).get("repeat_penalty",1.1))-1)),"stream":True,"stream_options":{"include_usage":True}}
    req=urllib.request.Request(c["base_url"]+"/chat/completions",data=json.dumps(payload).encode(),headers={"Content-Type":"application/json","Authorization":"Bearer "+c.get("api_key","lm-studio")})
    with urllib.request.urlopen(req,timeout=600) as r:
     for raw in r:
      line=raw.decode().strip()
      if not line.startswith("data:"):continue
      value=line[5:].strip()
      if value=="[DONE]":break
      x=json.loads(value);choices=x.get("choices",[])
      if choices:
       token=choices[0].get("delta",{}).get("content","")
       if token:emit({"type":"token","text":token})
      if x.get("usage"):emit({"type":"metrics","model":model,"prompt_tokens":x["usage"].get("prompt_tokens"),"completion_tokens":x["usage"].get("completion_tokens"),"tokens_per_second":None,"latency_ms":round((time.perf_counter()-started)*1000)})
    audit("ai.chat",details={"provider":c["provider"],"model":model,"browser_tools_enabled":False})
  return self.events(run)
 def pull(self,d):
  c=config();name=str(d.get("name","")).strip()
  if c["provider"]!="ollama" or not re.match(r"^[A-Za-z0-9_.:/-]{2,160}$",name):return self.json({"error":"Неверный провайдер или имя модели."},400)
  def run(emit):
   req=urllib.request.Request(c["base_url"]+"/api/pull",data=json.dumps({"name":name,"stream":True}).encode(),headers={"Content-Type":"application/json"})
   with urllib.request.urlopen(req,timeout=3600) as r:
    for line in r:
     x=json.loads(line);emit({"type":"progress","status":x.get("status"),"completed":x.get("completed"),"total":x.get("total")})
   audit("model.pull",details={"name":name})
  return self.events(run)
 def delete_model(self,d):
  c=config();name=str(d.get("name",""))
  if c["provider"]!="ollama":return self.json({"error":"Удаление доступно для Ollama."},400)
  with http(c["base_url"]+"/api/delete",{"name":name}) as r:r.read()
  audit("model.delete",details={"name":name});return self.json({"ok":True})
 def load_model(self,d):
  c=config();name=str(d.get("name") or c.get("model") or "").strip()
  if c["provider"]!="ollama":return self.json({"error":"Загрузка в память доступна через Ollama."},400)
  if not name:return self.json({"error":"Сначала выбери модель."},400)
  with http(c["base_url"]+"/api/generate",{"model":name,"prompt":"","stream":False,"keep_alive":"10m"}):pass
  audit("model.load",details={"name":name,"keep_alive":"10m"});return self.json({"ok":True,"model":name})
 def unload_model(self,d):
  c=config();name=str(d.get("name") or c.get("model") or "").strip()
  if c["provider"]!="ollama" or not name:return self.json({"error":"Укажи модель Ollama."},400)
  with http(c["base_url"]+"/api/generate",{"model":name,"prompt":"","stream":False,"keep_alive":0}):pass
  audit("model.unload",details={"name":name});return self.json({"ok":True,"model":name})
 def runtime_status(self):
  exe=config()["runtime"].get("ollama_executable") or shutil.which("ollama")
  if not exe:return self.json({"available":False,"running":False})
  p=subprocess.run([exe,"ps"],capture_output=True,text=True,timeout=8,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
  return self.json({"available":True,"running":p.returncode==0,"executable":exe,"output":p.stdout[:3000]})
 def start_runtime(self):
  exe=config()["runtime"].get("ollama_executable") or shutil.which("ollama")
  if not exe:return self.json({"error":"Ollama не найдена. Укажи путь к ollama.exe."},404)
  subprocess.Popen([exe,"serve"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0));audit("runtime.ollama.start");return self.json({"ok":True})
 def workspace(self):
  root=Path(config()["workspace"]["path"]).expanduser().resolve()
  items=[{"name":p.name,"directory":p.is_dir(),"size":p.stat().st_size if p.is_file() else None} for p in sorted(root.iterdir(),key=lambda x:(not x.is_dir(),x.name.lower()))[:250]] if root.is_dir() else []
  return self.json({"path":str(root),"exists":root.is_dir(),"items":items})
 def set_workspace(self,d):
  p=Path(str(d.get("path",""))).expanduser()
  if not p.is_dir():return self.json({"error":"Папка не существует."},400)
  c=config();c["workspace"]["path"]=str(p.resolve());write(CFG,c);audit("workspace.set",details={"path":str(p.resolve())});return self.workspace()
 def terminal(self,d):
  if not d.get("confirmed"):return self.json({"error":"Требуется явное подтверждение команды."},403)
  if not config()["tools"].get("terminal"):return self.json({"error":"PowerShell отключён в библиотеке возможностей."},403)
  command=str(d.get("command","")).strip();cwd=Path(config()["workspace"]["path"]).resolve();shell=shutil.which("pwsh") or shutil.which("powershell")
  if not command or len(command)>12000:return self.json({"error":"Пустая или слишком длинная команда."},400)
  if not shell:return self.json({"error":"PowerShell не найден."},404)
  p=subprocess.run([shell,"-NoLogo","-NoProfile","-NonInteractive","-Command",command],cwd=str(cwd),capture_output=True,text=True,timeout=120,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
  output=(p.stdout+"\n"+p.stderr)[-30000:];audit("terminal.powershell",details={"command":redact(command),"cwd":str(cwd),"exit_code":p.returncode,"output_tail":output[-3000:]})
  return self.json({"exit_code":p.returncode,"output":output,"cwd":str(cwd)})
 def ssh_profile(self,d):
  if not d.get("confirmed"):return self.json({"error":"Подтверди сохранение SSH-профиля."},403)
  name=str(d.get("name","")).strip();host=str(d.get("host","")).strip();user=str(d.get("user","")).strip();key=str(d.get("key_path","")).strip()
  if not name or not re.match(r"^[A-Za-z0-9.-]+$",host) or not re.match(r"^[A-Za-z0-9._-]+$",user):return self.json({"error":"Проверь имя, host и пользователя."},400)
  c=config();rows=[x for x in c["remote"].get("ssh_profiles",[]) if x["name"]!=name];rows.append({"name":name,"host":host,"user":user,"key_path":key});c["remote"]["ssh_profiles"]=rows;write(CFG,c);audit("ssh.profile.save",details={"name":name,"host":host});return self.json({"ok":True,"profiles":rows})
 def ssh_run(self,d):
  if not d.get("confirmed"):return self.json({"error":"SSH-команда требует подтверждения."},403)
  if not config()["tools"].get("ssh"):return self.json({"error":"SSH отключён."},403)
  prof=next((x for x in config()["remote"].get("ssh_profiles",[]) if x["name"]==d.get("profile")),None)
  if not prof:return self.json({"error":"Профиль не найден."},404)
  ssh=shutil.which("ssh")
  if not ssh:return self.json({"error":"OpenSSH Client не найден."},404)
  args=[ssh,"-o","BatchMode=yes","-o","ConnectTimeout=12"]
  if prof.get("key_path"):args+=["-i",prof["key_path"]]
  args += [prof["user"]+"@"+prof["host"],str(d.get("command",""))]
  p=subprocess.run(args,capture_output=True,text=True,timeout=90,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0));out=(p.stdout+"\n"+p.stderr)[-20000:]
  audit("ssh.execute",details={"profile":prof["name"],"command":redact(d.get("command","")),"exit_code":p.returncode,"output_tail":out[-3000:]});return self.json({"exit_code":p.returncode,"output":out})
 def github_status(self):
  gh=shutil.which("gh")
  if not gh:return self.json({"available":False,"authenticated":False,"message":"GitHub CLI (gh) не установлен."})
  p=subprocess.run([gh,"auth","status"],capture_output=True,text=True,timeout=12,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
  return self.json({"available":True,"authenticated":p.returncode==0,"message":(p.stdout+p.stderr)[:2500]})
 def github_run(self,d):
  if not d.get("confirmed"):return self.json({"error":"GitHub CLI требует подтверждения."},403)
  if not config()["tools"].get("github"):return self.json({"error":"GitHub CLI отключён."},403)
  groups={"status":["auth","status"],"repos":["repo","list"],"issues":["issue","list"],"prs":["pr","list"],"workflow":["workflow","list"]}
  action=str(d.get("action",""));gh=shutil.which("gh")
  if action not in groups:return self.json({"error":"Неизвестная команда."},400)
  if not gh:return self.json({"error":"GitHub CLI не установлен."},404)
  args=[gh]+groups[action]+[str(x)[:200] for x in d.get("args",[])[:8]]
  p=subprocess.run(args,cwd=config()["workspace"]["path"],capture_output=True,text=True,timeout=60,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0));out=(p.stdout+"\n"+p.stderr)[:20000]
  audit("github.cli",details={"action":action,"exit_code":p.returncode});return self.json({"exit_code":p.returncode,"output":out})
 def git_run(self,d):
  if not d.get("confirmed"):return self.json({"error":"Git-команда требует подтверждения."},403)
  if not config()["tools"].get("git"):return self.json({"error":"Git отключён в библиотеке возможностей."},403)
  actions={"status":["status","--short"],"diff":["diff","--stat"],"log":["log","-8","--oneline"],"branches":["branch","--all","--no-color"],"pull":["pull","--ff-only"]}
  action=str(d.get("action",""))
  if action not in actions:return self.json({"error":"Команда Git не разрешена."},400)
  git=shutil.which("git")
  if not git:return self.json({"error":"Git не найден."},404)
  cwd=config()["workspace"]["path"]
  p=subprocess.run([git]+actions[action],cwd=cwd,capture_output=True,text=True,timeout=90,creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
  output=(p.stdout+"\n"+p.stderr)[:20000];audit("git."+action,details={"cwd":cwd,"exit_code":p.returncode,"output":output[:3000]})
  return self.json({"exit_code":p.returncode,"output":output})
 def plugin_create(self,d):
  if not config()["tools"].get("plugins"):return self.json({"error":"Плагины отключены."},403)
  ident=re.sub(r"[^a-zA-Z0-9_-]","-",str(d.get("id","")).lower())[:48]
  if not ident:return self.json({"error":"Укажи ID."},400)
  p={"id":ident,"name":str(d.get("name",ident))[:100],"description":str(d.get("description",""))[:1000],"version":"0.1.0","enabled":False,"permissions":d.get("permissions",[]),"entry":"manifest-only","source":"local"}
  write(PLUGINS/(ident+".json"),p);audit("plugin.create",details={"id":ident});return self.json({"ok":True,"plugin":p})
 def plugin_toggle(self,d):
  ident=re.sub(r"[^a-zA-Z0-9_-]","-",str(d.get("id","")).lower());p=PLUGINS/(ident+".json")
  if not p.exists():return self.json({"error":"Плагин не найден."},404)
  x=read(p,{});x["enabled"]=bool(d.get("enabled"));write(p,x);audit("plugin.toggle",details={"id":ident,"enabled":x["enabled"]});return self.json({"ok":True})
 def tool_toggle(self,d):
  ident=str(d.get("id",""))
  if ident not in {x["id"] for x in CATALOG}:return self.json({"error":"Неизвестный инструмент."},404)
  c=config();c["tools"][ident]=bool(d.get("enabled"));write(CFG,c);audit("tool.toggle",details={"id":ident,"enabled":c["tools"][ident]});return self.json({"ok":True})
def main():
 for p in (DATA,CFG.parent,ROOT/"logs",PLUGINS):p.mkdir(parents=True,exist_ok=True)
 if not CFG.exists():write(CFG,DEFAULT)
 server=ThreadingHTTPServer(("127.0.0.1",9001),Handler);server.daemon_threads=True;print("One Core AI v1: http://127.0.0.1:9001")
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 finally:BROWSER.close();server.server_close()
if __name__=="__main__":main()
