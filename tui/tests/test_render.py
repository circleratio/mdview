import unittest

from rich.cells import cell_len

from mdview_tui.frontmatter import ERROR_PREFIX
from mdview_tui.parser import parse, parse_document
from mdview_tui.render import render
from mdview_tui.themes import THEMES
from tests.helpers import FIXTURES


def doc_of(text, width=40, theme="dark"):
    return render(parse(text), width, THEMES[theme])


def fm_doc_of(text, width=40, theme="dark"):
    parsed = parse_document(text)
    return render(parsed.tokens, width, THEMES[theme], parsed.front_matter)


class ParserTest(unittest.TestCase):
    def test_gfm_tokens(self):
        types = {t.type for t in parse("| a |\n|---|\n| 1 |\n\n~~s~~ https://ex.com\n")}
        self.assertIn("table_open", types)
        children = [c.type for t in parse("~~s~~ https://ex.com\n") if t.children for c in t.children]
        self.assertIn("s_open", children)
        self.assertIn("link_open", children)


class BlockTest(unittest.TestCase):
    def test_headings(self):
        doc = doc_of("# H1\n\n## H2\n\n### H3\n", width=20)
        self.assertEqual(doc.plain_lines[0], "H1")
        self.assertEqual(doc.plain_lines[1], "═" * 20)
        self.assertEqual(doc.plain_lines[3], "H2")
        self.assertEqual(doc.plain_lines[4], "─" * 20)
        self.assertEqual(doc.plain_lines[6], "### H3")
        self.assertEqual([(h.level, h.line) for h in doc.headings], [(1, 0), (2, 3), (3, 6)])

    def test_inline_styles(self):
        doc = doc_of("**b** *i* ~~s~~ `c`")
        self.assertEqual(doc.plain_lines, ["b i s c"])
        styles = {seg.text: seg.style for seg in doc.lines[0] if seg.text.strip()}
        self.assertTrue(styles["b"].bold)
        self.assertTrue(styles["i"].italic)
        self.assertTrue(styles["s"].strike)
        self.assertIsNotNone(styles["c"].bgcolor)

    def test_lists(self):
        doc = doc_of("- a\n- b\n  - c\n    - d\n\n3. x\n4. y\n")
        self.assertEqual(doc.plain_lines, ["• a", "• b", "  ◦ c", "    ▪ d", "", "3. x", "4. y"])

    def test_loose_list_has_blank_lines(self):
        doc = doc_of("- a\n\n- b\n")
        self.assertEqual(doc.plain_lines, ["• a", "", "• b"])

    def test_task_list(self):
        doc = doc_of("- [ ] todo\n- [x] done\n- [X] DONE\n")
        self.assertEqual(doc.plain_lines, ["☐ todo", "☑ done", "☑ DONE"])

    def test_task_list_rerender_is_stable(self):
        tokens = parse("- [ ] todo\n")
        first = render(tokens, 40, THEMES["dark"]).plain_lines
        second = render(tokens, 40, THEMES["dark"]).plain_lines
        self.assertEqual(first, second)

    def test_blockquote(self):
        doc = doc_of("> quote\n>\n> > nested\n")
        self.assertEqual(doc.plain_lines, ["▌ quote", "▌ ", "▌ ▌ nested"])

    def test_code_block(self):
        doc = doc_of("```python\nx = 1\n```\n", width=20)
        self.assertEqual(len(doc.lines), 1)
        self.assertEqual(doc.plain_lines[0], " x = 1".ljust(20))
        self.assertIsNotNone(doc.lines[0]._segments[0].style.bgcolor)

    def test_code_block_long_line_is_cropped(self):
        doc = doc_of("```\n" + "x" * 50 + "\n```\n", width=20)
        self.assertEqual(len(doc.lines), 1)
        self.assertEqual(cell_len(doc.plain_lines[0]), 20)

    def test_unknown_language(self):
        doc = doc_of("```nosuchlang\nabc\n```\n", width=10)
        self.assertEqual(doc.plain_lines[0].strip(), "abc")

    def test_table(self):
        doc = doc_of("| a | b |\n|:-|-:|\n| 1 | 22 |\n")
        self.assertEqual(
            doc.plain_lines,
            ["┌───┬────┐", "│ a │  b │", "├───┼────┤", "│ 1 │ 22 │", "└───┴────┘"],
        )

    def test_hr(self):
        self.assertEqual(doc_of("---\n", width=10).plain_lines, ["─" * 10])

    def test_html(self):
        self.assertEqual(doc_of("<div>x</div>\n").plain_lines, ["<div>x</div>"])
        self.assertEqual(doc_of("a <b>x</b>\n").plain_lines, ["a <b>x</b>"])

    def test_image(self):
        doc = doc_of("![alt](img.png)\n")
        self.assertEqual(doc.plain_lines, ["[image: alt](img.png)"])
        self.assertEqual(doc.links[0].href, "img.png")

    def test_image_path_is_shown_as_written(self):
        doc = doc_of("![図](<図 1.png>)\n", width=60)
        self.assertEqual(doc.plain_lines, ["[image: 図](図 1.png)"])
        self.assertEqual(doc.links[0].href, "%E5%9B%B3%201.png")

    def test_wrap(self):
        doc = doc_of("aaa bbb ccc ddd", width=10)
        self.assertEqual(doc.plain_lines, ["aaa bbb", "ccc ddd"])

    def test_wrap_wide_chars(self):
        doc = doc_of("あいうえおかきくけこ", width=10)
        self.assertEqual(doc.plain_lines, ["あいうえお", "かきくけこ"])
        for line in doc.plain_lines:
            self.assertLessEqual(cell_len(line), 10)

    def test_width_changes_line_count(self):
        text = (FIXTURES / "sample.md").read_text(encoding="utf-8")
        self.assertGreater(len(doc_of(text, width=30).lines), len(doc_of(text, width=80).lines))

    def test_light_theme(self):
        dark = doc_of("# h\n", theme="dark").lines[0]._segments[0].style.color
        light = doc_of("# h\n", theme="light").lines[0]._segments[0].style.color
        self.assertNotEqual(dark, light)


class LinkRegionTest(unittest.TestCase):
    def test_positions(self):
        doc = doc_of("see [link](a.md) and https://ex.com\n", width=80)
        self.assertEqual(
            [(r.href, r.line, r.start, r.end) for r in doc.links],
            [("a.md", 0, 4, 8), ("https://ex.com", 0, 13, 27)],
        )
        self.assertEqual(doc.link_ids(), [0, 1])

    def test_wide_chars_before_link(self):
        doc = doc_of("日本語 [リンク](a.md)\n")
        region = doc.links[0]
        self.assertEqual((region.start, region.end), (7, 13))

    def test_wrapped_link_has_two_regions(self):
        doc = doc_of("xxxxxxx [aaa bbb](a.md)\n", width=12)
        regions = doc.regions_of(0)
        self.assertEqual(len(regions), 2)
        self.assertEqual([r.line for r in regions], [0, 1])
        self.assertEqual(doc.link_ids(), [0])

    def test_link_in_table(self):
        doc = doc_of("| a |\n|---|\n| [x](b.md) |\n")
        region = doc.links[0]
        self.assertEqual(region.line, 3)
        self.assertEqual(doc.plain_lines[3][region.start:region.end], "x")

    def test_link_in_list(self):
        doc = doc_of("- [x](b.md)\n")
        self.assertEqual((doc.links[0].start, doc.links[0].end), (2, 3))


class AnchorTest(unittest.TestCase):
    def test_heading_by_anchor(self):
        doc = doc_of("# Intro\n\n## セクション 2\n\n## Intro\n")
        self.assertEqual(doc.heading_by_anchor("セクション-2").line, 3)
        self.assertEqual(doc.heading_by_anchor("intro-1").line, 6)
        self.assertEqual(doc.heading_by_anchor("Intro").line, 0)
        self.assertIsNone(doc.heading_by_anchor("none"))

    def test_source_position_roundtrip(self):
        text = (FIXTURES / "sample.md").read_text(encoding="utf-8")
        narrow, wide = doc_of(text, width=30), doc_of(text, width=80)
        for heading in narrow.headings:
            pos = narrow.source_position(heading.line)
            self.assertEqual(wide.line_for(*pos), wide.heading_by_anchor(heading.anchor).line)


FM_SAMPLE = """---
title: 設計メモ
author: [山田 太郎, 佐藤 花子]
date: 2026-10-08
version: 1.10
tags: [md, viewer]
---

# はじめに

本文。
"""


class FrontMatterTest(unittest.TestCase):
    def test_full_header(self):
        doc = fm_doc_of(FM_SAMPLE)
        self.assertEqual(
            doc.plain_lines[:8],
            [
                "設計メモ",
                "山田 太郎、佐藤 花子 ・ 2026-10-08",
                "┄" * 40,
                "version  1.10",
                "tags     md, viewer",
                "─" * 40,
                "",
                "はじめに",
            ],
        )

    def test_title_style_and_no_rule_under_title(self):
        doc = fm_doc_of("---\ntitle: T\n---\n")
        self.assertEqual(doc.plain_lines, ["T", "─" * 40])
        style = doc.lines[0]._segments[0].style
        self.assertTrue(style.bold)
        self.assertEqual(style.color, THEMES["dark"].heading[0].color)

    def test_title_is_not_a_heading(self):
        doc = fm_doc_of(FM_SAMPLE)
        self.assertEqual([h.text for h in doc.headings], ["はじめに"])
        self.assertEqual(doc.headings[0].line, 7)
        self.assertEqual(doc.links, [])

    def test_dotted_rule_only_between_sections(self):
        only_others = fm_doc_of("---\nversion: 1\n---\n")
        self.assertEqual(only_others.plain_lines, ["version  1", "─" * 40])
        only_byline = fm_doc_of("---\ndate: 2026-10-08\n---\n")
        self.assertEqual(only_byline.plain_lines, ["2026-10-08", "─" * 40])

    def test_long_value_wraps(self):
        doc = fm_doc_of("---\nnote: " + "x" * 50 + "\n---\n")
        self.assertEqual(doc.plain_lines[0], "note  " + "x" * 34)
        self.assertEqual(doc.plain_lines[1], "      " + "x" * 16)

    def test_narrow_width_puts_values_below_keys(self):
        doc = fm_doc_of("---\nversion: 1.10\ntags: [md, viewer]\n---\n", width=12)
        self.assertEqual(doc.plain_lines, ["version", "  1.10", "tags", "  md, viewer", "─" * 12])

    def test_empty_front_matter_shows_nothing(self):
        for text in ("---\n---\n# H\n", "---\ntitle: ''\n---\n# H\n"):
            with self.subTest(text=text):
                self.assertEqual(fm_doc_of(text).plain_lines[:2], ["H", "═" * 40])

    def test_error(self):
        doc = fm_doc_of("---\ntitle: [oops\n---\n\n# Body\n")
        self.assertTrue(doc.plain_lines[0].startswith(ERROR_PREFIX.rstrip()))
        self.assertIn("title: [oops", doc.plain_lines)
        self.assertIn("─" * 40, doc.plain_lines)
        self.assertEqual([h.text for h in doc.headings], ["Body"])

    def test_no_closing_fence_is_a_rule(self):
        doc = fm_doc_of("---\ntitle: x\n\n# Body\n")
        self.assertEqual(doc.plain_lines[0], "─" * 40)

    def test_anchors_use_file_line_numbers(self):
        doc = fm_doc_of(FM_SAMPLE)
        heading = doc.headings[0]
        self.assertEqual(doc.source_position(heading.line), (8, 0))
        self.assertEqual(doc.source_position(0), (0, 0))

    def test_light_theme(self):
        doc = fm_doc_of(FM_SAMPLE, theme="light")
        self.assertEqual(doc.lines[1]._segments[0].style.color, THEMES["light"].meta.color)


if __name__ == "__main__":
    unittest.main()
