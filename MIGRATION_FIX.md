# URGENT: Database Migration Fix

## Problem
The database is missing the `chatapp_group.last_activity` column required by the new auto-delete feature.

Error: `OperationalError: no such column: chatapp_group.last_activity`

## Solution

### For Render Deployment (Production)

**Option 1: Apply Migration via Dashboard** (Recommended)
1. Go to your Render dashboard
2. Find your Django service
3. Click "Shell" tab
4. Run these commands:
```bash
cd /opt/render/project/src
python manage.py migrate chatapp 0005_auto_activity_tracking
python manage.py migrate  # Apply all migrations just in case
```

**Option 2: Apply Migration via Build Command**
1. Add to your `render.yaml` or deployment settings:
```yaml
preDeployCommand: "python manage.py migrate"
```

2. Redeploy your app

**Option 3: Fix Code to Work Without Migration (Temporary)**
If you can't run migrations, I can modify the code to work without the new feature temporarily.

### For Local Development

If you're testing locally:
```bash
python manage.py migrate chatapp 0005_auto_activity_tracking
python manage.py runserver
```

## Migration Details

The migration `0005_auto_activity_tracking.py` adds:
1. `last_activity` column to `chatapp_group` table (DateTime field)
2. Database index on `last_activity` for performance
3. Database index on `created_at` field
4. Updates model ordering to use `last_activity`

## After Migration

Once migration is applied:
- ✅ Voice recording will work
- ✅ Auto-delete will work  
- ✅ User status tracking will work
- ✅ All new features active

## If Migration Still Fails

If you get errors running the migration, check:

1. **Database is locked**:
   ```bash
   # Restart the service to unlock
   ```

2. **Wrong database backend**:
   - Verify you're using SQLite or PostgreSQL
   - Check `DEBUG = False` setting

3. **Corrupted migration**:
   ```bash
   # Rollback and retry
   python manage.py migrate chatapp 0004_anonymoususer_alter_userstatus_unique_together_and_more
   python manage.py migrate chatapp 0005_auto_activity_tracking
   ```

## Fallback: Disable New Features Temporarily

If you **cannot** run migrations, I can:
1. Remove the database migration requirement
2. Make the code work with/without the column
3. Re-enable features once migration is applied

Let me know which option works best for you! 🚀
