"""File Import Service — import Excel/CSV files into MySQL tables.

Allows non-technical users to upload their data files (Excel, CSV)
and have them automatically converted to MySQL tables that the Agent
can query with natural language.
"""

import logging
import re
from io import BytesIO

import pandas as pd
from sqlalchemy import text

from app.core.database import get_workspace_session

logger = logging.getLogger(__name__)

# Max file size: 50MB
MAX_FILE_SIZE = 50 * 1024 * 1024
# Max rows to import (safety limit)
MAX_ROWS = 500_000
# Batch insert size
BATCH_SIZE = 1000


def _sanitize_table_name(filename: str) -> str:
    """Convert a filename to a valid MySQL table name.

    Rules:
    - Remove extension
    - Replace non-alphanumeric chars (including Chinese) with underscore
    - Collapse multiple underscores
    - Ensure starts with letter
    - Lowercase
    - Max 64 chars (MySQL limit)
    """
    # Remove extension
    name = re.sub(r"\.(xlsx?|csv|tsv)$", "", filename, flags=re.IGNORECASE)

    # Replace spaces, hyphens, dots with underscore
    name = re.sub(r"[\s\-\.]+", "_", name)

    # Keep Chinese chars, alphanumeric, underscore
    name = re.sub(r"[^\w\u4e00-\u9fff]", "_", name)

    # Collapse multiple underscores
    name = re.sub(r"_+", "_", name).strip("_")

    # Ensure starts with letter or underscore
    if name and not re.match(r"[a-zA-Z_\u4e00-\u9fff]", name[0]):
        name = "t_" + name

    # Lowercase (but keep Chinese)
    name = name.lower()

    # Truncate
    name = name[:64]

    return name or "imported_table"


def _pandas_dtype_to_mysql(dtype, sample_values=None) -> str:
    """Map pandas dtype to MySQL column type."""
    dtype_str = str(dtype)

    if "int" in dtype_str:
        return "BIGINT"
    elif "float" in dtype_str:
        return "DOUBLE"
    elif "datetime" in dtype_str:
        return "DATETIME"
    elif "bool" in dtype_str:
        return "TINYINT(1)"
    elif "category" in dtype_str:
        return "VARCHAR(255)"
    else:
        # object / string — check max length from sample
        if sample_values is not None:
            max_len = max(
                (len(str(v)) for v in sample_values if pd.notna(v)),
                default=50,
            )
            # Round up to nice boundary
            varchar_len = min(max(max_len * 2, 50), 2000)
            return f"VARCHAR({varchar_len})"
        return "TEXT"


def _sanitize_column_name(col: str) -> str:
    """Sanitize a column name for MySQL.

    Keep Chinese characters (they're valid in MySQL with backticks),
    replace problematic chars.
    """
    col = str(col).strip()
    # Replace backticks and null bytes
    col = col.replace("`", "").replace("\x00", "")
    # Replace control chars
    col = re.sub(r"[\x00-\x1f\x7f]", "", col)
    # Truncate
    col = col[:64]
    return col or "col"


def read_file(file_content: bytes, filename: str) -> pd.DataFrame:
    """Read an uploaded file into a DataFrame.

    Supports: .xlsx, .xls, .csv, .tsv
    """
    lower = filename.lower()

    if lower.endswith((".xlsx", ".xls")):
        df = pd.read_excel(BytesIO(file_content), engine="openpyxl")
    elif lower.endswith(".tsv"):
        df = pd.read_csv(BytesIO(file_content), sep="\t", encoding="utf-8")
    else:
        # CSV — try utf-8 first, then gbk (common for Chinese Excel exports)
        try:
            df = pd.read_csv(BytesIO(file_content), encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(BytesIO(file_content), encoding="gbk")

    # Basic cleanup
    df.columns = [_sanitize_column_name(c) for c in df.columns]
    # Drop completely empty rows
    df.dropna(how="all", inplace=True)

    if len(df) > MAX_ROWS:
        logger.warning(f"File truncated from {len(df)} to {MAX_ROWS} rows")
        df = df.head(MAX_ROWS)

    return df


def _check_table_exists(table_name: str) -> bool:
    """Check if a table already exists in the business database."""
    try:
        with get_workspace_session() as session:
            result = session.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = DATABASE() AND table_name = :name"
                ),
                {"name": table_name},
            )
            return result.scalar() > 0
    except Exception:
        return False


def _unique_table_name(base_name: str) -> str:
    """Generate a unique table name by appending a suffix if needed."""
    name = base_name
    suffix = 1
    while _check_table_exists(name):
        name = f"{base_name}_{suffix}"
        suffix += 1
        if suffix > 999:
            raise ValueError(f"Cannot find unique table name for '{base_name}'")
    return name


def import_to_mysql(
    df: pd.DataFrame,
    table_name: str,
    if_exists: str = "rename",
) -> dict:
    """Import a DataFrame into a MySQL table in the business database.

    Args:
        df: The data to import.
        table_name: Desired table name (will be sanitized).
        if_exists: 'rename' (default) to auto-rename, 'replace' to drop and recreate.

    Returns:
        dict with table_name, columns, row_count, column_types.
    """
    table_name = _sanitize_table_name(table_name)

    if if_exists == "rename":
        table_name = _unique_table_name(table_name)
    elif if_exists == "replace" and _check_table_exists(table_name):
        with get_workspace_session() as session:
            session.execute(text(f"DROP TABLE IF EXISTS `{table_name}`"))
            session.commit()

    # Build column definitions
    columns_info = []
    col_defs = []
    for col in df.columns:
        mysql_type = _pandas_dtype_to_mysql(df[col].dtype, df[col].head(100))
        col_defs.append(f"`{col}` {mysql_type}")
        columns_info.append({
            "name": col,
            "type": mysql_type,
        })

    # Create table
    create_sql = (
        f"CREATE TABLE `{table_name}` (\n"
        f"  `id` BIGINT AUTO_INCREMENT PRIMARY KEY,\n"
        f"  {','.join(col_defs)}\n"
        f") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
    )

    logger.info(f"Creating table: {table_name} ({len(df.columns)} columns)")

    with get_workspace_session() as session:
        session.execute(text(create_sql))
        session.commit()

    # Insert data in batches
    placeholders = ", ".join([f":{col}" for col in df.columns])
    col_names = ", ".join([f"`{col}`" for col in df.columns])
    insert_sql = f"INSERT INTO `{table_name}` ({col_names}) VALUES ({placeholders})"

    total_inserted = 0
    for start in range(0, len(df), BATCH_SIZE):
        batch = df.iloc[start : start + BATCH_SIZE]
        rows = []
        for _, row in batch.iterrows():
            row_dict = {}
            for col in df.columns:
                val = row[col]
                # Convert pandas NaT / NaN to None for MySQL
                if pd.isna(val):
                    row_dict[col] = None
                elif hasattr(val, "item"):
                    # numpy type → Python native
                    row_dict[col] = val.item()
                else:
                    row_dict[col] = val
            rows.append(row_dict)

        with get_workspace_session() as session:
            session.execute(text(insert_sql), rows)
            session.commit()
            total_inserted += len(rows)

    logger.info(f"Imported {total_inserted} rows into `{table_name}`")

    return {
        "table_name": table_name,
        "original_name": table_name,
        "columns": columns_info,
        "row_count": total_inserted,
        "column_count": len(df.columns),
    }
