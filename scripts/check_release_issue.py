"""Evaluate whether a closed release issue satisfies its completion contract."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

RELEASE_LABEL = "area:release"
CHECKBOX = re.compile(r"^\s*-\s+\[([ xX])\]\s+(.+?)\s*$", re.MULTILINE)
SUCCESSOR = re.compile(
    r"(?:#\d+|https://github\.com/[^/]+/[^/]+/issues/\d+)", re.IGNORECASE
)
MARKER = "<!-- release-issue-close-guard -->"


def closure_violation(event: dict) -> list[str]:
    issue = event.get("issue", {})
    labels = {label.get("name") for label in issue.get("labels", [])}
    if RELEASE_LABEL not in labels:
        return []

    body = issue.get("body") or ""
    state_reason = issue.get("state_reason") or "completed"
    if state_reason == "not_planned":
        missing = []
        partial = re.search(
            r"^##\s+Partial outcome\s*$\n(.*?)(?=^##\s|\Z)",
            body,
            re.MULTILINE | re.DOTALL,
        )
        if partial is None:
            missing.append("a `## Partial outcome` section")
        if partial is None or SUCCESSOR.search(partial.group(1)) is None:
            missing.append("a successor issue link")
        return missing

    checkboxes = CHECKBOX.findall(body)
    if not checkboxes:
        return ["at least one acceptance checkbox"]
    return [text for mark, text in checkboxes if mark == " "]


def render_comment(missing: list[str]) -> str:
    lines = [
        MARKER,
        "This release issue was reopened because its closure contract is incomplete.",
        "",
        "Missing requirements:",
    ]
    lines.extend(f"- {item}" for item in missing)
    lines.extend(
        [
            "",
            "Complete the criteria before closing as completed. If the release was "
            "canceled or superseded, close it as not planned after adding a "
            "`## Partial outcome` section and a successor issue link.",
        ]
    )
    return "\n".join(lines) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", type=Path, required=True)
    parser.add_argument("--comment", type=Path, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    event = json.loads(args.event.read_text(encoding="utf-8"))
    missing = closure_violation(event)
    if not missing:
        return
    args.comment.write_text(render_comment(missing), encoding="utf-8")
    raise SystemExit(3)


if __name__ == "__main__":
    main()
