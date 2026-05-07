#!/usr/bin/env python
"""
Debug script to test the multilingual workflow end-to-end
Tests: Hindi -> Canonical English -> Malayalam translation
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatproject.settings')
django.setup()

from chatapp.utils.language import process_message_content, translate_message_for_user
from chatapp.utils.translator import translate_text

print("=" * 80)
print("MULTILINGUAL WORKFLOW DEBUG TEST")
print("=" * 80)

# Test 1: Hindi message processing
print("\n[TEST 1] Hindi message processing")
print("-" * 80)
hindi_msg = "मैं ठीक हूँ"  # Hindi: "I am fine"
print(f"Input (Hindi): {hindi_msg}")

english_ver, display_ver, val_msg, warn, tamil_ver = process_message_content(hindi_msg, 'hindi')
print(f"English version (canonical): {english_ver}")
print(f"Display version (for sender): {display_ver}")
print(f"Tamil version (backward compat): {tamil_ver}")

# Check if canonical English was created
if english_ver == hindi_msg:
    print("❌ ERROR: English version is still Hindi! Not converted to canonical English.")
else:
    print("✓ OK: English version is different from Hindi input")

# Test 2: translate_text direct call
print("\n[TEST 2] Direct translate_text call (Hindi -> English)")
print("-" * 80)
success, translated, msg = translate_text(hindi_msg, 'English')
print(f"Success: {success}")
print(f"Translated: {translated}")
print(f"Message: {msg}")

if translated == hindi_msg:
    print("❌ ERROR: translate_text returned Hindi unchanged!")
    print("   This happens when it thinks text is already English (contains_tamil_script check)")
else:
    print("✓ OK: Text was translated")

# Test 3: Check contains_tamil_script behavior
print("\n[TEST 3] contains_tamil_script behavior")
print("-" * 80)
from chatapp.utils.tamil_detector import contains_tamil_script
print(f"contains_tamil_script('{hindi_msg}'): {contains_tamil_script(hindi_msg)}")
print(f"contains_tamil_script('Hello'): {contains_tamil_script('Hello')}")
print(f"contains_tamil_script('வணக்கம்'): {contains_tamil_script('வணக்கம்')}")

# Test 4: Translation chain (simulate the full workflow)
print("\n[TEST 4] Full translation workflow")
print("-" * 80)
print("Step 1: Hindi user sends message")
hindi_input = "मैं ठीक हूँ"
print(f"  Input: {hindi_input}")

print("\nStep 2: Backend processes and stores canonical English")
english_canonical, _, _, _, _ = process_message_content(hindi_input, 'hindi')
print(f"  Stored in DB: {english_canonical}")

print("\nStep 3: Malayalam user retrieves and sees Malayalam translation")
malayalam_output = translate_message_for_user(english_canonical, 'malayalam')
print(f"  Malayalam user sees: {malayalam_output}")

if malayalam_output == hindi_input:
    print("❌ ERROR: Malayalam user got Hindi text instead of Malayalam translation!")
elif english_canonical == hindi_input:
    print("❌ CRITICAL: Canonical English is still Hindi - translation chain broken!")
else:
    print("✓ OK: Different outputs (should be Malayalam)")

# Test 5: Check database storage simulation
print("\n[TEST 5] Simulated database storage test")
print("-" * 80)

# Simulate what send_message_ajax stores
hindi_sender_msg = "मैं ठीक हूँ"
print(f"Hindi user sends: {hindi_sender_msg}")

# Process message
english_canonical, display_ver, _, _, tamil_ver = process_message_content(hindi_sender_msg, 'hindi')
print(f"Canonical English to store: {english_canonical}")
print(f"Message.content field: {english_canonical}")
print(f"Message.english_content field: {english_canonical}")
print(f"Message.normalized_content field: {english_canonical}")
print(f"Message.tamil_content field: {tamil_ver}")

# Now simulate retrieval for different users
print("\nRetrieval simulation:")
users_and_langs = [
    ('English user', 'english'),
    ('Hindi user', 'hindi'),
    ('Tamil user', 'tamil'),
    ('Malayalam user', 'malayalam'),
]

for user_desc, lang_mode in users_and_langs:
    translated = translate_message_for_user(english_canonical, lang_mode)
    print(f"  {user_desc:20} sees: {translated}")
    if translated == hindi_sender_msg and lang_mode != 'hindi':
        print(f"    ❌ ERROR: Got Hindi instead of {lang_mode}!")

print("\n" + "=" * 80)
