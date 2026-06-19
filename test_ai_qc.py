"""Unit tests for ai_qc — demonstrates test-driven quality control."""

import textwrap
from pathlib import Path

import ai_qc


def _write(tmp_path: Path, code: str) -> Path:
    f = tmp_path / "sample.py"
    f.write_text(textwrap.dedent(code), encoding="utf-8")
    return f


def test_clean_file_has_no_high_findings(tmp_path):
    f = _write(tmp_path, '''
        """A tidy module."""

        def add(a, b):
            """Return the sum of a and b."""
            return a + b
    ''')
    rep = ai_qc.analyze_file(f)
    assert not [x for x in rep.findings if x.severity == "high"]
    assert rep.docstring_coverage == 1.0


def test_bare_except_is_flagged_high(tmp_path):
    f = _write(tmp_path, '''
        def risky():
            try:
                pass
            except:
                pass
    ''')
    rep = ai_qc.analyze_file(f)
    rules = {x.rule for x in rep.findings}
    assert "bare-except" in rules


def test_eval_is_flagged_high(tmp_path):
    f = _write(tmp_path, '''
        def danger(s):
            return eval(s)
    ''')
    rep = ai_qc.analyze_file(f)
    high = [x for x in rep.findings if x.severity == "high"]
    assert any(x.rule == "dangerous-call" for x in high)


def test_syntax_error_is_caught(tmp_path):
    f = _write(tmp_path, "def broken(:\n    pass\n")
    rep = ai_qc.analyze_file(f)
    assert any(x.rule == "syntax-error" for x in rep.findings)


def test_score_discriminates_good_from_bad(tmp_path):
    good = _write(tmp_path, '''
        """Good."""

        def f(x):
            """Doc."""
            return x
    ''')
    good_score = ai_qc.quality_score([ai_qc.analyze_file(good)])

    bad_file = tmp_path / "bad.py"
    bad_file.write_text(
        "def f(a,b,c,d,e,f,g):\n"
        "    try:\n        x = eval(input())\n    except:\n        pass\n",
        encoding="utf-8",
    )
    bad_score = ai_qc.quality_score([ai_qc.analyze_file(bad_file)])

    assert good_score > bad_score


def test_loc_counts_empty_and_trailing_newline(tmp_path):
    empty = tmp_path / "empty.py"
    empty.write_text("", encoding="utf-8")
    assert ai_qc.analyze_file(empty).loc == 0

    trailing = tmp_path / "trailing.py"
    trailing.write_text("x = 1\n", encoding="utf-8")
    assert ai_qc.analyze_file(trailing).loc == 1
