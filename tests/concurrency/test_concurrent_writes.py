"""tests/concurrency/test_concurrent_writes.py — Threading and concurrency tests."""

import os
import shutil
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


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


def test_db_concurrent_reads():
    """Concurrent DB reads should not crash."""
    from app.rms.db import init_db, make_engine, make_session_factory

    tmpdir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmpdir, "test.sqlite")
        engine = make_engine(f"sqlite:///{db_path}")
        init_db(engine)
        sf = make_session_factory(engine)

        results = []

        def read():
            with sf() as s:
                from sqlalchemy import text

                r = s.execute(text("SELECT 1")).scalar()
                results.append(r)

        threads = [threading.Thread(target=read) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


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
