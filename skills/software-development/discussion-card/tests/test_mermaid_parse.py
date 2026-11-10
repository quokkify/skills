import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from markdown_it import MarkdownIt  # noqa: E402

import mermaid_parse as mp  # noqa: E402
from mermaid_parse import Edge, parse_flowchart, split_subgraphs  # noqa: E402

TWO_PARTS = (
    "flowchart LR\n"
    "  subgraph one [First Stage]\n"
    "    A[Alpha] --> B{Beta}\n"
    "  end\n"
    "  subgraph two\n"
    "    C((Gamma)) -- \"ok\" --> D\n"
    "  end\n"
    "  B -->|go| C\n"
    "  X --> A\n"
)


class FindBlocksTests(unittest.TestCase):
    def test_find_blocks_index_and_kind(self):
        md = (
            "```python\nx\n```\n\n```mermaid\nflowchart LR\n A-->B\n```\n\n"
            "```mermaid\nsequenceDiagram\n A->>B: hi\n```\n"
        )
        toks = MarkdownIt("commonmark").enable("table").parse(md)
        got = mp.find_mermaid_blocks(toks)
        self.assertEqual([(i, k) for i, k, _ in got], [(1, "flowchart"), (2, "sequenceDiagram")])
        self.assertEqual(got[0][2], "flowchart LR\n A-->B")


class ParseTests(unittest.TestCase):
    def test_basic_labels_and_edges(self):
        fc = parse_flowchart(3, "flowchart TD\n A[Start] --> B{Check}\n B -->|yes| C[Done]")
        self.assertEqual((fc.index, fc.direction), (3, "TD"))
        self.assertEqual(fc.nodes, {"A": "Start", "B": "Check", "C": "Done"})
        self.assertEqual(fc.edges, [Edge("A", "B", None), Edge("B", "C", "yes")])

    def test_fanin_ampersand(self):
        fc = parse_flowchart(1, "flowchart LR\n C1 & C2 --> D")
        self.assertEqual(fc.edges, [Edge("C1", "D", None), Edge("C2", "D", None)])
        self.assertEqual(fc.nodes, {"C1": "C1", "C2": "C2", "D": "D"})

    def test_chain_comments_semicolons_and_quoted_labels(self):
        src = 'graph LR;\n %% note\n A["One<br/>two"] --> B[Two];\n B -- "lab" --> C;'
        fc = parse_flowchart(1, src)
        self.assertEqual(fc.direction, "LR")
        self.assertEqual(fc.nodes["A"], "One two")
        self.assertEqual(fc.edges, [Edge("A", "B", None), Edge("B", "C", "lab")])
        fc = parse_flowchart(1, "flowchart LR\n A --> B --> C")
        self.assertEqual(len(fc.edges), 2)

    def test_directive_lines_and_keyword_prefixed_ids(self):
        fc = parse_flowchart(1, "flowchart LR\n classDef w fill:#fee\n endpoint --> classifier\n style endpoint fill:#eee")
        self.assertEqual(list(fc.nodes), ["endpoint", "classifier"])

    def test_subgraph_membership(self):
        fc = parse_flowchart(1, TWO_PARTS)
        sg = {s.id: s for s in fc.subgraphs}
        self.assertEqual(sg["one"].title, "First Stage")
        self.assertEqual(sg["one"].node_ids, ["A", "B"])
        self.assertEqual(sg["two"].title, "two")
        self.assertEqual(sg["two"].node_ids, ["C", "D"])
        self.assertNotIn("X", sg["one"].node_ids + sg["two"].node_ids)

    def test_node_declared_outside_then_inside_belongs_to_subgraph(self):
        fc = parse_flowchart(1, "flowchart LR\n A --> B\n subgraph Box\n  A\n end")
        self.assertEqual(fc.subgraphs[0].node_ids, ["A"])

    def test_quoted_subgraph_title(self):
        fc = parse_flowchart(1, 'flowchart LR\n subgraph X["Big Title"]\n  A --> B\n end')
        self.assertEqual((fc.subgraphs[0].id, fc.subgraphs[0].title), ("X", "Big Title"))

    def test_unbalanced_raises(self):
        with self.assertRaises(ValueError):
            parse_flowchart(1, "flowchart LR\n subgraph X\n A --> B")
        with self.assertRaises(ValueError):
            parse_flowchart(1, "sequenceDiagram\n A->>B: hi")


class SplitTests(unittest.TestCase):
    def test_split_keeps_internal_edges_and_returns_cross_edges(self):
        parts, cross = split_subgraphs(parse_flowchart(1, TWO_PARTS))
        self.assertEqual([sg.id for sg, _ in parts], ["", "one", "two"])
        self.assertEqual(cross, [Edge("B", "C", "go"), Edge("X", "A", None)])
        self.assertIn("A --> B", parts[1][1])
        self.assertIn("C -->|ok| D", parts[2][1])
        self.assertNotIn("go", parts[1][1] + parts[2][1])

    def test_split_part_source_is_valid_flowchart(self):
        parts, _ = split_subgraphs(parse_flowchart(1, TWO_PARTS))
        src0, src1 = parts[1][1], parts[2][1]
        self.assertTrue(src0.startswith("flowchart LR\n"))
        self.assertIn("A[Alpha]", src0)
        self.assertIn("B{Beta}", src0)
        self.assertIn("C((Gamma))", src1)
        again = parse_flowchart(1, src1)
        self.assertEqual(set(again.nodes), {"C", "D"})
        self.assertEqual(again.nodes["C"], "Gamma")
        self.assertEqual(set(parse_flowchart(1, src0).nodes), {"A", "B"})

    def test_root_nodes_form_leading_part(self):
        # regression guard: nodes outside every subgraph used to be dropped by the split
        src = "flowchart LR\n X[Outside] -.-> A\n Y --> X\n subgraph s\n  A\n end"
        parts, cross = split_subgraphs(parse_flowchart(1, src))
        self.assertEqual([sg.id for sg, _ in parts], ["", "s"])
        self.assertIsNone(parts[0][0].title)
        self.assertEqual(parts[0][0].node_ids, ["X", "Y"])
        self.assertIn("X[Outside]", parts[0][1])
        self.assertIn("Y --> X", parts[0][1])
        self.assertEqual(cross, [Edge("X", "A", None, "-.->")])

    def test_arrow_styles_survive_split(self):
        src = "flowchart LR\n subgraph s\n  A ==> B\n  B -.-> C\n  C ---|t| D\n end"
        (_, text), = split_subgraphs(parse_flowchart(1, src))[0]
        self.assertIn("A ==> B", text)
        self.assertIn("B -.-> C", text)
        self.assertIn("C ---|t| D", text)


class NoSpaceEdgeTests(unittest.TestCase):
    def test_no_space_links(self):
        # regression guard: ids swallowed `--` so `A-->B` raised ValueError
        cases = {
            "A-->B": Edge("A", "B", None, "-->"),
            "A-->|yes|B": Edge("A", "B", "yes", "-->"),
            "A-.->B": Edge("A", "B", None, "-.->"),
            "A==>B": Edge("A", "B", None, "==>"),
            "A---B": Edge("A", "B", None, "---"),
            "A--xB": Edge("A", "B", None, "--x"),
            "A<-->B": Edge("A", "B", None, "<-->"),
        }
        for line, want in cases.items():
            with self.subTest(line=line):
                self.assertEqual(parse_flowchart(1, f"flowchart LR\n {line}").edges, [want])

    def test_hyphenated_ids(self):
        fc = parse_flowchart(1, "flowchart LR\n node-1-->node-2\n node-2 --> n-3")
        self.assertEqual(list(fc.nodes), ["node-1", "node-2", "n-3"])


class GrammarFormsTests(unittest.TestCase):
    """Regression guard: forms Mermaid renders fine used to fail the parse and turn the diagram into code."""

    NODE_CASES = {
        "A([Stadium])": ("A", "Stadium"),
        "A[[Sub]]": ("A", "Sub"),
        "A[(Db)]": ("A", "Db"),
        "A(((Twice)))": ("A", "Twice"),
        "A>Flag]": ("A", "Flag"),
        "A{{Hex}}": ("A", "Hex"),
        "A[/Lean/]": ("A", "Lean"),
        "A[\\Back\\]": ("A", "Back"),
        "A[/Trap\\]": ("A", "Trap"),
        "A[x]:::cls": ("A", "x"),
        "A:::cls": ("A", "A"),
        "1[One]": ("1", "One"),
        "Узел[Привет]": ("Узел", "Привет"),
        'A["paren (x) ] inside"]': ("A", "paren (x) ] inside"),
    }

    EDGE_CASES = {
        "A ---> B": Edge("A", "B", None, "--->"),
        "A ----> B": Edge("A", "B", None, "---->"),
        "A ---- B": Edge("A", "B", None, "----"),
        "A -. t .-> B": Edge("A", "B", "t", "-.->"),
        "A -. two words .- B": Edge("A", "B", "two words", "-.-"),
        "A -..-> B": Edge("A", "B", None, "-..->"),
        "A == t ==> B": Edge("A", "B", "t", "==>"),
        "A ===> B": Edge("A", "B", None, "===>"),
        "A === B": Edge("A", "B", None, "==="),
        "A x--x B": Edge("A", "B", None, "x--x"),
        "A o--o B": Edge("A", "B", None, "o--o"),
        "A <==> B": Edge("A", "B", None, "<==>"),
        "A ~~~ B": Edge("A", "B", None, "~~~"),
        "A -- t --> B": Edge("A", "B", "t", "-->"),
        "A -- t --- B": Edge("A", "B", "t", "---"),
        "A --> o": Edge("A", "o", None, "-->"),
        "A --- xray": Edge("A", "xray", None, "---"),
        "1 --> 2": Edge("1", "2", None, "-->"),
        "A[x]:::c --> B([y]):::d": Edge("A", "B", None, "-->"),
    }

    def test_node_shapes_and_ids(self):
        for line, (nid, label) in self.NODE_CASES.items():
            with self.subTest(line=line):
                fc = parse_flowchart(1, f"flowchart LR\n {line}")
                self.assertEqual(fc.nodes, {nid: label})

    def test_edge_forms(self):
        for line, want in self.EDGE_CASES.items():
            with self.subTest(line=line):
                fc = parse_flowchart(1, f"flowchart LR\n {line}")
                self.assertEqual(fc.edges, [want])
                self.assertEqual(set(fc.nodes), {want.src, want.dst})

    def test_graph_without_direction_is_tb(self):
        for head in ("graph", "flowchart"):
            with self.subTest(head=head):
                fc = parse_flowchart(1, f"{head}\n A --> B")
                self.assertEqual(fc.direction, "TB")
                self.assertEqual(set(fc.nodes), {"A", "B"})

    def test_class_suffix_not_in_split_decl(self):
        src = "flowchart LR\n subgraph s\n  A[x]:::hot --> B\n end"
        (_, text), = split_subgraphs(parse_flowchart(1, src))[0]
        self.assertIn("A[x]", text)
        self.assertNotIn(":::", text)

    def test_text_label_arrow_survives_split(self):
        src = "flowchart LR\n subgraph s\n  A -. maybe .-> B\n  B == sure ==> C\n end"
        (_, text), = split_subgraphs(parse_flowchart(1, src))[0]
        self.assertIn("A -.->|maybe| B", text)
        self.assertIn("B ==>|sure| C", text)
        again = parse_flowchart(1, text)
        self.assertEqual(again.edges, [Edge("A", "B", "maybe", "-.->"), Edge("B", "C", "sure", "==>")])

    def test_unsupported_forms_raise_named_reason(self):
        cases = {
            "A@{ shape: rect, label: x }": "@{",
            "A e1@--> B": "edge ids",
        }
        for line, reason in cases.items():
            with self.subTest(line=line):
                with self.assertRaises(ValueError) as cm:
                    parse_flowchart(1, f"flowchart LR\n {line}")
                self.assertIn(reason, str(cm.exception))


class SubgraphEndpointTests(unittest.TestCase):
    """Regression guard: an edge to a subgraph id created a phantom node (extra spot, root-part box)."""

    SRC = (
        "flowchart LR\n"
        "  X --> one\n"
        "  subgraph one [First]\n"
        "    A --> B\n"
        "  end\n"
        "  subgraph two\n"
        "    C\n"
        "  end\n"
        "  one --> two\n"
    )

    def test_subgraph_ids_are_not_nodes(self):
        fc = parse_flowchart(1, self.SRC)
        self.assertEqual(set(fc.nodes), {"X", "A", "B", "C"})
        self.assertIn(Edge("X", "one", None), fc.edges)
        self.assertIn(Edge("one", "two", None), fc.edges)

    def test_split_has_no_phantom_parts_or_nodes(self):
        fc = parse_flowchart(1, self.SRC)
        parts, cross = split_subgraphs(fc)
        self.assertEqual([sg.id for sg, _ in parts], ["", "one", "two"])
        self.assertEqual(parts[0][0].node_ids, ["X"])
        for _, text in parts:
            self.assertNotRegex(text, r"(?m)^\s+(one|two)\b")
            self.assertEqual(set(parse_flowchart(1, text).nodes) & {"one", "two"}, set())
        self.assertEqual(cross, [Edge("X", "one", None), Edge("one", "two", None)])
        self.assertEqual(fc.label_of("one"), "First")
        self.assertEqual(fc.label_of("X"), "X")

    def test_subgraph_declared_after_use(self):
        fc = parse_flowchart(1, "flowchart LR\n A --> late\n subgraph late\n  B\n end")
        self.assertEqual(set(fc.nodes), {"A", "B"})


if __name__ == "__main__":
    unittest.main()
