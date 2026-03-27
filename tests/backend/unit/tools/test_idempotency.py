"""
Unit tests for app.tools.idempotency — IdempotencyStore.
"""

import threading

import pytest

from app.tools.idempotency import IdempotencyStore


class TestIdempotencyStore:
    def test_first_call_returns_false(self) -> None:
        store = IdempotencyStore()
        assert store.check_and_mark("key_a") is False



class TestIdempotencyStoreThreading:
    def test_concurrent_calls_no_race_condition(self) -> None:
        """Test that concurrent calls are thread-safe."""
        store = IdempotencyStore()
        results = []
        n_threads = 10

        def worker(key: str) -> None:
            results.append(store.check_and_mark(key))

        threads = [threading.Thread(target=worker, args=(f"key_{i}",)) for i in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == n_threads
        assert all(not r for r in results)  # All first calls should be False

    def test_concurrent_calls_same_key(self) -> None:
        """Test that concurrent calls to the same key are consistent."""
        store = IdempotencyStore()
        results = []
        n_threads = 10

        def worker() -> None:
            results.append(store.check_and_mark("same_key"))

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == n_threads
        # At most one should be False (first), rest should be True
        false_count = sum(1 for r in results if not r)
        true_count = sum(1 for r in results if r)
        assert false_count + true_count == n_threads
        assert false_count <= 1


class TestIdempotencyStoreLRU:
    def test_lru_eviction_after_max_size(self) -> None:
        """Test that LRU eviction works when max_size is exceeded."""
        store = IdempotencyStore(max_size=3)

        # Add 3 keys (at limit)
        store.check_and_mark("key_1")
        store.check_and_mark("key_2")
        store.check_and_mark("key_3")

        # Add 4th key — evicts key_1 (LRU)
        assert store.check_and_mark("key_4") is False

        # key_2, key_3, key_4 should still be marked (check these first to
        # avoid side effects from re-inserting the evicted key)
        assert store.check_and_mark("key_2") is True
        assert store.check_and_mark("key_3") is True
        assert store.check_and_mark("key_4") is True

        # key_1 was evicted, so returns False (checked last to avoid
        # chain-eviction affecting the assertions above)
        assert store.check_and_mark("key_1") is False

    def test_lru_eviction_order(self) -> None:
        """Test that LRU eviction follows least-recently-used order."""
        store = IdempotencyStore(max_size=3)

        store.check_and_mark("key_1")
        store.check_and_mark("key_2")
        store.check_and_mark("key_3")

        # Access key_1 to make it most recently used
        # Store order (LRU→MRU): key_2, key_3, key_1
        store.check_and_mark("key_1")

        # Add key_4 — evicts key_2 (LRU)
        # Store order: key_3, key_1, key_4
        store.check_and_mark("key_4")

        # key_1, key_3, key_4 should still be marked (check these first)
        assert store.check_and_mark("key_1") is True
        assert store.check_and_mark("key_3") is True
        assert store.check_and_mark("key_4") is True

        # key_2 was evicted (checked last to avoid chain-eviction side effects)
        assert store.check_and_mark("key_2") is False


class TestIdempotencyStoreEdgeCases:
    def test_empty_key(self) -> None:
        """Test that empty keys are handled."""
        store = IdempotencyStore()
        assert store.check_and_mark("") is False
        assert store.check_and_mark("") is True

    def test_unicode_key(self) -> None:
        """Test that unicode keys work correctly."""
        store = IdempotencyStore()
        unicode_key = "你好世界🎉"
        assert store.check_and_mark(unicode_key) is False
        assert store.check_and_mark(unicode_key) is True

    def test_large_key(self) -> None:
        """Test that large keys are handled."""
        store = IdempotencyStore()
        large_key = "x" * 1000
        assert store.check_and_mark(large_key) is False
        assert store.check_and_mark(large_key) is True


    def test_second_call_returns_true(self) -> None:
        store = IdempotencyStore()
        store.check_and_mark("key_a")
        assert store.check_and_mark("key_a") is True

    def test_different_keys_independent(self) -> None:
        store = IdempotencyStore()
        assert store.check_and_mark("key_a") is False
        assert store.check_and_mark("key_b") is False

    def test_clear_resets_store(self) -> None:
        store = IdempotencyStore()
        store.check_and_mark("key_a")
        store.clear()
        assert store.check_and_mark("key_a") is False

    def test_multiple_clears_safe(self) -> None:
        store = IdempotencyStore()
        store.clear()
        store.clear()
        assert store.check_and_mark("key_a") is False

    def test_discard_removes_marked_key(self) -> None:
        store = IdempotencyStore()
        assert store.check_and_mark("rollback_key") is False
        store.discard("rollback_key")
        assert store.check_and_mark("rollback_key") is False

    def test_discard_missing_key_is_noop(self) -> None:
        store = IdempotencyStore()
        store.discard("missing_key")
        assert store.check_and_mark("missing_key") is False
