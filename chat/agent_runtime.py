from __future__ import annotations
import json, re, sys, threading, uuid
from typing import Any, Callable
from chat.chat_events import EventHub
from chat.conversation_store import ConversationStore
from chat.provider_adapter import OllamaAdapter

_SECRET_KEY = re.compile(r"(?:token|secret|password|api[_-]?key|authorization|private[_-]?key|client[_-]?secret)", re.I)
_SECRET_TEXT = (
    re.compile(r"(?i)\b(?:api[_-]?key|token|password|secret|authorization)\b\s*[:=]\s*([^\s,;]+)"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"),
)

def _redact(value):
    """Best-effort redaction before durable events are written."""
    if isinstance(value, dict):
        return {str(key): ("[REDACTED]" if _SECRET_KEY.search(str(key)) else _redact(item)) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        result = value
        result = _SECRET_TEXT[0].sub(lambda m: m.group(0).split(m.group(1))[0] + "[REDACTED]", result)
        for pattern in _SECRET_TEXT[1:]: result = pattern.sub("[REDACTED]", result)
        return result
    return value


def _parse_structured_response(text: str) -> tuple[str, list[dict]]:
    """Convert JSON-style model output into plain text or a normalized tool call."""
    candidate = text.strip()
    if not candidate.startswith("{"):
        return text, []
    try:
        payload = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        return text, []
    if not isinstance(payload, dict):
        return text, []
    response_type = str(payload.get("type") or "").lower()
    if response_type in {"message", "assistant_message"}:
        return str(payload.get("text") or payload.get("content") or ""), []
    if response_type in {"tool_call", "tool-call"} or (
        isinstance(payload.get("name"), str)
        and ("parameters" in payload or "arguments" in payload)
    ):
        name = payload.get("name")
        arguments = payload.get("parameters", payload.get("arguments", {}))
        if isinstance(name, str) and isinstance(arguments, dict):
            return "", [{"id": "call_" + uuid.uuid4().hex,
                         "function": {"name": name, "arguments": arguments}}]
    if isinstance(payload.get("text"), str):
        return payload["text"], []
    return "Я получил ответ в неподдерживаемом структурированном формате.", []

class AgentRuntime:
    """Выполняет один ход агента. command_id дедуплицируется только в памяти процесса."""
    def __init__(self, store: ConversationStore, hub: EventHub, provider: OllamaAdapter,
                 tool_executor: Callable, agent_config: dict, max_steps: int = 12):
        self.store, self.hub, self.provider = store, hub, provider
        self.tool_executor, self.agent_config, self.max_steps = tool_executor, agent_config, max(1, int(max_steps))
        self._command_lock = threading.Lock()
        self._processed_commands: dict[str, dict[str, Any]] = {}
        self._active_lock = threading.Lock()
        self._active_tasks: dict[str, tuple[str, threading.Event]] = {}

    def _emit(self, cid: str, typ: str, payload: dict, *, task_id: str | None = None,
              message_id: str | None = None, tool_call_id: str | None = None) -> dict:
        event = self.store.append_event(cid, typ, payload, task_id=task_id, message_id=message_id, tool_call_id=tool_call_id)
        self.hub.publish(cid, event)
        return event

    def cancel_task(self, task_id: str) -> bool:
        with self._active_lock: item = self._active_tasks.get(task_id)
        if not item: return False
        item[1].set(); return True

    def _messages(self, cid: str) -> list[dict]:
        messages = []
        for event in self.store.read_all(cid):
            p = event.get("payload") or {}; typ = event.get("type")
            if typ == "user_message":
                messages.append({"role":"user","content":str(p.get("text",""))})
            elif typ == "assistant_message":
                item = {"role":"assistant","content":str(p.get("content",""))}
                if p.get("tool_calls"): item["tool_calls"] = p["tool_calls"]
                messages.append(item)
            elif typ == "tool_result":
                messages.append({"role":"tool","tool_call_id":str(event.get("tool_call_id","")),
                                 "content":str(p.get("result",p.get("message",p.get("error","Tool execution failed"))) )})
        return messages

    def run_turn(self, conversation_id: str, user_text: str | None, cancel_event: threading.Event, command_id: str, task_id: str | None = None) -> dict:
        if not isinstance(command_id, str) or not command_id.strip(): raise ValueError("command_id обязателен")
        with self._command_lock:
            if command_id in self._processed_commands: return dict(self._processed_commands[command_id])
            self._processed_commands[command_id] = {"status":"processing"}
        task_id = task_id or ("task_" + uuid.uuid4().hex)
        result: dict[str, Any] = {"task_id":task_id,"status":"failed"}
        try:
            with self._active_lock:
                if any(cid == conversation_id for cid, _ in self._active_tasks.values()):
                    result = {"task_id":task_id,"status":"busy"}
                    with self._command_lock: self._processed_commands[command_id] = result
                    return result
                self._active_tasks[task_id] = (conversation_id, cancel_event)
            if user_text is not None:
                self._emit(conversation_id,"user_message",{"text":_redact(str(user_text)),"command_id":command_id},task_id=task_id)
            self._emit(conversation_id,"turn_state",{"state":"thinking"},task_id=task_id)
            messages = self._messages(conversation_id)
            system = str(self.agent_config.get("system_prompt") or "").strip()
            tool_guidance = (
                "Если вызванный тобой инструмент вернул ошибку, это ошибка выполнения твоего действия, "
                "а не пользователя. Изучи результат инструмента, попробуй исправить аргументы или путь "
                "и повтори вызов, если это безопасно и уместно. Не вызывай read_file для предположительных путей и не ищи файл /home/user/info.txt или аналогичный файл по умолчанию, если пользователь явно не попросил прочитать его либо путь не указан в сообщении/контексте проекта. Перед read_file убедись, что конкретный путь обоснован текущей задачей. Если исправить нельзя, сообщи от первого "
                "лица: что именно тебе не удалось сделать и почему; не обвиняй пользователя."
            )
            messages.insert(0, {"role": "system", "content": (system + "\n\n" + tool_guidance).strip()})
            model = str(self.agent_config.get("model") or "").strip()
            tools = self.agent_config.get("tools") if isinstance(self.agent_config.get("tools"),list) else []
            approval_tools = set(self.agent_config.get("approval_required_tools") or [])
            for step in range(self.max_steps):
                if cancel_event.is_set():
                    self._emit(conversation_id,"turn_cancelled",{"reason":"user_cancelled"},task_id=task_id)
                    result={"task_id":task_id,"status":"cancelled"}; break
                self._emit(conversation_id,"turn_state",{"state":"streaming","step":step+1},task_id=task_id)
                msg_id="msg_"+uuid.uuid4().hex; text_parts=[]; raw_calls=[]; error=""
                for chunk in self.provider.stream_chat(model,messages,tools or None,should_cancel=cancel_event):
                    if cancel_event.is_set(): break
                    if chunk.kind=="text":
                        text_parts.append(chunk.text)
                    elif chunk.kind=="tool_calls": raw_calls.extend(chunk.tool_calls or [])
                    elif chunk.kind=="error": error=chunk.text or "Ошибка провайдера"; break
                    elif chunk.kind=="done": break
                if cancel_event.is_set():
                    self._emit(conversation_id,"turn_cancelled",{"reason":"user_cancelled"},task_id=task_id)
                    result={"task_id":task_id,"status":"cancelled"}; break
                full_text="".join(text_parts)
                full_text, structured_calls = _parse_structured_response(full_text)
                raw_calls.extend(structured_calls)
                calls=[]
                for raw in raw_calls:
                    fn=raw.get("function") or {}; name=fn.get("name"); args=fn.get("arguments",{})
                    if isinstance(args,str):
                        try: args=json.loads(args)
                        except json.JSONDecodeError: args=None
                    if not isinstance(name,str) or not isinstance(args,dict):
                        self._emit(conversation_id,"error",{"code":"invalid_tool_call","message":"Модель вернула некорректный вызов инструмента"},task_id=task_id); continue
                    calls.append({"type":"function","id":str(raw.get("id") or "call_"+uuid.uuid4().hex),
                                  "function":{"name":name,"arguments":args}})
                if full_text:
                    self._emit(conversation_id, "assistant_delta", {"text": _redact(full_text)},
                               task_id=task_id, message_id=msg_id)
                if full_text or calls:
                    self._emit(conversation_id,"assistant_message",{"content":_redact(full_text),"tool_calls":_redact(calls)},task_id=task_id,message_id=msg_id)
                    messages.append({"role":"assistant","content":full_text,**({"tool_calls":calls} if calls else {})})
                if error:
                    self._emit(conversation_id,"error",{"code":"provider_error","message":error[:1000]},task_id=task_id)
                    self._emit(conversation_id,"turn_completed",{"status":"failed"},task_id=task_id)
                    result={"task_id":task_id,"status":"failed"}; break
                if not calls:
                    final_text = full_text.strip()
                    has_side_effects = self.store.has_side_effects_in_turn(conversation_id, task_id)
                    has_claim = self._text_has_completion_claim(final_text)
                    requires_verification = has_side_effects or has_claim

                    if requires_verification and not self.store.has_recent_verification(conversation_id, task_id):
                        reason = (
                            "verification_required: "
                            + ("в ходе были изменения системы; " if has_side_effects else "")
                            + ("в ответе есть заявление о завершении; " if has_claim else "")
                            + "запусти run_tests или подтверди результат."
                        )
                        self._emit(conversation_id, "error",
                                   {"message": reason, "code": "verification_required"},
                                   task_id=task_id)
                        result={"task_id":task_id,"status":"failed","reason":"verification_required"}; break

                    kind = "verified" if requires_verification else "informational"
                    self._emit(conversation_id,"turn_completed",{"status":"completed","kind":kind},task_id=task_id)
                    result={"task_id":task_id,"status":"completed"}; break
                stop=False
                for call in calls:
                    fn=call["function"]; name=fn["name"]; args=fn["arguments"]; call_id=call["id"]
                    # Не выполняем распространённый выдуманный путь по умолчанию,
                    # если пользователь не просил читать именно этот файл.
                    if name == "read_file":
                        requested_path = str(args.get("path") or "").replace("\\", "/").rstrip("/")
                        latest_user_text = next(
                            (str(item.get("content") or "") for item in reversed(messages)
                             if item.get("role") == "user"),
                            "",
                        )
                        if requested_path.casefold() == "/home/user/info.txt" and not re.search(
                            r"(?:прочитай|прочти|открой|прочитать|прочтение|проверь\s+файл|покажи\s+содержимое|read|open|inspect).{0,100}(?:/home/user/info\.txt|\binfo\.txt\b)",
                            latest_user_text, re.I,
                        ):
                            skipped_result = json.dumps({
                                "error": "unrequested_default_path",
                                "message": "Чтение не выполнено: путь /home/user/info.txt не указан пользователем и не подтверждён контекстом задачи.",
                            }, ensure_ascii=False)
                            self._emit(
                                conversation_id, "tool_result",
                                {"status": "denied", "result": skipped_result},
                                task_id=task_id, tool_call_id=call_id,
                            )
                            messages.append({"role": "tool", "tool_call_id": call_id, "content": skipped_result})
                            continue
                    # Проверка allowed_paths (если агент ограничен проектом)
                    try:
                        from agent_tools import check_allowed_paths
                        allowed = (self.agent_config or {}).get("allowed_paths") or []
                        check_allowed_paths(name, args or {}, allowed)
                    except PermissionError as exc:
                        denied_result = f"Заблокировано политикой allowed_paths: {exc}"
                        self.store.append_event(
                            conversation_id, "tool_result",
                            {"tool_call_id": call_id, "status": "denied",
                             "result": denied_result},
                            task_id=task_id, tool_call_id=call_id,
                        )
                        self._emit(conversation_id, "tool_result",
                                   {"tool_call_id": call_id, "status": "denied",
                                    "result": denied_result},
                                   task_id=task_id, tool_call_id=call_id)
                        messages.append({"role": "tool", "tool_call_id": call_id,
                                         "content": denied_result})
                        continue  # переходим к следующему tool_call, не выполняем этот
                    self._emit(conversation_id,"tool_call",{"name":name,"arguments":_redact(args)},task_id=task_id,tool_call_id=call_id)
                    if name in approval_tools:
                        aid=self.store.create_approval(conversation_id,task_id,call_id,name,_redact(args),f"Агент запрашивает разрешение на инструмент «{name}».")
                        self._emit(conversation_id,"approval_required",{"approval_id":aid,"tool_name":name,"tool_call_id":call_id,"description":f"Разрешить инструмент «{name}»?"},task_id=task_id,tool_call_id=call_id)
                        self._emit(conversation_id,"turn_state",{"state":"waiting_approval"},task_id=task_id)
                        result={"task_id":task_id,"status":"waiting_approval","approval_id":aid}; stop=True; break
                    if cancel_event.is_set():
                        self._emit(conversation_id,"turn_cancelled",{"reason":"user_cancelled"},task_id=task_id)
                        result={"task_id":task_id,"status":"cancelled"}; stop=True; break
                    try:
                        raw_result=self.tool_executor(name,args)
                        if name == "run_tests":
                            verified = isinstance(raw_result, dict) and raw_result.get("exit_code") == 0 and not raw_result.get("error")
                            output = "\n".join(str(raw_result.get(key) or "") for key in ("stdout", "stderr", "error") if isinstance(raw_result, dict)).strip()
                            self._emit(conversation_id,"verification",{"checks":[{"name":"tests","status":"passed" if verified else "failed","output":_redact(output[:4000])}],"verified":verified},task_id=task_id,tool_call_id=call_id)
                        elif name in {"write_file", "move_file", "delete_file", "create_directory", "delete_directory", "run_command", "ssh_execute"}:
                            # Any subsequent write/command can invalidate an earlier test result.
                            self._emit(conversation_id,"verification",{"checks":[],"verified":False,"reason":"project_changed_after_verification","invalidated_by":name},task_id=task_id,tool_call_id=call_id)
                        serialized=json.dumps(_redact(raw_result),ensure_ascii=False,default=str)
                        if len(serialized)>12000: serialized=serialized[:12000]+"…[обрезано]"
                        tool_failed = isinstance(raw_result, dict) and bool(raw_result.get("error"))
                        self._emit(conversation_id, "tool_result",
                                   {"status": "error" if tool_failed else "completed", "result": serialized},
                                   task_id=task_id, tool_call_id=call_id)
                        messages.append({"role":"tool","tool_call_id":call_id,"content":serialized})
                    except Exception as exc:
                        if name == "run_tests":
                            self._emit(conversation_id,"verification",{"checks":[{"name":"tests","status":"failed","output":"Инструмент тестирования завершился исключением."}],"verified":False},task_id=task_id,tool_call_id=call_id)
                        elif name in {"write_file", "move_file", "delete_file", "create_directory", "delete_directory", "run_command", "ssh_execute"}:
                            self._emit(conversation_id,"verification",{"checks":[],"verified":False,"reason":"project_changed_after_verification","invalidated_by":name},task_id=task_id,tool_call_id=call_id)
                        print(f"[AgentRuntime] Инструмент {name}: {type(exc).__name__}: {exc}",file=sys.stderr)
                        tool_error = {"error": "tool_execution_failed",
                                      "message": f"Не удалось выполнить {name}: {type(exc).__name__}: {str(exc)[:500]}"}
                        serialized = json.dumps(_redact(tool_error), ensure_ascii=False)
                        self._emit(conversation_id, "tool_result",
                                   {"status": "error", "error": "tool_execution_failed",
                                    "message": "Инструмент не выполнен.", "result": serialized},
                                   task_id=task_id, tool_call_id=call_id)
                        messages.append({"role":"tool","tool_call_id":call_id,"content":serialized})
                if stop: break
            else:
                self._emit(conversation_id,"error",{"code":"step_limit","message":"Превышен максимальный лимит шагов агента"},task_id=task_id)
                self._emit(conversation_id,"turn_completed",{"status":"failed","reason":"step_limit"},task_id=task_id)
                result={"task_id":task_id,"status":"failed","reason":"step_limit"}
        except Exception as exc:
            print(f"[AgentRuntime] Ошибка задачи {task_id}: {type(exc).__name__}: {exc}",file=sys.stderr)
            try:
                self._emit(conversation_id,"error",{"code":"runtime_error","message":"Ошибка выполнения агента"},task_id=task_id)
                self._emit(conversation_id,"turn_completed",{"status":"failed"},task_id=task_id)
            except Exception as log_exc: print(f"[AgentRuntime] Не удалось записать ошибку: {log_exc}",file=sys.stderr)
            result={"task_id":task_id,"status":"failed"}
        finally:
            with self._active_lock: self._active_tasks.pop(task_id,None)
            with self._command_lock: self._processed_commands[command_id]=dict(result)
        return result


    def resolve_approval(self, conversation_id: str, approval_id: str, decision: str,
                         cancel_event: threading.Event, command_id: str) -> dict:
        """Resolve an approval, execute the pending tool if allowed, then resume the LLM turn."""
        if decision not in ("approved", "rejected"):
            raise ValueError('decision должен быть "approved" или "rejected"')
        approval = self.store.get_approval(conversation_id, approval_id)
        if approval is None:
            raise ValueError("Запрос подтверждения не найден")
        if approval.get("resolved_at"):
            return {"task_id": approval.get("task_id"), "status": "already_resolved"}
        approval = self.store.resolve_approval(conversation_id, approval_id, decision)
        task_id = str(approval.get("task_id") or "")
        tool_call_id = str(approval.get("tool_call_id") or "")
        tool_name = str(approval.get("tool_name") or "")
        arguments = approval.get("arguments") if isinstance(approval.get("arguments"), dict) else {}
        serialized = ""
        tool_status = "denied"
        verification = {"verified": True, "reason": "approval_rejected_no_change"}
        if decision == "approved":
            try:
                from agent_tools import check_allowed_paths
                allowed = (self.agent_config or {}).get("allowed_paths") or []
                check_allowed_paths(tool_name, arguments, allowed)
                raw_result = self.tool_executor(tool_name, arguments)
                serialized = json.dumps(_redact(raw_result), ensure_ascii=False, default=str)
                if len(serialized) > 12000:
                    serialized = serialized[:12000] + "…[обрезано]"
                failed = isinstance(raw_result, dict) and bool(raw_result.get("error"))
                tool_status = "error" if failed else "completed"
                if tool_name == "create_directory":
                    path_value = str(arguments.get("path") or "")
                    try:
                        from pathlib import Path
                        exists = bool(path_value) and Path(path_value).is_dir()
                    except (OSError, ValueError):
                        exists = False
                    verification = {
                        # A returned tool error confirms that this operation did not complete;
                        # allow the model to explain that error instead of trapping the turn.
                        "verified": bool(failed or exists),
                        "reason": "directory_creation_failed_no_change" if failed else ("directory_exists" if exists else "directory_not_created"),
                    }
                elif tool_name in {"write_file", "move_file", "delete_file", "delete_directory", "run_command", "ssh_execute"}:
                    verification = {"verified": False, "reason": "project_changed_after_verification", "invalidated_by": tool_name}
                if failed and tool_name != "create_directory":
                    verification = {"verified": False, "reason": "tool_execution_failed"}
            except Exception as exc:
                tool_status = "error"
                serialized = json.dumps({
                    "error": "tool_execution_failed",
                    "message": f"Не удалось выполнить {tool_name}: {type(exc).__name__}: {str(exc)[:500]}",
                }, ensure_ascii=False)
                verification = {"verified": tool_name == "create_directory", "reason": "tool_failed_no_change"}
        else:
            serialized = json.dumps({
                "status": "denied",
                "message": f"Пользователь отклонил выполнение инструмента «{tool_name}».",
            }, ensure_ascii=False)
        # _emit writes the durable event to ConversationStore before publishing it to EventHub.
        self._emit(conversation_id, "tool_result",
                   {"status": tool_status, "result": serialized,
                    **({"error": "tool_execution_failed"} if tool_status == "error" else {})},
                   task_id=task_id, tool_call_id=tool_call_id)
        self._emit(conversation_id, "approval_resolved",
                   {"approval_id": approval_id, "decision": decision,
                    "resolved_at": approval.get("resolved_at")},
                   task_id=task_id, tool_call_id=tool_call_id)
        self._emit(conversation_id, "verification",
                   {"checks": [{"name": "tool_outcome", "status": "passed" if verification.get("verified") else "failed",
                                "output": str(verification.get("reason", ""))}],
                    **verification},
                   task_id=task_id, tool_call_id=tool_call_id)
        if cancel_event.is_set():
            self._emit(conversation_id, "turn_cancelled", {"reason": "user_cancelled"}, task_id=task_id)
            return {"task_id": task_id, "status": "cancelled"}
        # Rebuild messages from the durable journal: the pending assistant tool_call and
        # its tool_result are now both present, so the provider can continue the same turn.
        return self.run_turn(conversation_id, None, cancel_event, command_id + ":resume", task_id=task_id)

    _CLAIM_RE = None

    @classmethod
    def _text_has_completion_claim(cls, text: str) -> bool:
        if not text:
            return False
        if cls._CLAIM_RE is None:
            import re as _re
            cls._CLAIM_RE = _re.compile(
                r"\b(готово|исправлено|удалено|добавлено|объединено|проверено|выполнено|сделано)\b"
                r"|\b(done|fixed|completed|resolved)\b",
                _re.IGNORECASE,
            )
        return bool(cls._CLAIM_RE.search(text))
