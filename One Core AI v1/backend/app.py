from __future__ import annotations
import json, mimetypes, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT=Path(__file__).resolve().parent.parent
WEB=ROOT/"frontend"; DATA=ROOT/"data"; CFG=ROOT/"config"/"settings.json"; HISTORY=DATA/"conversations.json"
DEFAULT={"provider":"ollama","base_url":"http://127.0.0.1:11434","model":"","temperature":0.7,"system_prompt":"Ты — полезный AI-ассистент. Отвечай точно и структурированно на языке пользователя."}
def read(path, fallback):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError): return fallback
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding="utf-8"); tmp.replace(path)
def config():
    return {**DEFAULT,**read(CFG,{})}
def request(url,payload=None,headers=None,timeout=20):
    data=None if payload is None else json.dumps(payload,ensure_ascii=False).encode()
    req=urllib.request.Request(url,data=data,headers=headers or {},method="GET" if data is None else "POST")
    return urllib.request.urlopen(req,timeout=timeout)

class Handler(BaseHTTPRequestHandler):
    server_version="OneCoreAI/1.0"
    def log_message(self,fmt,*args): print("[%s] %s"%(time.strftime("%H:%M:%S"),fmt%args))
    def json(self,obj,status=200):
        raw=json.dumps(obj,ensure_ascii=False).encode()
        self.send_response(status); self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(raw)
    def body(self):
        n=min(int(self.headers.get("Content-Length","0")),2000000)
        return json.loads(self.rfile.read(n).decode()) if n else {}
    def do_GET(self):
        path=urlparse(self.path).path
        if path=="/api/status": return self.json({"ok":True,"version":"0.1.0","port":9001})
        if path=="/api/config":
            c=config(); c.pop("api_key",None); return self.json(c)
        if path=="/api/history": return self.json(read(HISTORY,[]))
        if path=="/api/models": return self.models()
        relative="index.html" if path=="/" else path.lstrip("/")
        target=(WEB/relative).resolve()
        if WEB.resolve() not in target.parents or not target.is_file(): return self.send_error(404)
        raw=target.read_bytes(); kind=mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if kind.startswith("text/") or target.suffix in (".js",".css"): kind+="; charset=utf-8"
        self.send_response(200); self.send_header("Content-Type",kind); self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_POST(self):
        path=urlparse(self.path).path
        try:
            data=self.body()
            if path=="/api/config":
                c=config()
                for key in ("provider","base_url","model","temperature","system_prompt","api_key"):
                    if key in data: c[key]=data[key]
                c["base_url"]=str(c["base_url"]).rstrip("/"); write(CFG,c); return self.json({"ok":True})
            if path=="/api/history":
                item=data.get("conversation")
                if not isinstance(item,dict) or not item.get("id"): return self.json({"error":"Некорректный диалог"},400)
                items=[x for x in read(HISTORY,[]) if x.get("id")!=item["id"]]; items.insert(0,item); write(HISTORY,items[:100]); return self.json({"ok":True})
            if path=="/api/shutdown":
                self.json({"ok":True}); threading.Thread(target=self.server.shutdown,daemon=True).start(); return
            if path=="/api/chat": return self.chat(data)
            return self.json({"error":"Маршрут не найден"},404)
        except (BrokenPipeError,ConnectionResetError): return
        except Exception as exc:
            try: self.json({"error":str(exc)},500)
            except (BrokenPipeError,ConnectionResetError): pass
    def models(self):
        c=config(); base=c["base_url"].rstrip("/")
        try:
            if c["provider"]=="ollama":
                with request(base+"/api/tags") as r: items=json.loads(r.read()).get("models",[])
                models=[{"id":x["name"],"name":x["name"]} for x in items]
            else:
                with request(base+"/models",headers={"Authorization":"Bearer "+c.get("api_key","lm-studio")}) as r: items=json.loads(r.read()).get("data",[])
                models=[{"id":x["id"],"name":x["id"]} for x in items]
            self.json({"ok":True,"models":models,"provider":c["provider"]})
        except Exception as exc: self.json({"ok":False,"models":[],"error":str(exc)},502)
    def chat(self,data):
        c=config(); model=str(data.get("model") or c.get("model") or "").strip(); messages=data.get("messages",[])
        if not model: return self.json({"error":"Выбери модель в настройках подключения."},400)
        if not messages: return self.json({"error":"Пустое сообщение."},400)
        self.send_response(200); self.send_header("Content-Type","text/event-stream; charset=utf-8")
        self.send_header("Cache-Control","no-cache"); self.send_header("Connection","keep-alive"); self.end_headers()
        start=time.perf_counter()
        def emit(event):
            self.wfile.write(("data: "+json.dumps(event,ensure_ascii=False)+"\\n\\n").encode()); self.wfile.flush()
        try:
            full=[{"role":"system","content":c["system_prompt"]}]+messages
            if c["provider"]=="ollama":
                payload={"model":model,"messages":full,"stream":True,"options":{"temperature":float(c["temperature"])}}
                req=urllib.request.Request(c["base_url"].rstrip("/")+"/api/chat",data=json.dumps(payload,ensure_ascii=False).encode(),headers={"Content-Type":"application/json"})
                with urllib.request.urlopen(req,timeout=300) as response:
                    for line in response:
                        if not line.strip(): continue
                        item=json.loads(line); token=item.get("message",{}).get("content","")
                        if token: emit({"type":"token","text":token})
                        if item.get("done"):
                            count=item.get("eval_count"); duration=item.get("eval_duration")
                            emit({"type":"metrics","model":model,"prompt_tokens":item.get("prompt_eval_count"),"completion_tokens":count,"tokens_per_second":round(count/(duration/1e9),2) if count and duration else None,"latency_ms":round((time.perf_counter()-start)*1000)})
            else:
                payload={"model":model,"messages":full,"temperature":float(c["temperature"]),"stream":True,"stream_options":{"include_usage":True}}
                headers={"Content-Type":"application/json","Authorization":"Bearer "+c.get("api_key","lm-studio")}
                req=urllib.request.Request(c["base_url"].rstrip("/")+"/chat/completions",data=json.dumps(payload,ensure_ascii=False).encode(),headers=headers)
                with urllib.request.urlopen(req,timeout=300) as response:
                    for raw in response:
                        line=raw.decode().strip()
                        if not line.startswith("data:"): continue
                        value=line[5:].strip()
                        if value=="[DONE]": break
                        item=json.loads(value); choices=item.get("choices",[])
                        if choices:
                            token=choices[0].get("delta",{}).get("content","")
                            if token: emit({"type":"token","text":token})
                        usage=item.get("usage")
                        if usage: emit({"type":"metrics","model":model,"prompt_tokens":usage.get("prompt_tokens"),"completion_tokens":usage.get("completion_tokens"),"tokens_per_second":None,"latency_ms":round((time.perf_counter()-start)*1000)})
        except Exception as exc: emit({"type":"error","message":str(exc)})
        finally:
            try: emit({"type":"done"})
            except (BrokenPipeError,ConnectionResetError): pass

def main():
    for folder in (DATA,CFG.parent,ROOT/"logs"): folder.mkdir(parents=True,exist_ok=True)
    if not CFG.exists(): write(CFG,DEFAULT)
    server=ThreadingHTTPServer(("127.0.0.1",9001),Handler); server.daemon_threads=True
    print("One Core AI v1: http://127.0.0.1:9001")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
if __name__=="__main__": main()
