from __future__ import annotations

from app.core import console


class LegacyEncodedStream:
    """Minimal stream that reproduces a Windows legacy-code-page failure."""

    def __init__(self) -> None:
        self.encoding = "gbk"
        self.content = ""

    def reconfigure(self, *, encoding: str) -> None:
        self.encoding = encoding

    def write(self, text: str) -> int:
        text.encode(self.encoding)
        self.content += text
        return len(text)

    def flush(self) -> None:
        return None


def test_console_reconfigures_legacy_windows_stream_for_ipa(monkeypatch) -> None:
    stdout = LegacyEncodedStream()
    stderr = LegacyEncodedStream()
    monkeypatch.setattr(console.sys, "stdout", stdout)
    monkeypatch.setattr(console.sys, "stderr", stderr)

    console.session_start(seed=888, preset="ipa_minimal")
    console.session_end(
        total_eras=1,
        alive=1,
        dead=0,
        morph="isolating",
        order="SVO",
        sample="/ʃa/",
    )

    assert stdout.encoding == "utf-8"
    assert stderr.encoding == "utf-8"
    assert "/ʃa/" in stdout.content
