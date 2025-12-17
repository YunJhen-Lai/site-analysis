#!/usr/bin/env python3
"""
Quick test script to diagnose TDX connection issues.
"""
import os
import sys
from pathlib import Path

# Add TDX module to path
sys.path.insert(0, str(Path(__file__).parent / 'data' / 'TDX'))

print("=" * 60)
print("TDX Connection Diagnostic")
print("=" * 60)

# Check environment variables
print("\n1. Checking environment variables...")
app_id = os.getenv('TDX_APP_ID')
app_key = os.getenv('TDX_APP_KEY')

if app_id:
    print(f"   ✓ TDX_APP_ID is set (first 10 chars: {app_id[:10]}...)")
else:
    print("   ✗ TDX_APP_ID not set")

if app_key:
    print(f"   ✓ TDX_APP_KEY is set (first 10 chars: {app_key[:10]}...)")
else:
    print("   ✗ TDX_APP_KEY not set")

# Try importing modules
print("\n2. Checking module imports...")
try:
    import requests
    print("   ✓ requests module loaded")
except Exception as e:
    print(f"   ✗ requests import failed: {e}")
    sys.exit(1)

try:
    import pandas
    print("   ✓ pandas module loaded")
except Exception as e:
    print(f"   ✗ pandas import failed: {e}")

try:
    from auth_TDX import TDXAuth
    print("   ✓ auth_TDX.TDXAuth loaded")
except Exception as e:
    print(f"   ✗ auth_TDX import failed: {e}")
    sys.exit(1)

# Try authentication
if app_id and app_key:
    print("\n3. Testing TDX authentication...")
    try:
        auth = TDXAuth(app_id, app_key)
        print("   ○ Sending authentication request...")
        auth.authenticate()
        print("   ✓ Authentication successful!")
        headers = auth.get_data_header()
        print(f"   ✓ Got data headers (token starts with: {headers['authorization'][:20]}...)")
    except Exception as e:
        print(f"   ✗ Authentication failed: {e}")
        print(f"   Error type: {type(e).__name__}")
        sys.exit(1)

    # Try fetching travel time data
    print("\n4. Testing data fetch...")
    try:
        url = "https://tdx.transportdata.tw/api/basic/v2/Bus/S2STravelTime/City/Taichung"
        print(f"   ○ Fetching from: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        print(f"   ✓ HTTP {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                print(f"   ✓ Got {len(data)} records")
            else:
                print(f"   ✓ Got data (type: {type(data).__name__})")
        else:
            print(f"   ✗ HTTP error: {response.text[:200]}")
    except Exception as e:
        print(f"   ✗ Data fetch failed: {e}")
        sys.exit(1)

else:
    print("\n3. Skipping authentication test (credentials not set)")
    print("   Set environment variables to test:")
    print("     export TDX_APP_ID='your_id'")
    print("     export TDX_APP_KEY='your_key'")

print("\n" + "=" * 60)
print("Diagnostic complete!")
print("=" * 60)
