#!/usr/bin/env python3
"""审计日志查询工具"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import argparse
import json
import datetime
from src.audit_service.logger import AuditLogger

def format_log_table(logs):
    """以表格格式输出日志"""
    if not logs:
        print("未找到匹配的审计日志")
        return
    
    headers = ["审计ID", "时间戳", "Trace ID", "决策", "Agent ID", "资源类型", "错误码", "风险等级"]
    col_widths = [45, 25, 36, 6, 15, 20, 8, 8]
    
    # 打印表头
    print("".join([headers[i].ljust(col_widths[i]) for i in range(len(headers))]))
    print("-" * sum(col_widths))
    
    # 打印内容
    for log in logs:
        error_code = log["authorization"].get("reason", "SUCCESS") if log["decision"] == "DENY" else "0"
        row = [
            log["audit_id"].ljust(col_widths[0]),
            log["timestamp"].ljust(col_widths[1]),
            log["trace_id"].ljust(col_widths[2]),
            log["decision"].ljust(col_widths[3]),
            log["subject"].get("agent_id", "unknown").ljust(col_widths[4]),
            log["resource"].get("type", "unknown").ljust(col_widths[5]),
            str(error_code).ljust(col_widths[6]),
            log["risk_assessment"]["risk_level"].ljust(col_widths[7])
        ]
        print("".join(row))

def main():
    parser = argparse.ArgumentParser(description="Agent权限系统审计日志查询工具")
    parser.add_argument("--traceid", type=str, help="按Trace ID查询审计日志")
    parser.add_argument("--all", action="store_true", help="查看所有审计日志")
    parser.add_argument("--error-code", type=str, help="按错误码筛选日志（如40302、50301）")
    parser.add_argument("--start-time", type=str, help="开始时间（ISO格式，如2026-05-01T00:00:00）")
    parser.add_argument("--end-time", type=str, help="结束时间（ISO格式）")
    parser.add_argument("--limit", type=int, default=100, help="返回日志数量限制，默认100")
    parser.add_argument("--order", type=str, choices=["desc", "asc"], default="desc", help="排序方式：desc最新在前，asc最早在前")
    parser.add_argument("--format", type=str, choices=["table", "json"], default="table", help="输出格式，默认table")
    
    args = parser.parse_args()
    logger = AuditLogger()
    
    # 构建查询条件
    query_params = {
        "limit": args.limit,
        "order": args.order
    }
    
    if args.start_time:
        query_params["start_time"] = args.start_time
    if args.end_time:
        query_params["end_time"] = args.end_time
    
    # 执行查询
    logs = logger.query_logs(**query_params)
    
    # 按Trace ID过滤
    if args.traceid:
        logs = [log for log in logs if log["trace_id"] == args.traceid]
    
    # 按错误码过滤
    if args.error_code:
        filtered = []
        for log in logs:
            error_code = log["authorization"].get("reason", "SUCCESS") if log["decision"] == "DENY" else "0"
            if str(error_code) == str(args.error_code):
                filtered.append(log)
        logs = filtered
    
    # 输出结果
    if args.format == "json":
        print(json.dumps(logs, ensure_ascii=False, indent=2))
    else:
        format_log_table(logs)
    
    # 如果是查询单个Trace ID，输出完整上下文
    if args.traceid and len(logs) == 1:
        print("\n" + "="*100)
        print("完整审计日志上下文:")
        print("="*100)
        print(json.dumps(logs[0], ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
