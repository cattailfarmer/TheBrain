from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable, Mapping


FIELD_RE = re.compile(r"^(?P<indent>\s*)\+ \[(?P<key>[^\]]+)\] is (?P<value>.*)$")


@dataclass(frozen=True)
class ActiveConversationPointer:
    path: Path
    conversation_uuid: str
    surface_path: Path

    @classmethod
    def load(cls, project_root: Path, pointer_path: Path | None = None) -> "ActiveConversationPointer":
        path = pointer_path or project_root / "coordination" / "active_conversation.sop"
        fields = parse_sop_fields(path.read_text(encoding="utf-8"))
        try:
            conversation_uuid = fields["active_conversation_uuid"][0]
            surface_ref = fields["conversation_surface_file"][0]
        except (KeyError, IndexError) as exc:
            raise ValueError(f"Invalid active conversation pointer: {path}") from exc
        return cls(
            path=path,
            conversation_uuid=conversation_uuid,
            surface_path=(project_root / surface_ref).resolve(),
        )


@dataclass
class ConversationSurface:
    path: Path
    text: str
    fields: dict[str, list[str]]

    @classmethod
    def load(cls, path: Path) -> "ConversationSurface":
        text = path.read_text(encoding="utf-8")
        return cls(path=path, text=text, fields=parse_sop_fields(text))

    @classmethod
    def load_active(cls, project_root: Path) -> "ConversationSurface":
        pointer = ActiveConversationPointer.load(project_root)
        surface = cls.load(pointer.surface_path)
        surface_uuid = surface.first("conversation_uuid")
        if surface_uuid != pointer.conversation_uuid:
            raise ValueError(
                f"Conversation UUID mismatch: pointer has {pointer.conversation_uuid}, "
                f"surface has {surface_uuid or '<missing>'}"
            )
        return surface

    def first(self, key: str, default: str | None = None) -> str | None:
        values = self.fields.get(key)
        return values[0] if values else default

    def set_fields(self, updates: Mapping[str, str]) -> None:
        text = self.text
        for key, value in updates.items():
            text = upsert_first_field(text, key, value)
        self.text = text
        self.fields = parse_sop_fields(text)

    def append_unique_fields(self, key: str, values: Iterable[str], after_key: str | None = None) -> None:
        text = self.text
        existing = set(self.fields.get(key, []))
        for value in values:
            if value in existing:
                continue
            text = insert_field(text, key, value, after_key=after_key or key)
            existing.add(value)
        self.text = text
        self.fields = parse_sop_fields(text)

    def write(self) -> None:
        self.path.write_text(self.text, encoding="utf-8")


def parse_sop_fields(text: str) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    for line in text.splitlines():
        match = FIELD_RE.match(line)
        if match:
            fields.setdefault(match.group("key"), []).append(match.group("value"))
    return fields


def replace_first_field(text: str, key: str, value: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        match = FIELD_RE.match(line)
        if match and match.group("key") == key:
            lines[index] = f"{match.group('indent')}+ [{key}] is {value}"
            return "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    raise KeyError(f"Field not found: {key}")


def upsert_first_field(text: str, key: str, value: str, after_key: str | None = None) -> str:
    try:
        return replace_first_field(text, key, value)
    except KeyError:
        return insert_field(text, key, value, after_key=after_key or key)


def insert_field(text: str, key: str, value: str, after_key: str) -> str:
    lines = text.splitlines()
    insert_at: int | None = None
    indent = "  "
    for index, line in enumerate(lines):
        match = FIELD_RE.match(line)
        if match and match.group("key") == after_key:
            insert_at = index + 1
            indent = match.group("indent")
    if insert_at is None:
        insert_at = len(lines)
    lines.insert(insert_at, f"{indent}+ [{key}] is {value}")
    return "\n".join(lines) + ("\n" if text.endswith("\n") else "")


def update_active_conversation_surface(
    project_root: Path,
    *,
    set_fields: Mapping[str, str] | None = None,
    unresolved_items: Iterable[str] = (),
    proofs: Iterable[str] = (),
) -> ConversationSurface:
    surface = ConversationSurface.load_active(project_root)
    if set_fields:
        surface.set_fields(set_fields)
    surface.append_unique_fields("unresolved_item", unresolved_items, after_key="unresolved_item")
    surface.append_unique_fields("last_proof", proofs, after_key="last_proof")
    surface.write()
    return surface
