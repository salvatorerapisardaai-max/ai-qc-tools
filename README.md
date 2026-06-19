# 🤖 ai-qc-tools

> AI-based automated **quality control** for Python software packages — runs *with or without* an LLM API key.

[![CI](https://github.com/salvatorerapisardaai-max/ai-qc-tools/actions/workflows/qc.yml/badge.svg)](https://github.com/salvatorerapisardaai-max/ai-qc-tools/actions)
![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)

A small, self-contained tool that automates a software quality-control workflow:

1. **Discovers** every `.py` file in a target package.
2. Runs **deterministic static checks** via the AST (syntax errors, bare `except`, `eval`/`exec`, over-long functions, too many arguments, missing docstrings) plus line-level checks (long lines, stray `print`, unresolved `TODO/FIXME`).
3. Optionally asks **Claude** for a senior-engineer review of the riskiest files.
4. Emits a structured **Markdown + JSON report** with a 0–100 quality score and a CI-friendly exit code.

The AI step is **optional by design**: with no `ANTHROPIC_API_KEY`, the tool runs fully offline and deterministic; with a key, it augments the static report with model-driven insight.

## Quickstart

```bash
pip install -r requirements.txt          # only needed for the AI step
python ai_qc.py path/to/package          # analyse a folder
python ai_qc.py file.py --no-ai          # force static-only
python ai_qc.py path/ --json report.json # also emit JSON
```

Set the key to enable AI review:

```bash
export ANTHROPIC_API_KEY=sk-...
python ai_qc.py path/to/package
```

## Example output

```
# 🤖 AI Quality-Control Report
**Quality score:** 70/100
**Files analysed:** 1
**Findings:** 0 high · 0 medium · 25 low
**AI review:** static-only (no API key)
```

A deliberately bad file (`eval`, bare `except`, 7 args) scores **10/100**; clean code scores high. The exit code is non-zero below 60, so the tool drops straight into a CI gate.

## Use in CI (GitHub Actions)

A ready-to-use workflow lives in [`.github/workflows/qc.yml`](.github/workflows/qc.yml): it runs the analyzer on every push and fails the build if quality drops below threshold.

## Tests

```bash
pytest -q
```

## Why I built it

I use Gen-AI tooling and prompt engineering daily while building production software, and I wanted a reproducible way to keep quality measurable rather than vibes-based. It also doubles as a clean demonstration of automated QC workflows.

## License

MIT © Salvatore Rapisarda
