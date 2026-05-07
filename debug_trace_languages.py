#!/usr/bin/env python
"""
DEBUG SCRIPT: Trace the exact point where non-Tamil languages fail
Helps identify if the issue is in:
1. process_message_content() normalization
2. translate_text() with source_language parameter
3. translate_message_for_user() retrieval
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatproject.settings')
django.setup()

from chatapp.utils.language import process_message_content, translate_message_for_user
from chatapp.utils.translator import translate_text, detect_language
from chatapp.utils.tamil_detector import contains_tamil_script

import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

print("\n" + "="*100)
print("DEBUG: TRACE NON-TAMIL LANGUAGE TRANSLATION")
print("="*100)

# Test case: Hindi message
test_msg = "मैं ठीक हूँ"  # Hindi: "I am fine"
test_lang = "hindi"

print(f"\n[INPUT]")
print(f"  Message: {test_msg}")
print(f"  Language mode: {test_lang}")

# Debug step 1: Detect language
print(f"\n[DEBUG 1] Language Detection")
detected = detect_language(test_msg)
print(f"  detect_language() result: {detected}")
print(f"  contains_tamil_script(): {contains_tamil_script(test_msg)}")

# Debug step 2: Process message
print(f"\n[DEBUG 2] process_message_content() - Hindi to English")
print(f"  Calling: process_message_content('{test_msg}', '{test_lang}')")

english_ver, display_ver, val_msg, warn, tamil_ver = process_message_content(test_msg, test_lang)

print(f"  Results:")
print(f"    english_version: {english_ver}")
print(f"    display_version: {display_ver}")
print(f"    tamil_version: {tamil_ver}")

if english_ver == test_msg:
    print(f"  ❌ PROBLEM DETECTED: english_version still equals Hindi input!")
    print(f"     This means process_message_content() didn't translate to English")
    
    # Try to debug what happened inside process_message_content
    print(f"\n  [INTERNAL DEBUG]")
    print(f"    - Detected language: {detected}")
    print(f"    - Contains Tamil script: {contains_tamil_script(test_msg)}")
    print(f"    - This is not Tamil/Ta mode, so should hit 'OTHER LANGUAGES' branch")
    print(f"    - Should call: translate_text('{test_msg}', 'English', source_language='Hindi')")
else:
    print(f"  ✓ OK: English version is different from Hindi input")

# Debug step 3: Direct translate_text call
print(f"\n[DEBUG 3] Direct translate_text() - Hindi to English WITH source_language")
print(f"  Calling: translate_text('{test_msg}', 'English', source_language='Hindi')")

success, translated, msg_str = translate_text(test_msg, 'English', source_language='Hindi')

print(f"  Results:")
print(f"    success: {success}")
print(f"    translated: {translated}")
print(f"    message: {msg_str}")

if success and translated and translated != test_msg:
    print(f"  ✓ OK: Direct translation worked")
else:
    print(f"  ❌ PROBLEM DETECTED: Direct translation returned original or failed")
    print(f"     Check if API_KEY is set correctly")

# Debug step 4: Retrieval - translate_message_for_user
print(f"\n[DEBUG 4] translate_message_for_user() - Retrieval for Malayalam user")

# Use the result from step 2 (or step 3 if step 2 failed)
canonical_english = english_ver if english_ver != test_msg else translated if success else test_msg

print(f"  Canonical English in DB: {canonical_english}")
print(f"  Target language: malayalam")
print(f"  Calling: translate_message_for_user('{canonical_english}', 'malayalam')")

malayalam_translation = translate_message_for_user(canonical_english, 'malayalam')

print(f"  Result: {malayalam_translation}")

if malayalam_translation == test_msg:
    print(f"  ❌ PROBLEM DETECTED: Malayalam user got Hindi instead of Malayalam!")
elif malayalam_translation == canonical_english:
    print(f"  ❌ PROBLEM DETECTED: Malayalam user got English instead of Malayalam!")
else:
    print(f"  ✓ OK: Malayalam user got Malayalam translation")

# Debug step 5: Same user retrieval
print(f"\n[DEBUG 5] translate_message_for_user() - Same language retrieval")
print(f"  Target language: {test_lang} (same as sender)")
print(f"  Calling: translate_message_for_user('{canonical_english}', '{test_lang}')")

hindi_translation = translate_message_for_user(canonical_english, test_lang)

print(f"  Result: {hindi_translation}")

if hindi_translation == test_msg:
    print(f"  ✓ OK: Hindi user got Hindi translation")
else:
    print(f"  ✓ Hindi user got translation in Hindi")

# Summary with recommendations
print(f"\n" + "="*100)
print("DIAGNOSIS AND RECOMMENDATIONS")
print("="*100)

issues = []

if english_ver == test_msg:
    issues.append("1. process_message_content() is NOT converting to English")
    issues.append("   FIX: Check language.py process_message_content() - 'OTHER LANGUAGES' branch")
    issues.append("   This branch should call translate_text(..., source_language='Hindi')")

if success and translated and translated == test_msg:
    issues.append("2. translate_text() with source_language parameter is not working")
    issues.append("   FIX: Check translator.py - verify source_language parameter is used in prompt")
    issues.append("   Prompt should be: 'Translate from Hindi to English'")

if malayalam_translation == test_msg:
    issues.append("3. translate_message_for_user() is returning original input for non-English")
    issues.append("   FIX: Check language.py translate_message_for_user() function")

if not issues:
    print("✓ No issues detected - Multilingual workflow appears to be working!")
else:
    print("Issues detected:")
    for issue in issues:
        print(f"  {issue}")

print("\n" + "="*100 + "\n")
