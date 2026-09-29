#!/usr/bin/env python3

"""Debug script for bank endpoint."""

import os
import sys
sys.path.insert(0, '.')

# Set auth disabled
os.environ['SASKIA_TEST_AUTH_DISABLED'] = '1'

from fastapi.testclient import TestClient
from app.rms.main import app

with TestClient(app) as client:
    print("Testing bank endpoint...")
    r = client.get('/bank')
    print(f"Status: {r.status_code}")
    print(f"Content-Type: {r.headers.get('content-type', 'missing')}")
    if r.status_code == 200:
        print(f"First 200 chars: {r.text[:200]}")
    else:
        print(f"Error: {r.text[:500]}")
    
    print("\nTesting CSV export...")
    r = client.get('/bank/export.csv')
    print(f"Status: {r.status_code}")
    print(f"Content-Type: {r.headers.get('content-type', 'missing')}")
    if r.status_code == 200:
        print(f"First 200 chars: {r.text[:200]}")
    else:
        print(f"Error: {r.text[:500]}")