#!/usr/bin/env python3
"""
Simple ORKG API Test - Run this to diagnose connection issues

Usage: py test_orkg_api.py
"""

import json
import urllib.request
import urllib.error
import ssl

print("=" * 60)
print("ORKG API Connection Test (Fixed with Versioned Media Types)")
print("=" * 60)

# Test 1: Papers endpoint with versioned media type
print("\nTest 1: Papers endpoint (with versioned media type)")
url = "https://orkg.org/api/papers?size=3"
print(f"  URL: {url}")

try:
    request = urllib.request.Request(url)
    # ORKG papers endpoint requires versioned media type!
    request.add_header("Content-Type", "application/vnd.orkg.paper.v2+json;charset=UTF-8")
    request.add_header("Accept", "application/vnd.orkg.paper.v2+json")
    request.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
    
    context = ssl.create_default_context()
    
    with urllib.request.urlopen(request, timeout=30, context=context) as response:
        data = json.loads(response.read().decode('utf-8'))
        print(f"  ✓ SUCCESS! Status: {response.status}")
        print(f"  Keys: {list(data.keys())}")
        if 'content' in data:
            print(f"  Items: {len(data['content'])}")
            if data['content']:
                paper = data['content'][0]
                print(f"  First paper ID: {paper.get('id')}")
                print(f"  First paper title: {paper.get('title', 'N/A')[:60]}...")
                print(f"  Contributions: {len(paper.get('contributions', []))}")
        if 'page' in data:
            print(f"  Total papers: {data['page'].get('total_elements', 'N/A')}")
            
except urllib.error.HTTPError as e:
    print(f"  ✗ HTTP Error {e.code}: {e.reason}")
    try:
        error = e.read().decode('utf-8')
        print(f"  Error body: {error[:300]}")
    except:
        pass
except Exception as e:
    print(f"  ✗ Error: {e}")

# Test 2: Statements endpoint (standard headers work)
print("\nTest 2: Statements endpoint (standard headers)")
url = "https://orkg.org/api/statements?size=3"
print(f"  URL: {url}")

try:
    request = urllib.request.Request(url)
    request.add_header("Accept", "application/json")
    request.add_header("User-Agent", "Mozilla/5.0")
    
    context = ssl.create_default_context()
    
    with urllib.request.urlopen(request, timeout=30, context=context) as response:
        data = json.loads(response.read().decode('utf-8'))
        print(f"  ✓ SUCCESS! Status: {response.status}")
        print(f"  Total statements: {data['page'].get('total_elements', 'N/A')}")
            
except Exception as e:
    print(f"  ✗ Error: {e}")

print("\n" + "=" * 60)
print("Test complete!")
print("=" * 60)
