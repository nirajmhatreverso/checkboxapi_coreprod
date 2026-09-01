from api.utils.auth_utils import validate_token
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.contrib.auth import get_user_model

User = get_user_model()

class TokenAuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if this is an authenticated endpoint
        if self._is_authenticated_endpoint(request.path):
            auth_header = request.headers.get('Authorization', '')

            if not auth_header.startswith('Bearer '):
                return JsonResponse(
                    {'error': 'Unauthorized - missing or malformed token'},
                    status=401
                )

            parts = auth_header.split()
            if len(parts) != 2:
                return JsonResponse(
                    {'error': 'Unauthorized - invalid header format'},
                    status=401
                )

            token = parts[1]
            username = validate_token(token)

            if username is None:
                return JsonResponse(
                    {'error': 'Unauthorized - invalid or expired token'},
                    status=401
                )

            try:
                user = User.objects.get(username=username)
                request.user = user
                request.token_username = username
            except User.DoesNotExist:
                return JsonResponse(
                    {'error': 'Forbidden - user not found'},
                    status=403
                )

        return self.get_response(request)

    def _is_authenticated_endpoint(self, path):
        """Check if the path requires authentication"""
        # Auth endpoints that don't require auth
        auth_paths = ['/api/login/', '/api/register/']

        # If it's an auth endpoint that doesn't require authentication, skip
        for auth_path in auth_paths:
            if path.startswith(auth_path):
                return False

        # If it's under /api/, it requires authentication (except auth endpoints)
        # Use 'or' to add more endpoints to check for authorizaion.
        if path.startswith('/api/info/'):
            return True

        return False