"""Semantic-ish markdown chunking: heading-aware, 300-500 tokens, overlap."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

TARGET_TOKENS = 400
MIN_TOKENS = 300
MAX_TOKENS = 500
OVERLAP_TOKENS = 80
FRONT_MATTER = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)


@dataclass(frozen=True)
class Chunk:
    document_id: str
    document_title: str
    chunk_index: int
    content: str
    section: str | None
    extra: dict[str, str]

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    @property
    def token_count(self) -> int:
        return _tokens(self.content)


def _tokens(text: str) -> int:
    return max(1, len(text.split()))


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    match = FRONT_MATTER.match(text)
    if not match:
        return {}, text
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip()
    return meta, match.group(2).lstrip()


def chunk_markdown(
    text: str,
    *,
    document_id: str,
    document_title: str,
    target_tokens: int = TARGET_TOKENS,
    overlap_tokens: int = OVERLAP_TOKENS,
) -> list[Chunk]:
    """Split on `##` sections, then pack to ~target_tokens with overlap."""
    _meta, body = parse_front_matter(text)
    sections = _split_sections(body)
    pieces: list[tuple[str | None, str]] = []
    for heading, section_body in sections:
        packed = _pack(section_body, target_tokens=target_tokens, overlap_tokens=overlap_tokens)
        pieces.extend((heading, part) for part in packed)

    chunks = [
        Chunk(
            document_id=document_id,
            document_title=document_title,
            chunk_index=i,
            content=content.strip(),
            section=section,
            extra={"source": "markdown"},
        )
        for i, (section, content) in enumerate(pieces)
        if content.strip()
    ]
    return chunks


def chunk_file(path: Path) -> list[Chunk]:
    text = path.read_text(encoding="utf-8")
    meta, _ = parse_front_matter(text)
    document_id = meta.get("document_id") or meta.get("case_id") or path.stem
    title = meta.get("title") or meta.get("citation") or path.stem
    chunks = chunk_markdown(text, document_id=document_id, document_title=title)
    for chunk in chunks:
        extra = dict(chunk.extra)
        extra.update({k: v for k, v in meta.items() if k not in {"document_id", "title"}})
        object.__setattr__(chunk, "extra", extra)
    return chunks


def _split_sections(body: str) -> list[tuple[str | None, str]]:
    parts = re.split(r"(?m)^(## .+)$", body)
    if len(parts) == 1:
        return [(None, body.strip())]
    sections: list[tuple[str | None, str]] = []
    preamble = parts[0].strip()
    if preamble:
        sections.append((None, preamble))
    for i in range(1, len(parts), 2):
        heading = parts[i].lstrip("# ").strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        sections.append((heading, f"{parts[i].strip()}\n\n{content}".strip()))
    return sections


def _pack(text: str, *, target_tokens: int, overlap_tokens: int) -> list[str]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return []
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for para in paragraphs:
        n = _tokens(para)
        if current and current_tokens + n > MAX_TOKENS:
            chunks.append("\n\n".join(current))
            overlap = _tail_tokens("\n\n".join(current), overlap_tokens)
            current = [overlap, para] if overlap else [para]
            current_tokens = _tokens("\n\n".join(current))
        else:
            current.append(para)
            current_tokens += n
            if current_tokens >= target_tokens and current_tokens >= MIN_TOKENS:
                chunks.append("\n\n".join(current))
                overlap = _tail_tokens("\n\n".join(current), overlap_tokens)
                current = [overlap] if overlap else []
                current_tokens = _tokens(overlap) if overlap else 0
    if current and "\n\n".join(current).strip():
        tail = "\n\n".join(current).strip()
        if chunks and _tokens(tail) < 40:
            chunks[-1] = chunks[-1] + "\n\n" + tail
        else:
            chunks.append(tail)
    return chunks


def _tail_tokens(text: str, n: int) -> str:
    words = text.split()
    if len(words) <= n:
        return ""
    return " ".join(words[-n:])
