"""Rendered document data structures."""

from __future__ import annotations

from dataclasses import dataclass, field

from textual.strip import Strip

from mdview_tui.slug import slugify


@dataclass(frozen=True)
class Heading:
    level: int
    text: str
    anchor: str
    line: int


@dataclass(frozen=True)
class LinkRegion:
    link_id: int
    href: str
    line: int
    start: int  # cell offset (inclusive)
    end: int  # cell offset (exclusive)


@dataclass
class RenderedDoc:
    lines: list[Strip]
    plain_lines: list[str]
    headings: list[Heading] = field(default_factory=list)
    links: list[LinkRegion] = field(default_factory=list)
    width: int = 0
    # (rendered line, source line) pairs sorted by rendered line
    anchors: list[tuple[int, int]] = field(default_factory=list)

    def heading_by_anchor(self, anchor: str) -> Heading | None:
        for candidate in (anchor, anchor.lower(), slugify(anchor)):
            for heading in self.headings:
                if heading.anchor == candidate:
                    return heading
        return None

    def link_ids(self) -> list[int]:
        seen: list[int] = []
        for region in self.links:
            if not seen or seen[-1] != region.link_id:
                if region.link_id not in seen:
                    seen.append(region.link_id)
        return seen

    def regions_of(self, link_id: int) -> list[LinkRegion]:
        return [r for r in self.links if r.link_id == link_id]

    def source_position(self, line: int) -> tuple[int, int]:
        """Map a rendered line to (source line of its block, offset in block)."""
        best: tuple[int, int] | None = None
        for rendered, source in self.anchors:
            if rendered > line:
                break
            best = (rendered, source)
        if best is None:
            return (0, line)
        return (best[1], line - best[0])

    def line_for(self, source_line: int, offset: int = 0) -> int:
        """Inverse of source_position(), clamped to the document."""
        last = max(0, len(self.lines) - 1)
        for i, (rendered, source) in enumerate(self.anchors):
            if source == source_line:
                # Stay within this block when its rendered height shrank.
                limit = last
                for later, later_source in self.anchors[i + 1:]:
                    if later > rendered and later_source != source_line:
                        limit = later - 1
                        break
                return min(rendered + offset, limit)
            if source > source_line:
                return min(rendered, last)
        return min(offset, last) if not self.anchors else last
