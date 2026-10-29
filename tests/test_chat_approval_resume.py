import tempfile
import threading
import unittest
from pathlib import Path

from chat.agent_runtime import AgentRuntime
from chat.chat_events import EventHub
from chat.conversation_store import ConversationStore
from chat.provider_adapter import ProviderChunk
from agent_tools import normalize_tool_paths


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def stream_chat(self, model, messages, tools=None, should_cancel=None):
        self.calls.append({"model": model, "messages": messages, "tools": tools})
        yield from self.responses.pop(0)


class ApprovalResumeTests(unittest.TestCase):
    def test_approved_create_directory_executes_and_resumes_llm_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "111"
            store = ConversationStore(root / "conversations")
            conversation_id = store.create_conversation("approval test")
            provider = FakeProvider([
                [ProviderChunk("tool_calls", tool_calls=[{
                    "id": "call_create_dir",
                    "function": {"name": "create_directory", "arguments": {"path": str(target)}},
                }]), ProviderChunk("done")],
                [ProviderChunk("text", "Папка 111 создана."), ProviderChunk("done")],
            ])

            def execute(name, arguments):
                if name != "create_directory":
                    return {"error": "unexpected tool"}
                path = Path(arguments["path"])
                path.mkdir(parents=False, exist_ok=False)
                return {"path": str(path), "message": "Папка создана."}

            runtime = AgentRuntime(
                store, EventHub(), provider, execute,
                {"model": "test-model", "system_prompt": "Ты тестовый агент.",
                 "tools": [{"type": "function", "function": {"name": "create_directory"}}],
                 "approval_required_tools": ["create_directory"]},
            )
            initial = runtime.run_turn(conversation_id, "Создай папку 111", threading.Event(), "command-1")
            self.assertEqual(initial["status"], "waiting_approval")
            approval = next(
                event["payload"] for event in store.read_all(conversation_id)
                if event["type"] == "approval_required"
            )
            result = runtime.resolve_approval(
                conversation_id, approval["approval_id"], "approved", threading.Event(), "approval-command-1"
            )

            self.assertTrue(target.is_dir())
            self.assertEqual(result["status"], "completed")
            events = store.read_all(conversation_id)
            types = [event["type"] for event in events]
            self.assertLess(types.index("tool_result"), types.index("approval_resolved"))
            self.assertEqual(types[-1], "turn_completed")
            self.assertEqual(events[-1]["payload"]["status"], "completed")
            continuation_messages = provider.calls[1]["messages"]
            self.assertTrue(any(message.get("role") == "tool" and "Папка создана" in message.get("content", "")
                                for message in continuation_messages))

    def test_rejected_tool_is_not_executed_and_agent_turn_resumes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "must-not-exist"
            store = ConversationStore(root / "conversations")
            conversation_id = store.create_conversation("rejection test")
            provider = FakeProvider([
                [ProviderChunk("tool_calls", tool_calls=[{
                    "id": "call_create_dir",
                    "function": {"name": "create_directory", "arguments": {"path": str(target)}},
                }]), ProviderChunk("done")],
                [ProviderChunk("text", "Я не создавал папку, поскольку вы отклонили действие."), ProviderChunk("done")],
            ])
            calls = []

            def execute(name, arguments):
                calls.append(name)
                Path(arguments["path"]).mkdir()
                return {"path": arguments["path"]}

            runtime = AgentRuntime(
                store, EventHub(), provider, execute,
                {"model": "test-model", "system_prompt": "Ты тестовый агент.",
                 "tools": [{"type": "function", "function": {"name": "create_directory"}}],
                 "approval_required_tools": ["create_directory"]},
            )
            initial = runtime.run_turn(conversation_id, "Создай папку", threading.Event(), "command-2")
            self.assertEqual(initial["status"], "waiting_approval")
            approval = next(
                event["payload"] for event in store.read_all(conversation_id)
                if event["type"] == "approval_required"
            )
            result = runtime.resolve_approval(
                conversation_id, approval["approval_id"], "rejected", threading.Event(), "approval-command-2"
            )

            self.assertFalse(target.exists())
            self.assertEqual(calls, [])
            self.assertEqual(result["status"], "completed")
            self.assertTrue(any(event["type"] == "approval_resolved" and event["payload"]["decision"] == "rejected"
                                for event in store.read_all(conversation_id)))


    def test_chat_mode_does_not_require_verification_for_completion_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ConversationStore(Path(tmp) / "conversations")
            conversation_id = store.create_conversation("chat verification gate")
            provider = FakeProvider([[ProviderChunk("text", "Готово, я помог с вопросом."), ProviderChunk("done")]])
            runtime = AgentRuntime(
                store, EventHub(), provider, lambda *_: {"ok": True},
                {"model": "test-model", "system_prompt": "Ты тестовый агент.", "mode": "chat"},
            )
            result = runtime.run_turn(conversation_id, "Ответь на вопрос", threading.Event(), "chat-no-verification")
            self.assertEqual(result["status"], "completed")
            self.assertFalse(any(
                event["type"] == "error" and event.get("payload", {}).get("code") == "verification_required"
                for event in store.read_all(conversation_id)
            ))

    def test_project_relative_paths_are_resolved_inside_allowed_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            for raw in ("chat/username.txt", "./chat/username.txt", "/chat/username.txt"):
                normalized = normalize_tool_paths("write_file", {"path": raw}, [str(root)])
                self.assertEqual(Path(normalized["path"]), root / "chat" / "username.txt")

    def test_project_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            with self.assertRaises(PermissionError):
                normalize_tool_paths("write_file", {"path": "../outside.txt"}, [str(root)])

    def test_unrequested_default_info_file_read_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = ConversationStore(root / "conversations")
            conversation_id = store.create_conversation("default path guard")
            provider = FakeProvider([
                [ProviderChunk("tool_calls", tool_calls=[{
                    "id": "call_read_default",
                    "function": {"name": "read_file", "arguments": {"path": "/home/user/info.txt"}},
                }]), ProviderChunk("done")],
                [ProviderChunk("text", "Чем могу помочь?"), ProviderChunk("done")],
            ])
            calls = []
            def execute(name, arguments):
                calls.append((name, arguments))
                return {"error": "Файл не найден."}
            runtime = AgentRuntime(
                store, EventHub(), provider, execute,
                {"model": "test-model", "system_prompt": "Не читай файлы без запроса.",
                 "tools": [{"type": "function", "function": {"name": "read_file"}}]},
            )
            result = runtime.run_turn(
                conversation_id, "Привет, как дела?", threading.Event(), "default-path-command"
            )
            self.assertEqual(result["status"], "completed")
            self.assertEqual(calls, [])
            events = store.read_all(conversation_id)
            self.assertFalse(any(
                event["type"] == "tool_call" and event.get("payload", {}).get("name") == "read_file"
                for event in events
            ))
            self.assertTrue(any(
                event["type"] == "tool_result"
                and "unrequested_default_path" in str(event.get("payload", {}).get("result", ""))
                for event in events
            ))


if __name__ == "__main__":
    unittest.main()
