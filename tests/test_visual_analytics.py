import pandas as pd

from streamlit_app import (
    build_chart,
    dataframe_to_csv_bytes,
    dataframe_to_excel_bytes,
    infer_auto_chart,
    numeric_distribution_dataframe,
)


def test_auto_chart_prefers_line_for_date_and_numeric() -> None:
    df = pd.DataFrame(
        [
            {"order_date": "2026-01-01", "sales": 10},
            {"order_date": "2026-01-02", "sales": 14},
        ]
    )

    assert infer_auto_chart(df) == "Line Chart"


def test_auto_chart_prefers_pie_for_few_categories_and_numeric() -> None:
    df = pd.DataFrame(
        [
            {"region": "North", "sales": 10},
            {"region": "South", "sales": 14},
        ]
    )

    assert infer_auto_chart(df) == "Pie Chart"


def test_auto_chart_prefers_bar_for_many_categories_and_numeric() -> None:
    df = pd.DataFrame([{"region": f"R{i}", "sales": i} for i in range(8)])

    assert infer_auto_chart(df) == "Bar Chart"


def test_chart_handles_missing_numeric_columns_gracefully() -> None:
    figure, error = build_chart(pd.DataFrame([{"region": "North"}]), "Bar Chart")

    assert figure is None
    assert "No numeric columns" in error


def test_raw_numeric_marks_result_auto_bins_distribution() -> None:
    df = pd.DataFrame([{"marks": value} for value in [35, 42, 57, 71, 88, 92]])

    figure, error = build_chart(df, "Auto")

    assert error is None
    assert figure is not None
    assert figure.data[0].type == "bar"
    distribution = numeric_distribution_dataframe(df, "marks")
    assert list(distribution.columns) == ["value_range", "record_count"]
    assert distribution["record_count"].sum() == 6


def test_bucketed_distribution_result_prefers_bar_chart() -> None:
    df = pd.DataFrame(
        [
            {"mark_range": "0-39", "student_count": 2},
            {"mark_range": "40-59", "student_count": 5},
            {"mark_range": "60-79", "student_count": 8},
        ]
    )

    assert infer_auto_chart(df) == "Bar Chart"
    figure, error = build_chart(df, "Auto")

    assert error is None
    assert figure is not None
    assert figure.data[0].type == "bar"


def test_category_count_result_prefers_bar_chart() -> None:
    df = pd.DataFrame(
        [
            {"attendance_category": "Low", "student_count": 3},
            {"attendance_category": "Medium", "student_count": 7},
            {"attendance_category": "High", "student_count": 9},
        ]
    )

    assert infer_auto_chart(df) == "Bar Chart"


def test_csv_export_contains_rows() -> None:
    csv_bytes = dataframe_to_csv_bytes(pd.DataFrame([{"region": "North", "sales": 10}]))

    assert b"region,sales" in csv_bytes
    assert b"North,10" in csv_bytes


def test_excel_export_returns_xlsx_bytes() -> None:
    excel_bytes = dataframe_to_excel_bytes(pd.DataFrame([{"region": "North", "sales": 10}]))

    assert excel_bytes.startswith(b"PK")
