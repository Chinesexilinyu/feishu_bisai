import jwt
import time
from .key_manager import KeyManager
from .token_issuer import TokenIssuer

class TokenValidator:
    def __init__(self, key_manager: KeyManager = None):
        self.key_manager = key_manager or KeyManager()
        self.token_issuer = TokenIssuer()

    def verify_token(self, token: str) -> dict:
        try:
            payload = jwt.decode(
                token,
                self.key_manager.public_key,
                algorithms=["RS256"],
                options={"verify_exp": True},
                leeway=60,  # 允许60秒的时钟偏差
                audience="agent-service"
            )
            
            # 检查Token是否被吊销
            if self.token_issuer.is_token_revoked(payload["jti"]):
                return {"valid": False, "payload": None, "error": "TOKEN_REVOKED"}
            
            return {
                "valid": True,
                "payload": payload,
                "error": None
            }
        except jwt.ExpiredSignatureError:
            return {"valid": False, "payload": None, "error": "TOKEN_EXPIRED"}
        except jwt.InvalidSignatureError:
            return {"valid": False, "payload": None, "error": "INVALID_SIGNATURE"}
        except Exception as e:
            return {"valid": False, "payload": None, "error": str(e)}
