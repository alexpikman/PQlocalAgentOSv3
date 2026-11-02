const $=s=>document.querySelector(s);const state={provider:"ollama",config:{},messages:[],id:crypto.randomUUID(),title:"Новый диалог",busy:false,files:[]};
async function api(url,options={}){const r=await fetch(url,{...options,headers:{"Content-Type":"application/json",...(options.headers||{})}});const d=await r.json();if(!r.ok)throw Error(d.error||("HTTP "+r.status));return d}
function setConnection(ok,t){$("#connection").className="connection "+(ok?"online":"offline");$("#connection span").textContent=t}
function setModel(m){$("#modelName").textContent=m||"Модель не выбрана";$("#monitorModel").textContent=m||"Не выбрана"}
function showView(v){["chat","browser","terminal","operations","plugins","tasks"].forEach(x=>$("#"+x+"View").hidden=x!==v);document.querySelectorAll("[data-view]").forEach(x=>x.classList.toggle("selected",x.dataset.view===v));if(v==="operations")loadLogs();if(v==="tasks")loadTasks();if(v==="terminal")loadTerminalHistory();if(v==="plugins")loadPlugins();if(v==="browser")browserStatus()}
async function load(){try{state.config=await api("/api/config");state.provider=state.config.provider;const appearance=state.config.appearance||{};document.documentElement.style.setProperty("--font-scale",(appearance.font_size||14)/14);document.documentElement.style.setProperty("--text-color",appearance.font_color||"#30435e");$("#providerName").textContent=state.provider==="ollama"?"Ollama":"LM Studio";$("#providerLogo").textContent=state.provider==="ollama"?"O":"LM";$("#endpoint").textContent=state.config.base_url.replace(/^https?:\/\//,"");setModel(state.config.model);setConnection(true,"Настройки загружены")}catch(e){setConnection(false,"Сервер модели недоступен")}loadHistory();loadWorkspace()}
async function loadHistory(){try{const a=await api("/api/history");$("#history").innerHTML="";a.slice(0,12).forEach(x=>{const b=document.createElement("button");b.textContent=x.title||"Диалог";b.onclick=()=>openConversation(x);$("#history").append(b)})}catch(e){}}
function openConversation(x){state.id=x.id;state.title=x.title;state.messages=x.messages||[];$("#title").textContent=state.title;$("#messages").innerHTML="";state.messages.forEach(m=>addMessage(m.role,m.content))}
function newChat(){state.id=crypto.randomUUID();state.title="Новый диалог";state.messages=[];$("#title").textContent="Чем займёмся сегодня?";$("#messages").innerHTML='<div class="welcome"><div class="art"><div class="orbit one"></div><div class="orbit two"></div><div class="core"><i></i><i></i><i></i></div></div><label>ТВОЙ AI. ТВОИ ПРАВИЛА.</label><h2>Привет! Я на связи.</h2><p>Локальная модель, рабочие файлы и инструменты — в одном пространстве.</p></div>'}
function addMessage(role,text){const row=document.createElement("div");row.className="message "+role;const avatar=document.createElement("div");avatar.className="msg-avatar";avatar.textContent=role==="user"?"A":"OC";const bubble=document.createElement("div");bubble.className="bubble";const meta=document.createElement("div");meta.className="meta";meta.textContent=role==="user"?"ВЫ":"ONE CORE AI";const body=document.createElement("span");body.textContent=text;bubble.append(meta,body);row.append(avatar,bubble);$("#messages").append(row);$("#messages").scrollTop=$("#messages").scrollHeight;return body}
function flow(id){["stepReady","stepModel","stepDone"].forEach(x=>$("#"+x).classList.toggle("active",x===id))}
function metrics(d){if(d.tokens_per_second!=null)$("#speed").textContent=Number(d.tokens_per_second).toFixed(1);if(d.prompt_tokens!=null)$("#promptTokens").textContent=d.prompt_tokens;if(d.completion_tokens!=null)$("#completionTokens").textContent=d.completion_tokens;$("#metricsNote").textContent=d.latency_ms!=null?"Задержка: "+d.latency_ms+" мс":"Часть метрик недоступна у провайдера"}
async function persist(){try{await api("/api/history",{method:"POST",body:JSON.stringify({conversation:{id:state.id,title:state.title,updated_at:new Date().toISOString(),messages:state.messages}})});loadHistory()}catch(e){}}
async function send(text=$("#input").value.trim()){if(!text||state.busy)return;if(!state.config.model){location.href="/settings.html#models";return}const welcome=document.querySelector(".welcome");if(welcome)welcome.remove();state.busy=true;$("#send").disabled=true;$("#input").value="";const attached=state.files.map(f=>"\n\n[ФАЙЛ: "+f.name+"]\n"+f.content).join("");state.files=[];renderFiles();const content=text+attached;state.messages.push({role:"user",content});addMessage("user",content);const out=addMessage("assistant","");flow("stepModel");try{const r=await fetch("/api/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({model:state.config.model,messages:state.messages.slice(-30)})});if(!r.ok)throw Error((await r.json()).error);const reader=r.body.getReader(),decoder=new TextDecoder();let buffer="",answer="";while(true){const x=await reader.read();if(x.done)break;buffer+=decoder.decode(x.value,{stream:true});const chunks=buffer.split("\n\n");buffer=chunks.pop()||"";for(const chunk of chunks){const line=chunk.split("\n").find(x=>x.startsWith("data:"));if(!line)continue;const d=JSON.parse(line.slice(5));if(d.type==="token"){answer+=d.text;out.textContent=answer;$("#messages").scrollTop=$("#messages").scrollHeight}else if(d.type==="metrics")metrics(d);else if(d.type==="tool_start"){$("#browserMeta").textContent="AI использует браузер: "+(d.args.url||d.args.query||d.tool);$("#browserLiveCard").hidden=false}else if(d.type==="tool_result"){$("#browserMeta").textContent="AI просмотрел: "+d.title+" · "+d.url;$("#browserLiveCard").hidden=false}else if(d.type==="error")throw Error(d.message)}}if(!answer)answer="Модель завершила ответ без текста.";state.messages.push({role:"assistant",content:answer});if(state.messages.length===2){state.title=text.slice(0,42);$("#title").textContent=state.title}await persist();flow("stepDone");setConnection(true,"Модель активна")}catch(e){out.textContent="Ошибка: "+e.message;setConnection(false,"Ошибка запроса")}finally{state.busy=false;$("#send").disabled=false;setTimeout(()=>flow("stepReady"),1500)}}
function renderFiles(){$("#attachmentList").innerHTML="";state.files.forEach((f,i)=>{const b=document.createElement("button");b.className="attachment-chip";b.textContent=f.name+" ×";b.onclick=()=>{state.files.splice(i,1);renderFiles()};$("#attachmentList").append(b)})}
$("#fileInput").onchange=async e=>{for(const f of [...e.target.files]){if(f.size<=500000)state.files.push({name:f.name,content:await f.text()})}renderFiles();e.target.value=""};
$("#send").onclick=()=>send();$("#input").onkeydown=e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();send()}};$("#newChat").onclick=newChat;$("#modelButton").onclick=()=>location.href="/settings.html";
document.addEventListener("click",e=>{const p=e.target.closest("[data-prompt]");if(p)send(p.dataset.prompt);const nav=e.target.closest("[data-view]");if(nav)showView(nav.dataset.view)});
$("#workspaceButton").onclick=()=>location.href="/settings.html#knowledge";
async function loadWorkspace(){try{const d=await api("/api/workspace");$("#workspaceLabel").textContent=d.path;$("#terminalCwd").textContent=d.path}catch(e){}}
$("#terminalRun").onclick=async()=>{if(!$("#terminalConfirm").checked){$("#terminalOutput").textContent="Подтверди выполнение команды.";return}$("#terminalOutput").textContent="Выполнение…";try{const d=await api("/api/terminal/run",{method:"POST",body:JSON.stringify({command:$("#terminalCommand").value,confirmed:true})});$("#terminalOutput").textContent="Exit code: "+d.exit_code+"\n"+d.output}catch(e){$("#terminalOutput").textContent=e.message}};
async function loadLogs(){const rows=await api("/api/logs");$("#logList").innerHTML="";rows.filter(x=>JSON.stringify(x).toLowerCase().includes($("#logSearch").value.toLowerCase())).forEach(x=>{const el=document.createElement("article");el.className="log-entry";const b=document.createElement("b");b.textContent=x.action;const time=document.createElement("small");time.textContent=new Date(x.time).toLocaleString();const details=document.createElement("pre");details.textContent=JSON.stringify(x.details||{},null,2);el.append(b,time,details);$("#logList").append(el)})}
async function loadTerminalHistory(){try{const rows=await api("/api/logs");$("#terminalHistory").innerHTML="";rows.filter(x=>x.action==="terminal.powershell").slice(0,30).forEach(x=>{const e=document.createElement("article");e.className="terminal-history-row";const cmd=document.createElement("code");cmd.textContent=x.details.command;const date=document.createElement("small");date.textContent=new Date(x.time).toLocaleString();const out=document.createElement("pre");out.textContent=x.details.output_tail||"";e.append(cmd,date,out);$("#terminalHistory").append(e)})}catch(e){}}
$("#refreshLogs").onclick=loadLogs;$("#logSearch").oninput=loadLogs;
async function browserStatus(){try{const d=await api("/api/browser/status");$("#browserMeta").textContent=d.running?d.title+" · "+d.url:"Браузер не запущен. Требуется Playwright."}catch(e){}}
async function screenshot(){try{const d=await api("/api/browser/screenshot");if(d.image){const src="data:image/jpeg;base64,"+d.image;$("#browserImage").src=src;$("#browserImage").hidden=false;$("#browserEmpty").hidden=true;$("#browserLiveImage").src=src;$("#browserLiveCard").hidden=false;$("#browserMeta").textContent=d.status.title+" · "+d.status.url}}catch(e){}}
$("#browserGo").onclick=async()=>{try{const d=await api("/api/browser/navigate",{method:"POST",body:JSON.stringify({url:$("#browserUrl").value})});$("#browserMeta").textContent=d.title+" · "+d.url;screenshot()}catch(e){$("#browserMeta").textContent=e.message}};
$("#browserClose").onclick=async()=>{await api("/api/browser/close",{method:"POST"});$("#browserImage").hidden=true;$("#browserEmpty").hidden=false;browserStatus()};setInterval(()=>screenshot(),2500);$("#openBrowserView").onclick=e=>{e.preventDefault();showView("browser")};
async function loadPlugins(){const rows=await api("/api/plugins");$("#pluginGrid").innerHTML="";rows.forEach(p=>{const c=document.createElement("article");c.className="plugin-card";const h=document.createElement("h3");h.textContent=p.name;const d=document.createElement("p");d.textContent=p.description;const t=document.createElement("label");const ch=document.createElement("input");ch.type="checkbox";ch.checked=p.enabled;ch.onchange=()=>api("/api/plugins/toggle",{method:"POST",body:JSON.stringify({id:p.id,enabled:ch.checked})});t.append(ch,document.createTextNode(" Включён"));c.append(h,d,t);$("#pluginGrid").append(c)})}
$("#newPlugin").onclick=()=>$("#pluginModal").classList.add("open");$("#pluginClose").onclick=()=>$("#pluginModal").classList.remove("open");$("#pluginCreate").onclick=async()=>{try{await api("/api/plugins",{method:"POST",body:JSON.stringify({id:$("#pluginId").value,name:$("#pluginName").value,description:$("#pluginDescription").value,permissions:$("#pluginPermissions").value.split(",").map(x=>x.trim()).filter(Boolean)})});$("#pluginModal").classList.remove("open");loadPlugins()}catch(e){alert(e.message)}};
load();

async function loadTasks(){
 try{
  const data=await api("/api/tasks");
  const list=$("#taskList"),history=$("#taskHistory");
  list.innerHTML="";history.innerHTML="";
  $("#taskCount").textContent=data.tasks.length+" задач";
  if(!data.tasks.length){const empty=document.createElement("div");empty.className="task-empty";empty.textContent="Пока здесь пусто. Добавь задачу, чтобы не потерять её.";list.append(empty)}
  data.tasks.forEach(task=>{
   const card=document.createElement("article");card.className="task-item";
   const title=document.createElement("h3");title.textContent=task.title;
   const description=document.createElement("p");description.textContent=task.description||"Без дополнительного описания.";
   const created=document.createElement("small");created.textContent="Создано: "+new Date(task.created_at).toLocaleString();
   card.append(title,description,created);list.append(card);
  });
  if(!data.history.length){const empty=document.createElement("div");empty.className="task-empty";empty.textContent="История создания появится после добавления первой задачи.";history.append(empty)}
  data.history.forEach(item=>{
   const row=document.createElement("article");row.className="task-history-item";
   const title=document.createElement("b");title.textContent=item.title;
   const date=document.createElement("small");date.textContent=new Date(item.created_at).toLocaleString();
   row.append(title,date);history.append(row);
  });
 }catch(error){$("#taskList").textContent="Не удалось загрузить задачи: "+error.message}
}
$("#taskCreate").onclick=async()=>{
 const title=$("#taskTitle").value.trim(),description=$("#taskDescription").value.trim();
 if(!title){$("#taskTitle").focus();return}
 const button=$("#taskCreate");button.disabled=true;
 try{
  await api("/api/tasks",{method:"POST",body:JSON.stringify({title,description})});
  $("#taskTitle").value="";$("#taskDescription").value="";
  await loadTasks();
 }catch(error){alert(error.message)}
 finally{button.disabled=false}
};
