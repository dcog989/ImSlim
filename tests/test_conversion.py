import pytest

from imslim.conversion import decode_commands


@pytest.mark.parametrize("mime", ["image/avif", "image/jxl", "image/jpeg", "image/tiff"])
def test_every_decode_command_has_a_memory_limit(mime: str) -> None:
    # Both a bundled decoder and the Qt fallback decode one full-size image.
    (command,) = decode_commands(mime, "source", "out.png")

    assert command.limit is not None
