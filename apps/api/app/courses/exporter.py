from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Literal


@dataclass(frozen=True)
class LessonBlock:
    kind: Literal["text", "image", "video", "code", "attachment", "interaction", "step", "challenge"]
    content: str
    authored_by: Literal["teacher", "ai"] = "teacher"


@dataclass(frozen=True)
class Course:
    course_id: str
    title: str
    blocks: tuple[LessonBlock, ...]


def export_offline_html(course: Course) -> str:
    parts = ["<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>", escape(course.title), "</title><main>"]
    for block in course.blocks:
        if block.authored_by == "ai":
            parts.extend(["<aside>AI 功能需要联网：", escape(block.content), "</aside>"])
        elif block.kind == "code":
            parts.extend(["<pre data-copyable='true'>", block.content, "</pre>"])
        else:
            parts.extend(["<section>", escape(block.content), "</section>"])
    parts.append("</main></html>")
    return "".join(parts)
