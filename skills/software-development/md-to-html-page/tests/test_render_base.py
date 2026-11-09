import base64
import re
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SCRIPTS))

import check  # noqa: E402
import render  # noqa: E402

PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)
RU_PROSE = "Это короткая заметка о том, как устроен процесс выпуска и что проверить заранее."
EN_PROSE = "This is a short note about how the release process works and what to check first."


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def h2s(n: int, prose: str = EN_PROSE) -> str:
    return "".join(f"## Part {i}\n\n{prose}\n\n" for i in range(1, n + 1))


class RenderBaseTests(unittest.TestCase):
    def render(self, src: str, **kwargs) -> render.RenderResult:
        result = render.build(src, **kwargs)
        verdict = check.check(src, result.html)
        self.assertTrue(verdict.ok, f"{verdict.line} {verdict.samples}")
        return result

    def test_minimal_document(self):
        r = self.render(fixture("minimal.md"), stem="Заметка")
        self.assertIn("<title>Заметка</title>", r.html)
        self.assertEqual(r.transforms, ())
        self.assertEqual((r.genre, r.genre_source), ("note", "detected"))

    def test_title_precedence(self):
        body = "# Heading title\n\nSome text.\n"
        fm = "---\ntitle: Front title\n---\n\n"
        self.assertIn("<title>Front title</title>", self.render(fm + body, stem="stem").html)
        self.assertIn("<title>Heading title</title>", self.render(body, stem="stem").html)
        self.assertIn("<title>stem</title>", self.render("Some text.\n", stem="stem").html)

    def test_front_matter_title_without_h1_is_chrome(self):
        r = self.render("---\ntitle: Front title\n---\n\nSome text.\n")
        self.assertRegex(r.html, r"<h1[^>]*data-chrome[^>]*>Front title</h1>")

    def test_front_matter_hidden(self):
        r = self.render(fixture("note.md"))
        self.assertNotIn("visibility", r.html)
        self.assertNotIn("internal", r.html)

    def test_toc_threshold(self):
        r = self.render(h2s(3))
        self.assertIn("toc", r.transforms)
        self.assertIn("<nav data-chrome", r.html)
        r = self.render(h2s(2))
        self.assertNotIn("toc", r.transforms)
        self.assertNotIn("<nav", r.html)

    def test_code_highlight_and_copy(self):
        r = self.render(fixture("code.md"))
        self.assertIn('class="highlight"', r.html)
        self.assertIn("code", r.transforms)
        self.assertRegex(r.html, r'<button[^>]*class="copy"[^>]*data-chrome')
        used = set(re.findall(r'<span class="([\w-]+)"', r.html))
        self.assertIn("k", used)
        self.assertNotIn("kd", used)
        self.assertNotIn(".highlight .kd", r.html)
        self.assertIn(".highlight .k ", r.html)

    def test_inline_code_wbr(self):
        r = self.render(fixture("code.md"))
        self.assertIn("<code>a/<wbr>b_<wbr>c.<wbr>d:<wbr>e</code>", r.html)

    def test_callouts(self):
        r = self.render(fixture("callouts.md"))
        self.assertIn("callout", r.transforms)
        self.assertIn('class="callout c-warning"', r.html)
        self.assertIn("Disk almost full", r.html)
        self.assertRegex(r.html, r'<details class="callout c-note"')
        self.assertNotIn("[!", r.html)
        self.assertNotIn("c-foobar", r.html)
        self.assertEqual(r.html.count("c-note"), 2)

    def test_ui_auto(self):
        r = self.render(h2s(3, RU_PROSE))
        self.assertIn('lang="ru"', r.html)
        self.assertIn("Содержание", r.html)
        r = self.render(h2s(3, EN_PROSE))
        self.assertIn('lang="en"', r.html)
        self.assertIn("Contents", r.html)
        r = self.render(h2s(3, RU_PROSE), ui="en")
        self.assertIn("Contents", r.html)
        self.assertNotIn("Содержание", r.html)

    def test_pick_ui_ignores_code(self):
        src = "Короткий текст.\n\n```\n" + "english words " * 50 + "\n```\n\n`more english code here`\n"
        self.assertEqual(render.pick_ui(src, "auto"), "ru")
        self.assertEqual(render.pick_ui(src, "en"), "en")
        self.assertEqual(render.pick_ui(EN_PROSE, "auto"), "en")

    def test_local_image_embedded(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "dot.png").write_bytes(PNG_1X1)
            src = "Picture: ![dot](dot.png)\n"
            r = self.render(src, source_dir=Path(tmp))
        self.assertIn('src="data:image/png;base64,', r.html)
        self.assertIn("image", r.transforms)

    def test_image_outside_source_dir_not_embedded(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "dot.png").write_bytes(PNG_1X1)
            sub = Path(tmp, "sub")
            sub.mkdir()
            r = self.render("![dot](../dot.png)\n", source_dir=sub)
        self.assertNotIn("<img", r.html)
        self.assertTrue(r.warnings)

    def test_remote_image_placeholder(self):
        r = self.render("See ![pic](https://example.com/p.png) here.\n")
        self.assertNotIn("<img", r.html)
        self.assertIn("image", r.transforms)
        self.assertRegex(r.html, r"<span data-derived>[^<]*https://example\.com/p\.png")

    def test_wikilinks_plain_and_reported(self):
        r = self.render("Read [[Other note|see]] and [x](./other.md) too.\n")
        self.assertIn("see", r.html)
        self.assertNotIn('href="./other.md"', r.html)
        self.assertEqual(r.unresolved_links, ("[[Other note]]", "./other.md"))

    def test_callout_title_links_resolved_and_reported(self):
        # Regression guard: title children left the inline before link handling ran.
        r = self.render("> [!TIP] See [doc](./other.md) and [[Wiki]]\n> body\n")
        self.assertNotIn('href="./other.md"', r.html)
        self.assertEqual(r.unresolved_links, ("./other.md", "[[Wiki]]"))

    def test_two_remote_image_placeholders(self):
        # Regression guard: adjacent data-derived spans were joined into one word.
        r = self.render("![a](https://example.com/h.png) ![b](https://example.com/p.png)\n")
        self.assertEqual(r.html.count("<span data-derived>"), 2)

    def test_footnote_passes_gate(self):
        r = self.render("Text with a note[^1].\n\n[^1]: Foot text.\n")
        self.assertIn('class="footnote-ref"', r.html)
        self.assertIn("Foot text.", r.html)

    def test_raw_html_allowlist(self):
        r = self.render(fixture("note.md"))
        self.assertIn("<kbd>Ctrl</kbd>", r.html)
        self.assertIn("&lt;service-name&gt;", r.html)
        r = self.render('<div class="x">block</div>\n\nText <b onclick="x()">b</b> <script>alert(1)</script>\n')
        self.assertNotIn("<script>alert", r.html)
        self.assertNotIn('<div class="x">', r.html)

    def test_raw_html_rule_matches_check(self):
        samples = [
            "<b>x</b>", "<B>x</B>", "<br/>", "<br >", "<b class='x'>x</b>", "<kbd>K</kbd>",
            "<span>s</span>", "<script>a</script>", "<i\n>x</i>", "a < b > c", "<mark>m</mark>&amp;",
        ]
        for s in samples:
            self.assertEqual(render.escape_raw(s), check._escape_raw(s), s)

    def test_task_list_checkboxes(self):
        r = self.render(fixture("note.md"))
        self.assertIn('type="checkbox"', r.html)
        self.assertNotIn("&lt;input", r.html)

    def test_note_fixture_full(self):
        r = self.render(fixture("note.md"), stem="note")
        self.assertEqual(r.transforms, ("toc", "code", "callout"))
        self.assertIn("<title>Release checklist</title>", r.html)

    def test_breaks_on(self):
        r = self.render("line one\nline two\n", breaks="on")
        self.assertIn("line one<br>", r.html)
        r = self.render("line one\nline two\n")
        self.assertNotIn("line one<br>", r.html)

    def test_deterministic(self):
        src = fixture("note.md")
        self.assertEqual(render.build(src).html, render.build(src).html)

    def test_offline_shell(self):
        r = self.render(fixture("code.md"))
        self.assertIn(f'<meta http-equiv="Content-Security-Policy" content="{check.CSP}">', r.html)
        for tag in re.findall(r"<(?:link|script)\b[^>]*>", r.html):
            self.assertNotRegex(tag, r"https?://")
        self.assertIn("prefers-color-scheme: dark", r.html)
        self.assertIn("@media print", r.html)
        self.assertNotRegex(r.html, r"\son\w+=")

    def test_ui_labels_complete(self):
        keys = {
            "toc", "copy", "copied", "theme", "note", "tip", "important", "warning", "caution",
            "image_not_embedded", "diagram_source", "diagram_text", "genre_bug", "genre_incident",
            "genre_thread", "genre_explainer", "genre_spec", "genre_howto", "genre_note",
        }
        for lang in ("ru", "en"):
            self.assertLessEqual(keys, set(render.UI[lang]), lang)

    def test_cli_report(self):
        import subprocess

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp, "in.md")
            src.write_text("Read [[Other note]].\n\n## A\n\nx\n\n## B\n\ny\n\n## C\n\nz\n", encoding="utf-8")
            out = Path(tmp, "out.html")
            proc = subprocess.run(
                [sys.executable, "-I", str(SCRIPTS / "render.py"), str(src), "-o", str(out), "--ui", "en"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(
                proc.stderr.splitlines(),
                ["genre: note (detected)", "transforms: toc", "unresolved: [[Other note]]"],
            )
            self.assertIn("<title>in</title>", out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
