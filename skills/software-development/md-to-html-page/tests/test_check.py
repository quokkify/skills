import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check  # noqa: E402

CSP = "default-src 'none'; img-src data:; style-src 'unsafe-inline'; script-src 'unsafe-inline'"


def page(body: str, head: str = "", csp: bool = True) -> str:
    meta = f'<meta http-equiv="Content-Security-Policy" content="{CSP}">' if csp else ""
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        f"{meta}<title>T</title>{head}</head><body>{body}</body></html>"
    )


MD = "# T\n\nHello **world** 42.\n"
BODY = "<h1>T</h1><p>Hello <strong>world</strong> 42.</p>"
TABLE_MD = "|a|b|\n|-|-|\n|1|2|\n"


def table(c1: str, c2: str) -> str:
    return (
        "<table><thead><tr><th>a</th><th>b</th></tr></thead>"
        f"<tbody><tr><td>{c1}</td><td>{c2}</td></tr></tbody></table>"
    )


class FidelityTests(unittest.TestCase):
    def test_identical_passes(self):
        r = check.check(MD, page(BODY))
        self.assertTrue(r.ok, r.line)
        self.assertTrue(r.line.startswith("PASS words="))
        self.assertIsNone(r.gate)

    def test_changed_digit_fails(self):
        r = check.check(MD, page(BODY.replace("42", "43")))
        self.assertEqual(r.gate, "words")
        self.assertTrue(any("42" in s for s in r.samples))

    def test_dropped_word_fails(self):
        r = check.check(MD, page("<h1>T</h1><p>Hello 42.</p>"))
        self.assertEqual(r.gate, "words")

    def test_swapped_cells_fails(self):
        r = check.check(TABLE_MD, page(table("2", "1")))
        self.assertEqual(r.gate, "order")

    def test_table_passes(self):
        r = check.check(TABLE_MD, page(table("1", "2")))
        self.assertTrue(r.ok, r.line)

    def test_punctuation_change_fails(self):
        r = check.check(MD, page(BODY.replace("42.", "42!")))
        self.assertEqual(r.gate, "order")

    def test_code_whitespace_fails(self):
        r = check.check("```\na  b\n```\n", page("<pre><code>a b</code></pre>"))
        self.assertEqual(r.gate, "blocks")

    def test_code_block_passes(self):
        r = check.check("```\na  b\n```\n", page("<pre><code>a  b\n</code></pre>"))
        self.assertTrue(r.ok, r.line)

    def test_inline_code_must_be_code(self):
        r = check.check("`x_y`\n", page("<p>x_y</p>"))
        self.assertEqual(r.gate, "blocks")

    def test_removed_href_fails(self):
        r = check.check(
            "[t](https://example.com/a)\n",
            page('<p><a href="https://example.com/b">t</a></p>'),
        )
        self.assertEqual(r.gate, "blocks")

    def test_href_present_passes(self):
        r = check.check(
            "[t](https://example.com/a)\n",
            page('<p><a href="https://example.com/a">t</a></p>'),
        )
        self.assertTrue(r.ok, r.line)
        self.assertIn("hrefs=1", r.line)

    def test_relative_href_not_required(self):
        md = "[a](./other.md) [b](../x/y.md) [c](#top) [d](mailto:a@example.com)\n"
        body = '<p><span>a</span> <span>b</span> <a href="#top">c</a> <a href="mailto:a@example.com">d</a></p>'
        r = check.check(md, page(body))
        self.assertTrue(r.ok, r.line)
        self.assertIn("hrefs=2", r.line)

    def test_anchor_href_still_required(self):
        r = check.check("[c](#top)\n", page("<p><span>c</span></p>"))
        self.assertEqual(r.gate, "blocks")

    def test_wbr_rejoined(self):
        r = check.check("`a/b_c`\n", page("<p><code>a/<wbr>b_<wbr>c</code></p>"))
        self.assertTrue(r.ok, r.line)

    def test_chrome_ignored(self):
        r = check.check(MD, page("<nav data-chrome>Содержание</nav>" + BODY))
        self.assertTrue(r.ok, r.line)

    def test_derived_word_not_in_source_fails(self):
        r = check.check(MD, page(BODY + "<div data-derived>invented</div>"))
        self.assertEqual(r.gate, "derived")

    def test_derived_placeholder_passes(self):
        r = check.check(
            "![pic](https://example.com/p.png)\n",
            page("<figure><span data-derived>pic https://example.com/p.png</span></figure>"),
        )
        self.assertTrue(r.ok, r.line)

    def test_front_matter_ignored(self):
        r = check.check("---\nsecret: x\n---\n" + MD, page(BODY))
        self.assertTrue(r.ok, r.line)

    def test_wikilink_alias(self):
        r = check.check("[[Note|alias]]\n", page("<p>alias</p>"))
        self.assertTrue(r.ok, r.line)

    def test_wikilink_target(self):
        r = check.check("[[Note]]\n", page("<p>Note</p>"))
        self.assertTrue(r.ok, r.line)

    def test_callout_and_task_markers_removed(self):
        md = "> [!NOTE]+ Careful\n> body\n\n- [x] done\n- [ ] todo\n"
        body = (
            "<blockquote><p>Careful body</p></blockquote>"
            '<ul><li><input type="checkbox" checked>done</li>'
            '<li><input type="checkbox">todo</li></ul>'
        )
        r = check.check(md, page(body))
        self.assertTrue(r.ok, r.line)

    def test_wikilink_inside_code_untouched(self):
        r = check.check("`[[a|b]]`\n", page("<p><code>[[a|b]]</code></p>"))
        self.assertTrue(r.ok, r.line)

    def test_allowed_raw_inline_tag_passes(self):
        r = check.check("Press <kbd>Ctrl</kbd> now.\n", page("<p>Press <kbd>Ctrl</kbd> now.</p>"))
        self.assertTrue(r.ok, r.line)

    def test_allowed_raw_br_passes(self):
        r = check.check("a<br>b\n", page("<p>a<br>b</p>"))
        self.assertTrue(r.ok, r.line)

    def test_disallowed_raw_tag_must_be_escaped(self):
        md = "x <span class=x>y</span>\n"
        escaped = "<p>x &lt;span class=x&gt;y&lt;/span&gt;</p>"
        self.assertTrue(check.check(md, page(escaped)).ok)
        self.assertFalse(check.check(md, page("<p>x <span class=\"x\">y</span></p>")).ok)

    def test_first_gate_only(self):
        r = check.check(MD, page(BODY.replace("42", "43"), csp=False))
        self.assertEqual(r.gate, "words")


class OfflineTests(unittest.TestCase):
    def gate(self, head="", body=BODY, csp=True):
        return check.check(MD, page(body, head, csp))

    def test_script_src_fails(self):
        self.assertEqual(self.gate('<script src="app.js"></script>').gate, "offline")

    def test_remote_link_fails(self):
        r = self.gate('<link rel="stylesheet" href="https://example.com/a.css">')
        self.assertEqual(r.gate, "offline")

    def test_remote_img_fails(self):
        r = self.gate(body=BODY + '<img src="https://example.com/a.png" alt="">')
        self.assertEqual(r.gate, "offline")

    def test_import_fails(self):
        r = self.gate('<style>@import "a.css";</style>')
        self.assertEqual(r.gate, "offline")

    def test_url_http_fails(self):
        r = self.gate("<style>b{background:url(https://example.com/a.png)}</style>")
        self.assertEqual(r.gate, "offline")

    def test_fetch_in_inline_js_fails(self):
        r = self.gate("<script>fetch('x')</script>")
        self.assertEqual(r.gate, "offline")

    def test_event_handler_attr_fails(self):
        r = self.gate(body=BODY.replace("<p>", '<p onclick="fetch(1)">'))
        self.assertEqual(r.gate, "offline")

    def test_javascript_url_fails(self):
        r = self.gate(body=BODY + '<a href="JavaScript:void(0)"></a>')
        self.assertEqual(r.gate, "offline")

    def test_missing_csp_fails(self):
        self.assertEqual(self.gate(csp=False).gate, "offline")

    def test_wrong_csp_fails(self):
        html_text = page(BODY).replace("img-src data:", "img-src *")
        self.assertEqual(check.check(MD, html_text).gate, "offline")

    def test_clean_inline_assets_pass(self):
        r = self.gate("<style>b{color:red}</style><script>var a=1</script>")
        self.assertTrue(r.ok, r.line)
        self.assertIn("offline=ok", r.line)

    def test_data_img_passes(self):
        r = self.gate(body=BODY + '<img src="data:image/png;base64,AAAA" alt="">')
        self.assertTrue(r.ok, r.line)


class CliTests(unittest.TestCase):
    def run_cli(self, md, html_text):
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            m, h = Path(d, "a.md"), Path(d, "a.html")
            if md is not None:
                m.write_text(md, encoding="utf-8")
            h.write_text(html_text, encoding="utf-8")
            return subprocess.run(
                [sys.executable, "-I", str(Path(check.__file__)), str(m), str(h)],
                capture_output=True,
                text=True,
            )

    def test_exit_codes(self):
        ok = self.run_cli(MD, page(BODY))
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertTrue(ok.stdout.startswith("PASS words="))
        bad = self.run_cli(MD, page(BODY.replace("42", "43")))
        self.assertEqual(bad.returncode, 1)
        self.assertIn("\n  - ", bad.stdout)
        self.assertEqual(self.run_cli(None, page(BODY)).returncode, 2)


if __name__ == "__main__":
    unittest.main()
