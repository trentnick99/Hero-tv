from herotv import report


def test_only_errors_since_the_last_start_count():
    log = ["HERO TV - starting checks", "Traceback (most recent call last):", '  File "x.py"', "UnicodeDecodeError: old",
           "", "=== HERO TV quiet start ===", "HERO TV - starting checks", "ok", "Traceback (most recent call last):",
           '  File "y.py", line 3', "    boom()", "ValueError: new problem", "after"]
    errs = report.program_errors(log)
    assert len(errs) == 1
    assert errs[0][0].startswith("Traceback") and errs[0][-1] == "ValueError: new problem"
    assert report.since_start(log)[0] == "HERO TV - starting checks" and "UnicodeDecodeError: old" not in report.since_start(log)


def test_no_start_marker_keeps_everything():
    assert report.since_start(["a", "b"]) == ["a", "b"]
