import pandas as pd

from local_data_masker.detectors.regex_detector import (
    CATEGORY_ADDRESS,
    CATEGORY_DATE,
    CATEGORY_DATE_OF_BIRTH,
    CATEGORY_EMAIL,
    CATEGORY_ID,
    CATEGORY_NAME,
    CATEGORY_PHONE,
    classify_column,
    classify_dataframe,
)


def test_classifies_by_column_name():
    assert classify_column("Email", ["a@b.com"]).category == CATEGORY_EMAIL
    assert classify_column("phone_number", ["+1 555 1234"]).category == CATEGORY_PHONE
    assert classify_column("date_of_birth", ["1975/02/21"]).category == CATEGORY_DATE_OF_BIRTH
    assert classify_column("start_date", ["2024/01/01"]).category == CATEGORY_DATE
    assert classify_column("employee_id", ["481927"]).category == CATEGORY_ID
    assert classify_column("full_name", ["Ben Miller"]).category == CATEGORY_NAME


def test_name_exclusions_keep_organizational_columns_unclassified_by_name():
    result = classify_column("company_name", ["Acme GmbH"])
    assert result.category != CATEGORY_NAME


def test_classifies_by_value_shape_when_column_name_is_generic():
    result = classify_column("contact", ["ben.miller@example.com", "john.winter@example.com"])
    assert result.category == CATEGORY_EMAIL


def test_unclassified_column_returns_none():
    result = classify_column("course_title", ["Money Laundering"])
    assert result.category is None


def test_classifies_address_columns():
    assert classify_column("address", ["Main St 1, 12345 Town"]).category == CATEGORY_ADDRESS
    assert classify_column("Anschrift", ["Scheffelstr.14, 09120 Chemnitz"]).category == CATEGORY_ADDRESS
    assert classify_column("street", ["Barbarossastr.61"]).category == CATEGORY_ADDRESS


def test_classifies_examiner_as_person_name():
    assert classify_column("examiner", ["Dipl.med Babette Rother"]).category == CATEGORY_NAME
    assert classify_column("Untersucher", ["Dipl.med. Iris Bühler"]).category == CATEGORY_NAME


def test_classifies_dotted_dates_by_value_shape():
    result = classify_column("when", ["14.12.1990", "01.02.2000", "15.03.1991"])
    assert result.category == CATEGORY_DATE


def test_classify_dataframe_returns_one_result_per_column():
    df = pd.DataFrame({"name": ["Ben Miller"], "email": ["ben@example.com"]})
    results = classify_dataframe(df)
    assert {r.column for r in results} == {"name", "email"}
