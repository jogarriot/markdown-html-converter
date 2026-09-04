#!/usr/bin/env python3
"""Minimal tests for md2html.convert — run: python test_md2html.py"""

import sys

from md2html import convert, to_document


def check(name, md, must_contain):
    out = convert(md)
    for needle in must_contain:
        assert needle in out, f"[{name}] expected {needle!r} in:\n{out}"
    print(f"ok: {name}")


def main() -> int:
    check("heading", "# Title", ["<h1>Title</h1>"])
    check("heading6", "###### Deep", ["<h6>Deep</h6>"])
    check("paragraph", "Hello world.", ["<p>Hello world.</p>"])
    check("bold", "a **b** c", ["<strong>b</strong>"])
    check("italic", "a *b* c", ["<em>b</em>"])
    check("inline code", "use `x = 1` here", ["<code>x = 1</code>"])
    check("link", "[go](https://x.com)", ['<a href="https://x.com">go</a>'])
    check("image", "![alt](p.png)", ['<img src="p.png" alt="alt">'])
    check("ul", "- one\n- two", ["<ul>", "<li>one</li>", "<li>two</li>", "</ul>"])
    check("ol", "1. one\n2. two", ["<ol>", "<li>one</li>", "</ol>"])
    check("nested list", "- a\n  - b", ["<ul>", "<li>a", "<li>b</li>"])
    check("blockquote", "> quoted", ["<blockquote>", "<p>quoted</p>", "</blockquote>"])
    check("fenced code", "```py\nx=1\n```", ['<pre><code class="language-py">', "x=1"])
    check("hr", "---", ["<hr>"])
    check("escape", "a < b & c", ["a &lt; b &amp; c"])
    check("code not formatted", "`**not bold**`", ["<code>**not bold**</code>"])

    # document wrapper
    doc = to_document(convert("# Hi"), title="T")
    assert "<!doctype html>" in doc and "<title>T</title>" in doc and "<h1>Hi</h1>" in doc
    print("ok: document wrapper")

    print("\nALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
