"""
ai_qc.py — AI-based automated quality control for Python software packages.

A small, self-contained prototype of an automated QC workflow:

    1. Discovers all .py files in a target package/directory.
    2. Runs deterministic static checks (syntax, complexity heuristics,
       missing docstrings, long functions, bare excepts, TODO/FIXME, ...).
    3. Optionally asks an LLM (Anthropic Claude) for a higher-level review
       of the riskiest files (maintainability, bugs, security smells).
    4. Emits a structured report (Markdown + JSON) with a 0–100 quality score.

Designed to run *with or without* an API key:
  - No key  -> static analysis only (fully offline, deterministic).
  - With key (ANTHROPIC_API_KEY) -> static + AI-augmented review.

Usage:
    python ai_qc.py <path>                 # analyse a package/folder
    python ai_qc.py <path> --json out.json # also write JSON report
    python ai_qc.py <path> --no-ai         # force static-only

Author: Salvatore Rapisarda
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# AI review is optional. We import lazily and degrade gracefully.
AI_MODEL = "claude-sonnet-4-6"
MAX_FUNC_LINES = 60
MAX_FILES_FOR_AI = 5


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass
class Finding:
    file: str
    line: int
    severity: str            # "high" | "medium" | "low"
    rule: str
    message: str


@dataclass
class FileReport:
    path: str
    loc: int = 0
    n_functions: int = 0
    n_classes: int = 0
    docstring_coverage: float = 0.0
    findings: list[Finding] = field(default_factory=list)
    ai_review: Optional[str] = None

    @property
    def risk(self) -> float:
        weights = {"high": 8.0, "medium": 3.0, "low": 0.5}
        return sum(weights[f.severity] for f in self.findings)


# --------------------------------------------------------------------------- #
# Static analysis
# --------------------------------------------------------------------------- #
class StaticAnalyzer(ast.NodeVisitor):
    """Walks an AST and collects deterministic quality findings."""

    def __init__(self, path: str, source: str):
        self.path = path
        self.source = source.splitlines()
        self.findings: list[Finding] = []
        self.documented = 0
        self.documentable = 0
        self.n_functions = 0
        self.n_classes = 0

    def _add(self, line: int, severity: str, rule: str, message: str) -> None:
        self.findings.append(Finding(self.path, line, severity, rule, message))

    def _check_docstring(self, node) -> None:
        self.documentable += 1
        if ast.get_docstring(node):
            self.documented += 1
        else:
            name = getattr(node, "name", "<module>")
            self._add(getattr(node, "lineno", 1), "low", "missing-docstring",
                      f"'{name}' has no docstring.")

    def _check_length(self, node) -> None:
        if node.body:
            start = node.lineno
            end = max(getattr(n, "end_lineno", start) for n in node.body)
            length = end - start + 1
            if length > MAX_FUNC_LINES:
                self._add(start, "medium", "long-function",
                          f"'{node.name}' is {length} lines (> {MAX_FUNC_LINES}); "
                          f"consider splitting.")

    def visit_Module(self, node):       # noqa: N802
        self._check_docstring(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node):     # noqa: N802
        self.n_classes += 1
        self._check_docstring(node)
        self.generic_visit(node)

    def _visit_func(self, node):
        self.n_functions += 1
        self._check_docstring(node)
        self._check_length(node)
        # Heuristic: too many arguments hurts readability.
        n_args = len(node.args.args) + len(node.args.kwonlyargs)
        if n_args > 6:
            self._add(node.lineno, "low", "too-many-args",
                      f"'{node.name}' takes {n_args} arguments (> 6).")
        self.generic_visit(node)

    visit_FunctionDef = _visit_func             # noqa: N815
    visit_AsyncFunctionDef = _visit_func        # noqa: N815

    def visit_ExceptHandler(self, node):        # noqa: N802
        if node.type is None:
            self._add(node.lineno, "high", "bare-except",
                      "Bare 'except:' swallows all errors; catch specific types.")
        self.generic_visit(node)

    def visit_Call(self, node):                 # noqa: N802
        func = node.func
        name = getattr(func, "id", None) or getattr(func, "attr", None)
        if name in {"eval", "exec"}:
            self._add(node.lineno, "high", "dangerous-call",
                      f"Use of '{name}' is a security/maintainability risk.")
        self.generic_visit(node)


def scan_textual(path: str, source: str) -> list[Finding]:
    """Cheap line-based checks that don't need an AST."""
    out: list[Finding] = []
    for i, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if any(tag in stripped for tag in ("TODO", "FIXME", "XXX")):
            out.append(Finding(path, i, "low", "todo-marker",
                               "Unresolved TODO/FIXME marker."))
        if len(line) > 120:
            out.append(Finding(path, i, "low", "long-line",
                               f"Line is {len(line)} chars (> 120)."))
        if "print(" in stripped and not stripped.startswith("#"):
            out.append(Finding(path, i, "low", "stray-print",
                               "Stray 'print' — use logging in production code."))
    return out


def analyze_file(path: Path) -> FileReport:
    source = path.read_text(encoding="utf-8", errors="replace")
    rep = FileReport(path=str(path), loc=len(source.splitlines()))
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        rep.findings.append(Finding(str(path), e.lineno or 1, "high",
                                    "syntax-error", f"Syntax error: {e.msg}"))
        return rep

    sa = StaticAnalyzer(str(path), source)
    sa.visit(tree)
    rep.findings.extend(sa.findings)
    rep.findings.extend(scan_textual(str(path), source))
    rep.n_functions = sa.n_functions
    rep.n_classes = sa.n_classes
    rep.docstring_coverage = (sa.documented / sa.documentable) if sa.documentable else 1.0
    return rep


# --------------------------------------------------------------------------- #
# AI-augmented review (optional)
# --------------------------------------------------------------------------- #
def ai_review_file(path: str, source: str) -> Optional[str]:
    """Ask Claude for a concise senior-engineer review. Returns None on failure."""
    try:
        import anthropic  # imported lazily so the tool runs without the package
    except ImportError:
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    client = anthropic.Anthropic(api_key=api_key)
    prompt = (
        "You are a senior software engineer doing quality control on a Python "
        "module. In under 120 words, list the top concrete issues (bugs, "
        "maintainability, security) and one strength. Be specific and actionable. "
        "Do not restate the code.\n\n"
        f"File: {path}\n```python\n{source[:6000]}\n```"
    )
    try:
        msg = client.messages.create(
            model=AI_MODEL,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if b.type == "text").strip()
    except Exception as e:                      # noqa: BLE001 — demo resilience
        return f"(AI review unavailable: {e})"


# --------------------------------------------------------------------------- #
# Scoring & reporting
# --------------------------------------------------------------------------- #
def quality_score(reports: list[FileReport]) -> int:
    """Combine risk density and docstring coverage into a 0–100 score."""
    if not reports:
        return 100
    total_loc = sum(r.loc for r in reports) or 1
    total_risk = sum(r.risk for r in reports)
    risk_density = total_risk / total_loc            # findings-weight per line
    avg_doc = sum(r.docstring_coverage for r in reports) / len(reports)
    score = 100 - min(70, risk_density * 400) - (1 - avg_doc) * 20
    return max(0, round(score))


def build_markdown(reports: list[FileReport], score: int, used_ai: bool) -> str:
    sev_order = {"high": 0, "medium": 1, "low": 2}
    n_high = sum(1 for r in reports for f in r.findings if f.severity == "high")
    n_med = sum(1 for r in reports for f in r.findings if f.severity == "medium")
    n_low = sum(1 for r in reports for f in r.findings if f.severity == "low")

    lines = [
        "# 🤖 AI Quality-Control Report",
        "",
        f"**Quality score:** **{score}/100**  ",
        f"**Files analysed:** {len(reports)}  ",
        f"**Findings:** {n_high} high · {n_med} medium · {n_low} low  ",
        f"**AI review:** {'enabled (Claude)' if used_ai else 'static-only (no API key)'}",
        "",
        "---",
        "",
        "## Files by risk",
        "",
        "| File | LOC | Docstrings | Risk | Findings |",
        "|------|----:|-----------:|-----:|---------:|",
    ]
    for r in sorted(reports, key=lambda x: x.risk, reverse=True):
        lines.append(
            f"| `{r.path}` | {r.loc} | {r.docstring_coverage:.0%} | "
            f"{r.risk} | {len(r.findings)} |"
        )
    lines.append("")

    for r in sorted(reports, key=lambda x: x.risk, reverse=True):
        if not r.findings and not r.ai_review:
            continue
        lines += ["---", "", f"### `{r.path}`", ""]
        for f in sorted(r.findings, key=lambda x: (sev_order[x.severity], x.line)):
            badge = {"high": "🔴", "medium": "🟡", "low": "⚪"}[f.severity]
            lines.append(f"- {badge} **L{f.line}** `{f.rule}` — {f.message}")
        if r.ai_review:
            lines += ["", "> **AI review:**", ""]
            lines += [f"> {ln}" for ln in r.ai_review.splitlines()]
        lines.append("")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def discover(target: Path) -> list[Path]:
    if target.is_file() and target.suffix == ".py":
        return [target]
    return sorted(
        p for p in target.rglob("*.py")
        if "venv" not in p.parts and "__pycache__" not in p.parts
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="AI-based automated QC for Python packages.")
    ap.add_argument("target", type=Path, help="File or directory to analyse.")
    ap.add_argument("--json", type=Path, help="Also write a JSON report to this path.")
    ap.add_argument("--no-ai", action="store_true", help="Disable AI review.")
    ap.add_argument("--ai-files", type=int, default=MAX_FILES_FOR_AI,
                    help="Max riskiest files to send for AI review.")
    args = ap.parse_args()

    if not args.target.exists():
        print(f"error: {args.target} not found", file=sys.stderr)
        return 2

    files = discover(args.target)
    if not files:
        print("No Python files found.", file=sys.stderr)
        return 1

    reports = [analyze_file(f) for f in files]

    use_ai = not args.no_ai and bool(os.environ.get("ANTHROPIC_API_KEY"))
    if use_ai:
        for r in sorted(reports, key=lambda x: x.risk, reverse=True)[:args.ai_files]:
            src = Path(r.path).read_text(encoding="utf-8", errors="replace")
            r.ai_review = ai_review_file(r.path, src)

    score = quality_score(reports)
    md = build_markdown(reports, score, use_ai)
    Path("qc_report.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"\n📝 Markdown report written to qc_report.md")

    if args.json:
        payload = {"score": score, "ai": use_ai,
                   "files": [asdict(r) for r in reports]}
        args.json.write_text(json.dumps(payload, indent=2, default=lambda o: o.__dict__),
                             encoding="utf-8")
        print(f"📦 JSON report written to {args.json}")

    # Non-zero exit if quality is poor — handy for CI gates.
    return 0 if score >= 60 else 1


if __name__ == "__main__":
    raise SystemExit(main())
