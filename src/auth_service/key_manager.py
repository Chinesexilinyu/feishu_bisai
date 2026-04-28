from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import os

class KeyManager:
    def __init__(self, private_key_path: str = None, public_key_path: str = None):
        self.private_key_path = private_key_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config", "private_key.pem"
        )
        self.public_key_path = public_key_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config", "public_key.pem"
        )
        self._private_key = None
        self._public_key = None

    @property
    def private_key(self):
        if not self._private_key:
            with open(self.private_key_path, 'rb') as f:
                self._private_key = serialization.load_pem_private_key(
                    f.read(), password=None, backend=default_backend()
                )
        return self._private_key

    @property
    def public_key(self):
        if not self._public_key:
            with open(self.public_key_path, 'rb') as f:
                self._public_key = serialization.load_pem_public_key(
                    f.read(), backend=default_backend()
                )
        return self._public_key
