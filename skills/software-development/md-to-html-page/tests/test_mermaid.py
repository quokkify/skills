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

    def test_directive_lines_and_subgraph(self):
        # regression guard: styling lines and subgraphs used to make render() return None
        src = (
            "flowchart TB\n  classDef warm fill:#fee\n  subgraph one [First Stage]\n"
            "    direction LR\n    A[Alpha] --> B[Beta]\n  end\n"
            "  subgraph Second\n    C --> D\n  end\n  B --> C\n"
            "  style A fill:#eee\n  class B warm\n  linkStyle 0 stroke:red\n  click A href"
        )
        out = mermaid_view.render(src)
        self.assertIsNotNone(out)
        self.assertEqual(out.count('class="fl-group-label"'), 2)
        for w in ("First Stage", "Second", "Alpha", "Beta"):
            self.assertIn(w, out)
        self.assertNotIn("fill", out)
        self.assertLess(out.index("First Stage"), out.index("Alpha"))

    def test_node_ids_starting_with_keywords(self):
        # regression guard: bare prefix matching rejected ids like `endpoint`
        out = mermaid_view.render("flowchart LR\n endpoint --> classifier\n style1 --> end2")
        self.assertIsNotNone(out)
        for w in ("endpoint", "classifier", "style1", "end2"):
            self.assertIn(w, out)

    def test_trailing_semicolons(self):
        out = mermaid_view.render("graph LR;\n A[One] --> B[Two];\n B --> C;")
        self.assertIsNotNone(out)
        self.assertIn("One", out)
        self.assertNotIn(";", out)

    def test_ampersand_expands_sources_and_targets(self):
        out = mermaid_view.render("flowchart LR\n A & B --> C\n C --> D & E")
        parsed = mermaid_view.parse("flowchart LR\n A & B --> C\n C --> D & E")
        self.assertEqual(parsed[2], [("A", "C", ""), ("B", "C", ""), ("C", "D", ""), ("C", "E", "")])
        self.assertIn("E", out)

    def test_subgraph_claims_node_seen_earlier(self):
        out = mermaid_view.render("flowchart LR\n A --> B\n subgraph Box\n  A\n end")
        self.assertLess(out.index("Box"), out.index('fl-label">A<'))

    def test_unbalanced_subgraph_returns_none(self):
        self.assertIsNone(mermaid_view.render("flowchart LR\n subgraph X\n A --> B"))
        self.assertIsNone(mermaid_view.render("flowchart LR\n A --> B\n end"))

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
