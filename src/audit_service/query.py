import json
from typing import List, Optional
import os
from datetime import datetime

class AuditQuery:
    def __init__(self, log_path: str = None):
        self.log_path = log_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "audit_logs.jsonl"
        )

    def _load_all_logs(self) -> List[dict]:
        logs = []
        if not os.path.exists(self.log_path):
            return logs
        with open(self.log_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    logs.append(json.loads(line))
        return logs

    def query_by_trace_id(self, trace_id: str) -> List[dict]:
        logs = self._load_all_logs()
        return [log for log in logs if log.get("trace_id") == trace_id]

    def query_denied_events(self, time_range_hours: int = 1) -> List[dict]:
        logs = self._load_all_logs()
        result = []
        now = datetime.utcnow()
        for log in logs:
            if log.get("decision") == "DENY":
                log_time = datetime.fromisoformat(log["timestamp"])
                if (now - log_time).total_seconds() <= time_range_hours * 3600:
                    result.append(log)
        return result

    def query_by_agent(self, agent_id: str, time_range_hours: int = 24) -> List[dict]:
        logs = self._load_all_logs()
        result = []
        now = datetime.utcnow()
        for log in logs:
            if log.get("subject", {}).get("agent_id") == agent_id:
                log_time = datetime.fromisoformat(log["timestamp"])
                if (now - log_time).total_seconds() <= time_range_hours * 3600:
                    result.append(log)
        return result
