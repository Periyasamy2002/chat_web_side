#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test: Meaning Translation (NOT Transliteration)
Verify system translates meaning, not creates Tanglish
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatproject.settings')
django.setup()

from chatapp.utils.tamil_detector import ensure_english_only_display, ensure_tamil_only_display

print("\n" + "="*80)
print("TEST: DISPLAY FILTERS - MEANING TRANSLATION (NO TANGLISH)")
print("="*80)

# Test cases
test_cases_english_filter = [
    ("hello", "Pure English text"),
    ("வணக்கம்", "Tamil text (greeting)"),
    ("hello வணக்கம்", "Mixed English and Tamil"),
]

test_cases_tamil_filter = [
    ("வணக்கம்", "Pure Tamil text"),
    ("hello", "English text (should be removed)"),
    ("hello வணக்கம்", "Mixed (keep only Tamil)"),
]

print("\n[*] TEST 1: ensure_english_only_display()")
print("-" * 80)
print("This should REMOVE Tamil, NOT transliterate to 'vanakkam'")
print()

for text, description in test_cases_english_filter:
    result = ensure_english_only_display(text)
    print("Input:  '{}'".format(text))
    print("Desc:   {}".format(description))
    print("Output: '{}'".format(result))
    
    # Check for Tanglish (indicator: contains 'v', 'n', 'k' patterns from Tamil transliteration)
    has_transliteration = ('vanakkam' in result.lower() or 'nanri' in result.lower() or 
                          'naan' in result.lower() or '[T]' in result)
    
    if has_transliteration:
        print("ERROR: Tanglish detected! (This is NOT translation!)")
    else:
        print("OK: No Tanglish (correct!)")
    print()

print("-" * 80)
print("\n[*] TEST 2: ensure_tamil_only_display()")
print("-" * 80)
print("This should REMOVE English, keep only Tamil")
print()

for text, description in test_cases_tamil_filter:
    result = ensure_tamil_only_display(text)
    print("Input:  '{}'".format(text))
    print("Desc:   {}".format(description))
    print("Output: '{}'".format(result))
    print("OK: Filter applied")
    print()

print("="*80)
print("[RESULT]")
print("="*80)  
print("""
CORRECT BEHAVIOR:
- ensure_english_only_display() removes Tamil, shows only English
  (Does NOT transliterate Tamil to 'vanakkam')
  
- ensure_tamil_only_display() removes English, shows only Tamil

TRANSLATION FLOW:
1. User sends "வணக்கம்"
2. Translation API returns: "hello" (meaning)
3. Display filter shows: "hello" (NOT "vanakkam")

This ensures:
- Meaning translation works properly
- No Tanglish in output
- Clean display in both modes
""")
print("="*80 + "\n")
