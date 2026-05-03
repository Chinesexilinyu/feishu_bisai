from .base_agent import BaseAgent
from src.utils.feishu_client import FeishuClient
import uuid

class DataAgent(BaseAgent):
    def __init__(self):
        super().__init__("data-agent")
        self.feishu_client = FeishuClient()

    def handle_request(self, token: str, resource: str, action: str, trace_id: str = None) -> dict:
        """处理来自其他Agent的请求"""
        # 使用传入的trace_id或生成新的
        trace_id = trace_id or self.trace_manager.get_trace_id() or str(uuid.uuid4())
        
        # 验证Token
        verify_result = self.token_validator.verify_token(token)
        if not verify_result["valid"]:
            # 记录审计日志
            self.audit_logger.log_authorization_event(
                event_type="AUTHORIZATION_DECISION",
                decision="DENY",
                subject={"agent_id": "unknown"},
                resource={"type": resource, "action": action},
                authorization={"requested_capability": f"{resource}:{action}", "reason": verify_result["error"]},
                trace_id=trace_id
            )
            return {"success": False, "error": verify_result["error"], "code": 401, "trace_id": trace_id}

        payload = verify_result["payload"]
        from_agent_id = payload["agent_id"]
        delegated_user = payload.get("delegated_user")

        # 权限校验
        requested_cap = f"{resource}:{action}"
        auth_result = self.delegation_handler.validate_delegation(
            from_agent_id=from_agent_id,
            to_agent_id=self.agent_id,
            requested_cap=requested_cap,
            delegated_user=delegated_user
        )

        # 记录审计日志
        self.audit_logger.log_authorization_event(
            event_type="AUTHORIZATION_DECISION",
            decision="ALLOW" if auth_result["authorized"] else "DENY",
            subject={"agent_id": from_agent_id, "agent_name": payload.get("agent_name")},
            resource={"type": resource, "action": action},
            authorization={
                "requested_capability": requested_cap,
                "effective_permissions": auth_result["effective_permissions"],
                "reason": auth_result["reason"]
            },
            trace_id=trace_id,
            delegation_context={
                "delegated_user": delegated_user,
                "chain_depth": len(payload.get("chain_of_trust", [])),
                "chain_path": [item["agent_id"] for item in payload.get("chain_of_trust", [])]
            }
        )

        if not auth_result["authorized"]:
            return {"success": False, "error": auth_result["reason"], "code": 403}

        # 执行操作
        try:
            if resource == "feishu:bitable" and action == "read":
                data = self.feishu_client.get_all_table_records()
                return {"success": True, "data": data, "code": 200}
            else:
                return {"success": False, "error": "UNSUPPORTED_OPERATION", "code": 400}
        except Exception as e:
            return {"success": False, "error": str(e), "code": 500}

    def handle_task(self, token: str, task_dict: dict) -> dict:
        """处理标准化任务请求"""
        from src.common.agent_protocol import TaskRequest, TaskResponse, ErrorCode
        task = TaskRequest.from_dict(task_dict)
        trace_id = task.trace_id or str(uuid.uuid4())

        # 验证Token
        verify_result = self.token_validator.verify_token(token)
        if not verify_result["valid"]:
            self.audit_logger.log_authorization_event(
                event_type="AUTHORIZATION_DECISION",
                decision="DENY",
                subject={"agent_id": "unknown"},
                resource={"type": task.task_type, "action": task.intent},
                authorization={"requested_capability": task.task_type, "reason": verify_result["error"]},
                trace_id=trace_id
            )
            return TaskResponse.rejected(
                task_id=task.task_id,
                error_code=ErrorCode.TOKEN_INVALID,
                error_message=verify_result["error"],
                trace_id=task.trace_id
            ).to_dict()

        payload = verify_result["payload"]
        from_agent_id = payload["agent_id"]
        delegated_user = payload.get("delegated_user")

        # 权限校验
        requested_cap = task.task_type
        auth_result = self.delegation_handler.validate_delegation(
            from_agent_id=from_agent_id,
            to_agent_id=self.agent_id,
            requested_cap=requested_cap,
            delegated_user=delegated_user
        )

        self.audit_logger.log_authorization_event(
            event_type="AUTHORIZATION_DECISION",
            decision="ALLOW" if auth_result["authorized"] else "DENY",
            subject={"agent_id": from_agent_id, "agent_name": payload.get("agent_name")},
            resource={"type": task.task_type, "action": task.intent},
            authorization={
                "requested_capability": requested_cap,
                "effective_permissions": auth_result["effective_permissions"],
                "reason": auth_result["reason"]
            },
            trace_id=trace_id,
            delegation_context={
                "delegated_user": delegated_user,
                "chain_depth": len(payload.get("chain_of_trust", [])),
                "chain_path": [item["agent_id"] for item in payload.get("chain_of_trust", [])]
            }
        )

        if not auth_result["authorized"]:
            return TaskResponse.rejected(
                task_id=task.task_id,
                error_code=ErrorCode.PERMISSION_DENIED,
                error_message=auth_result["reason"],
                trace_id=task.trace_id
            ).to_dict()

        # 执行任务
        try:
            task.status = "running"
            if task.task_type == "feishu:bitable:read":
                data = self.feishu_client.get_all_table_records()
                return TaskResponse.success(
                    task_id=task.task_id,
                    data={"records": data},
                    trace_id=task.trace_id
                ).to_dict()
            else:
                return TaskResponse.rejected(
                    task_id=task.task_id,
                    error_code=ErrorCode.CAPABILITY_NOT_SUPPORTED,
                    error_message=f"Unsupported task type: {task.task_type}",
                    trace_id=task.trace_id
                ).to_dict()
        except Exception as e:
            return TaskResponse.failed(
                task_id=task.task_id,
                error_code=ErrorCode.EXECUTION_FAILED,
                error_message=str(e),
                trace_id=task.trace_id
            ).to_dict()
