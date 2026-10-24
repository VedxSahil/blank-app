"""Refresh index.html with fresh pre-market data using Claude and web search."""

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic

MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 32000
MAX_CONTINUATIONS = 5
ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
PROMPT = ROOT / "scripts" / "prompt_template.md"
IST = timezone(timedelta(hours=5, minutes=30))

WEB_SEARCH_TOOL = {"type": "web_search_20250305", "name": "web_search", "max_uses": 15}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def check_reply(html: str) -> list[str]:
    """Return a list of reasons the reply is not safe to save."""
    problems = []
    if not html.lower().startswith("<!doctype html>"):
        problems.append("does not start with <!doctype html>")
    if not html.lower().endswith("</html>"):
        problems.append("does not end with </html>")
    if "Expected open" not in html:
        problems.append('missing the words "Expected open"')
    if "Not investment advice" not in html:
        problems.append('missing the words "Not investment advice"')
    if len(html) < 3000:
        problems.append(f"too short ({len(html)} characters, need at least 3000)")
    return problems


def extract_html(text: str) -> str:
    """Drop any chatter around the page, e.g. narration between web searches."""
    text = text.strip()
    start = text.lower().find("<!doctype html>")
    end = text.lower().rfind("</html>")
    if start == -1 or end == -1 or end < start:
        return text
    return text[start : end + len("</html>")].strip()


def main() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        fail("ANTHROPIC_API_KEY is not set. Add it as a repository secret or export it.")

    current_html = INDEX.read_text(encoding="utf-8")
    template = PROMPT.read_text(encoding="utf-8")
    now_ist = datetime.now(IST).strftime("%A, %d %B %Y, %H:%M IST")

    user_message = (
        f"{template}\n\n"
        f"Current date and time: {now_ist}\n\n"
        f"Current index.html:\n\n{current_html}"
    )

    client = anthropic.Anthropic(api_key=api_key)
    messages = [{"role": "user", "content": user_message}]
    texts = []

    try:
        for _ in range(MAX_CONTINUATIONS + 1):
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                tools=[WEB_SEARCH_TOOL],
                messages=messages,
            )
            texts.extend(b.text for b in response.content if b.type == "text")
            # Long searches can pause the turn; send it back to continue.
            if response.stop_reason != "pause_turn":
                break
            messages.append({"role": "assistant", "content": response.content})
        else:
            fail("The reply kept pausing. Giving up; index.html was not changed.")
    except anthropic.APIError as exc:
        fail(f"Anthropic API call failed: {exc}")

    if response.stop_reason == "max_tokens":
        fail("The reply was cut off at the token limit. index.html was not changed.")

    new_html = extract_html("".join(texts))

    problems = check_reply(new_html)
    if problems:
        print("Safety check failed. Keeping the old index.html.", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        sys.exit(1)

    INDEX.write_text(new_html + "\n", encoding="utf-8")
    print(f"index.html updated ({len(new_html)} characters).")


if __name__ == "__main__":
    main()
