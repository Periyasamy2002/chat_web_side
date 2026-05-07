#!/usr/bin/env python
"""
Test script to verify Hindi language mode now displays correctly.
Tests that language_mode normalization works for all supported languages.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatproject.settings')
django.setup()

from chatapp.views import get_language_mode
from chatapp.utils.language import translate_message_for_user, SUPPORTED_LANGUAGES
from django.test import RequestFactory

def test_language_mode_normalization():
    """Test that get_language_mode handles both short codes and full names"""
    factory = RequestFactory()
    
    test_cases = [
        ('hindi', 'hindi'),
        ('hi', 'hindi'),
        ('tamil', 'tamil'),
        ('ta', 'tamil'),
        ('telugu', 'telugu'),
        ('te', 'telugu'),
        ('malayalam', 'malayalam'),
        ('ml', 'malayalam'),
        ('english', 'english'),
        ('en', 'english'),
    ]
    
    print("\n✅ TESTING LANGUAGE MODE NORMALIZATION")
    print("=" * 60)
    
    for input_mode, expected_output in test_cases:
        request = factory.get('/')
        request.session = {'language_mode': input_mode}
        
        result = get_language_mode(request, 'test_session_123')
        
        status = "✓" if result == expected_output else "✗"
        print(f"{status} Input: '{input_mode:12}' → Output: '{result:12}' (Expected: '{expected_output}')")
        
        if result != expected_output:
            print(f"   ❌ FAILED: Expected '{expected_output}' but got '{result}'")
            return False
    
    return True

def test_supported_languages_dict():
    """Test that SUPPORTED_LANGUAGES dict has all needed entries"""
    print("\n✅ TESTING SUPPORTED_LANGUAGES DICTIONARY")
    print("=" * 60)
    
    required_keys = [
        'hindi', 'hi',
        'tamil', 'ta', 
        'telugu', 'te',
        'malayalam', 'ml',
        'kannada', 'kn',
        'bengali', 'bn',
        'gujarati', 'gu',
        'marathi', 'mr',
        'punjabi', 'pa',
        'urdu', 'ur',
        'english', 'en'
    ]
    
    print(f"SUPPORTED_LANGUAGES has {len(SUPPORTED_LANGUAGES)} entries")
    print(f"Required entries: {len(required_keys)}")
    
    for key in required_keys:
        if key in SUPPORTED_LANGUAGES:
            lang_name = SUPPORTED_LANGUAGES[key]
            print(f"✓ '{key}' → '{lang_name}'")
        else:
            print(f"✗ '{key}' MISSING from SUPPORTED_LANGUAGES!")
            return False
    
    return True

def test_translate_message_for_user():
    """Test that translate_message_for_user works for Hindi"""
    print("\n✅ TESTING TRANSLATION FUNCTION")
    print("=" * 60)
    
    test_message = "Hello, how are you?"
    
    test_languages = [
        ('hindi', 'Hindi'),
        ('hi', 'Hindi'),
        ('tamil', 'Tamil'),
        ('english', 'English'),
    ]
    
    for lang_mode, lang_name in test_languages:
        try:
            result = translate_message_for_user(test_message, lang_mode)
            if result != test_message or lang_mode == 'english':
                print(f"✓ {lang_name} ({lang_mode}): Function executed successfully")
                if result:
                    print(f"  Translation: {result[:50]}...")
            else:
                print(f"✗ {lang_name} ({lang_mode}): Returned English instead of translating!")
                return False
        except Exception as e:
            print(f"✗ {lang_name} ({lang_mode}): {str(e)}")
            return False
    
    return True

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("HINDI MODE FIX - VERIFICATION TESTS")
    print("=" * 60)
    
    tests = [
        ("Language Mode Normalization", test_language_mode_normalization),
        ("SUPPORTED_LANGUAGES Dictionary", test_supported_languages_dict),
        ("Translate Message Function", test_translate_message_for_user),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"\n✅ {test_name}: PASSED")
            else:
                failed += 1
                print(f"\n❌ {test_name}: FAILED")
        except Exception as e:
            failed += 1
            print(f"\n❌ {test_name}: FAILED WITH ERROR")
            print(f"   Error: {str(e)}")
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! Hindi mode should now work correctly.")
        print("\nWhat was fixed:")
        print("1. ✓ SUPPORTED_LANGUAGES now includes both short codes and full names")
        print("2. ✓ get_language_mode() normalizes all language format variations")
        print("3. ✓ translate_message_for_user() handles Hindi and all languages")
        print("\nHow to test in browser:")
        print("1. Join a group with Hindi language mode")
        print("2. Send a Hindi message: नमस्ते or हैलो")
        print("3. Messages should display in Hindi")
        print("4. Other users should see translations in their language")
    else:
        print("\n❌ Some tests failed. Please review the errors above.")
    
    return failed == 0

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
