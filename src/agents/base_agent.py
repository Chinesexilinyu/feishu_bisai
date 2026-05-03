from src.auth_service.token_issuer import TokenIssuer
from src.auth_service.token_validator import TokenValidator
from src.policy_engine.delegation import DelegationHandler
from src.policy_engine.static_policy import StaticPolicy
from src.audit_service.logger import AuditLogger
from src.audit_service.tracer import TraceManager
from src.common.agent_protocol import TaskRequest, TaskResponse, ErrorCode, AgentProtocol
import requests
from typing import Optional, Dict, Any

class BaseAgent:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.token_issuer = TokenIssuer()
        self.token_validator = TokenValidator()
        self.delegation_handler = DelegationHandler()
        self.static_policy = StaticPolicy()
        self.audit_logger = AuditLogger()
        self.trace_manager = TraceManager()
        self.agent_endpoints = {
            "doc_agent": "http://localhost:8001",
            "data_agent": "http://localhost:8002",
            "web_agent": "http://localhost:8003"
        }

    def get_identity_token(self, delegated_user: dict = None, expires_in: int = 7200, chain_of_trust: list = None, parent_token_id: str = None):
        """获取Agent的身份Token"""
        from src.policy_engine.static_policy import StaticPolicy
        agent_info = StaticPolicy().get_agent_info(self.agent_id)
        return self.token_issuer.issue_token(
            agent_id=self.agent_id,
            agent_role=agent_info["role"],
            agent_name=agent_info["name"],
            capabilities=agent_info["capabilities"],
            delegated_user=delegated_user,
            expires_in=expires_in,
            chain_of_trust=chain_of_trust,
            parent_token_id=parent_token_id
        )

    def create_task_request(
        self,
        task_type: str,
        intent: str,
        parameters: Dict[str, Any],
        parent_task_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> TaskRequest:
        """创建标准化任务请求"""
        return TaskRequest(
            task_type=task_type,
            intent=intent,
            parameters=parameters,
            parent_task_id=parent_task_id,
            trace_id=trace_id,
            context=context
        )

    def delegate_task(self, target_agent_id: str, task: TaskRequest, delegated_user: dict = None) -> TaskResponse:
        """委托任务给其他Agent"""
        if target_agent_id not in self.agent_endpoints:
            return TaskResponse.rejected(
                task_id=task.task_id,
                error_code=ErrorCode.RESOURCE_NOT_FOUND,
                error_message=f"Agent {target_agent_id} not found",
                trace_id=task.trace_id
            )

        if not self.delegation_handler.can_delegate(self.agent_id, target_agent_id, task.task_type):
            return TaskResponse.rejected(
                task_id=task.task_id,
                error_code=ErrorCode.DELEGATION_NOT_ALLOWED,
                error_message=f"Not allowed to delegate task {task.task_type} to {target_agent_id}",
                trace_id=task.trace_id
            )

        token, token_id = self.get_identity_token(
            delegated_user=delegated_user,
            chain_of_trust=AgentProtocol.add_trust_chain({}, self.agent_id, f"delegate_task:{task.task_type}"),
            parent_token_id=token_id if 'token_id' in locals() else None
        )

        try:
            response = requests.post(
                f"{self.agent_endpoints[target_agent_id]}/api/v1/task",
                headers={"Authorization": f"Bearer {token}"},
                json=task.to_dict(),
                timeout=task.timeout
            )
            response.raise_for_status()
            data = response.json()
            return TaskResponse(
                task_id=data["task_id"],
                status=data["status"],
                data=data.get("data", {}),
                error_code=ErrorCode(data.get("code", ErrorCode.SUCCESS.value)),
                error_message=data.get("message"),
                trace_id=data.get("trace_id")
            )
        except requests.exceptions.RequestException as e:
            return TaskResponse.failed(
                task_id=task.task_id,
                error_code=ErrorCode.AGENT_UNAVAILABLE,
                error_message=f"Failed to connect to {target_agent_id}: {str(e)}",
                trace_id=task.trace_id
            )
