# Prompts

This folder documents the prompts used by `ai-qc-tools`, versioned alongside the
code. Treating prompts as reviewable, version-controlled artifacts is part of
applying prompt engineering as an engineering discipline, not guesswork.

## `code_review` — AI quality review of a source file

**Goal:** obtain a concise, senior-level review of the riskiest files, to
complement the deterministic static analysis.

**Design choices**
- **Role prompting:** the model is framed as a senior software engineer doing QC,
  to set tone and depth.
- **Hard length cap (≤120 words):** keeps the report scannable and actionable, and
  controls token cost.
- **Explicit task shape:** top concrete issues (bugs, maintainability, security)
  plus one strength — balanced, not just negative.
- **Anti-padding instruction:** "do not restate the code", to avoid the model
  echoing the input instead of analysing it.
- **Low temperature (recommended):** for repeatable, deterministic reviews.

**Prompt template**

```
You are a senior software engineer doing quality control on a Python module.
In under 120 words, list the top concrete issues (bugs, maintainability,
security) and one strength. Be specific and actionable. Do not restate the code.

File: {path}
```python
{source}
```
```

**Notes**
- The source is truncated to a safe character budget before being inserted, to
  respect the model's context window.
- The call degrades gracefully: with no API key, the tool skips this step and
  runs static-only.

## Ideas for future prompts
- A `structured_findings` prompt returning **JSON** (severity, line, rule) so the
  AI review can be merged with the static findings into a single typed report.
- A `fix_suggestion` prompt proposing a minimal patch for each high-severity issue.
