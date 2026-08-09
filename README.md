# 🤖 ai-qc-tools

> AI-assisted **quality control** for Python packages — runs *with or without* an LLM API key.

> 🇬🇧 [English](#-english) · 🇮🇹 [Italiano](#-italiano)

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)

---

## 🇬🇧 English

A single-file analyzer that walks a Python package, applies deterministic AST and line-level checks, optionally asks Claude for a senior-engineer review of the riskiest files, and emits a Markdown + JSON report with a 0–100 quality score and a CI-friendly exit code.

### Overview

Code review by feel doesn't scale, and full static-analysis suites are heavy for small projects. `ai-qc-tools` sits in between: one script, no configuration, a score you can gate a build on.

The design decision that matters is that **the AI step is optional**. Without `ANTHROPIC_API_KEY` the tool is fully offline and deterministic — the same input always produces the same score — so it is safe to run in CI without secrets. With a key, the model review is layered on top of the static findings rather than replacing them.

### Features

- **Recursive discovery** of `.py` files, skipping `venv/` and `__pycache__/`.
- **AST-based checks** for real code structure, not regex guessing.
- **Line-level checks** for the things an AST doesn't see.
- **Severity-weighted scoring** — high `8.0`, medium `3.0`, low `0.5`. Score combines risk density per line of code with docstring coverage:
  `100 − min(70, risk_density × 400) − (1 − avg_docstring_coverage) × 20`
- **Optional AI review** — the *N* riskiest files (default 5) are sent to Claude with a length-capped prompt; the source is truncated to 6 000 characters to stay inside a predictable token budget.
- **Graceful degradation** — the `anthropic` package is imported lazily, and a missing package, missing key or failing API call each fall back to static-only instead of crashing.
- **Two report formats** — a Markdown report always written to `qc_report.md`, plus an optional structured JSON dump.
- **CI gate** — exit code `1` when the score drops below 60, `0` otherwise.
- **Versioned prompts** — `prompts/code_review.md` documents the prompt and the reasoning behind each of its parts, reviewed like any other source file.

#### Rule catalogue

| Rule | Severity | What it catches |
|------|:--------:|-----------------|
| `syntax-error` | 🔴 high | File does not parse |
| `bare-except` | 🔴 high | `except:` swallowing every error |
| `dangerous-call` | 🔴 high | Calls to `eval` or `exec` |
| `long-function` | 🟡 medium | Function body longer than 60 lines |
| `too-many-args` | ⚪ low | More than 6 positional + keyword-only arguments |
| `missing-docstring` | ⚪ low | Module, class or function without a docstring |
| `long-line` | ⚪ low | Line longer than 120 characters |
| `stray-print` | ⚪ low | `print(` outside a comment |
| `todo-marker` | ⚪ low | Unresolved `TODO` / `FIXME` / `XXX` |

### Tech Stack

- **Python 3.10+** — standard library only for the analysis path (`ast`, `argparse`, `dataclasses`, `pathlib`, `json`)
- **[`anthropic`](https://pypi.org/project/anthropic/) ≥ 0.40** — optional, only for the AI review step
- **pytest ≥ 8** — test suite
- **GitHub Actions** — CI workflow definition in `workflows/qc.yml`

### Getting Started

```bash
git clone https://github.com/salvatorerapisardaai-max/ai-qc-tools
cd ai-qc-tools
pip install -r requirements.txt
```

The analysis path needs no dependencies at all — `requirements.txt` installs `anthropic` for the AI step and `pytest` for the test suite. To run static-only on a machine with nothing installed, `python ai_qc.py <path> --no-ai` works out of the box.

Enable the AI review by exporting a key:

```bash
export ANTHROPIC_API_KEY=sk-...
```

### Usage

```bash
python ai_qc.py path/to/package            # analyse a folder (AI review if a key is set)
python ai_qc.py file.py --no-ai            # force static-only
python ai_qc.py path/ --json report.json   # also emit a JSON report
python ai_qc.py path/ --ai-files 10        # review the 10 riskiest files instead of 5
```

Every run writes `qc_report.md` to the current directory and prints it to stdout.

Analysing this repository's own analyzer:

```console
$ python ai_qc.py ai_qc.py --no-ai
# 🤖 AI Quality-Control Report

**Quality score:** **70/100**
**Files analysed:** 1
**Findings:** 0 high · 0 medium · 25 low
**AI review:** static-only (no API key)
```

A deliberately bad file — `eval`, a bare `except`, seven arguments, no docstrings — scores **10/100**:

```console
$ python ai_qc.py bad.py --no-ai
**Quality score:** **10/100**
**Findings:** 2 high · 0 medium · 3 low
```

#### Use in CI

`workflows/qc.yml` defines a GitHub Actions job that installs dependencies, runs the test suite, runs the analyzer with `--no-ai` (no secrets needed) and uploads `qc_report.md` as a build artifact. The build fails when the quality score drops below the threshold.

> ⚠️ GitHub only picks up workflows under `.github/workflows/`. Move the file there to activate it:
> ```bash
> mkdir -p .github/workflows && git mv workflows/qc.yml .github/workflows/qc.yml
> ```

### Tests

```bash
pytest -q
```

Six tests cover the analyzer end to end: a clean file produces no high-severity findings, `bare-except` and `eval` are flagged, syntax errors are caught rather than raised, the score discriminates good code from bad, and line counting handles empty files and trailing newlines.

### Project Structure

```
ai-qc-tools/
├── ai_qc.py                 # The whole tool: analysis, scoring, reporting, CLI
├── test_ai_qc.py            # pytest suite
├── prompts/
│   └── code_review.md       # Versioned prompt + the reasoning behind its design
├── workflows/
│   └── qc.yml               # GitHub Actions QC pipeline
├── requirements.txt
└── LICENSE
```

`ai_qc.py` is organised in four blocks: the `Finding` / `FileReport` data model, the `StaticAnalyzer` AST visitor plus textual scanner, the optional AI review, and scoring, Markdown rendering and the CLI.

### Why I built it

I use Gen-AI tooling and prompt engineering daily while building production software, and I wanted a reproducible way to keep quality measurable rather than vibes-based. Treating the prompt as a versioned, reviewable artifact — rather than a string buried in the code — is part of the same idea.

### License

MIT © Salvatore Rapisarda — see [LICENSE](LICENSE).

---

## 🇮🇹 Italiano

Un analizzatore in un solo file che attraversa un package Python, applica controlli deterministici su AST e su riga, chiede facoltativamente a Claude una review da senior engineer sui file più rischiosi, e produce un report Markdown + JSON con un punteggio di qualità 0–100 e un exit code adatto alla CI.

### Panoramica

La review "a sensazione" non scala, e le suite di analisi statica complete sono pesanti per i progetti piccoli. `ai-qc-tools` sta nel mezzo: uno script, zero configurazione, un punteggio su cui bloccare una build.

La scelta di progetto che conta è che **il passaggio AI è opzionale**. Senza `ANTHROPIC_API_KEY` lo strumento è completamente offline e deterministico — lo stesso input produce sempre lo stesso punteggio — quindi si può usare in CI senza secret. Con una chiave, la review del modello si aggiunge ai risultati statici invece di sostituirli.

### Funzionalità

- **Scoperta ricorsiva** dei file `.py`, saltando `venv/` e `__pycache__/`.
- **Controlli basati su AST**, sulla struttura reale del codice e non su regex.
- **Controlli riga per riga** per ciò che l'AST non vede.
- **Punteggio pesato per gravità** — high `8.0`, medium `3.0`, low `0.5`. Il punteggio combina la densità di rischio per riga di codice con la copertura dei docstring:
  `100 − min(70, densità_rischio × 400) − (1 − copertura_docstring_media) × 20`
- **Review AI opzionale** — gli *N* file più rischiosi (default 5) vengono inviati a Claude con un prompt a lunghezza limitata; il sorgente è troncato a 6 000 caratteri per restare in un budget di token prevedibile.
- **Degrado controllato** — il pacchetto `anthropic` è importato in modo lazy, e pacchetto mancante, chiave assente o chiamata API fallita ricadono sulla sola analisi statica invece di far crashare il tool.
- **Due formati di report** — un report Markdown sempre scritto in `qc_report.md`, più un dump JSON strutturato opzionale.
- **Gate per la CI** — exit code `1` quando il punteggio scende sotto 60, `0` altrimenti.
- **Prompt versionati** — `prompts/code_review.md` documenta il prompt e il ragionamento dietro ogni sua parte, revisionabile come qualunque altro sorgente.

#### Catalogo delle regole

| Regola | Gravità | Cosa intercetta |
|--------|:-------:|-----------------|
| `syntax-error` | 🔴 alta | Il file non è parsabile |
| `bare-except` | 🔴 alta | `except:` che ingoia qualsiasi errore |
| `dangerous-call` | 🔴 alta | Chiamate a `eval` o `exec` |
| `long-function` | 🟡 media | Corpo di funzione più lungo di 60 righe |
| `too-many-args` | ⚪ bassa | Più di 6 argomenti posizionali + keyword-only |
| `missing-docstring` | ⚪ bassa | Modulo, classe o funzione senza docstring |
| `long-line` | ⚪ bassa | Riga più lunga di 120 caratteri |
| `stray-print` | ⚪ bassa | `print(` fuori da un commento |
| `todo-marker` | ⚪ bassa | `TODO` / `FIXME` / `XXX` non risolti |

### Stack tecnologico

- **Python 3.10+** — solo libreria standard per il percorso di analisi (`ast`, `argparse`, `dataclasses`, `pathlib`, `json`)
- **[`anthropic`](https://pypi.org/project/anthropic/) ≥ 0.40** — opzionale, solo per la review AI
- **pytest ≥ 8** — suite di test
- **GitHub Actions** — definizione della pipeline CI in `workflows/qc.yml`

### Installazione

```bash
git clone https://github.com/salvatorerapisardaai-max/ai-qc-tools
cd ai-qc-tools
pip install -r requirements.txt
```

Il percorso di analisi non richiede alcuna dipendenza: `requirements.txt` installa `anthropic` per il passaggio AI e `pytest` per i test. Per eseguire la sola analisi statica su una macchina senza nulla installato, `python ai_qc.py <path> --no-ai` funziona così com'è.

Per abilitare la review AI, esporta una chiave:

```bash
export ANTHROPIC_API_KEY=sk-...
```

### Utilizzo

```bash
python ai_qc.py path/to/package            # analizza una cartella (review AI se c'è una chiave)
python ai_qc.py file.py --no-ai            # forza la sola analisi statica
python ai_qc.py path/ --json report.json   # produce anche un report JSON
python ai_qc.py path/ --ai-files 10        # esamina i 10 file più rischiosi invece di 5
```

Ogni esecuzione scrive `qc_report.md` nella cartella corrente e lo stampa su stdout.

Analizzando l'analizzatore stesso di questo repository:

```console
$ python ai_qc.py ai_qc.py --no-ai
# 🤖 AI Quality-Control Report

**Quality score:** **70/100**
**Files analysed:** 1
**Findings:** 0 high · 0 medium · 25 low
**AI review:** static-only (no API key)
```

Un file volutamente pessimo — `eval`, `except` nudo, sette argomenti, nessun docstring — ottiene **10/100**:

```console
$ python ai_qc.py bad.py --no-ai
**Quality score:** **10/100**
**Findings:** 2 high · 0 medium · 3 low
```

#### Uso in CI

`workflows/qc.yml` definisce un job GitHub Actions che installa le dipendenze, esegue i test, lancia l'analizzatore con `--no-ai` (nessun secret necessario) e carica `qc_report.md` come artifact della build. La build fallisce quando il punteggio di qualità scende sotto la soglia.

> ⚠️ GitHub esegue solo i workflow sotto `.github/workflows/`. Sposta il file lì per attivarlo:
> ```bash
> mkdir -p .github/workflows && git mv workflows/qc.yml .github/workflows/qc.yml
> ```

### Test

```bash
pytest -q
```

Sei test coprono l'analizzatore end to end: un file pulito non produce risultati di gravità alta, `bare-except` ed `eval` vengono segnalati, gli errori di sintassi sono intercettati invece che sollevati, il punteggio distingue il codice buono da quello cattivo, e il conteggio delle righe gestisce file vuoti e newline finali.

### Struttura del progetto

```
ai-qc-tools/
├── ai_qc.py                 # Tutto il tool: analisi, scoring, report, CLI
├── test_ai_qc.py            # Suite pytest
├── prompts/
│   └── code_review.md       # Prompt versionato + il ragionamento dietro il design
├── workflows/
│   └── qc.yml               # Pipeline QC per GitHub Actions
├── requirements.txt
└── LICENSE
```

`ai_qc.py` è organizzato in quattro blocchi: il modello dati `Finding` / `FileReport`, il visitor AST `StaticAnalyzer` con lo scanner testuale, la review AI opzionale, e scoring, rendering Markdown e CLI.

### Perché l'ho costruito

Uso quotidianamente strumenti Gen-AI e prompt engineering mentre sviluppo software di produzione, e volevo un modo riproducibile per tenere la qualità misurabile invece che affidata alle sensazioni. Trattare il prompt come un artefatto versionato e revisionabile — invece che come una stringa sepolta nel codice — fa parte della stessa idea.

### Licenza

MIT © Salvatore Rapisarda — vedi [LICENSE](LICENSE).
