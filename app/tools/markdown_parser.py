import re
import unicodedata
from dataclasses import dataclass

from app.core.constants import SECTION_DELIMITER, TRAP_SECTION_MARKER, TRAP_SUBSECTION_MARKER


@dataclass(frozen=True)
class KBSection:
    title: str
    body: str


def _strip_trap_subsections(body: str, subsection_marker: str = TRAP_SUBSECTION_MARKER) -> str:
    lines = body.splitlines()
    clean: list[str] = []
    in_trap = False

    for line in lines:
        if line.strip().startswith(subsection_marker):
            in_trap = True
            continue
        if in_trap and (
            line.strip() == "---"
            or (
                line.strip().startswith("###")
                and not line.strip().startswith(subsection_marker)
            )
        ):
            in_trap = False
        if not in_trap:
            clean.append(line)

    return "\n".join(clean).strip()


def parse_sections(
    raw: str,
    delimiter: str = SECTION_DELIMITER,
    trap_marker: str = TRAP_SECTION_MARKER,
) -> list[KBSection]:
    sections: list[KBSection] = []
    trap_lower = trap_marker.lower()
    chunks = raw.split(f"\n{delimiter}")

    for chunk in chunks[1:]:
        lines = chunk.splitlines()
        if not lines:
            continue

        title = lines[0].strip()
        body = "\n".join(lines[1:]).strip()

        if trap_lower in title.lower():
            continue

        body = _strip_trap_subsections(body)
        sections.append(KBSection(title=title, body=body))

    return sections


def normalize(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_only = nfkd.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9 ]", " ", ascii_only.lower())


def score_section(section: KBSection, query: str) -> float:
    q_words = set(normalize(query).split())
    if not q_words:
        return 0.0

    section_text = f"{section.title} {section.body}"
    s_words = set(normalize(section_text).split())

    return len(q_words & s_words) / len(q_words)
