import re
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SCRIPTS))

import check  # noqa: E402
import render  # noqa: E402

COMPONENTS = ("passport", "lede", "stepper", "compare", "timeline", "hypotheses", "chat")
BUG_TRANSFORMS = ["passport", "lede", "stepper", "compare", "timeline", "hypotheses"]
SOFT_BREAK_BR = re.compile(r"<br>\n")


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def badge(html: str) -> str:
    m = re.search(r'<div class="genre-badge"[^>]*data-chrome[^>]*>([^<]*)</div>', html)
    return m.group(1) if m else ""


class ComponentTests(unittest.TestCase):
    def page(self, src: str, **kwargs) -> "render.RenderResult":
        result = render.build(src, **kwargs)
        verdict = check.check(src, result.html)
        self.assertTrue(verdict.ok, f"{verdict.line} {verdict.samples}")
        return result

    def components(self, result: "render.RenderResult") -> list[str]:
        return [t for t in result.transforms if t in COMPONENTS]

    def test_bug_report_components(self):
        r = self.page(fixture("bug.md"))
        self.assertEqual(self.components(r), BUG_TRANSFORMS)
        self.assertEqual((r.genre, r.genre_source), ("bug", "detected"))
        self.assertEqual(badge(r.html), "Баг-репорт")
        self.assertIn('class="passport"', r.html)
        self.assertIn('<ol class="stepper">', r.html)
        self.assertIn('class="compare"', r.html)
        self.assertIn('class="timeline"', r.html)
        self.assertIn('<ol class="hypotheses">', r.html)
        self.assertRegex(r.html, r'<h2 id="[^"]+">Ожидаемый результат</h2>')
        self.assertRegex(r.html, r'<h2 id="[^"]+">Фактический результат</h2>')

    def test_bug_report_english(self):
        r = self.page(fixture("bug-en.md"))
        self.assertEqual(self.components(r), BUG_TRANSFORMS)
        self.assertEqual(r.genre, "bug")
        self.assertEqual(badge(r.html), "Bug report")

    def test_passport_only_directly_after_h1(self):
        r = self.page("# Title\n\nIntro text first.\n\n|  |  |\n|---|---|\n| Owner | Ann |\n| Status | open |\n")
        self.assertNotIn("passport", r.transforms)

    def test_compare_needs_adjacent_pair(self):
        src = ("# Заголовок\n\n## Ожидаемый результат\n\nОдно.\n\n## Окружение\n\nДругое.\n\n"
               "## Фактический результат\n\nТретье.\n")
        r = self.page(src)
        self.assertNotIn("compare", r.transforms)
        self.assertNotIn('class="compare"', r.html)

    def test_timeline_requires_all_time_cells(self):
        src = "| Время | Событие |\n|---|---|\n| 10:00 | Старт |\n| позже | Финиш |\n| 10:30 | Отчёт |\n"
        r = self.page(src)
        self.assertNotIn("timeline", r.transforms)

    def test_thread_chat_and_breaks(self):
        r = self.page(fixture("thread.md"))
        self.assertIn("chat", r.transforms)
        self.assertEqual((r.genre, r.genre_source), ("thread", "detected"))
        self.assertRegex(r.html, SOFT_BREAK_BR)
        hues = dict(re.findall(r'<div class="msg[^"]*" data-author="(\w+)" style="--hue: (\d+)"', r.html))
        self.assertEqual(hues["Ann"], str(render.author_hue("Ann")))
        self.assertEqual(hues["Bob"], str(render.author_hue("Bob")))
        self.assertNotEqual(hues["Ann"], hues["Bob"])
        self.assertEqual(len(re.findall(r'<div class="msg[ "]', r.html)), 5)

    def test_thread_list_form_chat(self):
        r = self.page(fixture("thread-list.md"))
        self.assertIn("chat", r.transforms)
        self.assertEqual((r.genre, r.genre_source), ("thread", "detected"))
        hues = dict(re.findall(r'<div class="msg[^"]*" data-author="([^"]+)" style="--hue: (\d+)"', r.html))
        self.assertEqual(hues["Ann Example"], str(render.author_hue("Ann Example")))
        self.assertEqual(hues["Bob Sample"], str(render.author_hue("Bob Sample")))
        self.assertNotEqual(hues["Ann Example"], hues["Bob Sample"])
        self.assertEqual(len(re.findall(r'<div class="msg[ "]', r.html)), 4)
        self.assertNotRegex(r.html, r"<ul>\s*<li><p><strong>Ann")
        self.assertRegex(r.html, r'<div class="msg-body">\s*<p><strong>Ann Example</strong> <span class="stamp">\(10:01\):</span>')

    def test_thread_list_multiline_item_order_and_nesting(self):
        r = self.page(fixture("thread-list.md"))
        body = re.search(r'data-author="Bob Sample".*?</div></div>', r.html, re.S).group(0)
        self.assertRegex(body, r"the replica lag is back under a second\.<br>\nI will keep the dashboard open")
        self.assertIn("<li>Restart the consumer.</li>", body)
        self.assertNotRegex(self.page(fixture("thread-list.md"), breaks="off").html, SOFT_BREAK_BR)

    def test_mixed_list_not_chat(self):
        src = ("## Replies\n\n- **Ann Example** (10:01): First reply.\n- A plain item without an author.\n"
               "- **Bob Sample** (10:05): Second reply.\n")
        r = self.page(src)
        self.assertNotIn("chat", r.transforms)
        self.assertIn("<ul>", r.html)
        self.assertNotIn('class="chat"', r.html)

    def test_single_item_list_not_chat(self):
        r = self.page("## Replies\n\n- **Ann Example** (10:01): Only reply.\n")
        self.assertNotIn("chat", r.transforms)

    def test_chat_list_item_with_setext_underline(self):
        src = ("## Replies\n\n- **Ann Example** (10:01): First reply.\n"
               "- **Bob Sample** (10:05): Second reply.\n  ---\n  More from Bob.\n"
               "- **Ann Example** (10:07): Third reply.\n")
        r = self.page(src)
        self.assertIn("chat", r.transforms)
        self.assertEqual(r.genre, "thread")
        chat = re.search(r'<div class="chat">.*</div>', r.html, re.S).group(0)
        self.assertEqual(len(re.findall(r'<div class="msg[ "]', chat)), 3)
        self.assertNotIn("<h2", chat)
        self.assertIn("More from Bob.", chat)

    def test_chat_list_item_atx_heading_not_message(self):
        src = ("## Replies\n\n- ## **Ann Example** (10:00): x\n"
               "- **Bob Sample** (10:05): Second reply.\n- **Ann Example** (10:07): Third reply.\n")
        r = self.page(src)
        self.assertNotIn("chat", r.transforms)
        self.assertIn("<ul>", r.html)

    def test_breaks_off_overrides(self):
        r = self.page(fixture("thread.md"), breaks="off")
        self.assertEqual(r.genre, "thread")
        self.assertNotRegex(r.html, SOFT_BREAK_BR)

    def test_breaks_on_for_other_genres(self):
        src = "# Note\n\nFirst line\nsecond line.\n"
        self.assertNotRegex(self.page(src).html, SOFT_BREAK_BR)
        self.assertRegex(self.page(src, breaks="on").html, SOFT_BREAK_BR)

    def test_type_override(self):
        r = self.page("---\ntype: howto\n---\n\n" + fixture("bug.md"))
        self.assertEqual((r.genre, r.genre_source), ("howto", "type"))
        self.assertEqual(badge(r.html), "Инструкция")
        r = self.page("---\ntype: banana\n---\n\n" + fixture("bug.md"))
        self.assertEqual((r.genre, r.genre_source), ("bug", "detected"))
        self.assertIn("unknown type 'banana', using detection", r.warnings)

    def test_heading_with_inline_code_not_flex(self):
        css = (SCRIPTS.parent / "assets" / "style.css").read_text(encoding="utf-8")
        rules = re.findall(r"([^{}]+)\{([^{}]*)\}", css)
        for selector, body in rules:
            if re.search(r"(?<![\w-])h[1-4](?![\w-])", selector):
                self.assertNotRegex(body, r"display:\s*(?:inline-)?flex", selector)
        h2_code = [body for selector, body in rules if re.search(r"(?<![\w-])h2 code\b", selector)]
        self.assertTrue(any(re.search(r"overflow-wrap:\s*anywhere", b) for b in h2_code))
        r = self.page("# Title\n\n## Fix `src/very/long/module_name.py:120` now\n\nText.\n")
        self.assertIn("<code>src/<wbr>", r.html)

    def test_headings_wrap_long_tokens(self):
        """Regression guard: a long unbroken token in a heading scrolled the phone page sideways."""
        css = (SCRIPTS.parent / "assets" / "style.css").read_text(encoding="utf-8")
        css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        rules = dict((sel.strip(), body) for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css))
        body = rules["h1, h2, h3, h4, h5, h6"]
        self.assertRegex(body, r"overflow-wrap:\s*anywhere")
        self.assertRegex(body, r"display:\s*block")

    def test_incident_timeline(self):
        r = self.page(fixture("incident.md"))
        self.assertEqual(r.genre, "incident")
        self.assertIn("timeline", r.transforms)
        self.assertEqual(badge(r.html), "Incident")

    def test_howto_detection(self):
        r = self.page(fixture("howto.md"))
        self.assertEqual(r.genre, "howto")
        self.assertIn("stepper", r.transforms)

    def test_note_fallback(self):
        r = self.page(fixture("note.md"))
        self.assertEqual((r.genre, r.genre_source), ("note", "detected"))
        self.assertEqual(self.components(r), [])
        self.assertEqual(badge(r.html), "")

    def test_detect_genre_rules(self):
        self.assertEqual(render.detect_genre(None, [], set()), ("note", "detected", None))
        self.assertEqual(render.detect_genre("Spec", [], set()), ("spec", "type", None))
        self.assertEqual(render.detect_genre(None, ["Scope", "Non-goals"], set())[0], "spec")
        self.assertEqual(render.detect_genre(None, [f"Part {i}" for i in range(5)], set())[0], "explainer")
        self.assertEqual(render.detect_genre(None, ["Причина сбоя"], {"timeline"})[0], "incident")
        self.assertEqual(render.detect_genre(None, [], {"timeline"})[0], "note")
        self.assertEqual(render.detect_genre(None, [], {"compare"})[0], "note")
        self.assertEqual(render.detect_genre(None, [], {"chat"})[0], "thread")
        self.assertEqual(render.GENRES, ("bug", "incident", "thread", "explainer", "spec", "howto", "note"))
        self.assertEqual(set(render.KEYWORDS), {"lede", "steps", "expected", "actual", "hypotheses", "time_head"})

    def test_author_hue_deterministic(self):
        self.assertEqual(render.author_hue("Ann"), int(__import__("hashlib").sha256(b"Ann").hexdigest()[:8], 16) % 360)

    def test_components_deterministic(self):
        for name in ("bug.md", "thread.md", "incident.md"):
            self.assertEqual(render.build(fixture(name)).html, render.build(fixture(name)).html)


if __name__ == "__main__":
    unittest.main()
