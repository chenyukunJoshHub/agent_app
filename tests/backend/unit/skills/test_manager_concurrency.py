"""
Tests for SkillManager concurrency safety.

This test module validates that SkillManager is thread-safe when
build_snapshot() is called concurrently from multiple coroutines.

TDD Workflow: RED → GREEN → REFACTOR
"""
import asyncio
import tempfile
from pathlib import Path

import pytest

from app.skills.manager import SkillManager
from app.skills.models import SkillSnapshot


class TestSkillManagerConcurrency:
    """Test SkillManager concurrent access safety."""

    @pytest.fixture
    def temp_skills_dir(self):
        """Create a temporary skills directory with sample skills."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir) / "skills"
            skills_dir.mkdir(parents=True, exist_ok=True)

            # Create multiple skills
            for i in range(5):
                skill_dir = skills_dir / f"skill-{i}"
                skill_dir.mkdir()
                (skill_dir / "SKILL.md").write_text(
                    f"""---
name: skill-{i}
description: Test skill {i}
version: 1.0.0
status: active
tools: []
---
# Skill {i}
""",
                    encoding="utf-8",
                )

            yield skills_dir

    @pytest.mark.asyncio
    async def test_concurrent_build_snapshot_increments_version_sequentially(
        self, temp_skills_dir
    ):
        """验证并发调用 build_snapshot() 时版本号顺序递增（无重复）."""
        manager = SkillManager(skills_dir=str(temp_skills_dir))

        # Track versions from all concurrent calls
        versions = []

        async def build_and_track():
            """Build snapshot and track version."""
            snapshot = manager.build_snapshot()
            versions.append(snapshot.version)
            # Simulate some processing time
            await asyncio.sleep(0.001)
            return snapshot

        # Run 100 concurrent builds
        tasks = [build_and_track() for _ in range(100)]
        await asyncio.gather(*tasks)

        # Assert all versions are unique
        assert len(versions) == 100, f"Expected 100 versions, got {len(versions)}"
        assert len(set(versions)) == 100, f"Version collision detected: {versions}"

        # Assert versions are sequential
        assert versions == sorted(versions), f"Versions not sequential: {versions}"

        # Assert final version is 100
        assert max(versions) == 100, f"Expected final version 100, got {max(versions)}"

    @pytest.mark.asyncio
    async def test_concurrent_build_snapshot_returns_valid_snapshots(
        self, temp_skills_dir
    ):
        """验证并发调用 build_snapshot() 返回有效的 SkillSnapshot 对象."""
        manager = SkillManager(skills_dir=str(temp_skills_dir))

        async def build_and_validate():
            """Build snapshot and validate it."""
            snapshot = manager.build_snapshot()
            assert isinstance(snapshot, SkillSnapshot)
            assert len(snapshot.skills) == 5
            assert snapshot.version > 0
            assert snapshot.prompt
            return snapshot

        # Run 50 concurrent builds
        tasks = [build_and_validate() for _ in range(50)]
        snapshots = await asyncio.gather(*tasks)

        # All snapshots should be valid
        assert len(snapshots) == 50
        for snap in snapshots:
            assert isinstance(snap, SkillSnapshot)

    @pytest.mark.asyncio
    async def test_concurrent_build_with_different_filters(
        self, temp_skills_dir
    ):
        """验证并发调用 build_snapshot() 时不同过滤器不会冲突."""
        manager = SkillManager(skills_dir=str(temp_skills_dir))

        async def build_with_filter(filter_list):
            """Build snapshot with specific filter."""
            await asyncio.sleep(0.001)  # Add randomness
            return manager.build_snapshot(skill_filter=filter_list)

        # Run concurrent builds with different filters
        tasks = [
            build_with_filter(["skill-0", "skill-1"]),
            build_with_filter(["skill-2", "skill-3"]),
            build_with_filter(["skill-4"]),
            build_with_filter(None),  # No filter
        ]

        snapshots = await asyncio.gather(*tasks)

        # Validate each snapshot
        assert len(snapshots[0].skills) == 2
        assert len(snapshots[1].skills) == 2
        assert len(snapshots[2].skills) == 1
        assert len(snapshots[3].skills) == 5  # No filter = all skills

        # Versions should still be sequential
        versions = [s.version for s in snapshots]
        assert versions == sorted(versions), f"Versions not sequential: {versions}"

    @pytest.mark.asyncio
    async def test_concurrent_scan_and_build(self, temp_skills_dir):
        """验证 scan() 和 build_snapshot() 并发调用不冲突."""
        manager = SkillManager(skills_dir=str(temp_skills_dir))

        async def scan():
            """Scan skills directory."""
            await asyncio.sleep(0.001)
            return manager.scan()

        async def build():
            """Build snapshot."""
            await asyncio.sleep(0.001)
            return manager.build_snapshot()

        # Run mixed concurrent operations
        tasks = []
        for _ in range(10):
            tasks.append(scan())
            tasks.append(build())

        results = await asyncio.gather(*tasks)

        # All operations should complete successfully
        assert len(results) == 20

        # Scan results should be lists
        scan_results = [r for r in results if isinstance(r, list)]
        for scan_result in scan_results:
            assert isinstance(scan_result, list)
            assert len(scan_result) == 5

        # Build results should be SkillSnapshot
        build_results = [r for r in results if isinstance(r, SkillSnapshot)]
        for build_result in build_results:
            assert isinstance(build_result, SkillSnapshot)

    @pytest.mark.asyncio
    async def test_race_condition_on_version_increment(self, temp_skills_dir):
        """
        测试竞态条件：多个协程同时调用 build_snapshot()。

        这是一个关键的测试，如果没有锁保护，版本号会出现重复。
        """
        manager = SkillManager(skills_dir=str(temp_skills_dir))

        # Reset version to 0 for consistent testing
        manager._version = 0

        async def build_and_get_version():
            """调用 build_snapshot() 并返回版本号."""
            await asyncio.sleep(0.0001)  # 增加竞态条件发生的概率
            snapshot = manager.build_snapshot()
            return snapshot.version

        # Run 20 concurrent builds
        tasks = [build_and_get_version() for _ in range(20)]
        results = await asyncio.gather(*tasks)

        # With lock: results will be sequential (e.g., [1, 2, 3, 4, 5, ...])
        # Without lock: results will have duplicates (e.g., [1, 1, 1, 2, 2, 3, ...])
        assert len(set(results)) == len(results), (
            f"Race condition detected! Version collision: {results}. "
            f"Expected 20 unique values, got {len(set(results))}. "
            f"This indicates build_snapshot() is not thread-safe."
        )

        # Final version should be 20
        assert manager._version == 20, (
            f"Expected final version 20, got {manager._version}. "
            f"Lost updates due to race condition."
        )
