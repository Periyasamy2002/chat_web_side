#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test: COMPLETE BILINGUAL FLOW - Both modes verified
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatproject.settings')
django.setup()

from chatapp.views import process_english_mode_message, process_tamil_mode_message

print("\n" + "="*100)
print("COMPLETE BILINGUAL TEST - English Mode + Tamil Mode")
print("="*100)

test_cases = [
    # (description, content, mode, expected_display_is_english)
    ("English mode: User sends Tamil", "வணக்கம்", "english", True),
    ("English mode: User sends English", "Hello", "english", True),
    ("Tamil mode: User sends English", "Hello", "tamil", False),  # False = expect Tamil
    ("Tamil mode: User sends Tamil", "வணக்கம்", "tamil", False),  # False = expect Tamil
]

print("\nTest Scenarios:")
print("-" * 100)

results = []

for desc, content, mode, expect_english in test_cases:
    print(f"\n📝 {desc}")
    print(f"  Input: '{content}' | Mode: {mode}")
    
    try:
        if mode == "english":
            english_version, tamil_version, msg, warn = process_english_mode_message(content)
            display = english_version
            lang_type = "ENGLISH"
        else:
            english_version, tamil_version, msg, warn = process_tamil_mode_message(content)
            display = tamil_version
            lang_type = "TAMIL"
        
        has_tamil = any(0xB80 <= ord(c) <= 0xBFF for c in display)
        
        # Determine if display is English
        is_display_english = not has_tamil
        
        # Check if it matches expectation
        is_correct = is_display_english == expect_english
        status = "✅ PASS" if is_correct else "❌ FAIL"
        
        print(f"  Display ({lang_type}): '{display}'")
        print(f"  Has Tamil script: {has_tamil}")
        print(f"  {status}")
        
        results.append((desc, is_correct))
        
    except Exception as e:
        print(f"  ❌ ERROR: {str(e)}")
        results.append((desc, False))

print("\n" + "="*100)
print("SUMMARY")
print("="*100)

passed = sum(1 for _, result in results if result)
total = len(results)

for desc, result in results:
    status = "✅" if result else "❌"
    print(f"{status} {desc}")

print(f"\nResult: {passed}/{total} tests passed")

if passed == total:
    print("\n🎉 ALL TESTS PASSED! System is working correctly!")
else:
    print(f"\n⚠️  {total - passed} test(s) failed. Review above.")

print("="*100 + "\n")
