"""
Custom middleware to handle missing media files gracefully.

On ephemeral filesystems like Render, uploaded files may disappear between
deployments. This middleware catches FileNotFoundError exceptions and
returns appropriate error responses instead of crashing the application.
"""

import logging
from django.http import JsonResponse, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

logger = logging.getLogger(__name__)


class MissingMediaFileMiddleware:
    """
    Middleware to handle missing media file errors gracefully.
    Catches FileNotFoundError and returns appropriate responses.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except FileNotFoundError as e:
            logger.warning(f"Missing file accessed: {str(e)}")

            # For API endpoints, return JSON error
            if request.path.startswith('/api/') or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'error': 'Media file not found',
                    'status': 'file_not_found',
                    'message': 'The requested media file is no longer available. This may happen on ephemeral filesystems.'
                }, status=404)

            # For regular requests, return a simple error page
            return HttpResponse(
                'Media file not found. The file may have been deleted or is unavailable.',
                status=404
            )

        except Exception as e:
            # Log other exceptions but don't interfere
            logger.exception(f"Unexpected error in middleware: {str(e)}")
            raise
