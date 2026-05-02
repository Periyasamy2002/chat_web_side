"""
Django Admin Login Troubleshooting & Fix Script
Checks and repairs admin user authentication issues
Run: python manage.py shell < fix_admin_login.py
"""

from django.contrib.auth.models import User
from chatapp.models import UserProfile
import sys

print("\n" + "="*70)
print("🔐 ADMIN LOGIN TROUBLESHOOTING SCRIPT")
print("="*70 + "\n")

# 1. Check if admin user exists
print("1️⃣  CHECKING FOR ADMIN USER")
print("-" * 70)

admin_users = User.objects.filter(is_superuser=True)
if admin_users.exists():
    print(f"✅ Found {admin_users.count()} superuser(s):")
    for user in admin_users:
        print(f"   └─ Username: {user.username}")
        print(f"      • Email: {user.email}")
        print(f"      • Is Active: {user.is_active}")
        print(f"      • Date Joined: {user.date_joined}")
        
        # Check UserProfile
        try:
            profile = user.profile
            print(f"      • Profile: YES (approved={profile.is_approved})")
        except UserProfile.DoesNotExist:
            print(f"      • Profile: NO - ⚠️  MISSING!")
else:
    print("❌ NO SUPERUSER FOUND")

# 2. Check total users
print("\n2️⃣  ALL USERS IN DATABASE")
print("-" * 70)
all_users = User.objects.all()
if all_users.exists():
    print(f"✅ Found {all_users.count()} user(s):")
    for user in all_users:
        tag = "👑 " if user.is_superuser else "   "
        active = "✅" if user.is_active else "❌"
        print(f"{tag}{active} {user.username} (staff={user.is_staff}, active={user.is_active})")
else:
    print("❌ NO USERS IN DATABASE")

# 3. Offer to create/reset admin
print("\n3️⃣  ADMIN SETUP OPTIONS")
print("-" * 70)

if not admin_users.exists():
    print("⚠️  NO ADMIN USER - CREATING ONE NOW...")
    
    admin = User.objects.create_superuser(
        username='admin123',
        email='admin@chat.com',
        password='Admin@123'
    )
    
    profile = UserProfile.objects.create(user=admin, is_approved=True)
    
    print("✅ ADMIN USER CREATED")
    print(f"   Username: admin123")
    print(f"   Password: Admin@123")
    print(f"   Email: admin@chat.com")
else:
    print("Admin user exists. Testing authentication...\n")
    
    from django.contrib.auth import authenticate
    
    admin = admin_users.first()
    result = authenticate(username=admin.username, password='Admin@123')
    
    if result:
        print(f"✅ Authentication test PASSED")
        print(f"   User '{admin.username}' can login with password 'Admin@123'")
    else:
        print(f"❌ Authentication test FAILED")
        print(f"   Password 'Admin@123' does NOT work")
        print(f"\n   Would you like to reset the password? (auto-fixing...)")
        
        admin.set_password('Admin@123')
        admin.save()
        
        # Verify
        result = authenticate(username=admin.username, password='Admin@123')
        if result:
            print(f"✅ Password reset successful!")
        else:
            print(f"❌ Password reset failed - manual intervention needed")

# 4. Ensure all users have profiles
print("\n4️⃣  CHECKING USER PROFILES")
print("-" * 70)
for user in User.objects.all():
    try:
        profile = user.profile
    except UserProfile.DoesNotExist:
        print(f"⚠️  User '{user.username}' has NO profile - creating...")
        profile = UserProfile.objects.create(
            user=user,
            is_approved=user.is_superuser  # Approve admins automatically
        )
        print(f"✅ Profile created (approved={profile.is_approved})")

print("✅ All users have profiles")

# 5. Final summary
print("\n5️⃣  FINAL STATUS")
print("-" * 70)
admin = User.objects.filter(is_superuser=True).first()
if admin:
    active = "✅" if admin.is_active else "❌"
    
    try:
        profile = admin.profile
        profile_status = f"✅ (approved={profile.is_approved})"
    except:
        profile_status = "❌ MISSING"
    
    print(f"Admin Username: {admin.username}")
    print(f"Admin Status: {active}")
    print(f"Admin Profile: {profile_status}")
    print(f"Test Credentials: {admin.username} / Admin@123")
    print(f"\n✅ Ready to login at /admin/login/")
else:
    print("❌ CRITICAL: Still no admin user!")

print("\n" + "="*70)
print("✅ Admin login fix complete. Try logging in now!")
print("="*70 + "\n")
