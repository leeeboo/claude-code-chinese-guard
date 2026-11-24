import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from hooks.chinese_guard import needs_rewrite


ENGLISH = (
    "The installation finished successfully and the updated plugin checks final replies "
    "before Claude ends the current turn."
)
SCRIPT = Path(__file__).resolve().parents[1] / "hooks" / "chinese_guard.py"


class ProseTests(unittest.TestCase):
    def test_english_summary_with_chinese_heading(self):
        self.assertTrue(needs_rewrite(f"## 结果\n\n- {ENGLISH}"))

    def test_chinese_explanation_with_technical_terms(self):
        self.assertFalse(needs_rewrite(
            "已修复初始化偶发失败的问题。现在 Claude Code 会先读取本地配置，再启动插件。"
            "GitHub Actions 的 Python 测试也已通过，升级前可先用 `claude --version` 检查版本。"
        ))

    def test_traditional_chinese_and_extension_han(self):
        self.assertFalse(needs_rewrite(
            "外掛載入成功，可以在新的對話中檢查最終回覆。"
            "也會保留測試內容中的英文引文。\n" + ENGLISH
        ))
        boundary_han = "𠮷" * (2 * len(ENGLISH.split()))
        self.assertFalse(needs_rewrite(f"{boundary_han}\n{ENGLISH}"))
        self.assertTrue(needs_rewrite(f"{boundary_han[1:]}\n{ENGLISH}"))

    def test_short_status_and_empty_message(self):
        for message in ("Done. All tests passed.", "👍", ""):
            with self.subTest(message=message):
                self.assertFalse(needs_rewrite(message))

    def test_fenced_code_and_quoted_english(self):
        for marker in ("```", "~~~", "````"):
            with self.subTest(marker=marker):
                message = f"原文如下\n\n{marker}text\n{ENGLISH}\n{marker}\n\n> {ENGLISH}"
                self.assertFalse(needs_rewrite(message))

    def test_unclosed_fence_does_not_expose_code(self):
        self.assertFalse(needs_rewrite(f"如图\n\n```text\n{ENGLISH}"))

    def test_shorter_fence_does_not_close_longer_fence(self):
        self.assertFalse(needs_rewrite(f"````markdown\n```\n{ENGLISH}\n````"))

    def test_english_after_fence_is_checked(self):
        self.assertTrue(needs_rewrite(f"```sh\nls\n```\n\n{ENGLISH}"))

    def test_inline_code_links_and_image_alt(self):
        url = "https://example.org/the/installation/finished/successfully/with/a/very/long/path"
        message = (
            f"这里是 `echo {ENGLISH}`，以及 ``含有 `引号` 的 {ENGLISH}``。\n"
            f"[文档]({url})、[参考][reference]、{url}\n"
            f"![{ENGLISH}]({url})\n\n[reference]: {url} \"{ENGLISH}\""
        )
        self.assertFalse(needs_rewrite(message))

    def test_visible_english_link_label_is_checked(self):
        self.assertTrue(needs_rewrite(f"[{ENGLISH}](https://example.org)"))

    def test_raw_json_is_allowed_but_json_with_english_prose_is_checked(self):
        for data in ({"body": ENGLISH}, [ENGLISH]):
            payload = json.dumps(data)
            with self.subTest(payload=payload):
                self.assertFalse(needs_rewrite(payload))
                self.assertTrue(needs_rewrite(f"{payload}\n\n{ENGLISH}"))

    def test_full_width_latin_is_recognized(self):
        full_width = "".join(chr(ord(char) + 0xFEE0) if char.isalpha() else char for char in ENGLISH)
        self.assertTrue(needs_rewrite(full_width))


class HookTests(unittest.TestCase):
    def run_hook(self, payload, disabled=False):
        env = os.environ.copy()
        env.update({
            "CLAUDE_CHINESE_GUARD_DISABLE": "1" if disabled else "0",
            "LC_ALL": "C",
            "PYTHONUTF8": "0",
        })
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=payload.encode("utf-8"),
            capture_output=True,
            env=env,
            check=True,
            timeout=5,
        )
        self.assertEqual(result.stderr, b"")
        return result.stdout.decode("utf-8")

    def test_stop_blocks_once_and_does_not_echo_reply(self):
        event = {
            "hook_event_name": "Stop",
            "stop_hook_active": False,
            "last_assistant_message": ENGLISH,
            "transcript_path": "/does-not-exist/transcript.jsonl",
        }
        result = json.loads(self.run_hook(json.dumps(event)))
        self.assertEqual(result["decision"], "block")
        self.assertIn("用中文重写", result["reason"])
        self.assertNotIn(ENGLISH, result["reason"])
        event["stop_hook_active"] = True
        self.assertEqual(self.run_hook(json.dumps(event)), "")

    def test_missing_or_unexpected_hook_input_fails_open(self):
        for payload in ("", "{broken", "[]", "{}", '{"hook_event_name":"Stop"}'):
            with self.subTest(payload=payload):
                self.assertEqual(self.run_hook(payload), "")
        for changes in (
            {"hook_event_name": "SubagentStop"},
            {"stop_hook_active": "false"},
            {"last_assistant_message": []},
        ):
            event = {
                "hook_event_name": "Stop",
                "stop_hook_active": False,
                "last_assistant_message": ENGLISH,
            }
            with self.subTest(changes=changes):
                self.assertEqual(self.run_hook(json.dumps(event | changes)), "")

    def test_environment_switch_allows_english(self):
        event = {"hook_event_name": "Stop", "stop_hook_active": False, "last_assistant_message": ENGLISH}
        self.assertEqual(self.run_hook(json.dumps(event), disabled=True), "")

    def test_utf8_payload_can_pass_in_the_c_locale(self):
        event = {"hook_event_name": "Stop", "stop_hook_active": False, "last_assistant_message": "已完成。"}
        self.assertEqual(self.run_hook(json.dumps(event, ensure_ascii=False)), "")
