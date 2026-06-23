import json

from local_data_masker.maskers.mapping_store import MappingStore


def test_set_and_get_roundtrip():
    store = MappingStore()
    store.set("name", "Ben Miller", "John Winter")
    assert store.get("name", "Ben Miller") == "John Winter"


def test_get_missing_returns_none():
    store = MappingStore()
    assert store.get("name", "Unknown Person") is None


def test_save_and_load_roundtrip(tmp_path):
    path = tmp_path / "mapping.json"
    store = MappingStore()
    store.set("email", "ben@example.com", "fake@example.test")
    store.save(path)

    loaded = json.loads(path.read_text())
    assert loaded["email::ben@example.com"] == "fake@example.test"

    new_store = MappingStore()
    new_store.load(path)
    assert new_store.get("email", "ben@example.com") == "fake@example.test"
