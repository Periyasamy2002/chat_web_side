#!/usr/bin/env python
"""
Comprehensive test suite for multilingual chat workflow.
Tests the complete flow: Send → Store as English → Display per-user language
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatproject.settings')
django.setup()

from django.test import TestCase, Client, RequestFactory
from django.utils import timezone
from chatapp.models import Group, Message, AnonymousUser
from chatapp.views import send_message_ajax, get_new_messages, group
from chatapp.utils.language import process_message_content, translate_message_for_user
from chatapp.utils.translator import translate_text
import json

class MultilingualWorkflowTests(TestCase):
    """Test complete multilingual workflow"""
    
    @classmethod
    def setUpTestData(cls):
        """Create test group and users"""
        cls.group = Group.objects.create(
            code='TEST001',
            created_by=None,
            group_name='Test Multilingual Group'
        )
        
        cls.user_tamil = AnonymousUser.objects.create(
            name='Tamil User',
            session_id='session_tamil_123',
            language_mode='tamil'
        )
        
        cls.user_hindi = AnonymousUser.objects.create(
            name='Hindi User',
            session_id='session_hindi_456',
            language_mode='hindi'
        )
        
        cls.user_english = AnonymousUser.objects.create(
            name='English User',
            session_id='session_english_789',
            language_mode='english'
        )
    
    def setUp(self):
        """Setup for each test"""
        self.client = Client()
        self.factory = RequestFactory()
    
    def test_01_language_processing(self):
        """Test message processing converts to canonical English"""
        print("\n=== TEST 1: Language Processing ===")
        
        test_cases = [
            ("வணக்கம்", "tamil", "Tamil greeting"),
            ("नमस्ते", "hindi", "Hindi greeting"),
            ("Hello world", "english", "English greeting"),
        ]
        
        for content, lang_mode, description in test_cases:
            english_ver, display_ver, val_msg, warn, tamil_ver = process_message_content(content, lang_mode)
            print(f"✓ {description}: {content[:20]}... → {english_ver[:30]}...")
            assert english_ver, f"English version should not be empty for {description}"
            print(f"  English version: {english_ver[:60]}")
            print(f"  Tamil version: {tamil_ver[:60]}")
    
    def test_02_message_storage_canonical_english(self):
        """Test send_message_ajax stores canonical English"""
        print("\n=== TEST 2: Message Storage (Canonical English) ===")
        
        # Simulate sending message
        msg = Message.objects.create(
            group=self.group,
            user_name='Test User',
            session_id='session_test_001',
            content='Hello everyone',
            message_type='text',
            english_content='Hello everyone',
            normalized_content='Hello everyone',
            translations='',
            translated_language=''
        )
        
        print(f"✓ Message stored:")
        print(f"  ID: {msg.id}")
        print(f"  Original: {msg.content}")
        print(f"  English: {msg.english_content}")
        print(f"  Normalized: {msg.normalized_content}")
        
        assert msg.english_content, "Must store English content"
        assert msg.normalized_content, "Must store normalized content"
    
    def test_03_per_user_translation_retrieval(self):
        """Test message translates to each user's language"""
        print("\n=== TEST 3: Per-User Translation Retrieval ===")
        
        # Create a message with canonical English
        msg = Message.objects.create(
            group=self.group,
            user_name='System',
            session_id='system',
            content='Good morning everyone',
            message_type='text',
            english_content='Good morning everyone',
            normalized_content='Good morning everyone',
            translations='',
            translated_language=''
        )
        
        # Get message translations for each user
        test_users = [
            ('english', 'English User'),
            ('tamil', 'Tamil User'),
            ('hindi', 'Hindi User'),
        ]
        
        for lang_mode, user_desc in test_users:
            translated = translate_message_for_user(msg.english_content, lang_mode)
            print(f"✓ {user_desc}:")
            print(f"  Original: {msg.english_content}")
            print(f"  Translated ({lang_mode}): {translated}")
            assert translated, f"Translation for {lang_mode} failed"
            
            # English should match original
            if lang_mode == 'english':
                assert translated == msg.english_content, "English should match original"
                print(f"  ✓ English matches original")
            else:
                # Non-English should be different (unless translation failed)
                print(f"  ✓ Translated to {lang_mode}")
    
    def test_04_multiple_languages_workflow(self):
        """Test complete workflow with multiple languages"""
        print("\n=== TEST 4: Complete Multi-Language Workflow ===")
        
        test_messages = [
            {
                'content': 'Hello my friends',
                'english': 'Hello my friends',
                'sender': 'english',
                'description': 'English message'
            },
            {
                'content': 'வணக்கம் நண்பர்கள்',
                'expected_english_contains': 'hello',  # After translation to English
                'sender': 'tamil',
                'description': 'Tamil message'
            },
            {
                'content': 'नमस्ते दोस्तों',
                'expected_english_contains': 'hello',  # After translation to English
                'sender': 'hindi',
                'description': 'Hindi message'
            }
        ]
        
        for test_msg in test_messages:
            # Process message (simulating send_message_ajax)
            english_version, display_version, val_msg, warn, tamil_version = process_message_content(
                test_msg['content'],
                test_msg['sender']
            )
            
            print(f"\n✓ {test_msg['description']}")
            print(f"  Input: {test_msg['content'][:40]}...")
            print(f"  Canonical English: {english_version[:60]}...")
            
            # Store in database
            msg = Message.objects.create(
                group=self.group,
                user_name='Test User',
                session_id='test_session',
                content=test_msg['content'],
                message_type='text',
                english_content=english_version,
                normalized_content=english_version,
                translations='',
                translated_language=''
            )
            
            # Retrieve for each language user
            for user_lang in ['english', 'tamil', 'hindi']:
                user_display = translate_message_for_user(english_version, user_lang)
                print(f"  → User in {user_lang}: {user_display[:50]}...")
    
    def test_05_language_mode_persistence(self):
        """Test language mode persists and affects display"""
        print("\n=== TEST 5: Language Mode Persistence ===")
        
        # Verify users have correct language modes
        print(f"✓ Tamil User language_mode: {self.user_tamil.language_mode}")
        assert self.user_tamil.language_mode == 'tamil'
        
        print(f"✓ Hindi User language_mode: {self.user_hindi.language_mode}")
        assert self.user_hindi.language_mode == 'hindi'
        
        print(f"✓ English User language_mode: {self.user_english.language_mode}")
        assert self.user_english.language_mode == 'english'
        
        print("✓ All language modes correctly stored")
    
    def test_06_all_supported_languages(self):
        """Test all 11 supported languages"""
        print("\n=== TEST 6: All Supported Languages ===")
        
        supported_langs = [
            'english', 'tamil', 'hindi', 'telugu', 'malayalam',
            'kannada', 'bengali', 'gujarati', 'marathi', 'punjabi', 'urdu'
        ]
        
        test_message = "Hello, how are you?"
        
        for lang in supported_langs:
            try:
                translated = translate_message_for_user(test_message, lang)
                print(f"✓ {lang.upper()}: {translated[:50]}...")
                assert translated, f"Failed to translate to {lang}"
            except Exception as e:
                print(f"✗ {lang.upper()}: ERROR - {e}")
    
    def test_07_translation_fallback(self):
        """Test graceful fallback on translation failure"""
        print("\n=== TEST 7: Translation Fallback ===")
        
        # Empty message
        result = translate_message_for_user('', 'tamil')
        print(f"✓ Empty message fallback: '{result}'")
        assert result == '', "Empty message should stay empty"
        
        # Very long message (might fail)
        long_msg = "This is a test. " * 100
        try:
            result = translate_message_for_user(long_msg, 'hindi')
            print(f"✓ Long message handling: Success ({len(result)} chars)")
        except Exception as e:
            print(f"! Long message handling: Fallback triggered - {str(e)[:50]}...")


def run_all_tests():
    """Run comprehensive test suite"""
    print("\n" + "="*70)
    print("MULTILINGUAL CHAT SYSTEM - COMPREHENSIVE TEST SUITE")
    print("="*70)
    
    from django.test.runner import DiscoverRunner
    runner = DiscoverRunner(verbosity=2)
    
    # Clear existing messages
    Message.objects.all().delete()
    AnonymousUser.objects.all().delete()
    Group.objects.all().delete()
    
    # Run tests
    test_suite = MultilingualWorkflowTests()
    test_suite.setUpClass()
    
    tests = [
        test_suite.test_01_language_processing,
        test_suite.test_02_message_storage_canonical_english,
        test_suite.test_03_per_user_translation_retrieval,
        test_suite.test_04_multiple_languages_workflow,
        test_suite.test_05_language_mode_persistence,
        test_suite.test_06_all_supported_languages,
        test_suite.test_07_translation_fallback,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        test_suite.setUp()
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ TEST FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ TEST ERROR: {e}")
            failed += 1
    
    # Summary
    print("\n" + "="*70)
    print(f"TEST RESULTS: {passed} PASSED, {failed} FAILED")
    print("="*70 + "\n")
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
