import zipfile

from deploy_gui.packager import create_zip


def test_create_zip_from_source_directory(tmp_path):
    src = tmp_path / "Program"
    src.mkdir()
    (src / "a.txt").write_text("ok", encoding="utf-8")
    target = tmp_path / "out.zip"
    create_zip(src, target)
    assert target.exists()
    with zipfile.ZipFile(target) as zf:
        assert "Program/a.txt" in zf.namelist()
