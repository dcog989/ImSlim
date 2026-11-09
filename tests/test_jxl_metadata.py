from pathlib import Path

from imslim.compressors.jxl_compressor import JXLCompressor, metadata_kinds_from_info


def test_jxlinfo_text_reports_present_kinds() -> None:
    text = (
        "JPEG XL file format container (ISO/IEC 18181-2)\n"
        "Brotli-compressed Exif metadata: 46 compressed bytes\n"
        "Brotli-compressed xml  metadata: 28 compressed bytes\n"
    )

    assert metadata_kinds_from_info(text) == frozenset({"exif", "xmp"})


def test_jxlinfo_text_without_metadata_reports_nothing() -> None:
    text = "JPEG XL image, 4x2, lossy, 8-bit RGB\nColor space: RGB\n"

    assert metadata_kinds_from_info(text) == frozenset()


def test_prune_drops_missing_and_empty_sidecars(tmp_path: Path) -> None:
    empty = tmp_path / "empty.exif"
    empty.write_bytes(b"")
    argv = [
        "cjxl",
        "-x",
        f"exif={empty}",
        "-x",
        f"xmp={tmp_path / 'missing.xmp'}",
        "in.png",
        "out.jxl",
    ]

    assert JXLCompressor()._prune_metadata_hints(argv) == ["cjxl", "in.png", "out.jxl"]
