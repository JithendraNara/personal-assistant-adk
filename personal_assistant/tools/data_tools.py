"""
Data analysis tools for the data_agent.

Supports CSV profiling, SQL query generation, and data summarization.
"""

import io
import json
import os
from typing import Optional

# Optional heavy deps — gracefully degrade if not installed
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


def profile_csv(file_path: str, max_rows: int = 10000) -> dict:
    """
    Profile a CSV file: shape, dtypes, missing values, basic statistics, and sample rows.

    Args:
        file_path: Absolute or relative path to the CSV file.
        max_rows: Maximum number of rows to load for profiling (default 10,000).

    Returns:
        A dict with 'status', 'file', 'shape', 'columns', 'dtypes',
        'missing_values', 'stats', and 'sample_rows'.
    """
    if not PANDAS_AVAILABLE:
        return {
            "status": "error",
            "message": "pandas is not installed. Run: pip install pandas",
        }

    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File not found: {file_path}"}

    if not file_path.endswith(".csv"):
        return {"status": "error", "message": "Only CSV files are supported."}

    try:
        df = pd.read_csv(file_path, nrows=max_rows)
    except Exception as e:
        return {"status": "error", "message": f"Failed to read CSV: {e}"}

    # Missing value analysis
    missing = df.isnull().sum()
    missing_pct = (missing / len(df) * 100).round(2)
    missing_report = {
        col: {"count": int(missing[col]), "pct": float(missing_pct[col])}
        for col in missing[missing > 0].index
    }

    # Numeric stats
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    stats = {}
    if numeric_cols:
        desc = df[numeric_cols].describe().round(4)
        stats = desc.to_dict()

    # Categorical columns — top values
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    cat_summary = {}
    for col in cat_cols[:10]:  # Limit to 10 categorical cols
        vc = df[col].value_counts().head(5)
        cat_summary[col] = {
            "unique_count": int(df[col].nunique()),
            "top_5": vc.to_dict(),
        }

    return {
        "status": "success",
        "file": os.path.basename(file_path),
        "shape": {"rows": len(df), "columns": len(df.columns)},
        "columns": df.columns.tolist(),
        "dtypes": df.dtypes.astype(str).to_dict(),
        "missing_values": missing_report,
        "numeric_stats": stats,
        "categorical_summary": cat_summary,
        "sample_rows": df.head(5).to_dict(orient="records"),
        "truncated": len(df) == max_rows,
    }


def generate_sql_query(
    description: str,
    table_schema: str,
    dialect: str = "bigquery",
) -> dict:
    """
    Generate a SQL query from a natural language description and table schema.

    Args:
        description: Natural language description of the desired query
                     (e.g. 'total sales by region for last 30 days').
        table_schema: DDL or JSON description of the table(s) involved
                      (e.g. 'orders(id INT, region STRING, amount FLOAT, created_at TIMESTAMP)').
        dialect: SQL dialect to use — 'bigquery', 'postgres', 'snowflake', 'mysql', 'duckdb'.

    Returns:
        A dict with 'status', 'dialect', 'description', 'sql', and 'notes'.
    """
    valid_dialects = {"bigquery", "postgres", "snowflake", "mysql", "duckdb", "sqlite"}
    if dialect not in valid_dialects:
        dialect = "bigquery"

    # Dialect-specific notes
    dialect_notes = {
        "bigquery": "Uses standard SQL with backtick quoting. Date functions: DATE_SUB, DATE_TRUNC.",
        "postgres": "Uses double-quote identifiers. Date functions: NOW(), INTERVAL, DATE_TRUNC.",
        "snowflake": "Uses double-quote identifiers. QUALIFY for window filtering. CURRENT_DATE().",
        "mysql": "Uses backtick quoting. DATE_FORMAT, DATE_SUB with INTERVAL.",
        "duckdb": "PostgreSQL-compatible with extensions. Good for local CSV analysis.",
        "sqlite": "Limited window functions. Use strftime for dates.",
    }

    # The LLM agent will generate the actual SQL based on these inputs.
    # This function structures the request for consistent output.
    return {
        "status": "ready",
        "dialect": dialect,
        "description": description,
        "table_schema": table_schema,
        "dialect_notes": dialect_notes.get(dialect, ""),
        "instruction": (
            f"Generate a {dialect} SQL query that: {description}. "
            f"Table schema: {table_schema}. "
            "Include comments explaining key clauses. "
            "Use CTEs for readability if the query is complex. "
            "Validate against: " + dialect_notes.get(dialect, "standard SQL")
        ),
    }


def analyze_dataframe_from_csv(file_path: str, analysis_request: str) -> dict:
    """
    Load a CSV and perform a specific analysis on it using pandas.

    Args:
        file_path: Path to the CSV file.
        analysis_request: What to analyze (e.g. 'find top 10 rows by revenue',
                         'correlation between age and salary', 'monthly trend of orders').

    Returns:
        A dict with 'status', 'analysis_request', 'result', and 'code'.
    """
    if not PANDAS_AVAILABLE:
        return {
            "status": "error",
            "message": "pandas is not installed. Run: pip install pandas",
        }

    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File not found: {file_path}"}

    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        return {"status": "error", "message": f"Failed to read CSV: {e}"}

    # Return the dataframe metadata so the LLM can write appropriate pandas code
    return {
        "status": "ready",
        "file": os.path.basename(file_path),
        "shape": {"rows": len(df), "columns": len(df.columns)},
        "columns": df.columns.tolist(),
        "dtypes": df.dtypes.astype(str).to_dict(),
        "analysis_request": analysis_request,
        "instruction": (
            f"The CSV has {len(df)} rows and {len(df.columns)} columns: "
            f"{df.columns.tolist()}. "
            f"Perform this analysis: {analysis_request}. "
            "Provide both the pandas code and the interpretation of results."
        ),
        "sample": df.head(3).to_dict(orient="records"),
    }


def describe_data_for_visualization(
    file_path: str,
    chart_type: Optional[str] = None,
) -> dict:
    """
    Analyze a CSV and recommend appropriate visualizations with ready-to-use code.

    Args:
        file_path: Path to the CSV file.
        chart_type: Optional chart type to generate code for
                    (e.g. 'bar', 'line', 'scatter', 'heatmap', 'histogram').

    Returns:
        A dict with 'status', 'recommendations', and 'sample_code'.
    """
    if not PANDAS_AVAILABLE:
        return {
            "status": "error",
            "message": "pandas is not installed. Run: pip install pandas",
        }

    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File not found: {file_path}"}

    try:
        df = pd.read_csv(file_path, nrows=1000)
    except Exception as e:
        return {"status": "error", "message": f"Failed to read CSV: {e}"}

    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    date_cols = [c for c in df.columns if "date" in c.lower() or "time" in c.lower()]

    recommendations = []
    if len(numeric_cols) >= 2:
        recommendations.append({
            "chart": "scatter",
            "columns": numeric_cols[:2],
            "reason": "Explore correlation between numeric variables.",
        })
    if cat_cols and numeric_cols:
        recommendations.append({
            "chart": "bar",
            "x": cat_cols[0],
            "y": numeric_cols[0],
            "reason": "Compare numeric values across categories.",
        })
    if date_cols and numeric_cols:
        recommendations.append({
            "chart": "line",
            "x": date_cols[0],
            "y": numeric_cols[0],
            "reason": "Show trend over time.",
        })
    if numeric_cols:
        recommendations.append({
            "chart": "histogram",
            "column": numeric_cols[0],
            "reason": "Understand distribution of a numeric variable.",
        })

    chart_filter = chart_type.lower() if chart_type else None
    if chart_filter:
        recommendations = [r for r in recommendations if r["chart"] == chart_filter]

    return {
        "status": "success",
        "file": os.path.basename(file_path),
        "numeric_columns": numeric_cols,
        "categorical_columns": cat_cols,
        "date_columns": date_cols,
        "recommendations": recommendations,
        "library": "matplotlib / seaborn or plotly",
        "note": "Use matplotlib.pyplot or plotly.express for interactive charts.",
    }
