import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
import os
import csv
from io import StringIO

class AuditLogger:
    def __init__(self, log_path: str = None):
        self.log_path = log_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "audit_logs.jsonl"
        )
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def _generate_audit_id(self, event_type: str, decision: str) -> str:
        """生成唯一审计ID，格式：audit-{事件类型}-{决策结果}-{时间戳}-{8位UUID}"""
        event_abbr = event_type.replace("_", "")[:8].upper()
        decision_abbr = "ALLOW" if decision == "ALLOW" else "DENY"
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        uuid_suffix = uuid.uuid4().hex[:8]
        return f"audit-{event_abbr}-{decision_abbr}-{timestamp}-{uuid_suffix}"

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
            "audit_id": self._generate_audit_id(event_type, decision),
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
    
    def query_logs(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        decision: Optional[str] = None,
        agent_id: Optional[str] = None,
        risk_level: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        order: str = "desc"  # desc: 最新的在前，asc: 最早的在前
    ) -> List[Dict[str, Any]]:
        """
        多条件查询审计日志
        :param start_time: 开始时间，ISO格式如"2026-05-01T00:00:00"
        :param end_time: 结束时间，ISO格式
        :param decision: 决策结果：ALLOW/DENY
        :param agent_id: 操作主体Agent ID
        :param risk_level: 风险等级：LOW/MEDIUM/HIGH
        :param limit: 返回数量限制
        :param offset: 偏移量
        :param order: 排序方式：desc(最新在前)/asc(最早在前)
        :return: 符合条件的审计日志列表
        """
        all_logs = []
        
        with open(self.log_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    log = json.loads(line)
                except json.JSONDecodeError:
                    continue
                
                # 时间过滤
                if start_time and log["timestamp"] < start_time:
                    continue
                if end_time and log["timestamp"] > end_time:
                    continue
                
                # 决策过滤
                if decision and log["decision"] != decision:
                    continue
                
                # Agent ID过滤
                if agent_id and log["subject"].get("agent_id") != agent_id:
                    continue
                
                # 风险等级过滤
                if risk_level and log["risk_assessment"].get("risk_level") != risk_level:
                    continue
                
                all_logs.append(log)
        
        # 按时间排序
        all_logs.sort(key=lambda x: x["timestamp"], reverse=(order == "desc"))
        
        # 分页
        start = offset
        end = offset + limit
        return all_logs[start:end]
    
    def export_logs(self, logs: List[Dict[str, Any]], format: str = "json") -> str:
        """
        导出审计日志为指定格式
        :param logs: 要导出的日志列表
        :param format: 导出格式：json/csv
        :return: 导出的内容字符串
        """
        if format.lower() == "json":
            return json.dumps(logs, ensure_ascii=False, indent=2)
        elif format.lower() == "csv":
            if not logs:
                return ""
            
            # 扁平化字段
            def flatten_log(log: Dict[str, Any]) -> Dict[str, Any]:
                flat = {}
                for k, v in log.items():
                    if isinstance(v, dict):
                        for sk, sv in v.items():
                            flat[f"{k}_{sk}"] = sv
                    else:
                        flat[k] = v
                return flat
            
            flat_logs = [flatten_log(log) for log in logs]
            
            # 收集所有可能的字段
            fieldnames = set()
            for log in flat_logs:
                fieldnames.update(log.keys())
            fieldnames = sorted(list(fieldnames))
            
            output = StringIO()
            writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(flat_logs)
            
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def get_statistics(self, start_time: Optional[str] = None, end_time: Optional[str] = None) -> Dict[str, Any]:
        """
        获取审计统计数据
        :param start_time: 开始时间
        :param end_time: 结束时间
        :return: 统计结果
        """
        stats = {
            "total_events": 0,
            "allow_count": 0,
            "deny_count": 0,
            "risk_level_distribution": {"LOW": 0, "MEDIUM": 0, "HIGH": 0},
            "agent_statistics": {}
        }
        
        logs = self.query_logs(start_time=start_time, end_time=end_time, limit=10000)
        
        for log in logs:
            stats["total_events"] += 1
            if log["decision"] == "ALLOW":
                stats["allow_count"] += 1
            else:
                stats["deny_count"] += 1
            
            risk_level = log["risk_assessment"].get("risk_level", "LOW")
            stats["risk_level_distribution"][risk_level] += 1
            
            agent_id = log["subject"].get("agent_id", "unknown")
            if agent_id not in stats["agent_statistics"]:
                stats["agent_statistics"][agent_id] = {"allow": 0, "deny": 0}
            stats["agent_statistics"][agent_id][log["decision"].lower()] += 1
        
        if stats["total_events"] > 0:
            stats["allow_rate"] = round(stats["allow_count"] / stats["total_events"], 4)
            stats["deny_rate"] = round(stats["deny_count"] / stats["total_events"], 4)
        else:
            stats["allow_rate"] = 0
            stats["deny_rate"] = 0
        
        return stats

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
