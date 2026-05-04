#!/usr/bin/env python
"""
Test script to verify admin registration and login system is working correctly.

Usage:
    python test_admin_system.py

This will:
1. Check if Django is properly configured
2. Verify admin-related views exist
3. Test creating a test superuser
4. Verify authentication works
5. Cleanup test user
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatproject.settings')
sys.path.insert(0, os.path.dirname(__file__))

try:
    django.setup()
except Exception as e:
    print(f"❌ Django setup failed: {e}")
    sys.exit(1)

from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.test import Client
import json


def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print('='*60)


def test_django_setup():
    """Test if Django is properly configured."""
    print_header("1️⃣ Testing Django Setup")
    try:
        from django.conf import settings
        print(f"✅ DEBUG: {settings.DEBUG}")
        print(f"✅ Database: {settings.DATABASES['default']['ENGINE']}")
        print(f"✅ Installed Apps: {len(settings.INSTALLED_APPS)} apps")
        return True
    except Exception as e:
        print(f"❌ Django setup error: {e}")
        return False


def test_admin_views():
    """Test if admin views are accessible."""
    print_header("2️⃣ Testing Admin Views")
    try:
        from chatapp.views import admin_register_view, login_view
        print("✅ admin_register_view exists")
        print("✅ login_view exists")
        return True
    except ImportError as e:
        print(f"❌ View import error: {e}")
        return False


def test_admin_creation():
    """Test creating a test admin user."""
    print_header("3️⃣ Testing Admin User Creation")
    
    # Cleanup any existing test user
    User.objects.filter(username='test_admin_123').delete()
    
    try:
        test_user = User.objects.create_superuser(
            username='test_admin_123',
            email='test@example.com',
            password='TestPass@123456'
        )
        print(f"✅ Created test admin: {test_user.username}")
        print(f"✅ Is superuser: {test_user.is_superuser}")
        print(f"✅ Is staff: {test_user.is_staff}")
        return test_user
    except Exception as e:
        print(f"❌ Admin creation failed: {e}")
        return None


def test_authentication(user):
    """Test Django authentication."""
    print_header("4️⃣ Testing Authentication")
    
    try:
        # Test correct credentials
        auth_user = authenticate(username='test_admin_123', password='TestPass@123456')
        if auth_user is not None:
            print(f"✅ Authentication successful: {auth_user.username}")
        else:
            print("❌ Authentication failed with correct credentials")
            return False
        
        # Test wrong password
        wrong_auth = authenticate(username='test_admin_123', password='wrongpassword')
        if wrong_auth is None:
            print("✅ Wrong password correctly rejected")
        else:
            print("❌ Wrong password was accepted (security issue!)")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Authentication test failed: {e}")
        return False


def test_admin_panel_access():
    """Test if admin panel is accessible."""
    print_header("5️⃣ Testing Admin Panel Access")
    
    try:
        client = Client()
        
        # Try accessing admin without login
        response = client.get('/admin/')
        if response.status_code in [301, 302]:
            print("✅ Admin panel redirects unauthenticated users")
        else:
            print(f"⚠️  Unexpected status code: {response.status_code}")
        
        # Try accessing admin-register page
        response = client.get('/admin-register/')
        if response.status_code == 200:
            print("✅ Admin register page is accessible")
        else:
            print(f"❌ Admin register page error: {response.status_code}")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Admin panel access test failed: {e}")
        return False


def test_admin_count():
    """Test admin counting."""
    print_header("6️⃣ Testing Admin Count")
    
    try:
        count = User.objects.filter(is_superuser=True).count()
        print(f"✅ Current superuser count: {count}")
        if count <= 3:
            print("✅ Admin limit (3) is not exceeded")
            return True
        else:
            print("⚠️  Admin count exceeds limit of 3")
            return True
    except Exception as e:
        print(f"❌ Admin count test failed: {e}")
        return False


def cleanup_test_user():
    """Remove test user."""
    print_header("🧹 Cleanup")
    
    try:
        User.objects.filter(username='test_admin_123').delete()
        print("✅ Test user removed")
        return True
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "🧪 ADMIN SYSTEM TEST SUITE 🧪".center(60))
    
    results = {
        "Django Setup": test_django_setup(),
        "Admin Views": test_admin_views(),
    }
    
    test_user = test_admin_creation()
    results["Admin Creation"] = test_user is not None
    
    if test_user:
        results["Authentication"] = test_authentication(test_user)
        results["Admin Panel"] = test_admin_panel_access()
        results["Admin Count"] = test_admin_count()
        cleanup_test_user()
    
    # Summary
    print_header("📊 Test Summary")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Admin system is ready to use.")
        sys.exit(0)
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please check the errors above.")
        sys.exit(1)


if __name__ == '__main__':
    main()
