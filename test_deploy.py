#!/usr/bin/env python3
"""Test app.py for import and runtime errors."""
import os, sys

# Test that required modules exist
for mod in ['flask', 'jwt', 'cryptography']:
    try:
        __import__(mod)
        print(f'{mod}: OK')
    except ImportError as e:
        print(f'{mod}: MISSING - {e}')

os.chdir(r'C:\Users\Quinn\company-bookmarks')

# Test that logo file exists
logo_path = 'logo_b64.txt'
if os.path.exists(logo_path):
    with open(logo_path) as f:
        data = f.read().strip()
    print(f'logo_b64.txt: OK ({len(data)} chars)')
else:
    print('logo_b64.txt: MISSING')

# Test the % formatting used in LOGIN_PAGE  
test_tmpl = '<img src="data:image/png;base64,%s" alt="Casago">'
try:
    result = test_tmpl % data[:100]
    print(f'%s formatting: OK')
except Exception as e:
    print(f'%s formatting: FAILED - {e}')

# Simulate app import (will hit ENV var errors but shouldn't crash)
os.environ['GOOGLE_CLIENT_ID'] = 'test'  
os.environ['GOOGLE_CLIENT_SECRET'] = 'test'
os.environ['SESSION_SECRET'] = 'test'

print('Trying to import app...')
try:
    import app as _  # noqa: F401
    print('app.py imported successfully')
except Exception as e:
    print(f'app.py import FAILED: {e}')
    import traceback
    traceback.print_exc()