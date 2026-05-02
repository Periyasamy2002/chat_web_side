"""
Django Auth Debug Script
Checks all authentication components and provides detailed diagnostics
Run: python manage.py shell < debug_auth.py
"""

from django.contrib.auth.models import User
from django.db import connection
from chatapp.models import UserProfile
import json

print("\n" + "="*60)
print("🔍 DJANGO AUTHENTICATION SYSTEM DEBUG")
print("="*60 + "\n")

# 1. Database Connection Check
print("1️⃣  DATABASE CONNECTION")
print("-" * 60)
try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    print("✅ Database connection: OK")
except Exception as e:
    print(f"❌ Database connection: FAILED - {e}")

# 2. Check Django User Table
print("\n2️⃣  USERS IN DATABASE")
print("-" * 60)
users = User.objects.all()
if users.exists():
    print(f"✅ Found {users.count()} user(s):")
    for user in users:
        print(f"   └─ {user.username}")
        print(f"      • ID: {user.id}")
        print(f"      • Email: {user.email}")
        print(f"      • Is Active: {user.is_active}")
        print(f"      • Is Staff: {user.is_staff}")
        print(f"      • Is Superuser: {user.is_superuser}")
else:
    print("❌ No users found in database")

# 3. Check for Specific Test User
print("\n3️⃣  SEARCHING FOR 'admin123'")
print("-" * 60)
admin_user = User.objects.filter(username='admin123').first()
if admin_user:
    print("✅ User 'admin123' FOUND")
    print(f"   • ID: {admin_user.id}")
    print(f"   • Is Active: {admin_user.is_active}")
    print(f"   • Is Superuser: {admin_user.is_superuser}")
    
    # Test password
    from django.contrib.auth import authenticate
    auth_user = authenticate(username='admin123', password='Admin@123')
    if auth_user:
        print("   • Password 'Admin@123': ✅ CORRECT")
    else:
        print("   • Password 'Admin@123': ❌ INCORRECT")
else:
    print("❌ User 'admin123' NOT FOUND")

# 4. Check UserProfile Table
print("\n4️⃣  USER PROFILES")
print("-" * 60)
profiles = UserProfile.objects.all()
if profiles.exists():
    print(f"✅ Found {profiles.count()} profile(s):")
    for profile in profiles:
        print(f"   └─ User: {profile.user.username}")
        print(f"      • Is Approved: {profile.is_approved}")
        print(f"      • Mobile: {profile.mobile_number or 'Not set'}")
else:
    print("❌ No profiles found in database")

# 5. Check for Missing Profiles
print("\n5️⃣  USERS WITHOUT PROFILES")
print("-" * 60)
users_without_profile = []
for user in User.objects.all():
    try:
        _ = user.profile
    except UserProfile.DoesNotExist:
        users_without_profile.append(user.username)

if users_without_profile:
    print(f"⚠️  Found {len(users_without_profile)} user(s) without profile:")
    for username in users_without_profile:
        print(f"   └─ {username}")
        # Auto-create profile
        user = User.objects.get(username=username)
        profile = UserProfile.objects.create(user=user, is_approved=user.is_superuser)
        print(f"      ✅ Profile created (approved={profile.is_approved})")
else:
    print("✅ All users have profiles")

# 6. Check Sessions
print("\n6️⃣  SESSION TABLE")
print("-" * 60)
try:
    from django.contrib.sessions.models import Session
    session_count = Session.objects.count()
    print(f"✅ Session table exists: {session_count} session(s)")
except Exception as e:
    print(f"❌ Session table error: {e}")

# 7. Django Settings Check
print("\n7️⃣  DJANGO SETTINGS")
print("-" * 60)
from django.conf import settings
print(f"✅ DEBUG: {settings.DEBUG}")
print(f"✅ SESSION_ENGINE: {settings.SESSION_ENGINE}")
print(f"✅ SESSION_COOKIE_SECURE: {settings.SESSION_COOKIE_SECURE}")
print(f"✅ SESSION_COOKIE_HTTPONLY: {settings.SESSION_COOKIE_HTTPONLY}")
print(f"✅ LOGIN_URL: {settings.LOGIN_URL}")
print(f"✅ MIDDLEWARE count: {len(settings.MIDDLEWARE)}")

# 8. Recommendation
print("\n8️⃣  RECOMMENDATIONS")
print("-" * 60)

if not User.objects.filter(username='admin123').exists():
    print("❌ ACTION REQUIRED: Create admin user")
    print("\n   Run: python manage.py create_admin --username admin123 --password Admin@123")
else:
    admin = User.objects.get(username='admin123')
    if not admin.is_superuser:
        print("⚠️  WARNING: 'admin123' is not a superuser")
        print("   This user will need admin approval to login")
    
    try:
        profile = admin.profile
        if not profile.is_approved:
            print("⚠️  WARNING: admin profile not approved")
            print("   Run: python -c \"from chatapp.models import UserProfile; p = UserProfile.objects.get(user__username='admin123'); p.is_approved = True; p.save()\"")
    except UserProfile.DoesNotExist:
        print("❌ CRITICAL: admin profile missing")
        print("   Run: python -c \"from django.contrib.auth.models import User; from chatapp.models import UserProfile; u = User.objects.get(username='admin123'); UserProfile.objects.create(user=u, is_approved=True)\"")

print("\n" + "="*60)
print("✅ Debug report complete. Check results above.")
print("="*60 + "\n")
