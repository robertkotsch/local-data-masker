import pandas as pd

from local_data_masker.exporters.table_exporter import export_csv, export_excel
from local_data_masker.extractors.table_extractor import is_supported, load_table


def test_is_supported():
    from pathlib import Path

    assert is_supported(Path("data.csv"))
    assert is_supported(Path("data.xlsx"))
    assert not is_supported(Path("data.pdf"))


def test_csv_roundtrip(tmp_path):
    path = tmp_path / "data.csv"
    df = pd.DataFrame({"name": ["Ben Miller"], "email": ["ben@example.com"]})
    export_csv(df, path)

    sheets = load_table(path)
    assert list(sheets.keys()) == ["Sheet1"]
    loaded = sheets["Sheet1"]
    assert loaded["name"][0] == "Ben Miller"


def test_excel_roundtrip(tmp_path):
    path = tmp_path / "data.xlsx"
    df = pd.DataFrame({"name": ["Ben Miller"]})
    export_excel({"Sheet1": df}, path)

    sheets = load_table(path)
    assert "Sheet1" in sheets
    assert sheets["Sheet1"]["name"][0] == "Ben Miller"
