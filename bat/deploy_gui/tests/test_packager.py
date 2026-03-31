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


def test_create_zip_can_exclude_specific_relative_path(tmp_path):
    src = tmp_path / "Program"
    backend = src / "backend"
    backend.mkdir(parents=True)
    (backend / "project_completion.db").write_text("db", encoding="utf-8")
    (backend / "app.py").write_text("print('ok')", encoding="utf-8")

    target = tmp_path / "out.zip"
    create_zip(src, target, ignore_relative_paths={"backend/project_completion.db"})

    with zipfile.ZipFile(target) as zf:
        names = zf.namelist()

    assert "Program/backend/app.py" in names
    assert "Program/backend/project_completion.db" not in names
