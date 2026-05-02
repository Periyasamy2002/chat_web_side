# ⚡ Quick Fix Commands

## 🎯 TL;DR - 3 Steps to Fix Login

```bash
# Step 1: Activate environment
env\Scripts\activate.bat

# Step 2: Create admin user (REQUIRED!)
python manage.py create_admin --username admin123 --password Admin@123

# Step 3: Test login
python manage.py runserver
# Open: http://localhost:8000/login/
# Enter: admin123 / Admin@123
# Should redirect to: http://localhost:8000/dashboard/
```

---

## 🔧 Useful Commands

### **Database**
```bash
# Apply migrations
python manage.py migrate

# Create superuser manually
python manage.py createsuperuser

# Show all users
python manage.py shell
>>> from django.contrib.auth.models import User
>>> for u in User.objects.all():
...     print(f"{u.username} - superuser: {u.is_superuser}")
```

### **Debug & Test**
```bash
# Run diagnostic script
python manage.py shell < debug_auth.py

# Open Django shell
python manage.py shell

# Check logs
type auth_debug.log  # Windows
tail -f auth_debug.log  # Linux/Mac
```

### **User Management**

#### Create admin:
```bash
python manage.py create_admin --username admin123 --password Admin@123 --email admin@chat.com
```

#### Create regular user:
```bash
python manage.py shell
>>> from django.contrib.auth.models import User
>>> from chatapp.models import UserProfile
>>> user = User.objects.create_user(username='testuser', password='Test@123')
>>> UserProfile.objects.create(user=user, is_approved=False)  # Not approved
>>> exit()
```

#### Approve user:
```bash
python manage.py shell
>>> from chatapp.models import UserProfile
>>> profile = UserProfile.objects.filter(user__username='testuser').first()
>>> profile.is_approved = True
>>> profile.save()
>>> exit()
```

#### Delete user:
```bash
python manage.py shell
>>> from django.contrib.auth.models import User
>>> User.objects.filter(username='testuser').delete()
>>> exit()
```

### **Server**
```bash
# Development
python manage.py runserver

# Specific port
python manage.py runserver 8080

# Production test
gunicorn chatproject.wsgi:application --bind 0.0.0.0:8000
```

---

## 📝 Python Shell Commands

### **Check user authentication**
```python
from django.contrib.auth import authenticate
user = authenticate(username='admin123', password='Admin@123')
print(user)  # Should show user object, not None
```

### **Check UserProfile**
```python
from django.contrib.auth.models import User
from chatapp.models import UserProfile

user = User.objects.get(username='admin123')
profile = user.profile
print(f"User: {user.username}")
print(f"Approved: {profile.is_approved}")
print(f"Superuser: {user.is_superuser}")
```

### **Fix missing profile**
```python
from django.contrib.auth.models import User
from chatapp.models import UserProfile

user = User.objects.get(username='admin123')
profile, created = UserProfile.objects.get_or_create(user=user)
if created:
    profile.is_approved = True
    profile.save()
    print(f"✅ Created and approved profile for {user.username}")
else:
    print(f"Profile already exists for {user.username}")
```

### **Approve pending user**
```python
from chatapp.models import UserProfile

pending = UserProfile.objects.filter(is_approved=False)
for profile in pending:
    print(f"Approving {profile.user.username}...")
    profile.is_approved = True
    profile.save()

print(f"✅ Approved {pending.count()} users")
```

### **List all users and status**
```python
from django.contrib.auth.models import User
from chatapp.models import UserProfile

for user in User.objects.all():
    try:
        profile = user.profile
        approved = "✅" if profile.is_approved else "⏳"
        admin = "👑" if user.is_superuser else ""
        print(f"{approved} {admin} {user.username} - Active: {user.is_active}")
    except:
        print(f"❌ {user.username} - NO PROFILE")
```

---

## 🐛 Common Issues & Quick Fixes

### **"Invalid username or password"**
```bash
# Check if user exists
python manage.py shell
>>> from django.contrib.auth.models import User
>>> User.objects.filter(username='admin123').exists()
False  # User doesn't exist!

# Create it
>>> python manage.py create_admin
```

### **"Account pending approval"**
```bash
# Approve the user
python manage.py shell
>>> from chatapp.models import UserProfile
>>> p = UserProfile.objects.get(user__username='admin123')
>>> p.is_approved = True
>>> p.save()
```

### **"Profile missing"**
```bash
# Create profile
python manage.py shell
>>> from django.contrib.auth.models import User
>>> from chatapp.models import UserProfile
>>> u = User.objects.get(username='admin123')
>>> UserProfile.objects.create(user=u, is_approved=True)
```

### **No redirect after login**
```bash
# Check logs
type auth_debug.log

# Should see: [LOGIN] ✅ SUCCESS
# If not, check error message in log
```

---

## ✅ Verification Checklist

Run this before testing:
```bash
python manage.py shell
```

Then:
```python
# 1. Check user exists
from django.contrib.auth.models import User
admin = User.objects.filter(username='admin123').first()
print(f"1. User exists: {admin is not None}")

# 2. Check authentication works
from django.contrib.auth import authenticate
auth = authenticate(username='admin123', password='Admin@123')
print(f"2. Auth works: {auth is not None}")

# 3. Check is superuser
print(f"3. Is superuser: {admin.is_superuser if admin else False}")

# 4. Check profile exists
try:
    profile = admin.profile
    print(f"4. Profile exists: True")
except:
    print(f"4. Profile exists: False")

# 5. Check is approved
print(f"5. Is approved: {profile.is_approved if admin else False}")

# All should be True - if not, see Quick Fixes above
```

---

## 🚀 Deploy to Render

Before deploying:
```bash
# 1. Test locally
python manage.py runserver

# 2. Create admin locally
python manage.py create_admin

# 3. Run migrations
python manage.py migrate

# 4. Commit changes
git add .
git commit -m "Fix login redirect issue"
git push origin main

# 5. Render will auto-deploy and run migrations
```

On Render dashboard:
```
Environment Variables:
- DEBUG = False
- SECRET_KEY = (set to long random string)
- DATABASE_URL = (auto-set)
```

---

## 📞 Support

If still stuck:
1. Check `auth_debug.log` for `[LOGIN]` messages
2. Run `python manage.py shell < debug_auth.py`
3. Check each verification step above
4. See `LOGIN_FIX_GUIDE.md` for detailed troubleshooting

