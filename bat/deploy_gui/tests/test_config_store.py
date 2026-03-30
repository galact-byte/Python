from deploy_gui.config_store import ConfigStore
from deploy_gui.models import ProjectConfig


def test_save_and_load_multiple_projects(tmp_path):
    store = ConfigStore(tmp_path / "projects.json")
    store.save_all([ProjectConfig(name="A", mode="zip"), ProjectConfig(name="B", mode="git")])
    loaded = store.load_all()
    assert [p.name for p in loaded] == ["A", "B"]
