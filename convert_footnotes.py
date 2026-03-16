#!/usr/bin/env python3
"""
Convert legacy Markdown footnotes in full-text-german.md to GitHub Flavored
Markdown (GFM) footnote format.

Input format (legacy):
  - Inline references: standalone * in body text
  - Definitions: lines starting with *) scattered throughout the body
    (may continue on the immediately following non-blank line(s) only if
    those lines contain no * character — bare citations like "S. 172.")

Output format (GFM):
  - Inline references become sequential [^1], [^2], ...
  - Definitions consolidated at the end as [^1]: content, [^2]: content, ...

Note: single-asterisk italic spans (*word*) in the body are detected and
preserved as-is; only a truly unmatched standalone * is treated as a footnote
reference.

Usage:
  python convert_footnotes.py [options]

Options:
  -i, --input FILE       Input Markdown file (default: see DEFAULT_INPUT_FILE)
  -o, --output FILE      Output Markdown file (default: see DEFAULT_OUTPUT_FILE)
  -n, --expected-count N Expected number of footnotes (default: 109)
  -d, --debug            Print per-definition and per-inline-ref debug info
"""

import argparse
import os

DEFAULT_INPUT_FILE = "die-historische-semiramis-und-herodot/full-text-german.md"
DEFAULT_OUTPUT_FILE = "die-historische-semiramis-und-herodot/full-text-german-gfm.md"
DEFAULT_EXPECTED_FOOTNOTE_COUNT = 109

_CONTEXT_CHARS = 40


def replace_inline_refs(line, counter, debug=False, orig_line_num=None):
    """Replace standalone * footnote markers in a body line with [^n] labels.

    Asterisks that are part of **bold** spans are skipped.  Asterisks inside
    _italic_ spans are treated as footnote references (per the source
    convention, e.g. _Adad-nirari* 3._).

    Single-asterisk italic spans (*word*) are detected and passed through
    unchanged.  When a * is encountered that is not adjacent to another *,
    the function looks ahead for a matching closing * with no interior
    asterisks.  If found, the entire *...* span is appended as-is.  Only a
    truly unmatched lone * (no closing * on the same line) is treated as a
    footnote reference and replaced with [^n].

    Note: the source file does not use ***bold-italic*** markup, so combined
    triple-asterisk sequences are not handled here.

    When *debug* is True and *orig_line_num* is provided, a debug line is
    printed for every inline reference replaced, showing its 1-based original
    line number and the surrounding context in the output string.
    """
    result = []
    i = 0
    n = len(line)
    while i < n:
        if i + 1 < n and line[i] == "*" and line[i + 1] == "*":
            # Start of a **bold** span — consume until the closing **
            j = line.find("**", i + 2)
            if j != -1:
                result.append(line[i : j + 2])
                i = j + 2
            else:
                # No closing **, treat as literals and move on
                result.append("**")
                i += 2
        elif line[i] == "*":
            prev_is_star = i > 0 and line[i - 1] == "*"
            next_is_star = i + 1 < n and line[i + 1] == "*"
            if not prev_is_star and not next_is_star:
                # Check if this opens a *word* italic span
                j = line.find("*", i + 1)
                if j != -1 and j > i + 1 and "*" not in line[i + 1 : j]:
                    # Italic span *...* — pass through unchanged
                    result.append(line[i : j + 1])
                    i = j + 1
                    continue
                # Truly standalone * — this is a footnote reference
                counter[0] += 1
                ref_str = f"[^{counter[0]}]"
                result.append(ref_str)
                i += 1
                if debug and orig_line_num is not None:
                    # Build approximate full output for context extraction.
                    # result already contains ref_str; remaining input is line[i:].
                    joined = "".join(result)
                    full = joined + line[i:]
                    ref_pos = len(joined) - len(ref_str)
                    ref_end = ref_pos + len(ref_str)
                    ctx_start = max(0, ref_pos - _CONTEXT_CHARS)
                    ctx_end = min(len(full), ref_end + _CONTEXT_CHARS)
                    snippet = full[ctx_start:ctx_end]
                    pre = "..." if ctx_start > 0 else ""
                    suf = "..." if ctx_end < len(full) else ""
                    print(
                        f"[DEBUG] Inline ref #{counter[0]}"
                        f"  (orig line {orig_line_num}):  {pre}{snippet}{suf}"
                    )
            else:
                result.append("*")
                i += 1
        else:
            result.append(line[i])
            i += 1
    return "".join(result)


def convert_footnotes(input_path, output_path, expected_count, debug=False):
    with open(input_path, encoding="utf-8") as f:
        lines = f.readlines()

    # ------------------------------------------------------------------
    # Pass 1 — Extract footnote definitions and record which lines they are.
    # A definition starts on a line beginning with *).  It may continue on
    # the immediately following line(s) as long as those lines are non-blank
    # and do not themselves start with *) (which would begin a new definition).
    # ------------------------------------------------------------------
    footnote_definitions = []
    definition_line_indices = set()
    # For debug: track which (0-based) line indices belong to each definition.
    def_line_spans = []   # list of lists of 0-based indices

    in_definition = False  # True while we may still see continuation lines

    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped.startswith("*)"):
            # New definition line — strip the *) marker
            content = stripped[2:].lstrip(" ")
            footnote_definitions.append(content)
            definition_line_indices.add(i)
            def_line_spans.append([i])
            in_definition = True
        elif in_definition and stripped and not stripped.startswith("*)") and "*" not in stripped:
            # Continuation line: non-blank, no * character, immediately follows
            # definition/continuation (real continuations are bare citations like
            # "S. 172." and never contain *)
            footnote_definitions[-1] += " " + stripped
            definition_line_indices.add(i)
            def_line_spans[-1].append(i)
        else:
            # Blank line or body-text line ends any active definition block
            in_definition = False

    if debug:
        for idx, (defn, span) in enumerate(zip(footnote_definitions, def_line_spans), 1):
            if len(span) == 1:
                loc = f"line {span[0] + 1}"
            else:
                loc = f"lines {span[0] + 1}-{span[-1] + 1}"
            print(f"[DEBUG] Def #{idx}  ({loc}):  {defn}")

    print(f"Extracted footnote definitions: {len(footnote_definitions)}")
    if len(footnote_definitions) != expected_count:
        print(
            f"⚠ WARNING: Expected {expected_count} footnotes, "
            f"found {len(footnote_definitions)}. "
            "Verify the input file or update --expected-count if intentional."
        )

    # ------------------------------------------------------------------
    # Pass 2 — Build body (skipping definition lines) and replace inline *
    # ------------------------------------------------------------------
    inline_counter = [0]
    body_lines = []

    for i, raw in enumerate(lines):
        if i in definition_line_indices:
            continue
        processed = replace_inline_refs(
            raw.rstrip("\n"),
            inline_counter,
            debug=debug,
            orig_line_num=i + 1,
        )
        body_lines.append(processed)

    print(f"Inline footnote references replaced: {inline_counter[0]}")

    n_defs = len(footnote_definitions)
    n_refs = inline_counter[0]

    if n_refs == n_defs:
        print("✓ Counts match. Writing output...")
    else:
        print(
            f"⚠ WARNING: Inline refs ({n_refs}) do not match "
            f"definitions ({n_defs}). "
            "Writing output anyway for inspection..."
        )
        if debug:
            if n_defs > n_refs:
                unmatched = list(range(n_refs + 1, n_defs + 1))
                print(
                    f"[DEBUG] Definition(s) with no matching inline ref: "
                    + ", ".join(f"#{u}" for u in unmatched)
                )
            else:
                unmatched = list(range(n_defs + 1, n_refs + 1))
                print(
                    f"[DEBUG] Inline ref(s) with no matching definition: "
                    + ", ".join(f"#{u}" for u in unmatched)
                )

    # ------------------------------------------------------------------
    # Post-process: collapse runs of consecutive blank lines left behind
    # after removing definition lines, and strip trailing blank lines
    # ------------------------------------------------------------------
    collapsed = []
    prev_blank = False
    for line in body_lines:
        is_blank = not line.strip()
        if is_blank and prev_blank:
            continue  # drop the extra blank
        collapsed.append(line)
        prev_blank = is_blank

    # Remove trailing blank lines before appending the footnote section
    while collapsed and not collapsed[-1].strip():
        collapsed.pop()

    # ------------------------------------------------------------------
    # Build the footnote section and write output
    # ------------------------------------------------------------------
    footnote_section = [
        f"[^{n}]: {defn}" for n, defn in enumerate(footnote_definitions, 1)
    ]

    output_lines = collapsed + [""] + footnote_section + [""]
    output_content = "\n".join(output_lines)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(output_content)

    print(f"Output written to: {output_path}")


def _build_arg_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Convert legacy *) footnote markers in a Markdown file to "
            "GitHub Flavored Markdown [^n] format."
        )
    )
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parser.add_argument(
        "-i", "--input",
        default=os.path.join(script_dir, DEFAULT_INPUT_FILE),
        metavar="FILE",
        help=f"Input Markdown file (default: {DEFAULT_INPUT_FILE})",
    )
    parser.add_argument(
        "-o", "--output",
        default=os.path.join(script_dir, DEFAULT_OUTPUT_FILE),
        metavar="FILE",
        help=f"Output Markdown file (default: {DEFAULT_OUTPUT_FILE})",
    )
    parser.add_argument(
        "-n", "--expected-count",
        type=int,
        default=DEFAULT_EXPECTED_FOOTNOTE_COUNT,
        metavar="N",
        help=f"Expected footnote count (default: {DEFAULT_EXPECTED_FOOTNOTE_COUNT})",
    )
    parser.add_argument(
        "-d", "--debug",
        action="store_true",
        help="Print debug info for each definition and inline reference",
    )
    return parser


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()
    convert_footnotes(
        input_path=args.input,
        output_path=args.output,
        expected_count=args.expected_count,
        debug=args.debug,
    )
