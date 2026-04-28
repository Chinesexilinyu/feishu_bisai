import json
import uuid
from datetime import datetime
from typing import List, Optional
import os

class AuditLogger:
    def __init__(self, log_path: str = None):
        self.log_path = log_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "audit_logs.jsonl"
        )
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def log_authorization_event(
        self,
        event_type: str,
        decision: str,
        subject: dict,
        resource: dict,
        authorization: dict,
        trace_id: str,
        delegation_context: dict = None
    ):
        audit_log = {
            "audit_id": f"audit-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}",
            "timestamp": datetime.utcnow().isoformat(),
            "trace_id": trace_id,
            "event_type": event_type,
            "event_category": "A2A_AUTH",
            "decision": decision,
            "subject": subject,
            "delegation_context": delegation_context,
            "resource": resource,
            "authorization": authorization,
            "risk_assessment": self._assess_risk(decision, authorization, delegation_context)
        }
        
        with open(self.log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(audit_log, ensure_ascii=False) + '\n')
        
        return audit_log["audit_id"]

    def _assess_risk(self, decision: str, authorization: dict, delegation_context: dict = None):
        risk_score = 0
        risk_factors = []
        
        if decision == "DENY":
            risk_score += 20
            risk_factors.append("AUTHORIZATION_DENIED")
        
        if delegation_context and delegation_context.get("chain_depth", 0) > 3:
            risk_score += 30
            risk_factors.append("DEEP_DELEGATION_CHAIN")
        
        risk_level = "HIGH" if risk_score >= 50 else "MEDIUM" if risk_score >= 30 else "LOW"
        return {
            "risk_level": risk_level,
            "risk_score": risk_score,
            "risk_factors": risk_factors
        }
