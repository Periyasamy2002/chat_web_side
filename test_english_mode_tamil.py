#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test: English Mode with Tamil Input
Verify Tamil input handling in English mode
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatproject.settings')
django.setup()

from chatapp.views import process_english_mode_message

print("\n" + "="*80)
print("TEST: English Mode - Tamil Input Processing")
print("="*80)

# Test sending Tamil in English mode
test_tamil = "வணக்கம்"  # Hello in Tamil

print(f"\nTest Case: Sending Tamil '{test_tamil}' in English mode")
print("-" * 80)

try:
    english_version, tamil_version, validation_msg, should_warn = process_english_mode_message(test_tamil)
    
    print(f"✅ Processing succeeded!")
    print(f"  English Version (display): '{english_version}'")
    print(f"  Tamil Version (storage): '{tamil_version}'")
    print(f"  Message: {validation_msg}")
    print(f"  Should warn: {should_warn}")
    
    # Check results
    if not english_version:
        print("\n❌ ERROR: English version is empty!")
    else:
        print("\n✅ English version has content")
        
except Exception as e:
    print(f"❌ Processing failed with error: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
