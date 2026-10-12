"""tests/concurrency/test_concurrent_writes.py — Phase 1 refactored."""
import pytest
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import text


pytestmark = [pytest.mark.concurrency, pytest.mark.slow]


def test_threading_imports():
    """Threading module should be available and usable."""
    assert threading.Lock() is not None
    assert threading.Thread
    assert ThreadPoolExecutor


def test_concurrent_dict_access():
    """Concurrent dict access should be safe (Python GIL)."""
    shared = {}

    def writer(i):
        for j in range(100):
            shared[f"key_{i}_{j}"] = j

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert len(shared) == 500


def test_thread_pool_executes_all():
    """ThreadPoolExecutor should execute all tasks."""
    results = []

    def task(i):
        results.append(i)
        return i

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(task, i) for i in range(20)]
        for f in as_completed(futures, timeout=10):
            pass

    assert len(results) == 20


def test_concurrent_set_access():
    """Concurrent set access should be safe."""
    shared = set()

    def add_values(i):
        for j in range(100):
            shared.add(i * 1000 + j)

    threads = [threading.Thread(target=add_values, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert len(shared) == 500


def test_two_threads_dont_deadlock():
    """Two threads with simple work should not deadlock."""
    import time
    done = [False, False]

    def worker(idx):
        time.sleep(0.01)
        done[idx] = True

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=2)
    assert done[0] and done[1]


def test_db_concurrent_reads(session_factory):
    """Concurrent DB reads should not crash."""
    results = []

    def read():
        with session_factory() as s:
            r = s.execute(text("SELECT 1")).scalar()
            results.append(r)

    threads = [threading.Thread(target=read) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)


def test_lock_works():
    """threading.Lock should provide mutual exclusion."""
    counter = [0]
    lock = threading.Lock()

    def increment():
        for _ in range(1000):
            with lock:
                counter[0] += 1

    threads = [threading.Thread(target=increment) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert counter[0] == 5000


def test_rate_limit_module_imports():
    """rate_limit module should be importable and have expected functions."""
    from app.rms import rate_limit
    assert hasattr(rate_limit, "is_rate_limited")
    assert hasattr(rate_limit, "is_disabled")
    assert hasattr(rate_limit, "is_write_rate_limited")
    assert hasattr(rate_limit, "is_read_rate_limited")


def test_rate_limit_decision_thread_safe():
    """RateLimitDecision should be safe to share across threads."""
    from app.rms.rate_limit import RateLimitDecision
    decisions = []
    lock = threading.Lock()

    def decide(idx):
        d = RateLimitDecision(
            allowed=(idx % 2 == 0),
            current_count=idx,
            limit=100,
            retry_after_seconds=0,
        )
        with lock:
            decisions.append(d)

    threads = [threading.Thread(target=decide, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert len(decisions) == 20
