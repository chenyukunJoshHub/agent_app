"""Unit tests for app.tools.csv_analyze.

These tests verify the csv_analyze tool functionality.
"""
import json
import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest


class TestCsvAnalyzeTool:
    """Test csv_analyze tool."""

    def test_tool_has_correct_metadata(self) -> None:
        """Test that tool has proper metadata."""
        from app.tools.csv_analyze import csv_analyze

        assert csv_analyze.name == "csv_analyze"
        assert csv_analyze.description is not None
        assert "CSV" in csv_analyze.description or "csv" in csv_analyze.description.lower()
        # Should include usage guidance
        assert "适用" in csv_analyze.description or "不适用" in csv_analyze.description

    def test_tool_args_schema(self) -> None:
        """Test that tool has correct args schema."""
        from app.tools.csv_analyze import csv_analyze

        schema = csv_analyze.args_schema
        assert schema is not None
        # Should have 'file_path' argument
        assert "file_path" in schema.model_fields

    def test_csv_analyze_basic_csv(self) -> None:
        """Test csv_analyze with a basic CSV file."""
        from app.tools.csv_analyze import csv_analyze

        # Create a temporary CSV file
        csv_content = """name,age,city
Alice,30,New York
Bob,25,Los Angeles
Charlie,35,Chicago
"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", encoding="utf-8") as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            result = csv_analyze.invoke({"file_path": temp_path})
            data = json.loads(result)

            # Verify basic structure
            assert data["row_count"] == 3
            assert data["column_count"] == 3
            assert "name" in data["columns"]
            assert "age" in data["columns"]
            assert "city" in data["columns"]
            assert "age" in data["numeric_stats"]

            # Verify numeric stats for age column
            age_stats = data["numeric_stats"]["age"]
            assert age_stats["count"] == 3
            assert age_stats["mean"] == 30.0
            assert age_stats["min"] == 25.0
            assert age_stats["max"] == 35.0

        finally:
            os.unlink(temp_path)

    def test_csv_analyze_with_numeric_columns(self) -> None:
        """Test csv_analyze with multiple numeric columns."""
        from app.tools.csv_analyze import csv_analyze

        # Create CSV with multiple numeric columns
        csv_content = """product,price,quantity,sales
A,10.5,100,1050.0
B,20.3,200,4060.0
C,15.7,150,2355.0
"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", encoding="utf-8") as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            result = csv_analyze.invoke({"file_path": temp_path})
            data = json.loads(result)

            # Verify all numeric columns have stats
            assert "price" in data["numeric_stats"]
            assert "quantity" in data["numeric_stats"]
            assert "sales" in data["numeric_stats"]

            # Verify price stats
            price_stats = data["numeric_stats"]["price"]
            assert price_stats["count"] == 3
            assert price_stats["min"] == 10.5
            assert price_stats["max"] == 20.3

        finally:
            os.unlink(temp_path)

    def test_csv_analyze_file_not_found(self) -> None:
        """Test csv_analyze raises FileNotFoundError for non-existent file."""
        from app.tools.csv_analyze import csv_analyze

        with pytest.raises(FileNotFoundError) as exc_info:
            csv_analyze.invoke({"file_path": "nonexistent.csv"})

        assert "not found" in str(exc_info.value).lower()

    def test_csv_analyze_file_too_large(self) -> None:
        """Test csv_analyze raises ValueError for files larger than 1 MB."""
        from app.tools.csv_analyze import csv_analyze, MAX_CSV_BYTES

        # Create a file larger than 1MB
        with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=".csv") as f:
            large_content = b"x" * (MAX_CSV_BYTES + 100_000)
            f.write(large_content)
            temp_path = f.name

        try:
            with pytest.raises(ValueError) as exc_info:
                csv_analyze.invoke({"file_path": temp_path})

            assert "too large" in str(exc_info.value).lower()
            assert str(MAX_CSV_BYTES) in str(exc_info.value)

        finally:
            os.unlink(temp_path)

    def test_csv_analyze_empty_file(self) -> None:
        """Test csv_analyze handles empty CSV files."""
        from app.tools.csv_analyze import csv_analyze

        # Create empty CSV file
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", encoding="utf-8") as f:
            f.write("")
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="empty"):
                csv_analyze.invoke({"file_path": temp_path})

        finally:
            os.unlink(temp_path)

    def test_csv_analyze_with_tilde_path(self) -> None:
        """Test csv_analyze expands tilde in file path."""
        from app.tools.csv_analyze import csv_analyze

        # Create a temp file in home directory
        csv_content = """value
1
2
3
"""
        home = Path.home()
        temp_dir = home / ".tmp_test_csv"
        temp_dir.mkdir(exist_ok=True)
        temp_path = temp_dir / "test.csv"

        try:
            # Write CSV file
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(csv_content)

            # Use tilde path
            result = csv_analyze.invoke({"file_path": "~/.tmp_test_csv/test.csv"})
            data = json.loads(result)

            assert data["row_count"] == 3

        finally:
            # Cleanup
            if temp_path.exists():
                temp_path.unlink()
            if temp_dir.exists():
                temp_dir.rmdir()

    def test_csv_analyze_non_csv_file(self) -> None:
        """Test csv_analyze handles non-CSV files."""
        from app.tools.csv_analyze import csv_analyze

        # Create a non-CSV file with unclosed quotes (will cause pandas error)
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
            # Write CSV with unclosed quote
            f.write('name,value\nAlice,"unclosed\nBob,20')
            temp_path = f.name

        try:
            with pytest.raises(ValueError):
                csv_analyze.invoke({"file_path": temp_path})

        finally:
            os.unlink(temp_path)

    def test_csv_analyze_mixed_data_types(self) -> None:
        """Test csv_analyze handles mixed data types."""
        from app.tools.csv_analyze import csv_analyze

        # Create CSV with mixed types
        csv_content = """id,name,score,active,notes
1,Alice,95.5,true,Good
2,Bob,87.3,false,Excellent
3,Charlie,92.1,true,
"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", encoding="utf-8") as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            result = csv_analyze.invoke({"file_path": temp_path})
            data = json.loads(result)

            # Verify structure
            assert data["row_count"] == 3
            assert data["column_count"] == 5

            # Verify only numeric columns have stats
            assert "score" in data["numeric_stats"]
            assert "name" not in data["numeric_stats"]
            assert "active" not in data["numeric_stats"]

        finally:
            os.unlink(temp_path)

    def test_csv_analyze_memory_usage(self) -> None:
        """Test csv_analyze reports memory usage."""
        from app.tools.csv_analyze import csv_analyze

        csv_content = """col1,col2
1,2
3,4
5,6
"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", encoding="utf-8") as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            result = csv_analyze.invoke({"file_path": temp_path})
            data = json.loads(result)

            # Verify memory usage is reported
            assert "memory_usage_mb" in data
            assert isinstance(data["memory_usage_mb"], (int, float))
            assert data["memory_usage_mb"] >= 0

        finally:
            os.unlink(temp_path)


class TestCsvAnalyzeEdgeCases:
    """Test csv_analyze tool edge cases."""

    def test_csv_analyze_description_clarity(self) -> None:
        """Test that tool description is clear and helpful."""
        from app.tools.csv_analyze import csv_analyze

        desc = csv_analyze.description.lower()
        # Should mention what it's for
        assert any(keyword in desc for keyword in ["csv", "分析", "统计"])
        # Should mention limitations
        assert "不适用" in desc or "限制" in desc or "1mb" in desc or "大型" in desc

    def test_csv_analyze_returns_json_string(self) -> None:
        """Test that csv_analyze always returns a valid JSON string."""
        from app.tools.csv_analyze import csv_analyze

        csv_content = """a,b
1,2
"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".csv", encoding="utf-8") as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            result = csv_analyze.invoke({"file_path": temp_path})
            assert isinstance(result, str)

            # Should be valid JSON
            data = json.loads(result)
            assert isinstance(data, dict)

        finally:
            os.unlink(temp_path)

    def test_max_csv_bytes_constant(self) -> None:
        """Test that MAX_CSV_BYTES is defined correctly."""
        from app.tools.csv_analyze import MAX_CSV_BYTES

        # Should be 1MB
        assert MAX_CSV_BYTES == 1_000_000
