from __future__ import annotations

from pathlib import Path
import re


FILE_BLOCK = re.compile(
    r"```(?:text|python|py|json|markdown|md|toml|yaml|yml)?\s+path=([^\n\r]+)\r?\n(.*?)```",
    re.DOTALL,
)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_implementation(root: Path, coder_output: str) -> list[Path]:
    implementation_root = root / "implementation"
    implementation_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for match in FILE_BLOCK.finditer(coder_output):
        raw_path = match.group(1).strip().strip('"')
        if raw_path.replace("\\", "/").startswith("implementation/"):
            raw_path = raw_path.replace("\\", "/", 1).removeprefix("implementation/")
        content = match.group(2).rstrip() + "\n"
        target = (implementation_root / raw_path).resolve()
        if not str(target).startswith(str(implementation_root.resolve())):
            raise ValueError(f"Refusing to write outside implementation root: {raw_path}")
        write_text(target, content)
        written.append(target)
    if not written:
        fallback = implementation_root / "coder_output.md"
        write_text(fallback, coder_output)
        written.append(fallback)
    return written
