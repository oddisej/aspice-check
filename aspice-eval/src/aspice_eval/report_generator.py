"""Report generator for ASPICE gap analysis results.

Produces a structured Markdown gap analysis report from evaluation results,
capability level determinations, evaluation configuration, and KB metadata.

The report includes: Metadata, Executive Summary, Capability Level Summary,
Detailed Findings (per-group, per-level, per-PA), Remediation Roadmap,
and Traceability Matrix.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 7.2, 15.3, 15.4, 15.5
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from aspice_eval.models import (
    CapabilityLevelResult,
    CriteriaRating,
    EvaluationConfig,
    EvaluationResult,
    KBMetadata,
)
from aspice_eval.report_renderer import (
    ReportRenderer,
    get_report_renderer,
    register_renderer,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Capability level names by level number.
_LEVEL_NAMES: dict[int, str] = {
    0: "Incomplete",
    1: "Performed",
    2: "Managed",
    3: "Established",
    4: "Predictable",
    5: "Optimizing",
}


# ---------------------------------------------------------------------------
# Built-in Renderers
# ---------------------------------------------------------------------------


class MarkdownReportRenderer(ReportRenderer):
    """Renders evaluation results as a structured Markdown gap analysis report.

    Produces a complete report containing:

    - **Metadata** — SDP path, target level, KB version, timestamp
    - **Executive Summary** — high-level compliance posture
    - **Capability Level Summary** — per-group table
    - **Detailed Findings** — per-group, per-level, per-PA ratings
    - **Remediation Roadmap** — prioritised recommendations
    - **Traceability Matrix** — criteria-to-SDP-section mapping
    """

    def render(
        self,
        evaluation: EvaluationResult,
        levels: dict[str, CapabilityLevelResult],
        config: EvaluationConfig,
        kb_metadata: KBMetadata,
    ) -> str:
        """Render evaluation results as Markdown."""
        sections: list[str] = [
            self._title(),
            self._metadata_section(config, kb_metadata, evaluation.evaluation_timestamp, evaluation.token_usage, evaluation.sdp_metadata),
            self._executive_summary(evaluation, levels, config),
            self._capability_level_summary(levels),
            self._detailed_findings(evaluation, levels, config),
            self._remediation_roadmap(evaluation),
            self._traceability_matrix(evaluation),
        ]
        return "\n\n".join(sections) + "\n"

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    @staticmethod
    def _title() -> str:
        return "# ASPICE Gap Analysis Report"

    @staticmethod
    def _metadata_section(
        config: EvaluationConfig,
        kb_metadata: KBMetadata,
        timestamp: str,
        token_usage: dict[str, int] | None = None,
        sdp_metadata: dict | None = None,
    ) -> str:
        """Build the Metadata section."""
        lines = [
            "## Metadata",
            "",
            f"- **SDP Document:** {config.sdp_path}",
            f"- **Target Capability Level:** {config.target_capability_level}",
            f"- **Process Groups Evaluated:** {', '.join(config.process_groups)}",
            f"- **Knowledge Base Version:** {kb_metadata.kb_version}",
            f"- **Evaluation Date:** {timestamp}",
        ]
        if sdp_metadata:
            model_provider = sdp_metadata.get("model_provider", "")
            model_name = sdp_metadata.get("model_name", "")
            if model_provider or model_name:
                model_display = f"{model_provider}/{model_name}" if model_provider and model_name else (model_provider or model_name)
                lines.append(f"- **AI Model:** {model_display}")
        if token_usage and token_usage.get("total_tokens", 0) > 0:
            lines.append(f"- **Token Usage:** {token_usage['input_tokens']:,} input + {token_usage['output_tokens']:,} output = {token_usage['total_tokens']:,} total ({token_usage['num_batches']} batch{'es' if token_usage['num_batches'] != 1 else ''})")
        return "\n".join(lines)

    @staticmethod
    def _executive_summary(
        evaluation: EvaluationResult,
        levels: dict[str, CapabilityLevelResult],
        config: EvaluationConfig,
    ) -> str:
        """Build the Executive Summary section."""
        lines: list[str] = ["## Executive Summary", ""]

        total_groups = len(config.process_groups)
        meeting_target = sum(
            1
            for g in config.process_groups
            if g in levels and levels[g].achieved_level >= levels[g].target_level
        )
        below_target = total_groups - meeting_target

        lines.append(
            f"This evaluation assessed **{total_groups}** process group(s) "
            f"against a target capability level of **{config.target_capability_level}**."
        )
        lines.append("")

        if meeting_target == total_groups:
            lines.append(
                "**All process groups meet or exceed the target capability level.**"
            )
        else:
            lines.append(
                f"**{meeting_target}** group(s) meet the target level; "
                f"**{below_target}** group(s) are below target."
            )

        # Summarise gaps
        all_gaps: list[str] = []
        for r in evaluation.ratings:
            all_gaps.extend(r.gaps)

        if all_gaps:
            lines.append("")
            lines.append(f"A total of **{len(all_gaps)}** gap(s) were identified across all criteria.")
        else:
            lines.append("")
            lines.append("No gaps were identified.")

        return "\n".join(lines)

    @staticmethod
    def _capability_level_summary(
        levels: dict[str, CapabilityLevelResult],
    ) -> str:
        """Build the Capability Level Summary table."""
        lines: list[str] = [
            "## Capability Level Summary",
            "",
            "| Process Group | Target Level | Achieved Level | Status |",
            "|---|---|---|---|",
        ]

        for group in sorted(levels.keys()):
            result = levels[group]
            if result.achieved_level >= result.target_level:
                status = "✅ Meets target"
            else:
                status = "⚠️ Below target"
            lines.append(
                f"| {group} | {result.target_level} | "
                f"{result.achieved_level} | {status} |"
            )

        return "\n".join(lines)

    @staticmethod
    def _detailed_findings(
        evaluation: EvaluationResult,
        levels: dict[str, CapabilityLevelResult],
        config: EvaluationConfig,
    ) -> str:
        """Build the Detailed Findings section.

        Contains subsections only for the process groups specified in
        ``config.process_groups``.
        """
        lines: list[str] = ["## Detailed Findings"]

        # Index ratings by (group, level, PA)
        grouped: dict[str, dict[int, dict[str, list[CriteriaRating]]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(list))
        )
        for r in evaluation.ratings:
            grouped[r.process_group][r.capability_level][r.process_attribute].append(r)

        for group in config.process_groups:
            group_name = group  # default
            level_result = levels.get(group)

            lines.append("")
            lines.append(f"### {group}")

            group_levels = grouped.get(group, {})
            if not group_levels:
                lines.append("")
                lines.append("No criteria evaluated for this group.")
                continue

            for level in sorted(group_levels.keys()):
                level_name = _LEVEL_NAMES.get(level, f"Level {level}")
                lines.append("")
                lines.append(f"#### Capability Level {level} — {level_name}")

                pa_map = group_levels[level]
                for pa in sorted(pa_map.keys()):
                    ratings = pa_map[pa]
                    lines.append("")
                    lines.append(f"##### {pa}")

                    for cr in ratings:
                        lines.append(f"- **Criteria ID:** {cr.criteria_id}")
                        lines.append(f"  - **Rating:** {cr.rating}")

                        if cr.evidence_found:
                            lines.append("  - **Evidence:**")
                            for ev in cr.evidence_found:
                                lines.append(f"    - {ev}")

                        if cr.gaps:
                            lines.append("  - **Gaps:**")
                            for gap in cr.gaps:
                                lines.append(f"    - {gap}")

                        if cr.recommendations:
                            lines.append("  - **Recommendations:**")
                            for rec in cr.recommendations:
                                lines.append(f"    - {rec}")

        return "\n".join(lines)

    @staticmethod
    def _remediation_roadmap(evaluation: EvaluationResult) -> str:
        """Build the Remediation Roadmap section."""
        lines: list[str] = ["## Remediation Roadmap", ""]

        # Collect all recommendations grouped by process group
        group_recs: dict[str, list[str]] = defaultdict(list)
        for r in evaluation.ratings:
            for rec in r.recommendations:
                group_recs[r.process_group].append(rec)

        if not any(group_recs.values()):
            lines.append("No remediation actions required.")
            return "\n".join(lines)

        priority = 1
        for group in sorted(group_recs.keys()):
            recs = group_recs[group]
            if not recs:
                continue
            lines.append(f"### {group}")
            lines.append("")
            for rec in recs:
                lines.append(f"{priority}. {rec}")
                priority += 1
            lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _traceability_matrix(evaluation: EvaluationResult) -> str:
        """Build the Traceability Matrix section.

        References every ``criteria_id`` from the evaluation results.
        """
        lines: list[str] = [
            "## Traceability Matrix",
            "",
            "| Criteria ID | Process Group | SDP Section(s) Assessed | Rating |",
            "|---|---|---|---|",
        ]

        for r in evaluation.ratings:
            sections = ", ".join(r.sdp_sections_assessed) if r.sdp_sections_assessed else "—"
            lines.append(
                f"| {r.criteria_id} | {r.process_group} | {sections} | {r.rating} |"
            )

        return "\n".join(lines)


class HTMLReportRenderer(ReportRenderer):
    """Renders evaluation results as HTML by converting Markdown output.

    Delegates to :class:`MarkdownReportRenderer` for content generation,
    then converts the Markdown to HTML.
    """

    def render(
        self,
        evaluation: EvaluationResult,
        levels: dict[str, CapabilityLevelResult],
        config: EvaluationConfig,
        kb_metadata: KBMetadata,
    ) -> str:
        """Render evaluation results as HTML."""
        md_renderer = MarkdownReportRenderer()
        md_report = md_renderer.render(evaluation, levels, config, kb_metadata)
        return self._markdown_to_html(md_report)

    @staticmethod
    def _markdown_to_html(md: str) -> str:
        """Convert the Markdown report to HTML.

        Handles the specific Markdown patterns used in the report:
        headers, tables, unordered/ordered lists (with nesting),
        bold text, and paragraphs.
        Produces clean HTML suitable for pasting into Confluence or
        other HTML-based documentation systems.
        """
        html_lines: list[str] = []
        lines = md.split("\n")
        in_table = False
        # Stack tracks open list elements: each entry is ("ul" or "ol", indent_level)
        list_stack: list[tuple[str, int]] = []
        i = 0

        def _close_lists_to(target_indent: int) -> None:
            """Close nested lists down to target indent level."""
            while list_stack and list_stack[-1][1] >= target_indent:
                tag = list_stack.pop()[0]
                html_lines.append(f"</{tag}>")

        def _close_all_lists() -> None:
            """Close all open lists."""
            while list_stack:
                tag = list_stack.pop()[0]
                html_lines.append(f"</{tag}>")

        while i < len(lines):
            line = lines[i]

            # --- Headers ---
            header_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if header_match:
                _close_all_lists()
                level = len(header_match.group(1))
                text = _html_inline(header_match.group(2))
                html_lines.append(f"<h{level}>{text}</h{level}>")
                i += 1
                continue

            # --- Table rows ---
            if line.startswith("|"):
                _close_all_lists()
                # Skip separator rows like |---|---|
                if re.match(r"^\|[-|:\s]+\|$", line):
                    i += 1
                    continue

                cells = [c.strip() for c in line.split("|")[1:-1]]

                if not in_table:
                    in_table = True
                    html_lines.append("<table>")
                    html_lines.append("<thead><tr>")
                    for cell in cells:
                        html_lines.append(f"  <th>{_html_inline(cell)}</th>")
                    html_lines.append("</tr></thead>")
                    html_lines.append("<tbody>")
                else:
                    html_lines.append("<tr>")
                    for cell in cells:
                        html_lines.append(f"  <td>{_html_inline(cell)}</td>")
                    html_lines.append("</tr>")
                i += 1
                continue

            # Close table if we were in one
            if in_table and not line.startswith("|"):
                html_lines.append("</tbody></table>")
                in_table = False

            # --- Unordered list items (with nesting) ---
            ul_match = re.match(r"^(\s*)- (.+)$", line)
            if ul_match:
                indent = len(ul_match.group(1))
                text = _html_inline(ul_match.group(2))

                if not list_stack:
                    html_lines.append("<ul>")
                    list_stack.append(("ul", indent))
                elif indent > list_stack[-1][1]:
                    # Deeper nesting — reopen the previous <li> to nest inside it
                    # Remove the </li> from the previous line if it ends with one
                    if html_lines and html_lines[-1].endswith("</li>"):
                        html_lines[-1] = html_lines[-1][:-5]  # strip </li>
                    html_lines.append("<ul>")
                    list_stack.append(("ul", indent))
                elif indent < list_stack[-1][1]:
                    _close_lists_to(indent + 1)
                    if not list_stack or list_stack[-1][1] != indent:
                        html_lines.append("<ul>")
                        list_stack.append(("ul", indent))

                html_lines.append(f"<li>{text}</li>")
                i += 1
                continue

            # --- Ordered list items ---
            ol_match = re.match(r"^(\s*)(\d+)\.\s+(.+)$", line)
            if ol_match:
                indent = len(ol_match.group(1))
                text = _html_inline(ol_match.group(3))

                if not list_stack:
                    html_lines.append("<ol>")
                    list_stack.append(("ol", indent))
                elif indent > list_stack[-1][1]:
                    if html_lines and html_lines[-1].endswith("</li>"):
                        html_lines[-1] = html_lines[-1][:-5]
                    html_lines.append("<ol>")
                    list_stack.append(("ol", indent))
                elif indent < list_stack[-1][1]:
                    _close_lists_to(indent + 1)
                    if not list_stack or list_stack[-1][1] != indent:
                        html_lines.append("<ol>")
                        list_stack.append(("ol", indent))
                elif list_stack[-1][0] != "ol":
                    _close_lists_to(indent)
                    html_lines.append("<ol>")
                    list_stack.append(("ol", indent))

                html_lines.append(f"<li>{text}</li>")
                i += 1
                continue

            # Close lists if current line is not a list item
            if list_stack and not line.strip().startswith("-") and not re.match(r"^\s*\d+\.", line):
                _close_all_lists()

            # --- Empty lines ---
            if not line.strip():
                i += 1
                continue

            # --- Paragraph text ---
            text = _html_inline(line)
            html_lines.append(f"<p>{text}</p>")
            i += 1

        # Close any open elements
        if in_table:
            html_lines.append("</tbody></table>")
        _close_all_lists()

        return "\n".join(html_lines) + "\n"


def _html_inline(text: str) -> str:
    """Convert inline Markdown formatting to HTML.

    Handles ``**bold**`` and emoji characters.
    """
    # Bold: **text**
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)

    return text


# ---------------------------------------------------------------------------
# Register built-in renderers
# ---------------------------------------------------------------------------

register_renderer("markdown", MarkdownReportRenderer)
register_renderer("html", HTMLReportRenderer)


# ---------------------------------------------------------------------------
# Backward-compatible ReportGenerator wrapper
# ---------------------------------------------------------------------------


class ReportGenerator:
    """Generates structured gap analysis reports.

    Delegates to the registered :class:`ReportRenderer` for the requested
    output format. Built-in formats are ``"markdown"`` and ``"html"``.

    Custom renderers can be registered via
    :func:`~aspice_eval.report_renderer.register_renderer`.
    """

    def generate(
        self,
        evaluation: EvaluationResult,
        levels: dict[str, CapabilityLevelResult],
        config: EvaluationConfig,
        kb_metadata: KBMetadata,
        output_format: str = "markdown",
    ) -> str:
        """Generate a complete Gap Analysis Report.

        Parameters
        ----------
        evaluation:
            Per-criteria evaluation results.
        levels:
            Per-group capability level results.
        config:
            The evaluation configuration used.
        kb_metadata:
            Knowledge base metadata for the report header.
        output_format:
            Output format name. Defaults to ``"markdown"``.
            Use ``"html"`` for HTML output. Custom formats can be
            registered via ``register_renderer()``.

        Returns
        -------
        str
            Complete report in the requested format.

        Raises
        ------
        UnsupportedFormatError
            If output_format is not a registered renderer name.
        """
        renderer_class = get_report_renderer(output_format)
        renderer = renderer_class()
        return renderer.render(evaluation, levels, config, kb_metadata)
