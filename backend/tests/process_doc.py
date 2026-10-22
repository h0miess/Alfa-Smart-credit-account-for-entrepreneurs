import re
from pathlib import Path

PROCESS_MD = Path(__file__).resolve().parents[2] / "docs" / "process.md"


def read_process_md() -> str:
    return PROCESS_MD.read_text(encoding="utf-8")


def section(text: str, heading_prefix: str) -> str:
    start = text.index(f"\n## {heading_prefix}")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else None]


def mermaid_block(text: str, kind: str) -> str:
    match = re.search(rf"```mermaid\n{kind}\n(.*?)```", text, re.S)
    assert match, f"нет mermaid-блока {kind}"
    return match.group(1)


def table_rows(text: str) -> list[list[str]]:
    rows = []
    for line in text.splitlines():
        if line.startswith("|") and not re.match(r"^\|[\s\-|]+\|$", line):
            rows.append([cell.strip() for cell in line.strip("|").split("|")])
    return rows


def backticked(cell: str) -> list[str]:
    return re.findall(r"`([^`]+)`", cell)
