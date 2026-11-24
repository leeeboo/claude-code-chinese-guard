"""Check user-facing prose from the Claude Code Stop hook."""

import json
import os
import re
import sys
import unicodedata


MIN_LATIN_WORDS = 12
REWRITE_REASON = (
    "最终回复的说明主要使用了英文。请只用中文重写给用户的说明，保留事实、"
    "命令、代码、链接、文件名和需要原样交付的引文。"
    "如果用户明确要求其他语言，按用户的要求回答。请沿用已有结果，直接给出最终回复。"
)

FENCE = re.compile(r"^ {0,3}(`{3,}(?!`)(?=[^`]*$)|~{3,})(.*)$")
QUOTE = re.compile(r"^ {0,3}>")
LINK_DEFINITION = re.compile(r"^ {0,3}\[[^\[\]]+\]:\s*")
INLINE_CODE = re.compile(r"(?<!`)(`+)(?!`).*?(?<!`)\1(?!`)")
IMAGE = re.compile(r"!\[[^\[\]\n]*\](?:\([^\n)]*\)|\[[^\[\]\n]*\])")
LINK = re.compile(r"\[([^\[\]\n]+)\](?:\([^\n)]*\)|\[[^\[\]\n]*\])")
URL = re.compile(r"(?:https?://|mailto:|www\.)[^\s<>\[\]()]+", re.IGNORECASE)
LATIN_WORD = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿĀ-ž]+(?:['’][A-Za-zÀ-ÖØ-öø-ÿĀ-ž]+)*")
HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\U00020000-\U000323af]")


def prose_lines(markdown):
    fence = None
    for line in markdown.splitlines():
        if QUOTE.match(line):
            continue

        match = FENCE.match(line)
        if fence is not None:
            if match:
                marker, suffix = match.groups()
                if marker[0] == fence[0] and len(marker) >= len(fence) and not suffix.strip():
                    fence = None
            continue

        if match:
            fence = match[1]
            continue
        if LINK_DEFINITION.match(line):
            continue

        line = INLINE_CODE.sub(" ", line)
        line = IMAGE.sub(" ", line)
        line = LINK.sub(r"\1 ", line)
        yield URL.sub(" ", line)


def needs_rewrite(message):
    stripped = message.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            if isinstance(json.loads(stripped), (dict, list)):
                return False
        except (ValueError, RecursionError):
            pass

    prose = unicodedata.normalize("NFKC", "\n".join(prose_lines(message)))
    latin_words = sum(1 for _ in LATIN_WORD.finditer(prose))
    han_characters = sum(1 for _ in HAN.finditer(prose))
    return latin_words >= MIN_LATIN_WORDS and 2 * latin_words > han_characters


def stop_decision(event):
    if not isinstance(event, dict) or event.get("hook_event_name") != "Stop":
        return None
    if event.get("stop_hook_active") is not False:
        return None

    message = event.get("last_assistant_message")
    if isinstance(message, str) and needs_rewrite(message):
        return {"decision": "block", "reason": REWRITE_REASON}
    return None


def main():
    if os.environ.get("CLAUDE_CHINESE_GUARD_DISABLE") == "1":
        return
    try:
        event = json.load(sys.stdin.buffer)
    except (ValueError, OSError, RecursionError):
        return
    decision = stop_decision(event)
    if decision is not None:
        print(json.dumps(decision))


if __name__ == "__main__":
    main()
