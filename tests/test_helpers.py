import argparse
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helper = load_script("codex_tui")
installer = load_script("install")


class FakeSocket:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.sent = []
        self.timeouts = []

    def send(self, raw):
        self.sent.append(json.loads(raw))

    def recv(self, timeout):
        self.timeouts.append(timeout)
        value = next(self.responses)
        if isinstance(value, BaseException):
            raise value
        return json.dumps(value)


def response(request_id, result):
    return {"id": request_id, "result": result}


def native_ack(recipient):
    return {"isError": False,
            "content": [{"type": "text", "text": json.dumps({"threadId": recipient})}]}


def native_registry(tools):
    return {"data": [{"name": "codex_tui", "runtimeStatus": "connected", "tools": tools}]}


class NativeHelperTests(unittest.TestCase):
    def test_rpc_ignores_notifications_and_unrelated_responses(self):
        ws = FakeSocket([{"method": "thread/status/changed"}, response(99, {}), response(3, {"ok": True})])
        self.assertEqual(helper.rpc(ws, 3, "example", {}), {"ok": True})
        self.assertEqual(len(ws.sent), 1)

    def test_sender_acceptance_keeps_action_unverified(self):
        ws = FakeSocket([response(3, native_ack("recipient"))])
        result = helper.send_handoff(ws, "context", "recipient", "Inspect the schema.")
        self.assertEqual(result, {"senderAccepted": True, "recipientThreadId": "recipient",
                                  "recipientActionVerified": False})
        params = ws.sent[0]["params"]
        self.assertEqual(params["threadId"], "context")
        self.assertEqual(params["arguments"], {"threadId": "recipient", "prompt": "Inspect the schema."})
        self.assertLessEqual(ws.timeouts[0], 45)

    def test_wrong_recipient_is_unknown(self):
        ws = FakeSocket([response(3, native_ack("another-recipient"))])
        with self.assertRaises(helper.DeliveryUnknown):
            helper.send_handoff(ws, "context", "recipient", "Inspect.")

    def test_missing_acknowledgment_is_unknown(self):
        ws = FakeSocket([response(3, {"isError": False, "content": []})])
        with self.assertRaises(helper.DeliveryUnknown):
            helper.send_handoff(ws, "context", "recipient", "Inspect.")

    def test_conflicting_acknowledgments_are_unknown(self):
        result = native_ack("recipient")
        result["structuredContent"] = {"threadId": "another-recipient"}
        ws = FakeSocket([response(3, result)])
        with self.assertRaises(helper.DeliveryUnknown):
            helper.send_handoff(ws, "context", "recipient", "Inspect.")

    def test_structured_acknowledgment(self):
        ws = FakeSocket([response(3, {"isError": False, "structuredContent": {"threadId": "recipient"}})])
        self.assertTrue(helper.send_handoff(ws, "context", "recipient", "Inspect.")["senderAccepted"])

    def test_native_rejection_cannot_be_success(self):
        ws = FakeSocket([response(3, {"isError": True, "content": []})])
        with self.assertRaises(helper.NativeToolError):
            helper.send_handoff(ws, "context", "recipient", "Inspect.")

    def test_lost_acknowledgment_never_retries(self):
        for error in (TimeoutError("timeout"), ConnectionError("closed"), KeyboardInterrupt()):
            with self.subTest(error=type(error).__name__):
                ws = FakeSocket([error])
                with self.assertRaises(helper.DeliveryUnknown):
                    helper.send_handoff(ws, "context", "recipient", "Inspect.")
                self.assertEqual(len(ws.sent), 1)

    def test_rpc_error_after_send_is_unknown(self):
        ws = FakeSocket([{"id": 3, "error": {"code": -1, "message": "request failed"}}])
        with self.assertRaises(helper.DeliveryUnknown):
            helper.send_handoff(ws, "context", "recipient", "Inspect.")

    def test_prompt_limit_counts_utf8_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "message.txt"
            path.write_text("éé", encoding="utf-8")
            tool = {"inputSchema": {"properties": {"prompt": {"maxLength": 3}}}}
            with self.assertRaises(ValueError):
                helper.read_prompt(path, tool)
            tool["inputSchema"]["properties"]["prompt"]["maxLength"] = 4
            self.assertEqual(helper.read_prompt(path, tool), "éé")

    def test_blank_invalid_utf8_and_missing_limit_cannot_send(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "message.txt"
            tool = {"inputSchema": {"properties": {"prompt": {"maxLength": 1000}}}}
            for data in (b"", b" \n", b"\xff"):
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    helper.read_prompt(path, tool)
            path.write_text("Inspect.")
            with self.assertRaises(ValueError):
                helper.read_prompt(path, {})

    def test_read_only_registry_cannot_send(self):
        ws = FakeSocket([response(1, {}), response(2, native_registry({"list_threads": {}}))])
        args = argparse.Namespace(context_thread="context", command="send")
        with self.assertRaisesRegex(RuntimeError, "unavailable"):
            helper.run(ws, args)
        self.assertFalse(any(item.get("method") == "mcpServer/tool/call" for item in ws.sent))

    def test_disconnected_context_cannot_claim_tools(self):
        ws = FakeSocket([response(2, {"data": []})])
        with self.assertRaisesRegex(RuntimeError, "not connected"):
            helper.context_tools(ws, "context")

    def test_archive_pagination_preserves_native_cursor(self):
        ws = FakeSocket([response(1, {}), response(2, native_registry({"list_archived_threads": {}})),
                         response(3, {"content": []})])
        args = argparse.Namespace(context_thread="context", command="archived", limit=7,
                                  cursor="opaque/native+cursor=")
        helper.run(ws, args)
        self.assertEqual(ws.sent[-1]["params"]["arguments"],
                         {"limit": 7, "cursor": "opaque/native+cursor="})


class InstallerTests(unittest.TestCase):
    def test_installed_skill_keeps_recovery_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "skill"
            installer.install(ROOT, destination)
            for name in ("SKILL.md", "agents/openai.yaml", "requirements.txt",
                         "scripts/codex_tui.py", "references/native-sender-recovery.md",
                         "examples/workflows.md"):
                self.assertEqual((ROOT / name).read_bytes(), (destination / name).read_bytes())
            self.assertFalse((destination / ".git").exists())
            self.assertFalse((destination / "README.md").exists())
            self.assertFalse(list(destination.rglob("__pycache__")))

    def test_existing_installation_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "skill"
            destination.mkdir()
            sentinel = destination / "SKILL.md"
            sentinel.write_text("Existing local changes")
            with self.assertRaises(FileExistsError):
                installer.install(ROOT, destination)
            self.assertEqual(sentinel.read_text(), "Existing local changes")

    def test_dangling_destination_symlink_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "skill"
            destination.symlink_to(Path(directory) / "missing")
            with self.assertRaises(FileExistsError):
                installer.install(ROOT, destination)
            self.assertTrue(destination.is_symlink())


if __name__ == "__main__":
    unittest.main()
