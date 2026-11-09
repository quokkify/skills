import html
import re
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SCRIPTS))

import check  # noqa: E402
import mermaid_view  # noqa: E402
import render  # noqa: E402


class MermaidViewTests(unittest.TestCase):
    def test_flowchart_view(self):
        out = mermaid_view.render("flowchart LR\n A[Start] --> B{Check}\n B -->|yes| C[Done]")
        self.assertIsNotNone(out)
        self.assertTrue(out.startswith('<div class="mermaid-view" data-derived>'))
        pos = [out.index(w) for w in ("Start", "Check", "yes", "Done")]
        self.assertEqual(pos, sorted(pos))

    def test_unsupported_returns_none(self):
        self.assertIsNone(mermaid_view.render("sequenceDiagram\n A->>B: hi"))
        self.assertIsNone(mermaid_view.render("flowchart\n A --> B"))
        self.assertIsNone(mermaid_view.render("flowchart LR\n A"))

    def test_labels_are_cleaned_and_escaped(self):
        out = mermaid_view.render('graph TD\n A["One<br/>two"] --> B(<b>x</b>)')
        self.assertIn("One two", out)
        self.assertNotIn("<b>", out)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", out)

    def test_explainer_page(self):
        src = (FIXTURES / "explainer.md").read_text(encoding="utf-8")
        r = render.build(src)
        v = check.check(src, r.html)
        self.assertTrue(v.ok, f"{v.line} {v.samples}")
        self.assertEqual(r.genre, "explainer")
        self.assertIn("mermaid", r.transforms)
        fence = re.search(r"```mermaid\n(.*?)\n```", src, re.S).group(1)
        pres = re.findall(r"<pre[^>]*>(.*?)</pre>", r.html, re.S)
        self.assertTrue(any(fence in html.unescape(p) for p in pres))
        self.assertIn('class="mermaid-view" data-derived', r.html)

    def test_unsupported_diagram_keeps_only_source(self):
        src = "# T\n\n```mermaid\nsequenceDiagram\n  A->>B: hi\n```\n"
        r = render.build(src)
        self.assertTrue(check.check(src, r.html).ok)
        self.assertIn("mermaid", r.transforms)
        self.assertNotIn('class="mermaid-view"', r.html)


if __name__ == "__main__":
    unittest.main()
