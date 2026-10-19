"""PostToolUse hook (Write|Edit), skill tool-testing. Exit 2 + stderr sends the
problem back to Claude.

* A Python tool under a `tools` directory (also its subdirectories) must have a
  test, <parent of tools>/tests/<same subdir>/test_<name>.py,
  <parent of tools>/tests/test_<name>.py, tests/tools/test_<name>.py, or any
  tests/**/test_*.py that imports or runs it; every such test must pass.
* Editing a test file runs that test too.
* Changing or removing an existing `assert` line in a test is reported: the
  expected result may only change with the user's consent (skill rule 5).
* A run in which no test was really executed (all skipped / deselected) does
  not count as a pass.

Windows: run with `py -3.12` (pytest installed there).
"""
import json, os, re, subprocess, sys
from pathlib import Path

sys.stdin.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

ev = json.load(sys.stdin)
ti = ev.get("tool_input", {}) or {}
p = Path(ti.get("file_path", ""))
root = os.environ.get("CLAUDE_PROJECT_DIR") or ev.get("cwd") or "."
problems = []


def assert_lines(text):
    return [l.strip() for l in (text or "").splitlines() if re.match(r"\s*assert\b", l)]


def changed_asserts():
    """Assert lines that existed before the edit and are gone or different now."""
    if ev.get("tool_name") == "Edit" or "old_string" in ti:
        old, new = assert_lines(ti.get("old_string")), assert_lines(ti.get("new_string"))
        return [l for l in old if l not in new]
    # Write: compare with the last committed version, if the file is tracked.
    r = subprocess.run(["git", "diff", "--unified=0", "HEAD", "--", str(p)], cwd=str(p.parent),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        return []
    removed = [l[1:].strip() for l in r.stdout.splitlines()
               if l.startswith("-") and not l.startswith("---") and re.match(r"-\s*assert\b", l)]
    added = [l[1:].strip() for l in r.stdout.splitlines()
             if l.startswith("+") and not l.startswith("+++")]
    return [l for l in removed if l not in added]


def run_test(test):
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rs", str(test)], cwd=root,
                       env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = r.stdout + r.stderr
    if "No module named pytest" in r.stderr:
        problems.append(f"Brak pytest w {sys.executable} (zainstaluj: py -3.12 -m pip install "
                        f"pytest). Testu {test} nie uruchomiono.")
    elif r.returncode == 5:  # pytest: no tests collected
        problems.append(f"{test}: pytest nie znalazł żadnego testu (funkcje test_*?).")
    elif r.returncode != 0:
        problems.append(out[-1500:] + f"\nTest padł: {test}.")
    else:
        m = re.search(r"(\d+) passed", out)
        if not m or int(m.group(1)) == 0:
            problems.append(f"{test}: żaden test nie został naprawdę wykonany (pominięte?):\n"
                            + out[-800:] + "\nPominięty test niczego nie dowodzi.")


if p.suffix != ".py" or p.name == "__init__.py":
    sys.exit(0)

is_test = p.name.startswith("test_") and any(a.name == "tests" for a in p.parents)
tools = None if is_test else next((a for a in p.parents if a.name == "tools"), None)

if is_test:
    gone = changed_asserts()
    if gone:
        problems.append("Zmieniono albo usunięto asercje (oczekiwany wynik):\n  "
                        + "\n  ".join(gone[:10])
                        + "\nZasada 5: oczekiwanego wyniku nie zmienia się, żeby test przeszedł. "
                          "Jeśli user tego nie zatwierdził, cofnij zmianę i zapytaj.")
    if p.exists():
        run_test(p)
elif tools is not None:
    sub = p.parent.relative_to(tools)
    tests_dir = tools.parent / "tests"
    candidates = [tests_dir / sub / f"test_{p.stem}.py",
                  tests_dir / f"test_{p.stem}.py",
                  tests_dir / "tools" / f"test_{p.stem}.py"]
    found = [c for c in dict.fromkeys(candidates) if c.exists()]
    if not found and tests_dir.is_dir():
        # A test under another name that imports or runs this tool (shared test files).
        pat = re.compile(r"(import\s+%s\b|from\s+[\w.]*\b%s\s+import|\b%s\.py\b|[\"']%s[\"'])"
                         % ((re.escape(p.stem),) * 4))
        for t in sorted(tests_dir.rglob("test_*.py")):
            try:
                if pat.search(t.read_text(encoding="utf-8", errors="replace")):
                    found.append(t)
            except OSError:
                pass
    if not found:
        wanted = " albo ".join(str(c) for c in dict.fromkeys(candidates))
        problems.append(f"Brak {wanted} (ani testu, który importuje {p.stem}). "
                        f"Napisz test ze znanym wynikiem.")
    for test in found:
        run_test(test)
else:
    sys.exit(0)

if problems:
    print("\n\n".join(problems) + "\nSkill: tool-testing.", file=sys.stderr)
    sys.exit(2)
