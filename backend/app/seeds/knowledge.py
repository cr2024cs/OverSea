import re
from datetime import date
from pathlib import Path

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def parse_front_matter(text: str):
    meta = {}
    body_start = 0
    if not text.startswith("---"):
        return meta, body_start
    end = text.find("\n---", 3)
    if end == -1:
        return meta, body_start
    raw = text[3:end]
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"').strip("'")
    newline = text.find("\n", end + 1)
    body_start = len(text) if newline == -1 else newline + 1
    return meta, body_start


def split_sections(text: str, body_start: int):
    sections = []
    stack = []
    current = None
    pos = 0

    for line in text.splitlines(keepends=True):
        match = HEADING_RE.match(line)
        if match:
            if current and current["parts"]:
                sections.append(current)
            level = len(match.group(1))
            title = match.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            current = {
                "heading_path": " / ".join(item[1] for item in stack),
                "start": pos + len(line),
                "parts": [],
            }
        elif current is not None:
            current["parts"].append(line)
        pos += len(line)

    if current and current["parts"]:
        sections.append(current)

    result = []
    for section in sections:
        content = "".join(section["parts"])
        if content.strip():
            result.append(
                {
                    "heading_path": section["heading_path"],
                    "start": section["start"],
                    "content": content,
                }
            )
    return result


def chunk_text(text: str, abs_start: int, target: int = 700, overlap: int = 100):
    chunks = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + target, length)
        if end < length:
            window = text[start:end]
            candidates = [
                window.rfind("\n"),
                window.rfind("。"),
                window.rfind("；"),
                window.rfind(". "),
            ]
            cut = max(candidates)
            if cut >= target // 2:
                end = start + cut + 1

        raw = text[start:end]
        stripped = raw.strip()
        if stripped:
            lead = len(raw) - len(raw.lstrip())
            trail = len(raw) - len(raw.rstrip())
            chunks.append((stripped, abs_start + start + lead, abs_start + end - trail))

        if end >= length:
            break
        start = max(end - overlap, start + 1)
    return chunks


def load_documents(rag_dir: Path):
    documents = []
    for path in sorted(rag_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta, body_start = parse_front_matter(text)
        doc_code = path.name.split("_", 1)[0]
        reviewed = None
        if meta.get("last_reviewed"):
            try:
                reviewed = date.fromisoformat(meta["last_reviewed"])
            except ValueError:
                reviewed = None

        chunks = []
        seq = 0
        for section in split_sections(text, body_start):
            for content, char_start, char_end in chunk_text(
                section["content"], section["start"]
            ):
                chunks.append(
                    {
                        "seq": seq,
                        "heading_path": section["heading_path"],
                        "content": content,
                        "char_start": char_start,
                        "char_end": char_end,
                    }
                )
                seq += 1

        documents.append(
            {
                "doc_code": doc_code,
                "title": meta.get("title", path.stem),
                "country": meta.get("country", "Thailand"),
                "industry": meta.get("industry", "Manufacturing"),
                "topic": meta.get("topic", ""),
                "source_priority": meta.get("source_priority", ""),
                "last_reviewed": reviewed,
                "path": path,
                "chunks": chunks,
            }
        )
    return documents
