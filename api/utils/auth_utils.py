import time
import hmac
import hashlib
import base64
from django.conf import settings

def generate_token(username):
    timestamp = str(int(time.time()))
    message = f"{username}:{timestamp}"

    signature = hmac.new(
        settings.SECRET_KEY.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    token = f"{username}:{timestamp}:{signature}"
    return base64.urlsafe_b64encode(token.encode()).decode()

def validate_token(token):
    try:
        decoded = base64.urlsafe_b64decode(token).decode()
        username, timestamp, signature = decoded.split(":", 2)
        message = f"{username}:{timestamp}"
        expected_signature = hmac.new(
            settings.SECRET_KEY.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            return None

        return username

    except Exception:
        return None