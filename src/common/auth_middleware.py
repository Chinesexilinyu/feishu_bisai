#!/usr/bin/env python3
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from src.auth_service.token_validator import TokenValidator
from src.audit_service.logger import AuditLogger
import time

class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, excluded_paths: list = None):
        super().__init__(app)
        self.token_validator = TokenValidator()
        self.audit_logger = AuditLogger()
        self.excluded_paths = excluded_paths or ["/health", "/docs", "/openapi.json"]
    
    async def dispatch(self, request: Request, call_next):
        # 跳过不需要鉴权的路径
        for path in self.excluded_paths:
            if request.url.path.startswith(path):
                return await call_next(request)
        
        # 获取Authorization头
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
        
        token = auth_header.split(" ")[1]
        verify_result = self.token_validator.verify_token(token)
        
        if not verify_result["valid"]:
            # 记录审计日志
            self.audit_logger.log_authorization_event(
                event_type="AUTHORIZATION_DECISION",
                decision="DENY",
                subject={"agent_id": "unknown"},
                resource={"type": request.url.path, "action": request.method},
                authorization={"requested_capability": request.url.path, "reason": verify_result["error"]},
                trace_id=request.headers.get("X-Trace-ID", f"trace-{int(time.time())}")
            )
            raise HTTPException(status_code=401, detail=verify_result["error"])
        
        # 将Token Payload放入请求状态
        request.state.token_payload = verify_result["payload"]
        request.state.agent_id = verify_result["payload"]["agent_id"]
        
        # 继续处理请求
        response = await call_next(request)
        return response
