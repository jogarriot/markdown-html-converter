#!/usr/bin/env python3
"""A simple, dependency-free Markdown -> HTML converter.

Supports a practical subset of Markdown:
  - ATX headings (# .. ######)
  - Paragraphs and hard line breaks (two trailing spaces)
  - Bold (**x** / __x__), italic (*x* / _x_), inline code (`x`)
  - Links [text](url) and images ![alt](url)
  - Unordered (-, *, +) and ordered (1.) lists, with nesting by indent
  - Blockquotes (> )
  - Fenced code blocks (``` ... ```)
  - Horizontal rules (---, ***, ___)

Usage:
  python md2html.py input.md                 # -> input.html
  python md2html.py input.md -o out.html     # explicit output
  python md2html.py input.md --stdout        # print HTML to stdout
  python md2html.py --full input.md          # wrap in a full HTML document
  cat input.md | python md2html.py -         # read from stdin, write to stdout
"""

from __future__ import annotations

import argparse
import html
import re
import sys

# ---- inline formatting -----------------------------------------------------

_CODE_SPAN = re.compile(r"`([^`]+)`")
_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)(?:\s+\"([^\"]*)\")?\)")
_BOLD = re.compile(r"(\*\*|__)(.+?)\1")
_ITALIC = re.compile(r"(?<![\*_])(\*|_)(?!\s)(.+?)(?<!\s)\1(?![\*_])")


def render_inline(text: str) -> str:
    """Convert inline Markdown in a single line to HTML (input is escaped)."""
    # Protect inline code spans from other transforms by extracting them first.
    placeholders: list[str] = []

    def _stash_code(m: re.Match) -> str:
        placeholders.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(placeholders) - 1}\x00"

    text = _CODE_SPAN.sub(_stash_code, text)
    text = html.escape(text, quote=False)

    text = _IMAGE.sub(
        lambda m: '<img src="{}" alt="{}"{}>'.format(
            html.escape(m.group(2), quote=True),
            html.escape(m.group(1), quote=True),
            ' title="{}"'.format(html.escape(m.group(3), quote=True)) if m.group(3) else "",
        ),
        text,
    )
    text = _LINK.sub(
        lambda m: '<a href="{}"{}>{}</a>'.format(
            html.escape(m.group(2), quote=True),
            ' title="{}"'.format(html.escape(m.group(3), quote=True)) if m.group(3) else "",
            m.group(1),
        ),
        text,
    )
    text = _BOLD.sub(r"<strong>\2</strong>", text)
    text = _ITALIC.sub(r"<em>\2</em>", text)

    # Hard line break: two or more trailing spaces became a newline marker upstream.
    text = text.replace("  \n", "<br>\n")

    # Restore code spans.
    def _unstash(m: re.Match) -> str:
        return placeholders[int(m.group(1))]

    return re.sub(r"\x00(\d+)\x00", _unstash, text)


# ---- block-level parsing ---------------------------------------------------

_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_HR = re.compile(r"^ {0,3}([-*_])(?:\s*\1){2,}\s*$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})\s*([\w-]*)\s*$")
_ULIST = re.compile(r"^(\s*)[-*+]\s+(.*)$")
_OLIST = re.compile(r"^(\s*)\d+\.\s+(.*)$")
_QUOTE = re.compile(r"^ {0,3}>\s?(.*)$")


class _Out:
    def __init__(self) -> None:
        self.parts: list[str] = []

    def add(self, s: str) -> None:
        self.parts.append(s)

    def text(self) -> str:
        return "\n".join(self.parts)


def _indent_level(spaces: str) -> int:
    return len(spaces.replace("\t", "    ")) // 2


def convert(md: str) -> str:
    """Convert a Markdown document to an HTML fragment."""
    lines = md.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out = _Out()
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        # Blank line
        if not line.strip():
            i += 1
            continue

        # Fenced code block
        fence = _FENCE.match(line)
        if fence:
            marker, lang = fence.group(1), fence.group(2)
            body: list[str] = []
            i += 1
            while i < n and not (lines[i].strip().startswith(marker[0] * 3)
                                 and lines[i].strip() == lines[i].strip()[0] * len(lines[i].strip())
                                 and len(lines[i].strip()) >= len(marker)):
                body.append(lines[i])
                i += 1
            i += 1  # consume closing fence (if present)
            cls = f' class="language-{html.escape(lang)}"' if lang else ""
            code = html.escape("\n".join(body))
            out.add(f"<pre><code{cls}>{code}</code></pre>")
            continue

        # Horizontal rule
        if _HR.match(line):
            out.add("<hr>")
            i += 1
            continue

        # Heading
        h = _HEADING.match(line)
        if h:
            level = len(h.group(1))
            out.add(f"<h{level}>{render_inline(h.group(2))}</h{level}>")
            i += 1
            continue

        # Blockquote (collect consecutive > lines, convert recursively)
        if _QUOTE.match(line):
            quoted: list[str] = []
            while i < n and _QUOTE.match(lines[i]):
                quoted.append(_QUOTE.match(lines[i]).group(1))
                i += 1
            out.add("<blockquote>")
            out.add(convert("\n".join(quoted)))
            out.add("</blockquote>")
            continue

        # Lists (ordered or unordered), with simple indent-based nesting
        if _ULIST.match(line) or _OLIST.match(line):
            i = _parse_list(lines, i, out)
            continue

        # Paragraph: gather until a blank line or a block starter
        para: list[str] = []
        while i < n and lines[i].strip() and not _is_block_start(lines[i]):
            para.append(lines[i].rstrip())
            i += 1
        joined = "  \n".join(  # keep hard breaks, join soft-wrapped lines with a space
            seg for seg in para
        )
        # Normalize: lines without trailing double-space join with a space.
        joined = _join_paragraph(para)
        out.add(f"<p>{render_inline(joined)}</p>")

    return out.text()


def _is_block_start(line: str) -> bool:
    return bool(
        _HEADING.match(line)
        or _HR.match(line)
        or _FENCE.match(line)
        or _QUOTE.match(line)
        or _ULIST.match(line)
        or _OLIST.match(line)
    )


def _join_paragraph(para: list[str]) -> str:
    """Join wrapped paragraph lines; preserve hard breaks (2+ trailing spaces)."""
    result = ""
    for idx, seg in enumerate(para):
        hard = seg.endswith("  ")
        seg = seg.rstrip()
        if idx == 0:
            result = seg
        elif hard or result.endswith("  \n"):
            result += "  \n" + seg
        else:
            result += " " + seg
        if hard:
            result += "  \n"
    return result


def _parse_list(lines: list[str], i: int, out: _Out) -> int:
    """Parse a (possibly nested) list starting at index i. Returns next index."""
    n = len(lines)

    def parse_at(i: int, base_indent: int) -> int:
        ordered = bool(_OLIST.match(lines[i]))
        tag = "ol" if ordered else "ul"
        out.add(f"<{tag}>")
        while i < n:
            m = _ULIST.match(lines[i]) or _OLIST.match(lines[i])
            if not m:
                if not lines[i].strip():
                    i += 1
                    continue
                break
            indent = _indent_level(m.group(1))
            if indent < base_indent:
                break
            # A deeper item than expected can't start a peer here; stop.
            if indent > base_indent:
                break

            content = render_inline(m.group(2))
            # Look ahead: does a more-indented list nest under this item?
            nxt = i + 1
            while nxt < n and not lines[nxt].strip():
                nxt += 1
            mm = _ULIST.match(lines[nxt]) if nxt < n else None
            mm = mm or (_OLIST.match(lines[nxt]) if nxt < n else None)
            if mm and _indent_level(mm.group(1)) > base_indent:
                out.add(f"<li>{content}")
                i = parse_at(nxt, _indent_level(mm.group(1)))
                out.add("</li>")
            else:
                out.add(f"<li>{content}</li>")
                i += 1
        out.add(f"</{tag}>")
        return i

    start_indent = _indent_level((_ULIST.match(lines[i]) or _OLIST.match(lines[i])).group(1))
    return parse_at(i, start_indent)


# ---- document wrapper ------------------------------------------------------

_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  body{{max-width:44rem;margin:2rem auto;padding:0 1rem;
    font:16px/1.6 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#222}}
  h1,h2,h3{{line-height:1.25}}
  code{{background:#f2f2f2;padding:.1em .3em;border-radius:4px;font-size:.9em}}
  pre{{background:#f6f8fa;padding:1rem;border-radius:8px;overflow:auto}}
  pre code{{background:none;padding:0}}
  blockquote{{margin:0;padding:.2rem 1rem;border-left:4px solid #ddd;color:#555}}
  a{{color:#0366d6}}
  img{{max-width:100%}}
  hr{{border:none;border-top:1px solid #ddd;margin:2rem 0}}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def to_document(body_html: str, title: str = "Document") -> str:
    return _TEMPLATE.format(title=html.escape(title), body=body_html)


# ---- CLI -------------------------------------------------------------------

def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="md2html", description="Convert Markdown to HTML (no dependencies).")
    p.add_argument("input", help="Markdown file to convert, or '-' for stdin.")
    p.add_argument("-o", "--output", help="Output HTML file. Defaults to INPUT with .html.")
    p.add_argument("--stdout", action="store_true", help="Write HTML to stdout instead of a file.")
    p.add_argument("--full", action="store_true", help="Wrap output in a full HTML document.")
    p.add_argument("--title", default=None, help="Title for --full document. Defaults to the input name.")
    args = p.parse_args(argv)

    if args.input == "-":
        md = sys.stdin.read()
        default_out = None
        title = args.title or "Document"
    else:
        try:
            with open(args.input, "r", encoding="utf-8") as fh:
                md = fh.read()
        except FileNotFoundError:
            print(f"error: file not found: {args.input}", file=sys.stderr)
            return 2
        default_out = re.sub(r"\.(md|markdown|txt)$", "", args.input) + ".html"
        title = args.title or args.input

    body = convert(md)
    result = to_document(body, title) if args.full else body

    if args.stdout or args.input == "-" and not args.output:
        sys.stdout.write(result + ("\n" if not result.endswith("\n") else ""))
        return 0

    out_path = args.output or default_out
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(result + "\n")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
