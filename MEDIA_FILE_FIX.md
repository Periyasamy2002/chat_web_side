# Fix for Missing Media Files Error on Render

## Problem
On Render's ephemeral filesystem, uploaded media files (voice messages) don't persist between deployments. When the application restarts or redeploys, these files are deleted from the filesystem, but references still exist in the database.

**Error:** `[Errno 2] No such file or directory: '/opt/render/project/src/media/...'`

This error occurs when the app tries to access a file that no longer exists on the filesystem.

## Solution

The fix includes multiple layers of protection:

### 1. **Safe File Access Helper Functions** (In `views.py`)
- `file_exists_safely()` - Checks if a file field's file actually exists before accessing it
- `get_audio_url_safely()` - Returns audio URL only if the file exists, returns None otherwise
- `get_translation_audio_url_safely()` - Same as above but for translated messages

**Benefits:**
- Prevents 404 errors when serving media URLs
- Gracefully degrades when files are missing
- Logs warnings for debugging

### 2. **Error Handling Middleware** (In `chatapp/middleware.py`)
- Catches `FileNotFoundError` exceptions and returns appropriate error responses
- Returns JSON for API requests
- Returns HTML for regular requests
- Prevents application crashes

**Where it's enabled:**
- Added to `MIDDLEWARE` in `settings.py`

### 3. **Database Cleanup Command** (New command)

For cleaning up orphaned file references in the database:

```bash
# Preview what will be cleaned (dry run)
python manage.py cleanup_missing_media --dry-run

# Actually clean up missing file references
python manage.py cleanup_missing_media
```

This command:
- Scans all Message, MessageTranslation, and DeletedMessage records
- Identifies files that no longer exist on the filesystem
- Removes the file references from the database (fields set to empty string)
- Provides detailed logging of what was cleaned

### 4. **Updated Views**
All places where audio URLs are generated now use the safe helper functions:
- Message serialization (line 950)
- Voice message response (line 2300)
- Load more messages endpoint (line 2545)
- Synthesize voice message response (line 2935)
- Load more with translations (lines 3036, 3050)

## How to Use

### After Deployment to Render:

1. **First-time setup** (optional but recommended):
   ```bash
   # Clean up any orphaned file references
   python manage.py cleanup_missing_media
   ```

2. **Monitor for issues:**
   - The middleware will catch any file not found errors gracefully
   - Check application logs for warnings about missing files
   - Use the cleanup command periodically if needed

### For Development:

- Use the safe helper functions when accessing audio files
- Test with missing files to ensure graceful degradation
- Run cleanup command occasionally to keep database clean

## Long-term Solution: Using S3 Storage (Optional but Recommended)

For a persistent solution, configure AWS S3 for media storage:

1. **Install django-storages:**
   ```bash
   pip install django-storages boto3
   ```

2. **Add to requirements.txt:**
   ```
   django-storages==1.14.2
   boto3==1.26.0
   botocore==1.29.0
   ```

3. **Configure in settings.py:**
   ```python
   if not DEBUG:  # Production only
       STORAGES = {
           "default": {
               "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
               "OPTIONS": {
                   "ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID"),
                   "SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY"),
                   "STORAGE_BUCKET_NAME": os.getenv("AWS_STORAGE_BUCKET_NAME"),
                   "S3_REGION_NAME": "us-east-1",
                   "S3_CUSTOM_DOMAIN": f"{os.getenv('AWS_STORAGE_BUCKET_NAME')}.s3.amazonaws.com",
                   "DEFAULT_ACL": "public-read",
               },
           },
           "staticfiles": {
               "BACKEND": "storages.backends.s3boto3.S3StaticStorage",
           },
       }
       STATIC_URL = f"https://{os.getenv('AWS_STORAGE_BUCKET_NAME')}.s3.amazonaws.com/static/"
       MEDIA_URL = f"https://{os.getenv('AWS_STORAGE_BUCKET_NAME')}.s3.amazonaws.com/media/"
   ```

4. **Add environment variables to Render:**
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `AWS_STORAGE_BUCKET_NAME`

## Testing

To test the fix:

```bash
# 1. Create a voice message (it should work normally)

# 2. Manually delete a file from media/voice_messages/

# 3. Try to load/play the message (should NOT crash, should degrade gracefully)

# 4. Run cleanup command
python manage.py cleanup_missing_media --dry-run
```

## Files Modified

1. **`chatapp/views.py`**
   - Added `file_exists_safely()` function
   - Added `get_audio_url_safely()` function
   - Added `get_translation_audio_url_safely()` function
   - Updated all audio URL generation to use safe functions
   - Improved `delete_file_field()` function

2. **`chatapp/middleware.py`** (NEW)
   - Added `MissingMediaFileMiddleware` class

3. **`chatapp/management/commands/cleanup_missing_media.py`** (NEW)
   - New management command for cleaning up orphaned files

4. **`chatproject/settings.py`**
   - Added `MissingMediaFileMiddleware` to MIDDLEWARE list

## Troubleshooting

### Still getting file not found errors?
1. Check that middleware is properly added to settings.py
2. Run cleanup command: `python manage.py cleanup_missing_media`
3. Check application logs for detailed error messages
4. Verify that safe helper functions are being used in all places accessing audio files

### Audio files working sometimes, missing other times?
- This is expected on ephemeral filesystems after deployments
- Run cleanup command periodically
- Consider implementing S3 storage for persistence

## References

- [Django File Storage Backends](https://docs.djangoproject.com/en/6.0/ref/files/storage/)
- [django-storages Documentation](https://django-storages.readthedocs.io/)
- [Render Ephemeral Filesystem](https://render.com/docs/persistent-disk)
