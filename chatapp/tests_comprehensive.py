"""
Comprehensive test suite for Django Chat Application
Run with: pytest tests.py -v
Or with Django: python manage.py test chatapp.tests
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from chatapp.models import Group, Message, AnonymousUser
import json
import io


class GroupModelTests(TestCase):
    """Test Group model functionality"""
    
    def setUp(self):
        """Create test data"""
        self.group = Group.objects.create(code="TEST123", name="Test Group")
    
    def test_group_creation(self):
        """Test that groups are created correctly"""
        self.assertEqual(self.group.code, "TEST123")
        self.assertEqual(self.group.name, "Test Group")
        self.assertIsNotNone(self.group.created_at)
        self.assertIsNotNone(self.group.last_activity)
    
    def test_group_unique_code(self):
        """Test that group codes must be unique"""
        with self.assertRaises(Exception):
            Group.objects.create(code="TEST123", name="Duplicate")
    
    def test_group_last_activity_tracking(self):
        """Test that last_activity is updated"""
        old_activity = self.group.last_activity
        self.group.last_activity = timezone.now()
        self.group.save()
        self.group.refresh_from_db()
        self.assertGreater(self.group.last_activity, old_activity)
    
    def test_group_auto_delete_check(self):
        """Test auto-delete logic"""
        # Fresh group should not auto-delete
        self.assertFalse(self.group.should_auto_delete())
        
        # Old group with no users should auto-delete
        self.group.last_activity = timezone.now() - timedelta(minutes=31)
        self.group.save()
        self.assertTrue(self.group.should_auto_delete())


class AnonymousUserModelTests(TestCase):
    """Test AnonymousUser model functionality"""
    
    def setUp(self):
        """Create test data"""
        self.user = AnonymousUser.objects.create(
            session_id="session123",
            user_name="TestUser",
            is_online=True
        )
    
    def test_user_creation(self):
        """Test that anonymous users are created correctly"""
        self.assertEqual(self.user.session_id, "session123")
        self.assertEqual(self.user.user_name, "TestUser")
        self.assertTrue(self.user.is_online)
    
    def test_user_unique_session_id(self):
        """Test that session IDs must be unique"""
        with self.assertRaises(Exception):
            AnonymousUser.objects.create(
                session_id="session123",
                user_name="AnotherUser"
            )
    
    def test_user_online_status(self):
        """Test user online/offline status tracking"""
        self.assertTrue(self.user.is_online)
        self.user.is_online = False
        self.user.save()
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_online)
    
    def test_user_last_seen_update(self):
        """Test last_seen timestamp updates"""
        old_time = self.user.last_seen
        self.user.last_seen = timezone.now()
        self.user.save()
        self.user.refresh_from_db()
        self.assertGreater(self.user.last_seen, old_time)


class MessageModelTests(TestCase):
    """Test Message model functionality"""
    
    def setUp(self):
        """Create test data"""
        self.group = Group.objects.create(code="TEST", name="Test")
        self.text_msg = Message.objects.create(
            group=self.group,
            user_name="Alice",
            session_id="session1",
            content="Hello World",
            message_type="text"
        )
        self.voice_msg = Message.objects.create(
            group=self.group,
            user_name="Bob",
            session_id="session2",
            message_type="voice",
            duration=5.2,
            audio_mime_type="audio/webm"
        )
    
    def test_text_message_creation(self):
        """Test text message creation"""
        self.assertEqual(self.text_msg.content, "Hello World")
        self.assertEqual(self.text_msg.message_type, "text")
        self.assertEqual(self.text_msg.is_deleted, "not_deleted")
    
    def test_voice_message_creation(self):
        """Test voice message creation"""
        self.assertEqual(self.voice_msg.message_type, "voice")
        self.assertEqual(self.voice_msg.duration, 5.2)
        self.assertEqual(self.voice_msg.audio_mime_type, "audio/webm")
    
    def test_message_ordering(self):
        """Test that messages are ordered by timestamp"""
        messages = Message.objects.all().values_list('id', flat=True)
        self.assertEqual(list(messages), [self.text_msg.id, self.voice_msg.id])
    
    def test_message_deletion_status(self):
        """Test message deletion status tracking"""
        # Test delete for me
        self.text_msg.is_deleted = "deleted_for_me"
        self.text_msg.save()
        self.text_msg.refresh_from_db()
        self.assertEqual(self.text_msg.is_deleted, "deleted_for_me")
        
        # Test delete for all
        self.text_msg.is_deleted = "deleted_for_all"
        self.text_msg.save()
        self.text_msg.refresh_from_db()
        self.assertEqual(self.text_msg.is_deleted, "deleted_for_all")
    
    def test_message_display_text(self):
        """Test get_display_text method"""
        self.assertEqual(self.text_msg.get_display_text(), "Hello World")
        
        self.text_msg.is_deleted = "deleted_for_all"
        self.assertEqual(
            self.text_msg.get_display_text(),
            "This message was deleted"
        )


class ViewsTests(TestCase):
    """Test view functionality"""
    
    def setUp(self):
        """Create test data"""
        self.client = Client()
        self.group = Group.objects.create(code="TESTCODE", name="Test")
        self.user = AnonymousUser.objects.create(
            session_id="test_session",
            user_name="TestUser",
            is_online=True
        )
    
    def test_home_view(self):
        """Test home page loads"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')
    
    def test_chat_view_get(self):
        """Test chat page loads"""
        response = self.client.get('/chat/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'chat.html')
    
    def test_group_view_get(self):
        """Test group chat page loads"""
        response = self.client.get(f'/group/{self.group.code}/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'group.html')
    
    def test_group_view_nonexistent(self):
        """Test that accessing nonexistent group redirects"""
        response = self.client.get('/group/NONEXISTENT/')
        self.assertEqual(response.status_code, 302)  # Redirect
    
    def test_send_message_ajax(self):
        """Test sending text message via AJAX"""
        # Set up session
        session = self.client.session
        session['user_name'] = 'TestUser'
        session['user_id'] = 'test_session'
        session.save()
        
        # Send message
        response = self.client.post(
            f'/group/{self.group.code}/send-message/',
            {'message': 'Hello World'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['message']['content'], 'Hello World')
        
        # Verify message was saved
        msg = Message.objects.filter(
            group=self.group,
            content='Hello World'
        ).first()
        self.assertIsNotNone(msg)
    
    def test_send_empty_message(self):
        """Test that empty messages are rejected"""
        response = self.client.post(
            f'/group/{self.group.code}/send-message/',
            {'message': ''}
        )
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn('error', data)
    
    def test_send_message_too_long(self):
        """Test that messages over 5000 chars are rejected"""
        long_message = 'a' * 5001
        response = self.client.post(
            f'/group/{self.group.code}/send-message/',
            {'message': long_message}
        )
        self.assertEqual(response.status_code, 400)
    
    def test_get_new_messages(self):
        """Test fetching new messages"""
        # Create a message
        Message.objects.create(
            group=self.group,
            user_name='Alice',
            session_id='session1',
            content='Hello',
            message_type='text'
        )
        
        # Fetch messages
        response = self.client.get(f'/group/{self.group.code}/get-messages/')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertGreater(len(data['messages']), 0)
    
    def test_get_online_users(self):
        """Test fetching online users"""
        response = self.client.get(f'/group/{self.group.code}/online-users/')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('users', data)
        self.assertIn('count', data)
    
    def test_delete_message_for_me(self):
        """Test deleting message for self"""
        msg = Message.objects.create(
            group=self.group,
            user_name='TestUser',
            session_id='test_session',
            content='Test message',
            message_type='text'
        )
        
        # Set up session with same session_id
        session = self.client.session
        session.session_key = 'test_session'
        session.save()
        
        response = self.client.post(
            f'/group/{self.group.code}/delete-message/',
            {
                'message_id': msg.id,
                'delete_type': 'for_me'
            }
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
    
    def test_delete_message_for_all_sender_only(self):
        """Test that only sender can delete for all"""
        msg = Message.objects.create(
            group=self.group,
            user_name='OtherUser',
            session_id='other_session',
            content='Test',
            message_type='text'
        )
        
        # Try to delete as different user
        response = self.client.post(
            f'/group/{self.group.code}/delete-message/',
            {
                'message_id': msg.id,
                'delete_type': 'for_all'
            }
        )
        
        # Should fail (403 Forbidden)
        self.assertEqual(response.status_code, 403)
    
    def test_update_user_status(self):
        """Test updating user online status"""
        session = self.client.session
        session['user_name'] = 'TestUser'
        session.save()
        
        response = self.client.post(
            f'/group/{self.group.code}/update-status/',
            {'is_online': 'true'}
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertTrue(data['is_online'])


class IntegrationTests(TestCase):
    """Integration tests simulating real usage"""
    
    def setUp(self):
        """Create test data"""
        self.client1 = Client()
        self.client2 = Client()
        self.group = Group.objects.create(code="INTEGRATION", name="Integration Test")
    
    def test_multi_user_conversation(self):
        """Test conversation between two users"""
        # User 1 sends message
        session1 = self.client1.session
        session1['user_name'] = 'Alice'
        session1['user_id'] = 'alice_session'
        session1.save()
        
        response = self.client1.post(
            f'/group/{self.group.code}/send-message/',
            {'message': 'Hi Bob'}
        )
        self.assertEqual(response.status_code, 200)
        
        # User 2 fetches messages
        session2 = self.client2.session
        session2['user_name'] = 'Bob'
        session2['user_id'] = 'bob_session'
        session2.save()
        
        response = self.client2.get(
            f'/group/{self.group.code}/get-messages/'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertGreater(len(data['messages']), 0)
        
        # Find message from Alice
        alice_msg = next(
            (m for m in data['messages'] if m['user_name'] == 'Alice'),
            None
        )
        self.assertIsNotNone(alice_msg)
        self.assertEqual(alice_msg['content'], 'Hi Bob')


class PerformanceTests(TestCase):
    """Performance and stress tests"""
    
    def setUp(self):
        """Create test data"""
        self.group = Group.objects.create(code="PERF", name="Performance Test")
    
    def test_message_query_performance(self):
        """Test that message queries are efficient"""
        # Create 100 messages
        for i in range(100):
            Message.objects.create(
                group=self.group,
                user_name=f'User{i}',
                session_id=f'session{i}',
                content=f'Message {i}',
                message_type='text'
            )
        
        # Query should be fast (< 100ms for 100 messages)
        import time
        start = time.time()
        messages = list(Message.objects.filter(group=self.group).values(
            'id', 'user_name', 'content', 'timestamp'
        ))
        duration = time.time() - start
        
        self.assertEqual(len(messages), 100)
        self.assertLess(duration, 0.1)  # Should be < 100ms
    
    def test_online_user_count_query(self):
        """Test online user count query is efficient"""
        # Create users
        for i in range(50):
            AnonymousUser.objects.create(
                session_id=f'session{i}',
                user_name=f'User{i}',
                is_online=i % 2 == 0  # Half online
            )
        
        # Query should be fast
        import time
        start = time.time()
        online = AnonymousUser.objects.filter(
            is_online=True,
            last_seen__gte=timezone.now() - timedelta(minutes=5)
        ).count()
        duration = time.time() - start
        
        self.assertGreater(online, 0)
        self.assertLess(duration, 0.1)  # Should be < 100ms


class ErrorHandlingTests(TestCase):
    """Test error handling and edge cases"""
    
    def setUp(self):
        """Create test data"""
        self.group = Group.objects.create(code="ERROR", name="Error Test")
    
    def test_invalid_group_code(self):
        """Test handling of invalid group codes"""
        response = self.client.get('/group/INVALID/')
        self.assertEqual(response.status_code, 302)  # Should redirect
    
    def test_missing_csrf_token(self):
        """Test CSRF protection"""
        # This would require disabling CSRF for this test
        # In production, this should always fail without token
        pass
    
    def test_message_not_found(self):
        """Test deleting nonexistent message"""
        response = self.client.post(
            f'/group/{self.group.code}/delete-message/',
            {
                'message_id': 99999,  # Nonexistent
                'delete_type': 'for_me'
            }
        )
        self.assertEqual(response.status_code, 404)
    
    def test_empty_group_messages(self):
        """Test fetching messages from empty group"""
        empty_group = Group.objects.create(code="EMPTY", name="Empty")
        response = self.client.get(f'/group/{empty_group.code}/get-messages/')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertEqual(len(data['messages']), 0)


# Test execution helpers
def run_all_tests():
    """Run all tests"""
    import django
    from django.conf import settings
    from django.test.utils import get_runner
    
    if not settings.configured:
        django.setup()
    
    TestRunner = get_runner(settings)
    test_runner = TestRunner()
    failures = test_runner.run_tests(['chatapp.tests'])
    return failures


if __name__ == '__main__':
    run_all_tests()
