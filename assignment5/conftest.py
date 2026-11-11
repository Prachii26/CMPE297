"""Root conftest: make `task`, `core` and `guard` importable, and send every
ledger, audit record, solver dump and result file a test writes into a
temporary directory -- tests never touch docs/."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _isolate_outputs(tmp_path, monkeypatch):
    import core.cli
    import core.ledger
    import core.loop
    import task.vault
    monkeypatch.setattr(core.ledger, "LEDGER_DIR", tmp_path / "ledgers")
    monkeypatch.setattr(task.vault, "AUDIT_DIR", tmp_path / "ledgers")
    monkeypatch.setattr(core.loop, "SOLVER_DIR", tmp_path / "solvers")
    monkeypatch.setattr(core.cli, "RESULTS_DIR", tmp_path / "results")
    yield tmp_path


def add_method_path(folder: str) -> None:
    """Method folders start with digits, so they are put on sys.path rather
    than imported as packages. Module names are prefixed per method to avoid
    collisions."""
    p = str(ROOT / folder)
    if p not in sys.path:
        sys.path.insert(0, p)
