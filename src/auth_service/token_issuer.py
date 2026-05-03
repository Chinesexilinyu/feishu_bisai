import time
import jwt
import uuid
from .key_manager import KeyManager
import os
import json

class TokenIssuer:
    def __init__(self, key_manager: KeyManager = None):
        self.key_manager = key_manager or KeyManager()
        self.revoked_tokens_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "revoked_tokens.json"
        )
        self._load_revoked_tokens()
    
    def _load_revoked_tokens(self):
        if os.path.exists(self.revoked_tokens_path):
            with open(self.revoked_tokens_path, 'r', encoding='utf-8') as f:
                self.revoked_tokens = set(json.load(f))
        else:
            self.revoked_tokens = set()
    
    def _save_revoked_tokens(self):
        with open(self.revoked_tokens_path, 'w', encoding='utf-8') as f:
            json.dump(list(self.revoked_tokens), f)
    
    def revoke_token(self, jti: str):
        """吊销Token"""
        self.revoked_tokens.add(jti)
        self._save_revoked_tokens()
    
    def is_token_revoked(self, jti: str) -> bool:
        """检查Token是否被吊销"""
        return jti in self.revoked_tokens

    def issue_token(
        self,
        agent_id: str,
        agent_role: str,
        agent_name: str,
        capabilities: list,
        delegated_user: dict = None,
        expires_in: int = 7200,
        chain_of_trust: list = None,
        parent_token_id: str = None
    ) -> str:
        now = int(time.time())
        payload = {
            "iss": "agent-auth-service",
            "sub": agent_id,
            "aud": "agent-service",
            "iat": now,
            "exp": now + expires_in,
            "jti": str(uuid.uuid4()),
            "agent_id": agent_id,
            "agent_role": agent_role,
            "agent_name": agent_name,
            "capabilities": capabilities,
            "delegated_user": delegated_user,
            "chain_of_trust": chain_of_trust or [],
            "parent_token_id": parent_token_id
        }

        if delegated_user and not chain_of_trust:
            payload["chain_of_trust"].append({
                "agent_id": delegated_user["user_id"],
                "agent_type": "human",
                "action": "initiate",
                "timestamp": now
            })

        token = jwt.encode(
            payload,
            self.key_manager.private_key,
            algorithm="RS256"
        )
        return token, payload["jti"]
