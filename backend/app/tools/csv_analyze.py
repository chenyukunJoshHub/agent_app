"""CSV analysis tool for Agent system.

Provides basic statistical analysis of CSV files.
"""
from pathlib import Path
from typing import Any

import pandas as pd
from langchain_core.tools import tool
from loguru import logger

# Maximum file size for CSV analysis (1MB)
MAX_CSV_BYTES = 1_000_000


@tool
def csv_analyze(file_path: str) -> str:
    """
    分析 CSV 文件的基本统计信息。

    适用场景：
    - 快速了解 CSV 文件的结构和内容
    - 查看列名、行数、数据类型
    - 获取数值列的基本统计信息（均值、最小值、最大值等）
    - 数据探索和初步分析

    不适用场景：
    - 超大型 CSV 文件（超过 1MB）
    - 需要复杂数据转换或清洗
    - 需要可视化或图表展示
    - 非 CSV 格式的文件

    Args:
        file_path: CSV 文件路径（支持相对路径、绝对路径、~ 展开）

    Returns:
        str: JSON 字符串格式的分析结果，包含：
            - row_count: 行数
            - column_count: 列数
            - columns: 列名列表
            - column_types: 每列的数据类型
            - numeric_stats: 数值列的统计信息（均值、最小值、最大值、标准差等）
            - memory_usage: 内存使用情况

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 文件大小超过限制（1MB）或文件格式错误
        pd.errors.EmptyDataError: CSV 文件为空
        pd.errors.ParserError: CSV 解析错误
    """
    # Resolve and validate file path
    input_path = Path(file_path).expanduser().resolve()

    # Check file exists
    if not input_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    # Check file size
    file_size = input_path.stat().st_size
    if file_size > MAX_CSV_BYTES:
        raise ValueError(
            f"CSV file too large: {file_size} > {MAX_CSV_BYTES} bytes. "
            f"Please use a smaller sample or split the file."
        )

    logger.info(f"Analyzing CSV file: {input_path} ({file_size} bytes)")

    try:
        # Read CSV file
        df = pd.read_csv(input_path)

        # Basic info
        row_count = len(df)
        column_count = len(df.columns)
        columns = df.columns.tolist()

        # Column types
        column_types = df.dtypes.astype(str).to_dict()

        # Numeric statistics
        numeric_stats = {}
        numeric_columns = df.select_dtypes(include=['number']).columns

        for col in numeric_columns:
            col_stats = df[col].describe()
            numeric_stats[col] = {
                "count": int(col_stats["count"]),
                "mean": float(col_stats["mean"]) if not pd.isna(col_stats["mean"]) else None,
                "std": float(col_stats["std"]) if not pd.isna(col_stats["std"]) else None,
                "min": float(col_stats["min"]) if not pd.isna(col_stats["min"]) else None,
                "25%": float(col_stats["25%"]) if not pd.isna(col_stats["25%"]) else None,
                "50%": float(col_stats["50%"]) if not pd.isna(col_stats["50%"]) else None,
                "75%": float(col_stats["75%"]) if not pd.isna(col_stats["75%"]) else None,
                "max": float(col_stats["max"]) if not pd.isna(col_stats["max"]) else None,
            }

        # Memory usage
        memory_usage_bytes = df.memory_usage(deep=True).sum()
        memory_usage_mb = memory_usage_bytes / (1024 * 1024)

        # Build result
        result = {
            "file_path": str(input_path),
            "file_size_bytes": file_size,
            "row_count": row_count,
            "column_count": column_count,
            "columns": columns,
            "column_types": column_types,
            "numeric_stats": numeric_stats,
            "memory_usage_mb": round(memory_usage_mb, 2),
        }

        logger.info(
            f"CSV analysis complete: {row_count} rows, {column_count} columns, "
            f"{len(numeric_stats)} numeric columns"
        )

        # Return as JSON string
        import json

        return json.dumps(result, ensure_ascii=False, indent=2)

    except pd.errors.EmptyDataError:
        logger.error(f"CSV file is empty: {input_path}")
        raise ValueError(f"CSV file is empty: {file_path}")

    except pd.errors.ParserError as e:
        logger.error(f"CSV parsing error: {input_path} - {e}")
        raise ValueError(f"Failed to parse CSV file: {e}")

    except Exception as e:
        logger.error(f"Error analyzing CSV {input_path}: {e}")
        raise


__all__ = ["csv_analyze"]
