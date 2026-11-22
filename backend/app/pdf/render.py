"""Server-side PDF rendering with embedded Noto Sans / Noto Sans Bengali.

PyMuPDF's HTML engine shapes text with HarfBuzz, so Bangla conjuncts and vowel
signs render correctly. MuPDF does not fall back through a CSS font list, so
Bangla runs are wrapped in a span that uses the embedded Bangla font; without
that it would substitute its own built-in serif font. All text is escaped:
document and summary text is data, never markup (Rule 9).
"""

import html
import io
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

import pymupdf

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
PAGE = pymupdf.paper_rect("a4")
MARGIN = 54  # 0.75 in

_CSS = """
@font-face {font-family: Latin; src: url(NotoSans-Regular.ttf);}
@font-face {font-family: Latin; font-weight: bold; src: url(NotoSans-Bold.ttf);}
@font-face {font-family: Bangla; src: url(NotoSansBengali-Regular.ttf);}
@font-face {font-family: Bangla; font-weight: bold; src: url(NotoSansBengali-Bold.ttf);}
body {font-family: Latin; font-size: 10.5pt; line-height: 1.45; color: #141a1d;}
.bn {font-family: Bangla;}
.eyebrow {font-size: 8pt; font-weight: bold; color: #00984a; letter-spacing: 1pt;}
h1 {font-size: 18pt; margin: 4pt 0 10pt 0;}
h2 {font-size: 12.5pt; margin: 14pt 0 4pt 0; color: #076732;}
table.meta {margin: 0 0 8pt 0;}
table.meta td {padding: 1pt 10pt 1pt 0; font-size: 9pt; vertical-align: top;}
td.label {color: #6c757d; font-weight: bold;}
.notice {font-size: 8.5pt; color: #6b5326; background-color: #fbf6e9; padding: 5pt; margin: 6pt 0;}
.item {margin: 0 0 6pt 0;}
.tags {font-size: 7.5pt; font-weight: bold; color: #6c757d;}
.source {font-size: 8pt; color: #6c757d;}
.footer {font-size: 8pt; color: #6c757d; margin-top: 16pt;}
"""

# Bangla letters, danda, ZWNJ/ZWJ; spaces and simple punctuation between two Bangla runs stay inside the run.
_BN = "ঀ-৿।॥‌‍"
_BANGLA_RUN = re.compile(rf"([{_BN}]+(?:[  ,;:()'\"\-]+[{_BN}]+)*)")


def markup(text: str) -> str:
    """Escaped HTML with Bangla runs in the embedded Bangla font."""
    parts = _BANGLA_RUN.split(unicodedata.normalize("NFC", text or ""))
    marked = "".join(
        f'<span class="bn">{html.escape(part)}</span>' if index % 2 else html.escape(part)
        for index, part in enumerate(parts)
    )
    return marked.replace("\n", "<br/>")


@dataclass(frozen=True)
class Item:
    text: str
    tags: list[str] = field(default_factory=list)
    source: str | None = None


@dataclass(frozen=True)
class Section:
    heading: str
    items: list[Item]


@dataclass(frozen=True)
class Document:
    eyebrow: str
    title: str
    meta: list[tuple[str, str]]
    sections: list[Section]
    notice: str | None = None
    footer: str | None = None
    body: str | None = None  # free text (client update), rendered as written


def _html(doc: Document) -> str:
    parts = [f'<p class="eyebrow">{markup(doc.eyebrow)}</p>', f"<h1>{markup(doc.title)}</h1>"]
    if doc.meta:
        rows = "".join(f'<tr><td class="label">{markup(k)}</td><td>{markup(v)}</td></tr>' for k, v in doc.meta)
        parts.append(f'<table class="meta">{rows}</table>')
    if doc.notice:
        parts.append(f'<p class="notice">{markup(doc.notice)}</p>')
    if doc.body:
        parts.append(f"<p>{markup(doc.body)}</p>")
    for number, section in enumerate(doc.sections, start=1):
        parts.append(f"<h2>{number}. {markup(section.heading)}</h2>")
        for item in section.items:
            tags = f'<div class="tags">{markup(" · ".join(item.tags))}</div>' if item.tags else ""
            source = f'<div class="source">{markup(item.source)}</div>' if item.source else ""
            parts.append(f'<div class="item">{tags}<div>{markup(item.text)}</div>{source}</div>')
    if doc.footer:
        parts.append(f'<p class="footer">{markup(doc.footer)}</p>')
    return "<body>" + "".join(parts) + "</body>"


def render_pdf(doc: Document) -> bytes:
    story = pymupdf.Story(html=_html(doc), user_css=_CSS, archive=pymupdf.Archive(str(FONT_DIR)))
    buffer = io.BytesIO()
    writer = pymupdf.DocumentWriter(buffer)
    area = PAGE + (MARGIN, MARGIN, -MARGIN, -MARGIN)
    more = 1
    while more:
        device = writer.begin_page(PAGE)
        more, _ = story.place(area)
        story.draw(device)
        writer.end_page()
    writer.close()
    return buffer.getvalue()


_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def attachment_headers(filename: str) -> dict[str, str]:
    """Content-Disposition attachment with an ASCII fallback and the UTF-8 name (RFC 6266/5987)."""
    name = unicodedata.normalize("NFC", filename).replace("/", "_").replace("\\", "_").strip() or "download"
    ascii_name = _UNSAFE.sub("-", unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()).strip("-.")
    if "." in name and "." not in ascii_name:
        ascii_name = f"download.{name.rsplit('.', 1)[-1]}"
    ascii_name = ascii_name or "download"
    return {
        "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(name, safe='')}",
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    }
