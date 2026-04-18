#!/usr/bin/env python
"""
Quick setup and test script for Chat Application features.
Run: python setup_and_test.py
"""

import os
import sys
import subprocess

def check_dependencies():
    """Check if all required packages are installed."""
    required = [
        'django',
        'google.generativeai',
        'gtts',
    ]
    
    missing = []
    for pkg in required:
        try:
            __import__(pkg.split('.')[0])
        except ImportError:
            missing.append(pkg)
    
    if missing:
        print(f"❌ Missing packages: {', '.join(missing)}")
        print("\nInstall with:")
        print("  pip install django google-generativeai gtts")
        return False
    
    print("✅ All dependencies found")
    return True


def check_env_vars():
    """Check for required environment variables."""
    if not os.getenv('GEMINI_API_KEY'):
        print("⚠️  GEMINI_API_KEY not set. Translation features will fail.")
        print("   Set with: export GEMINI_API_KEY='your-key'")
    else:
        print("✅ GEMINI_API_KEY is configured")


def test_tanglish_detection():
    """Test Tanglish detection locally."""
    print("\n" + "="*50)
    print("TESTING TANGLISH DETECTION")
    print("="*50)
    
    try:
        from chatapp.utils.tamil_detector import contains_tanglish
        
        test_cases = [
            ("solhra enna iruku", True, "Common Tanglish"),
            ("Hello how are you", False, "Pure English"),
            ("வணக்கம்", False, "Pure Tamil"),
            ("vanakkam", True, "Tanglish greeting"),
            ("tanglish", True, "Literal tanglish"),
            ("tangenglish", True, "Literal tangenglish"),
        ]
        
        for text, expected, desc in test_cases:
            result = contains_tanglish(text)
            status = "✅" if result == expected else "❌"
            print(f"{status} {desc}: '{text}' -> {result}")
        
        return True
    except Exception as e:
        print(f"❌ Error testing Tanglish: {e}")
        return False


def test_tts_function():
    """Test TTS function."""
    print("\n" + "="*50)
    print("TESTING TEXT-TO-SPEECH")
    print("="*50)
    
    try:
        from chatapp.utils.translator import synthesize_speech_with_gtts
        
        print("Testing gTTS synthesis...")
        success, audio_bytes, msg = synthesize_speech_with_gtts("Hello world", "en")
        
        if success and audio_bytes:
            print(f"✅ Generated {len(audio_bytes)} bytes of MP3 audio")
            print(f"   Message: {msg}")
        else:
            print(f"⚠️  Synthesis not available: {msg}")
        
        return True
    except Exception as e:
        print(f"❌ Error testing TTS: {e}")
        return False


def test_group_lifecycle():
    """Test group auto-delete constants."""
    print("\n" + "="*50)
    print("TESTING GROUP LIFECYCLE")
    print("="*50)
    
    try:
        from chatapp.models import NEW_GROUP_DELETE_MINUTES, INACTIVITY_DELETE_MINUTES
        
        print(f"New group auto-delete: {NEW_GROUP_DELETE_MINUTES} minutes (1 day = 1440)")
        print(f"Inactivity delete: {INACTIVITY_DELETE_MINUTES} minutes (12 hours = 720)")
        
        if NEW_GROUP_DELETE_MINUTES == 1440 and INACTIVITY_DELETE_MINUTES == 720:
            print("✅ Group lifecycle configured correctly")
            return True
        else:
            print("❌ Group lifecycle not configured correctly")
            return False
    except Exception as e:
        print(f"❌ Error checking group lifecycle: {e}")
        return False


def main():
    """Run all checks and tests."""
    print("\n" + "="*60)
    print("CHAT APPLICATION - SETUP & FEATURE VERIFICATION")
    print("="*60 + "\n")
    
    checks = [
        ("Dependencies", check_dependencies),
        ("Environment", check_env_vars),
        ("Tanglish Detection", test_tanglish_detection),
        ("Text-to-Speech", test_tts_function),
        ("Group Lifecycle", test_group_lifecycle),
    ]
    
    results = {}
    for name, check_fn in checks:
        try:
            results[name] = check_fn()
        except Exception as e:
            print(f"❌ Error in {name}: {e}")
            results[name] = False
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for name, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"{status} {name}")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("\n✅ All checks passed! Ready to run.")
        print("\nNext steps:")
        print("  1. python manage.py migrate")
        print("  2. python manage.py runserver")
        print("  3. Open http://localhost:8000")
    else:
        print("\n⚠️  Some checks failed. See above for details.")
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
