#!/usr/bin/env python3
"""企业数据Agent - 支持独立API服务模式和LLM智能权限验证交互模式"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from pydantic import BaseModel
from src.agents.data_agent import DataAgent
from src.llm.intent_recognizer import IntentRecognizer
import uvicorn
import argparse
import json

app = FastAPI(title="企业数据Agent服务", version="3.0.0")
data_agent = DataAgent()

from typing import Dict, Any

class HandleRequest(BaseModel):
    token: str
    resource: str
    action: str

class TaskRequestModel(BaseModel):
    task_id: str
    task_type: str
    intent: str
    parameters: Dict[str, Any]
    parent_task_id: str = None
    trace_id: str = None
    context: Dict[str, Any] = None
    created_at: int = None
    timeout: int = 300
    status: str = "pending"

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "agent": "data-agent",
        "port": 8002,
        "features": ["feishu:bitable:read", "feishu:bitable:write", "feishu:contact:read"]
    }

@app.post("/handle-request", summary="处理数据访问请求（兼容旧接口）")
async def handle_request(request: HandleRequest, x_trace_id: str = None):
    result = data_agent.handle_request(
        token=request.token,
        resource=request.resource,
        action=request.action,
        trace_id=x_trace_id
    )
    return result

@app.post("/api/v1/task", summary="处理标准化任务请求（新协议）")
async def handle_task(task: TaskRequestModel, authorization: str = None):
    if not authorization or not authorization.startswith("Bearer "):
        return {
            "code": "40102",
            "message": "Invalid authorization header",
            "task_id": task.task_id,
            "status": "rejected",
            "trace_id": task.trace_id
        }
    token = authorization.split(" ")[1]
    result = data_agent.handle_task(token=token, task_dict=task.dict())
    return result


def interactive_mode():
    """LLM智能权限验证模式 — 自然语言 + 身份来源区分"""
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8') if hasattr(sys.stdout, 'buffer') else sys.stdout

    intent_recognizer = IntentRecognizer()

    print("=" * 70)
    print(" 企业数据Agent 交互式控制台 v3.0 (LLM意图识别 + 身份区分)")
    print("=" * 70)
    print(" 此Agent负责: 飞书多维表格/通讯录/日历数据访问")
    print(" 具备权限: bitable, contact, calendar (读写)")
    print(" 禁止操作: 外部网络访问, 委托其他Agent")
    print("=" * 70)
    print(" 支持自然语言输入，Agent会通过LLM自动判断意图：")
    print("  - 如需读取内部数据 → 验证调用方身份后执行 (DocAgent允许/WebAgent拒绝)")
    print("  - 如需外部搜索 → 拒绝（DataAgent无外部网络权限）")
    print(" 快捷命令: 'read-data' | 'test-auth' | 'health' | 'exit'")
    print("=" * 70)

    while True:
        try:
            user_input = input("\n[DataAgent] 请输入指令: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ["exit", "quit", "q"]:
            print("[DataAgent] 企业数据Agent 已退出")
            break

        # ---- 快捷命令向后兼容 ----
        if user_input.lower() == "help":
            print("\n 使用说明:")
            print("  - 自然语言: 直接输入如'读取表格数据'/'生成数据报告'等")
            print("  - test-auth   : 测试权限→无效Token(401)+WebAgent越权(403)")
            print("  - read-data   : 用自身Token读取数据")
            print("  - health      : 查看自身状态")
            print("  - exit        : 退出")
            continue

        if user_input.lower() == "health":
            print("\n[DataAgent] 自身状态: online (端口8002)")
            print("[DataAgent] 权限: feishu:bitable, feishu:contact, feishu:calendar")
            print("[DataAgent] 禁止: 外部网络访问, 委托其他Agent")
            continue

        if user_input.lower() == "test-auth":
            print("\n[DataAgent] ===== 权限验证测试 =====")

            print("\n[DataAgent] 测试1: 无效Token → 预期401...")
            result = data_agent.handle_request(
                token="invalid_token_12345",
                resource="feishu:bitable",
                action="read"
            )
            print("[DataAgent]   结果: code={}, error={}".format(
                result["code"], result.get("error", "")))
            if result["code"] == 401:
                print("[DataAgent]   PASS: Token验证成功拦截")

            print("\n[DataAgent] 测试2: WebAgent越权请求 → 预期403...")
            print("[DataAgent]   场景: 外部检索Agent尝试读取企业内部数据")
            from src.agents.web_agent import WebAgent
            wa = WebAgent()
            token, _ = wa.get_identity_token(expires_in=3600)
            result = data_agent.handle_request(
                token=token,
                resource="feishu:bitable",
                action="read"
            )
            print("[DataAgent]   结果: code={}, error={}".format(
                result["code"], result.get("error", "")))
            if result["code"] == 403:
                print("[DataAgent]   PASS: 越权请求成功拦截！")
                print("[DataAgent]   来源: WebAgent(外部检索) → DataAgent拒绝")
                print("[DataAgent]   原因: WebAgent无'delegate:*'权限")
            continue

        if user_input.lower() == "read-data":
            print("\n[DataAgent] 用自身Token读取多维表格...")
            token, _ = data_agent.get_identity_token(expires_in=3600)
            result = data_agent.handle_request(
                token=token,
                resource="feishu:bitable",
                action="read"
            )
            print("[DataAgent] success={}, tables={}, total_rows={}".format(
                result.get("success", False),
                result.get("data", {}).get("table_count", 0),
                result.get("data", {}).get("total_rows", 0),
            ))
            continue

        # ---- LLM 意图识别：自然语言输入 ----
        print("\n[DataAgent] 正在使用LLM分析你的意图...")
        try:
            intent = intent_recognizer.analyze(user_input)
        except Exception as e:
            print("[DataAgent] LLM意图识别失败: {}".format(str(e)[:100]))
            continue

        print("[DataAgent] 意图识别结果:")
        print(json.dumps(intent, ensure_ascii=False, indent=2))

        need_data = intent["call_data_agent"]["decision"] == "yes"
        need_web = intent["call_web_agent"]["decision"] == "yes"

        if need_data:
            print("\n[DataAgent] LLM判断: 需要读取企业内部数据。")
            print("[DataAgent] 使用自身Token读取飞书多维表格...")
            token, _ = data_agent.get_identity_token(expires_in=3600)
            result = data_agent.handle_request(
                token=token,
                resource="feishu:bitable",
                action="read"
            )
            if result.get("success"):
                tables = result.get("data", {}).get("tables", {})
                print("[DataAgent] 读取成功: {}张表, {}行".format(
                    len(tables), result["data"].get("total_rows", 0)))
                for tn, td in tables.items():
                    print("[DataAgent]   [{}]: {}行, 字段={}".format(
                        tn, td["row_count"], td.get("fields", [])))
            else:
                print("[DataAgent] 读取失败: code={}, error={}".format(
                    result.get("code"), result.get("error", "")))

        if need_web:
            print("\n[DataAgent] LLM判断: 需要外部检索")
            print("[DataAgent] *** 拒绝 ***")
            print("[DataAgent] 企业数据Agent无外部网络访问权限(capabilities中无web:search)")
            print("[DataAgent] 如需搜索外部信息，请使用外部检索Agent:")
            print("[DataAgent]   python run_web_agent.py")

        if not need_data and not need_web:
            print("\n[DataAgent] 总结: {}".format(intent.get("summary", "未知意图")))


def run_server():
    """启动API服务模式"""
    print("=" * 70)
    print(" 企业数据Agent 服务 v3.0 (端口: 8002)")
    print(" API文档: http://localhost:8002/docs")
    print(" 健康检查: http://localhost:8002/health")
    print(" 权限: Token验证 + 委托方身份校验 + 审计日志")
    print("=" * 70)
    uvicorn.run(app, host="0.0.0.0", port=8002, timeout_keep_alive=180)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="企业数据Agent v3.0")
    parser.add_argument("--server", action="store_true", help="API服务模式")
    args = parser.parse_args()

    if args.server:
        run_server()
    else:
        interactive_mode()
