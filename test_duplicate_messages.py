"""
Test to verify duplicate message issue is fixed.
Run with: python manage.py shell < test_duplicate_messages.py
"""

from django.test import TestCase, Client
from django.contrib.sessions.models import Session
from chatapp.models import Group, Message, AnonymousUser
from django.utils import timezone
import json

class DuplicateMessageTest(TestCase):
    def setUp(self):
        """Create a test group and client"""
        self.group = Group.objects.create(code="test123", name="Test Group")
        self.client = Client()
        
    def test_send_message_via_ajax_only(self):
        """
        Test that messages are created only via AJAX endpoint,
        not through the group view POST handler
        """
        # Set up session data
        session = self.client.session
        session['user_name'] = 'Test User'
        session['group_code'] = self.group.code
        session.save()
        
        # Get initial message count
        initial_count = Message.objects.filter(group=self.group).count()
        
        # Try to POST directly to /group/test123/ (old path)
        response = self.client.post(
            f'/group/{self.group.code}/',
            {'message': 'Test message via POST'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        # Should redirect, not create a message
        # (group view should no longer handle POST for messages)
        direct_post_count = Message.objects.filter(group=self.group).count()
        
        # Send message via AJAX endpoint
        response = self.client.post(
            f'/group/{self.group.code}/send-message/',
            {'message': 'Test message via AJAX'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        ajax_count = Message.objects.filter(group=self.group).count()
        
        # Should only have 1 message total
        print(f"Initial count: {initial_count}")
        print(f"After direct POST: {direct_post_count}")
        print(f"After AJAX: {ajax_count}")
        
        # Verify: Only AJAX creates messages
        assert ajax_count == initial_count + 1, f"Expected {initial_count + 1}, got {ajax_count}"
        print("✓ Test passed: Messages are created only via AJAX endpoint")
        
    def test_button_click_creates_single_message(self):
        """
        Verify that clicking send button once creates exactly one message
        (JavaScript prevents double submission)
        """
        message_text = "Single message test"
        
        session = self.client.session
        session['user_name'] = 'Test User'
        session.save()
        
        # Send message via AJAX
        response = self.client.post(
            f'/group/{self.group.code}/send-message/',
            {'message': message_text}
        )
        
        messages = Message.objects.filter(
            group=self.group,
            content=message_text
        )
        
        count = messages.count()
        print(f"Messages created with text '{message_text}': {count}")
        
        assert count == 1, f"Expected 1 message, found {count}"
        print("✓ Test passed: Single click creates single message")

if __name__ == '__main__':
    print("Testing duplicate message fix...\n")
    test = DuplicateMessageTest()
    test.setUp()
    test.test_send_message_via_ajax_only()
    print()
    test.setUp()  # Reset for next test
    test.test_button_click_creates_single_message()
    print("\n✓ All tests passed!")
