from src.auth_service.token_issuer import TokenIssuer
from src.auth_service.token_validator import TokenValidator
from src.policy_engine.delegation import DelegationHandler
from src.policy_engine.static_policy import StaticPolicy
from src.audit_service.logger import AuditLogger
from src.audit_service.tracer import TraceManager

class BaseAgent:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.token_issuer = TokenIssuer()
        self.token_validator = TokenValidator()
        self.delegation_handler = DelegationHandler()
        self.static_policy = StaticPolicy()
        self.audit_logger = AuditLogger()
        self.trace_manager = TraceManager()

    def get_identity_token(self, delegated_user: dict = None, expires_in: int = 7200):
        """获取Agent的身份Token"""
        from src.policy_engine.static_policy import StaticPolicy
        agent_info = StaticPolicy().get_agent_info(self.agent_id)
        return self.token_issuer.issue_token(
            agent_id=self.agent_id,
            agent_role=agent_info["role"],
            agent_name=agent_info["name"],
            capabilities=agent_info["capabilities"],
            delegated_user=delegated_user,
            expires_in=expires_in
        )
