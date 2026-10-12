import pytest


@pytest.fixture(autouse=True)
def _stub_tool_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolve every bundled tool to its bare name.

    Compressor tests assert exact argv, which must not depend on whether the
    binaries were built on this host (CI has none) or are on PATH. `resolve_tool`
    calls this module-level `_resolve`, so one patch covers every compressor.
    """
    monkeypatch.setattr("imslim.binary_resolver._resolve", lambda name: name)
