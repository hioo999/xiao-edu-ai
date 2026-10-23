from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser


SCRIPT_TAG = re.compile(r"<script[\s\S]*?</script\s*>", re.IGNORECASE)
EVENT_HANDLER = re.compile(r"\s+on[a-z]+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)", re.IGNORECASE)
JAVASCRIPT_URL = re.compile(r"(href|src)\s*=\s*(['\"])javascript:[^'\"]*\2", re.IGNORECASE)


def sanitize_html(html: str) -> str:
    sanitized = SCRIPT_TAG.sub("", html)
    sanitized = EVENT_HANDLER.sub("", sanitized)
    return JAVASCRIPT_URL.sub(r"\1=\2#\2", sanitized)


class InteractiveDocument(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.parts: list[str] = []
        self.blocked = ""
        self.depth = 0
        self.body_attributes = ""

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if self.blocked:
            if tag == self.blocked:
                self.depth += 1
            return
        if tag in {"iframe", "object", "embed"} or (tag == "script" and "src" in attributes):
            if tag != "embed":
                self.blocked, self.depth = tag, 1
            return
        if tag in {"html", "head", "base", "link", "form"} or (tag == "meta" and "http-equiv" in attributes):
            return
        safe_attrs = []
        for name, value in attrs:
            if name in {"srcdoc", "action", "formaction", "target", "ping"}:
                continue
            if name in {"href", "src", "poster", "xlink:href"} and value and not value.startswith(("#", "data:image/", "data:audio/", "data:video/", "blob:")):
                continue
            safe_attrs.append(name if value is None else f'{name}="{escape(value, quote=True)}"')
        suffix = " " + " ".join(safe_attrs) if safe_attrs else ""
        if tag == "body":
            self.body_attributes = suffix
            return
        self.parts.append(f"<{tag}{suffix}>")

    def handle_endtag(self, tag):
        if self.blocked:
            if tag == self.blocked:
                self.depth -= 1
                if self.depth == 0:
                    self.blocked = ""
            return
        if tag not in {"html", "head", "body", "base", "link", "form", "embed", "meta"}:
            self.parts.append(f"</{tag}>")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in {"img", "br", "hr", "input", "meta", "link", "base", "embed", "source", "wbr"}:
            self.handle_endtag(tag)

    def handle_data(self, data):
        if not self.blocked:
            self.parts.append(data)

    def handle_entityref(self, name):
        self.handle_data(f"&{name};")

    def handle_charref(self, name):
        self.handle_data(f"&#{name};")

    def handle_decl(self, decl):
        return


def prepare_interactive_html(html: str) -> str:
    parser = InteractiveDocument()
    parser.feed(html)
    document = "".join(parser.parts)
    policy = "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; media-src data: blob:; font-src data:; connect-src 'none'; frame-src 'none'; object-src 'none'; form-action 'none'; base-uri 'none'"
    security = f'<meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="{policy}"><meta name="viewport" content="width=device-width,initial-scale=1">'
    return f'<!doctype html><html lang="zh-CN"><head>{security}</head><body{parser.body_attributes}>{document}</body></html>'
