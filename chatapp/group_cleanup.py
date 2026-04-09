"""
Group Auto-Deletion Utility
============================

This module handles automatic deletion of inactive/empty groups based on:
1. Group opened with 0 users online
2. New group with no joins in 5 minutes
3. All users left for 4+ minutes
"""

from django.utils import timezone
from datetime import timedelta
from .models import Group, AnonymousUser
import logging

logger = logging.getLogger(__name__)


def get_group_online_count(group):
    """
    Get count of users online in a specific group
    A user is online if last_seen is within last 5 minutes
    """
    five_min_ago = timezone.now() - timedelta(minutes=5)
    
    # Get all online users
    online_users = AnonymousUser.objects.filter(
        is_online=True,
        last_seen__gte=five_min_ago
    )
    
    # Cross-check: only count if they have messages in this group
    user_ids_in_group = set()
    for user in online_users:
        has_message = group.messages.filter(
            session_id=user.session_id
        ).exists()
        if has_message:
            user_ids_in_group.add(user.session_id)
    
    return len(user_ids_in_group)


def check_and_delete_empty_groups():
    """
    Periodic cleanup: Delete groups based on all conditions
    Should be called from management command or cron job
    
    Returns: (deleted_count, deletion_details)
    """
    deleted_count = 0
    deletion_details = []
    
    try:
        all_groups = Group.objects.all()
        
        for group in all_groups:
            should_delete, reason = group.should_auto_delete()
            
            if should_delete:
                # Double-check before deleting
                online_count = get_group_online_count(group)
                
                if online_count == 0:
                    # Verify reason is still valid
                    if reason == "new_empty_5min":
                        five_min_ago = timezone.now() - timedelta(minutes=5)
                        if group.created_at < five_min_ago:
                            logger.info(f"✓ AUTO-DELETE: Group '{group.code}' (new, empty for 5min)")
                            deletion_details.append({
                                'group_code': group.code,
                                'reason': 'new_empty_5min',
                                'created_at': group.created_at.isoformat(),
                                'deleted_at': timezone.now().isoformat()
                            })
                            group.delete()
                            deleted_count += 1
                    
                    elif reason == "all_left_4min":
                        four_min_ago = timezone.now() - timedelta(minutes=4)
                        if group.last_activity < four_min_ago:
                            logger.info(f"✓ AUTO-DELETE: Group '{group.code}' (all left for 4min)")
                            deletion_details.append({
                                'group_code': group.code,
                                'reason': 'all_left_4min',
                                'last_activity': group.last_activity.isoformat(),
                                'deleted_at': timezone.now().isoformat()
                            })
                            group.delete()
                            deleted_count += 1
        
        return deleted_count, deletion_details
    
    except Exception as e:
        logger.error(f"Error in check_and_delete_empty_groups: {str(e)}")
        return 0, []


def check_group_on_access(group):
    """
    Check and cleanup when group is accessed
    Condition 1: Group opened with 0 users online
    """
    try:
        online_count = get_group_online_count(group)
        
        # If accessed with 0 users, mark for deletion check
        if online_count == 0:
            logger.debug(f"Group '{group.code}' accessed with 0 online users")
            
            # Wait for 5 minutes if new
            five_min_ago = timezone.now() - timedelta(minutes=5)
            if group.created_at < five_min_ago:
                logger.info(f"Group '{group.code}' empty for 5+ minutes, deleting...")
                group.delete()
                return True, "deleted_empty"
        
        return False, "active"
    
    except Exception as e:
        logger.error(f"Error in check_group_on_access: {str(e)}")
        return False, "error"


def cleanup_on_user_join(group, user_session_id):
    """
    When user joins a group:
    - Update last_activity
    - Mark user as online
    - Prevent accidental deletion
    """
    try:
        group.last_activity = timezone.now()
        group.save(update_fields=['last_activity'])
        
        # Update user status
        try:
            anon_user = AnonymousUser.objects.get(session_id=user_session_id)
            anon_user.is_online = True
            anon_user.last_seen = timezone.now()
            anon_user.save(update_fields=['is_online', 'last_seen'])
        except AnonymousUser.DoesNotExist:
            pass
        
        logger.debug(f"User joined group '{group.code}', updated activity")
        return True
    
    except Exception as e:
        logger.error(f"Error in cleanup_on_user_join: {str(e)}")
        return False


def cleanup_on_user_leave(group, user_session_id):
    """
    When user leaves a group:
    - Check if group is now empty
    - Start 4-minute timer if all users left
    """
    try:
        online_count = get_group_online_count(group)
        
        if online_count == 0:
            # All users left, update last_activity to start 4-minute timer
            group.last_activity = timezone.now()
            group.save(update_fields=['last_activity'])
            logger.debug(f"All users left group '{group.code}', 4-minute timer started")
            return True, "all_left"
        
        return False, "users_remain"
    
    except Exception as e:
        logger.error(f"Error in cleanup_on_user_leave: {str(e)}")
        return False, "error"


def update_user_heartbeat(user_session_id):
    """
    Update user's last_seen timestamp (called every 30 seconds)
    This keeps user marked as online
    """
    try:
        anon_user = AnonymousUser.objects.get(session_id=user_session_id)
        anon_user.last_seen = timezone.now()
        anon_user.save(update_fields=['last_seen'])
        return True
    
    except AnonymousUser.DoesNotExist:
        return False
    except Exception as e:
        logger.error(f"Error in update_user_heartbeat: {str(e)}")
        return False


def get_group_deletion_status(group_code):
    """
    Get deletion status and reason for a specific group
    Returns: {
        'code': str,
        'should_delete': bool,
        'reason': str,
        'online_count': int,
        'age_minutes': int,
        'inactivity_minutes': int
    }
    """
    try:
        group = Group.objects.get(code=group_code)
        should_delete, reason = group.should_auto_delete()
        
        online_count = get_group_online_count(group)
        age_minutes = (timezone.now() - group.created_at).total_seconds() / 60
        inactivity_minutes = (timezone.now() - group.last_activity).total_seconds() / 60
        
        return {
            'code': group_code,
            'should_delete': should_delete,
            'reason': reason,
            'online_count': online_count,
            'age_minutes': round(age_minutes, 2),
            'inactivity_minutes': round(inactivity_minutes, 2),
            'created_at': group.created_at.isoformat(),
            'last_activity': group.last_activity.isoformat()
        }
    
    except Group.DoesNotExist:
        return {
            'code': group_code,
            'error': 'Group not found'
        }
    except Exception as e:
        logger.error(f"Error in get_group_deletion_status: {str(e)}")
        return {
            'code': group_code,
            'error': str(e)
        }


def get_all_groups_cleanup_status():
    """
    Get cleanup status for all groups
    Useful for monitoring/debugging
    """
    try:
        statuses = []
        for group in Group.objects.all():
            status = {
                'code': group.code,
                'name': group.name,
                'created_at': group.created_at.isoformat(),
                'last_activity': group.last_activity.isoformat(),
                'online_count': get_group_online_count(group),
                'should_delete': group.should_auto_delete()[0],
                'delete_reason': group.should_auto_delete()[1],
                'age_minutes': round((timezone.now() - group.created_at).total_seconds() / 60, 2),
                'inactivity_minutes': round((timezone.now() - group.last_activity).total_seconds() / 60, 2)
            }
            statuses.append(status)
        
        return statuses
    
    except Exception as e:
        logger.error(f"Error in get_all_groups_cleanup_status: {str(e)}")
        return []
