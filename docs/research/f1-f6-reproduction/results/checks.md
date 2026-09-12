# Verification record

2026-09-11, source main `668bf46c88c37f3c14a4e143eb60c8695df74c6f`
plus the evidence-only changes in this Task. Node 22.16.0, npm 11.4.1,
Python 3.12.14, uv 0.12.10, pytest 9.1.1, Ruff 0.16.7.

| Command | Result |
| --- | --- |
| README reproduction commands, fresh beta environment and detached main build | Both probes passed; both result comparisons identical |
| `uv run --project packages/python/spec --group test python -m pytest packages/python/spec/tests spec/tests tests/test_release_tools.py tests/test_public_docs.py` | 114 passed |
| `uv run --project packages/python/langgraph --group test pytest packages/python/langgraph/tests` | 46 passed |
| `npm run check --prefix packages/typescript/spec` | Build, formatting, type checks, 7 tests passed |
| `npm run check --prefix packages/typescript/langgraph` | Compatibility, build, formatting, type checks, 23 tests passed |
| `uvx --from ruff==0.16.7 ruff format --check packages/python scripts tests` | Passed, 26 files |
| `uvx --from ruff==0.16.7 ruff check packages/python scripts tests` | Passed |
| `uv build packages/python/spec --out-dir dist/spec --clear` | Wheel and sdist built |
| `uv build packages/python/langgraph --out-dir dist/langgraph --clear` | Wheel and sdist built |
| `uv run --project packages/python/spec --group test python -m pytest tests/test_public_docs.py` after final documentation edits | 65 passed |

Commands ran through `rtk`. An initial combined Python invocation used the
`pytest` entry point rather than `python -m pytest`, causing collection to fail
with `ModuleNotFoundError: No module named 'scripts'`. The corrected invocation
above passed without changing product or test code. This is not a product defect.

New probes additionally passed Node syntax checks and the repository's pinned
Prettier formatter. JSON results retain the probe's own formatting for exact
replay comparisons. Airflow was source-audited, not installed or scheduled.
The checks do not qualify a release or broaden framework/runtime support.
