# markdown-html-converter

A tiny, **dependency-free** Markdown → HTML converter in a single Python file.
No pip installs, no build step — just the standard library.

## Usage

```bash
python md2html.py input.md                 # -> input.html
python md2html.py input.md -o out.html     # explicit output path
python md2html.py input.md --stdout        # print HTML to stdout
python md2html.py --full input.md          # wrap in a complete HTML document
cat input.md | python md2html.py -         # read stdin, write stdout
```

Use it as a library too:

```python
from md2html import convert, to_document

html_fragment = convert("# Hello\n\nSome **bold** text.")
full_page = to_document(html_fragment, title="Hello")
```

## Supported Markdown

- ATX headings (`#` … `######`)
- Paragraphs and hard line breaks (two trailing spaces)
- **Bold** (`**x**` / `__x__`), *italic* (`*x*` / `_x_`), `inline code`
- Links `[text](url)` and images `![alt](url)`
- Unordered (`-`, `*`, `+`) and ordered (`1.`) lists, with indent nesting
- Blockquotes (`> …`)
- Fenced code blocks (```` ``` ````)
- Horizontal rules (`---`, `***`, `___`)

This is intentionally a practical subset — not a full CommonMark implementation.

## Test

```bash
python test_md2html.py
```

## License

MIT
