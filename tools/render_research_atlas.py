#!/usr/bin/env python3
"""Build the profile's source-pinned atlas; uses only the Python standard library.

Default: regenerate the documentation, issue form, and theme/size variants.
--check: fail if a generated file differs from the current manifest.
--verify-remote: verify referenced Git blob identities through public GitHub GETs.
Neither verification mode executes project tests or claims release readiness.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ROLES = ("inspect", "reproduce", "falsify", "boundary")
SHA = re.compile(r"[0-9a-f]{40}\Z")
VERIFICATION_SCOPE = "Source references and blob identities verified. Project test suites and experiments were not executed for this profile update."
CHALLENGE = "https://github.com/neuron7x/neuron7x/issues/new?template=research-challenge.yml"
PALETTES = {
    "dark": {"bg": "#0d1117", "panel": "#10151c", "fg": "#e6edf3", "muted": "#a1aab5", "border": "#30363d", "red": "#f85149"},
    "light": {"bg": "#ffffff", "panel": "#fcfcfd", "fg": "#1f2328", "muted": "#59636e", "border": "#d1d9e0", "red": "#c63244"},
}


def unique_json_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def expected_blobs(data: dict) -> dict[tuple[str, str, str], str]:
    expected = {}
    for project in data["projects"]:
        for role in ROLES:
            ref = project["files"][role]
            identity = (project["repository"], project["commit"], ref["path"])
            if expected.setdefault(identity, ref["blob"]) != ref["blob"]:
                raise ValueError(f"Conflicting blob declarations: {project['slug']} / {role}")
    return expected


def load_manifest() -> dict:
    data = json.loads((ROOT / "research/atlas.json").read_text(encoding="utf-8"),
                      object_pairs_hook=unique_json_object)
    if not isinstance(data, dict) or data.get("schema") != "neuron7x.research-atlas.v1":
        raise ValueError("Unsupported atlas schema")
    snapshot = data["verified_date"]
    if date.fromisoformat(snapshot).isoformat() != snapshot or data["verification_scope"] != VERIFICATION_SCOPE:
        raise ValueError("Unsupported verification scope or date")
    projects = data["projects"]
    if (not isinstance(projects, list) or not 1 <= len(projects) <= 8
            or len({p["slug"] for p in projects}) != len(projects)):
        raise ValueError("Projects must have distinct slugs")
    for project in projects:
        if not re.fullmatch(r"[a-z][a-z0-9-]*", project["slug"]):
            raise ValueError("Invalid project anchor")
        if (not re.fullmatch(r"neuron7x/[A-Za-z0-9_.-]+", project["repository"])
                or project["repository"].split("/")[1] in {".", ".."}):
            raise ValueError("Unexpected repository")
        if not SHA.fullmatch(project["commit"]) or set(project["files"]) != set(ROLES):
            raise ValueError("Every route requires a pinned commit and file")
        for reference in project["files"].values():
            path = reference["path"]
            if any(part in {"", ".", ".."} for part in path.split("/")) or not SHA.fullmatch(reference["blob"]):
                raise ValueError("Invalid source reference")
        if len(project["subtitle"]) != 2:
            raise ValueError("Each project needs two concise visual labels")
    expected_blobs(data)
    return data


def fingerprint(data: dict) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def source_url(project: dict, role: str) -> str:
    return f"https://github.com/{project['repository']}/blob/{project['commit']}/{quote(project['files'][role]['path'], safe='/')}"


def svg(data: dict, theme: str, mobile: bool, compact: bool = False) -> str:
    colors = PALETTES[theme]
    width, margin, gap = (400, 10, 10) if mobile else ((640, 16, 16) if compact else (960, 24, 20))
    card_width = (width - 2 * margin - gap) / 2
    card_height, row_gap, start = 130, 16, 88
    cards = [(p["name"], p.get("mobile_subtitle", p["subtitle"]) if mobile else p["subtitle"], "REF " + p["commit"][:12]) for p in data["projects"]]
    cards.append(("METHOD", ["Inspect · Reproduce", "Falsify · Challenge"], "ATLAS " + fingerprint(data)[:10]))
    rows = (len(cards) + 1) // 2
    height = start + rows * card_height + (rows - 1) * row_gap + 42
    body_font, ref_font = (16, 16) if mobile else (18, 18)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">NEURON7X Research Evidence Atlas</title>',
        '<desc id="desc">Public research projects and a common inspection method. The cards are a portfolio index, not an integrated system architecture. REF identifies a source commit, not a performance score. Open the linked atlas for mechanisms, reproduction guides, probes, and claim boundaries.</desc>',
        f'<rect width="{width}" height="{height}" fill="{colors["bg"]}"/>',
        f'<g font-family="DejaVu Sans,Arial,sans-serif" text-anchor="middle" fill="{colors["fg"]}">',
        f'<text x="{width/2:g}" y="32" font-size="22" font-weight="600" letter-spacing="1">RESEARCH EVIDENCE ATLAS</text>',
        f'<text x="{width/2:g}" y="59" font-size="16" fill="{colors["muted"]}">Mechanism · Probe · Claim boundary</text>',
        f'<path d="M{width/2-32:g} 73H{width/2+32:g}" stroke="{colors["red"]}" stroke-width="2"/>',
    ]
    for index, (name, subtitle, ref) in enumerate(cards):
        row, col = divmod(index, 2)
        last_wide = len(cards) % 2 == 1 and index == len(cards) - 1
        x = margin if last_wide else margin + col * (card_width + gap)
        w = width - 2 * margin if last_wide else card_width
        y, cx = start + row * (card_height + row_gap), x + w / 2
        parts.extend([
            f'<g data-card="{index}">',
            f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{card_height}" rx="10" fill="{colors["panel"]}" stroke="{colors["border"]}"/>',
            f'<text x="{cx:g}" y="{y+31:g}" font-size="{22 if mobile else 24}" font-weight="600">{html.escape(name)}</text>',
            f'<text x="{cx:g}" y="{y+57:g}" font-size="{body_font}" fill="{colors["muted"]}">{html.escape(subtitle[0])}</text>',
            f'<text x="{cx:g}" y="{y+79:g}" font-size="{body_font}" fill="{colors["muted"]}">{html.escape(subtitle[1])}</text>',
            f'<path d="M{cx-23:g} {y+94:g}H{cx+23:g}" stroke="{colors["red"]}" stroke-width="1.2" opacity=".75"/>',
            f'<text x="{cx:g}" y="{y+116:g}" font-family="DejaVu Sans Mono,monospace" font-size="{ref_font}" fill="{colors["muted"]}">{html.escape(ref)}</text>',
            '</g>',
        ])
    parts.extend([
        f'<text x="{width/2:g}" y="{height-13}" font-size="{16 if mobile else 18}" fill="{colors["muted"]}">PINNED SOURCE REFERENCES · {html.escape(data["verified_date"])}</text>',
        '</g></svg>',
    ])
    return "\n".join(parts) + "\n"


def document(data: dict) -> str:
    parts = [
        '# Research Evidence Atlas',
        '',
        'A source-pinned route from a research mechanism to its reproduction guide, an adversarial probe or counterexample, and the limit of the resulting claim.',
        '',
        f"**Source snapshot:** {data['verified_date']} · **Atlas fingerprint:** `{fingerprint(data)}`",
        '',
        data['verification_scope'],
        '',
        '**Navigate:** ' + ' · '.join(f"[{p['name']}](#{p['slug']})" for p in data['projects']),
        '',
        '## Inspection protocol',
        '',
        '1. **Inspect:** read the linked implementation and its assumptions.',
        '2. **Reproduce:** check out the pinned commit and follow that project\'s environment and run guide. The linked probe is a specific inspection target, not the project\'s complete validation programme.',
        '3. **Falsify:** use the adversarial test, property-based probe, or recorded counterexample; compare its scope with the claim boundary.',
        '4. **Challenge:** submit the revision, reproduction steps, prediction, observation, and rejection criterion through the [research challenge form](' + CHALLENGE + '). No issue is created until you submit it.',
        '',
    ]
    for p in data['projects']:
        parts.extend([
            f"## {p['slug']}",
            '',
            f"**[{p['name']}](https://github.com/{p['repository']})** · revision [{p['commit'][:12]}](https://github.com/{p['repository']}/commit/{p['commit']})",
            '',
            p['summary'],
            '',
            '| Route | Versioned source | Git blob |',
            '| :--- | :--- | :--- |',
        ])
        labels = {'inspect': 'Mechanism', 'reproduce': 'Reproduction guide', 'falsify': p['probe_kind'], 'boundary': 'Claim boundary'}
        for role in ROLES:
            parts.append(f"| {role.capitalize()} | [{labels[role]}]({source_url(p, role)}) | `{p['files'][role]['blob'][:12]}` |")
        parts.extend(['', '**Scope:** ' + p['scope'], ''])
    parts.extend([
        '## Maintain the index',
        '',
        'The manifest is [`research/atlas.json`](research/atlas.json). Update its references only after inspecting the new source revision; changing a SHA is not scientific validation.',
        '',
        'From a checkout of this profile repository, regenerate the atlas and check its consistency:',
        '',
        '```bash',
        'python3 tools/render_research_atlas.py',
        'python3 tools/render_research_atlas.py --check',
        '```',
        '',
        'To recheck the public Git blob identities, use:',
        '',
        '```bash',
        'python3 tools/render_research_atlas.py --check --verify-remote',
        '```',
        '',
        'The renderer uses only the Python standard library. Remote verification performs public read requests; it does not execute experiments. There are no scheduled workflows, paid services, or live readiness badges.',
        '',
    ])
    return '\n'.join(parts)


def issue_form(data: dict) -> str:
    options = '\n'.join('        - ' + json.dumps(p['name']) for p in data['projects'])
    return '''name: Research challenge
description: Submit a source-pinned, reproducible counterexample or replication discrepancy.
title: "[Research challenge]: "
body:
  - type: markdown
    attributes:
      value: |
        Start from the [Research Evidence Atlas](https://github.com/neuron7x/neuron7x/blob/main/RESEARCH_ATLAS.md).
        Identify the source revision, the prediction being challenged, and the observation that changes the verdict.
  - type: dropdown
    id: project
    attributes:
      label: Project
      options:
''' + options + '''
        - "Profile atlas / method"
    validations:
      required: true
  - type: input
    id: source_ref
    attributes:
      label: Source commit and claim identifier
      placeholder: Full commit SHA; claim ID or exact source location if available
    validations:
      required: true
  - type: dropdown
    id: evidence_type
    attributes:
      label: Evidence type
      options:
        - "Executable counterexample"
        - "Replication discrepancy"
        - "Claim or scope mismatch"
        - "Documentation inconsistency"
    validations:
      required: true
  - type: textarea
    id: reproduction
    attributes:
      label: Reproduction steps
      description: Minimal commands or source comparison; include seed, data, and environment when relevant.
    validations:
      required: true
  - type: textarea
    id: prediction_observation
    attributes:
      label: Prediction, observation, and rejection criterion
      description: State what was expected, what you observed, and which criterion would reject or narrow the claim.
    validations:
      required: true
  - type: textarea
    id: evidence
    attributes:
      label: Evidence and artifacts
      description: Attach or link logs, a minimal case, a result file, or the exact contradictory source passage.
    validations:
      required: false
'''


def verify_remote(data: dict) -> None:
    expected = expected_blobs(data)
    for (repository, commit, path), blob in expected.items():
        url = f"https://api.github.com/repos/{repository}/contents/{quote(path, safe='/')}?ref={commit}"
        request = Request(url, headers={'Accept': 'application/vnd.github+json', 'User-Agent': 'neuron7x-research-atlas'})
        with urlopen(request, timeout=20) as response:
            observed = json.load(response)
        if not isinstance(observed, dict) or observed.get("sha") != blob:
            raise ValueError(f"Source identity mismatch: {repository} / {path}")
    print(f"Verified {len(expected)} distinct public Git blob references; no project tests executed.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--verify-remote', action='store_true')
    args = parser.parse_args()
    data = load_manifest()
    outputs = {ROOT / 'RESEARCH_ATLAS.md': document(data), ROOT / '.github/ISSUE_TEMPLATE/research-challenge.yml': issue_form(data)}
    for theme in PALETTES:
        for size in ('desktop', 'compact', 'mobile'):
            prefix = '' if size == 'desktop' else size + '-'
            name = f"research-atlas-{prefix}{theme}.svg"
            outputs[ROOT / 'assets' / name] = svg(data, theme, size == 'mobile', size == 'compact')
    if args.check:
        mismatches = [str(path.relative_to(ROOT)) for path, content in outputs.items()
                      if not path.exists() or path.read_bytes() != content.encode()]
        if mismatches:
            print('Generated files differ: ' + ', '.join(mismatches), file=sys.stderr)
            return 1
    if args.verify_remote:
        verify_remote(data)
    if not args.check:
        for path, content in outputs.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content.encode())
    print(('Consistent' if args.check else 'Generated') + f": {len(outputs)} atlas files; {len(data['projects'])} source-pinned projects.")
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, TypeError, KeyError, OSError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from error
