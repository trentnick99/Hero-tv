"""Run the test suite on the CI machine and report each failure as a GitHub annotation, so the results can be read
through the normal GitHub API (the raw log is not always reachable). Exit code 1 when anything failed."""
import os
import sys
import unittest


def esc(text):
    return text.replace("%", "%25").replace("\r", "").replace("\n", "%0A")


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, root)
    os.chdir(root)
    suite = unittest.defaultTestLoader.discover("tests")
    res = unittest.TextTestRunner(verbosity=1).run(suite)
    problems = [("FAIL", t, tb) for t, tb in res.failures] + [("ERROR", t, tb) for t, tb in res.errors]
    for kind, test, tb in problems[:8]:
        tail = "\n".join(tb.strip().splitlines()[-25:])
        print(f"::error title={kind} {test.id()}::{esc(tail)}")
    if len(problems) > 8:
        rest = "\n\n".join(f"{k} {t.id()}\n" + "\n".join(tb.strip().splitlines()[-6:]) for k, t, tb in problems[8:40])
        print(f"::error title={len(problems) - 8} more failures::{esc(rest)}")
    print(f"::notice title=Tests::{res.testsRun} run, {len(res.failures)} failed, {len(res.errors)} errors, {len(res.skipped)} skipped")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
