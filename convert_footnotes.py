#!/usr/bin/env python3
"""
Convert legacy Markdown footnotes in full-text-german.md to GitHub Flavored
Markdown (GFM) footnote format.

Input format (legacy):
  - Inline references: standalone * in body text
  - Definitions: lines starting with *) scattered throughout the body

Output format (GFM):
  - Inline references become sequential [^1], [^2], ...
  - Definitions consolidated at the end as [^1]: content, [^2]: content, ...
"""

import os
import re

INPUT_FILE = "die-historische-semiramis-und-herodot/full-text-german.md"
OUTPUT_FILE = "die-historische-semiramis-und-herodot/full-text-german-gfm.md"
EXPECTED_FOOTNOTE_COUNT = 109


def replace_inline_refs(line, counter):
    """Replace standalone * footnote markers in a body line with [^n] labels.

    Asterisks that are part of **bold** spans are skipped.  Asterisks inside
    _italic_ spans are treated as footnote references (per the source
    convention, e.g. _Adad-nirari* 3._).

    Note: the source file does not use ***bold-italic*** markup, so combined
    triple-asterisk sequences are not handled here.
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
                # Standalone * — this is a footnote reference
                counter[0] += 1
                result.append(f"[^{counter[0]}]")
            else:
                result.append("*")
            i += 1
        else:
            result.append(line[i])
            i += 1
    return "".join(result)


def convert_footnotes(input_path, output_path):
    with open(input_path, encoding="utf-8") as f:
        lines = f.readlines()

    # ------------------------------------------------------------------
    # Pass 1 — Extract footnote definitions and record which lines they are
    # ------------------------------------------------------------------
    footnote_definitions = []
    definition_line_indices = set()

    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped.startswith("*)"):
            # Remove the *) marker (with optional following space)
            content = stripped[2:].lstrip(" ")
            footnote_definitions.append(content)
            definition_line_indices.add(i)

    print(f"Extracted footnote definitions: {len(footnote_definitions)}")
    if len(footnote_definitions) != EXPECTED_FOOTNOTE_COUNT:
        print(
            f"⚠ WARNING: Expected {EXPECTED_FOOTNOTE_COUNT} footnotes, "
            f"found {len(footnote_definitions)}. "
            "Verify the input file or update EXPECTED_FOOTNOTE_COUNT if intentional."
        )

    # ------------------------------------------------------------------
    # Pass 2 — Build body (skipping definition lines) and replace inline *
    # ------------------------------------------------------------------
    inline_counter = [0]
    body_lines = []

    for i, raw in enumerate(lines):
        if i in definition_line_indices:
            continue
        processed = replace_inline_refs(raw.rstrip("\n"), inline_counter)
        body_lines.append(processed)

    print(f"Inline footnote references replaced: {inline_counter[0]}")

    if inline_counter[0] == len(footnote_definitions):
        print("✓ Counts match. Writing output...")
    else:
        print(
            f"⚠ WARNING: Inline refs ({inline_counter[0]}) do not match "
            f"definitions ({len(footnote_definitions)}). "
            "Writing output anyway for inspection..."
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


if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_path = os.path.join(script_dir, INPUT_FILE)
    output_path = os.path.join(script_dir, OUTPUT_FILE)
    convert_footnotes(input_path, output_path)
