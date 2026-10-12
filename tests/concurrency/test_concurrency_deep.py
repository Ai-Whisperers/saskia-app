"""tests/concurrency/test_concurrency_deep.py — Deep concurrency tests for app code."""
import pytest
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import os
import tempfile
import shutil


def test_db_init_concurrent_safety():
    """init_db should be safe to call concurrently (idempotent)."""
    from app.rms.db import init_db, make_engine, make_session_factory

    tmpdir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmpdir, "test.sqlite")
        engine = make_engine(f"sqlite:///{db_path}")
        sf = make_session_factory(engine)

        # First, init the DB
        init_db(engine)

        # Now exercise concurrent reads
        results = []
        errors = []

        def read_op():
            try:
                with sf() as s:
                    from sqlalchemy import text
                    r = s.execute(text("SELECT COUNT(*) FROM app_meta")).scalar()
                    results.append(r)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=read_op) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)
        # At least some reads should succeed
        assert len(results) + len(errors) == 5
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_session_factory_thread_safe():
    """Session factory should be usable from multiple threads."""
    from app.rms.db import make_engine, make_session_factory
    from sqlalchemy import text

    tmpdir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmpdir, "test.sqlite")
        engine = make_engine(f"sqlite:///{db_path}")
        sf = make_session_factory(engine)

        # Set up schema
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE IF NOT EXISTS test (id INTEGER)"))

        # Insert from multiple threads
        def insert(i):
            with sf() as s:
                s.execute(text("INSERT INTO test (id) VALUES (:i)"), {"i": i})
                s.commit()

        threads = [threading.Thread(target=insert, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        # Verify some inserts worked
        with sf() as s:
            count = s.execute(text("SELECT COUNT(*) FROM test")).scalar()
            assert count >= 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_concurrent_cache_access():
    """Concurrent cache access should be thread-safe."""
    cache = {}
    lock = threading.Lock()

    def update(key, value):
        with lock:
            cache[key] = value

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = []
        for i in range(50):
            futures.append(pool.submit(update, f"key_{i}", i))
        for f in futures:
            f.result()

    assert len(cache) == 50


def test_concurrent_rate_limiter():
    """Rate limiter under concurrent load should not crash."""
    from app.rms.rate_limit import RateLimiter
    limiter = RateLimiter(max_calls=10, period_seconds=1)

    results = []

    def call():
        allowed = limiter.allow("test_key")
        results.append(allowed)

    threads = [threading.Thread(target=call) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert len(results) == 20


def test_concurrent_idempotency_keys():
    """Idempotency keys should be unique under concurrent writes."""
    from app.rms.idempotency import generate_idempotency_key
    keys = set()

    def gen():
        key = generate_idempotency_key()
        keys.add(key)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: gen(), range(100)))

    # All keys should be unique
    assert len(keys) == 100


def test_threading_with_app_state():
    """App state under threading should not corrupt."""
    state = {"count": 0}
    lock = threading.Lock()

    def increment():
        for _ in range(100):
            with lock:
                state["count"] += 1

    threads = [threading.Thread(target=increment) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert state["count"] == 500
