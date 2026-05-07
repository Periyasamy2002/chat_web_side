#!/usr/bin/env python
"""
COMPREHENSIVE MULTILINGUAL WORKFLOW TEST
Tests all languages: Hindi → English → Malayalam (and other languages)
This script validates the complete translation pipeline.
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatproject.settings')
django.setup()

from chatapp.models import Group, Message, AnonymousUser
from chatapp.utils.language import process_message_content, translate_message_for_user, SUPPORTED_LANGUAGES
from chatapp.utils.translator import translate_text
from django.utils import timezone
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("\n" + "="*100)
print("COMPREHENSIVE MULTILINGUAL WORKFLOW TEST - ALL LANGUAGES")
print("="*100)

# Test Messages in Different Languages
test_cases = [
    {
        'language': 'Hindi',
        'lang_mode': 'hindi',
        'input': 'मैं ठीक हूँ',  # I am fine
        'expected_english': 'I am fine',
    },
    {
        'language': 'Malayalam',
        'lang_mode': 'malayalam',
        'input': 'എനിക്ക് സുഖമാണ്',  # I am well
        'expected_english': 'I am well',
    },
    {
        'language': 'Telugu',
        'lang_mode': 'telugu',
        'input': 'నేను బాగున్నాను',  # I am fine
        'expected_english': 'I am fine',
    },
    {
        'language': 'Tamil',
        'lang_mode': 'tamil',
        'input': 'நான் நன்றாக இருக்கிறேன்',  # I am fine
        'expected_english': 'I am fine',
    },
    {
        'language': 'Kannada',
        'lang_mode': 'kannada',
        'input': 'ನಾನು ಚೆನ್ನಾಗಿದ್ದೇನೆ',  # I am fine
        'expected_english': 'I am fine',
    },
    {
        'language': 'Bengali',
        'lang_mode': 'bengali',
        'input': 'আমি ভালো আছি',  # I am fine
        'expected_english': 'I am fine',
    },
]

def test_translation_chain(test_case):
    """Test one language pair through the entire workflow"""
    language = test_case['language']
    lang_mode = test_case['lang_mode']
    input_msg = test_case['input']
    
    print(f"\n{'='*100}")
    print(f"TEST: {language.upper()} → English → Malayalam")
    print(f"{'='*100}")
    
    # STEP 1: User sends message in their language
    print(f"\n[STEP 1] User sends message in {language}")
    print(f"  Input: {input_msg}")
    
    # STEP 2: Backend processes to canonical English
    print(f"\n[STEP 2] Backend processes to canonical English")
    english_canonical, display_ver, val_msg, warn, tamil_ver = process_message_content(input_msg, lang_mode)
    print(f"  Canonical English: {english_canonical}")
    print(f"  Display (sender sees): {display_ver}")
    
    # Check if canonical English is different from input (except for English inputs)
    if lang_mode not in ['english', 'en']:
        if english_canonical == input_msg:
            print(f"  ❌ ERROR: Canonical English still equals input! Translation may have failed.")
            return False
        else:
            print(f"  ✓ OK: Canonical English is different from input")
    else:
        print(f"  ✓ OK: English input stored as-is")
    
    # STEP 3: Simulate storage in database
    print(f"\n[STEP 3] Store in database")
    print(f"  message.english_content = {english_canonical}")
    print(f"  message.content = {english_canonical}")
    
    # STEP 4: Retrieve and translate for different users
    print(f"\n[STEP 4] Retrieve and translate for each user's language")
    
    target_languages = [
        ('English', 'english'),
        (language, lang_mode),  # Same language as sender
        ('Malayalam', 'malayalam'),
        ('Hindi', 'hindi'),
    ]
    
    success = True
    for target_lang_name, target_lang_mode in target_languages:
        translated = translate_message_for_user(english_canonical, target_lang_mode)
        print(f"\n  [{target_lang_name} user]")
        print(f"    Sees: {translated}")
        
        # Validate
        if target_lang_mode == 'english':
            if translated != english_canonical:
                print(f"    ❌ ERROR: English user didn't get canonical English")
                success = False
            else:
                print(f"    ✓ OK: Got canonical English")
        elif target_lang_mode == lang_mode:
            # Same language as sender
            if translated == input_msg:
                print(f"    ✓ OK: Got same language as sender input")
            else:
                print(f"    ✓ OK: Got translated version in same language")
        else:
            # Different language
            if translated == input_msg:
                print(f"    ❌ ERROR: Got {language} instead of {target_lang_name}!")
                success = False
            elif translated == english_canonical:
                print(f"    ⚠️  WARNING: Got English instead of {target_lang_name} (translation may have failed)")
                success = False
            else:
                print(f"    ✓ OK: Got {target_lang_name} translation")
    
    return success

def test_direct_translation():
    """Test translate_text function with source_language parameter"""
    print(f"\n\n{'='*100}")
    print("TEST: Direct translate_text() function with source_language parameter")
    print(f"{'='*100}")
    
    hindi_text = "मैं ठीक हूँ"
    
    print(f"\nTest 1: Hindi → English (WITHOUT source_language)")
    success1, result1, msg1 = translate_text(hindi_text, 'English')
    print(f"  Input: {hindi_text}")
    print(f"  Success: {success1}")
    print(f"  Result: {result1}")
    print(f"  Message: {msg1}")
    
    print(f"\nTest 2: Hindi → English (WITH source_language='Hindi')")
    success2, result2, msg2 = translate_text(hindi_text, 'English', source_language='Hindi')
    print(f"  Input: {hindi_text}")
    print(f"  Success: {success2}")
    print(f"  Result: {result2}")
    print(f"  Message: {msg2}")
    
    if result1 and result2:
        if result1 == result2:
            print(f"\n  ✓ Both methods produced same result: {result1}")
        else:
            print(f"\n  ⚠️  Results differ!")
            print(f"     Without source: {result1}")
            print(f"     With source: {result2}")
    
    return result1 is not None and result2 is not None

# Run tests
print("\nRunning comprehensive multilingual tests...\n")

all_success = True

# Test direct translation function first
if not test_direct_translation():
    print("\n❌ Direct translation test failed")
    all_success = False

# Test each language
for test_case in test_cases:
    try:
        if not test_translation_chain(test_case):
            all_success = False
    except Exception as e:
        print(f"\n❌ ERROR in {test_case['language']} test: {e}")
        import traceback
        traceback.print_exc()
        all_success = False

# Summary
print(f"\n\n{'='*100}")
print("TEST SUMMARY")
print(f"{'='*100}")
if all_success:
    print("✓ All tests PASSED - Multilingual workflow is working correctly")
else:
    print("❌ Some tests FAILED - Please check the errors above")

print("\n" + "="*100 + "\n")

sys.exit(0 if all_success else 1)
