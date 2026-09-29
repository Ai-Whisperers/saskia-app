import sys
sys.path.insert(0, '/app')
from starlette.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from app.rms.main import app, StaticCacheMiddleware

# Force middleware stack to build
_ = app.url_path_for('static', path='test')

# Walk the chain from outermost to innermost
def walk(m, depth=0):
    prefix = "  " * depth
    name = m.__class__.__name__
    if hasattr(m, 'app'):
        print(f"{prefix}{name} ->")
        walk(m.app, depth+1)
    else:
        print(f"{prefix}{name} (endpoint)")

print("Middleware chain from app.user_middleware[0]:")
walk(app.user_middleware[0])
print()
print("user_middleware[0].app type:", type(app.user_middleware[0].app).__name__)
print("user_middleware[0].app.app type:", type(app.user_middleware[0].app.app).__name__)
print()

# Check if SCM is actually a BaseHTTPMiddleware wrapping SCM
for idx, m in enumerate(app.user_middleware):
    inner = m
    chain = [m.__class__.__name__]
    while hasattr(inner, 'app'):
        inner = inner.app
        chain.append(inner.__class__.__name__)
    if 'StaticCacheMiddleware' in chain:
        print(f"user_middleware[{idx}] contains StaticCacheMiddleware: {' -> '.join(chain)}")
        break
