#!/usr/bin/env python3
"""飞书文档助手Agent - 交互式自然语言控制台 + API服务"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from src.agents.doc_agent import DocAgent
from src.llm.intent_recognizer import IntentRecognizer
from src.llm import get_llm_client
import uvicorn
import argparse
import json
import requests

app = FastAPI(title="文档助手Agent服务", version="3.0.0")
doc_agent = None
intent_recognizer = None
llm_client = None

class GenerateReportRequest(BaseModel):
    user_id: str
    user_name: str
    user_role: str
    keyword: str = None
    need_web_search: bool = False

class NLInstructionRequest(BaseModel):
    user_id: str
    user_name: str
    user_role: str
    instruction: str

@app.get("/health")
async def health():
    agent_status = doc_agent.check_agent_health() if doc_agent else {}
    return {
        "status": "healthy",
        "agent": "doc-assistant",
        "port": 8001,
        "dependencies": agent_status
    }

@app.post("/generate-report")
async def generate_report(request: GenerateReportRequest):
    delegate_user = {
        "user_id": request.user_id,
        "user_name": request.user_name,
        "user_role": request.user_role
    }
    init_result = doc_agent.initiate_task(
        delegated_user=delegate_user,
        need_data=True,
        need_web=request.need_web_search,
        keyword=request.keyword
    )
    if not init_result["can_proceed"]:
        return {
            "success": False,
            "error": init_result["error"],
            "code": 503,
            "trace_id": init_result["trace_id"]
        }
    result = doc_agent.generate_novel_analysis_report(
        delegated_user=delegate_user,
        keyword=request.keyword,
        need_web_search=request.need_web_search,
        trace_id=init_result["trace_id"]
    )
    return result

@app.post("/nl-execute")
async def nl_execute(request: NLInstructionRequest):
    intent = intent_recognizer.analyze(request.instruction)
    if intent["task_type"] == "generate_report":
        need_data = intent["call_data_agent"]["decision"] == "yes"
        call_web = intent["call_web_agent"]["decision"] == "yes"
        keyword = intent["call_web_agent"].get("keyword")
        
        # 预检Agent健康状态，生成Trace ID并记录审计日志
        init_result = doc_agent.initiate_task(
            delegated_user={
                "user_id": request.user_id,
                "user_name": request.user_name,
                "user_role": request.user_role
            },
            need_data=need_data,
            need_web=call_web,
            keyword=keyword
        )
        
        if not init_result["can_proceed"]:
            return {
                "success": False,
                "error": init_result["error"],
                "code": 503,
                "trace_id": init_result["trace_id"],
                "intent": intent,
                "instruction": request.instruction
            }
        
        result = doc_agent.generate_novel_analysis_report(
            delegated_user={
                "user_id": request.user_id,
                "user_name": request.user_name,
                "user_role": request.user_role
            },
            keyword=keyword,
            need_web_search=call_web,
            trace_id=init_result["trace_id"]
        )
        return {"intent": intent, **result, "instruction": request.instruction}
    return {"success": False, "error": "不支持的指令类型", "intent": intent, "code": 400}


def interactive_mode():
    """交互式自然语言模式 — 通过HTTP协议与DataAgent/WebAgent通信"""
    global doc_agent, intent_recognizer, llm_client
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8') if hasattr(sys.stdout, 'buffer') else sys.stdout

    doc_agent = DocAgent()
    intent_recognizer = IntentRecognizer()
    llm_client = get_llm_client()

    print("=" * 70)
    print(" 飞书文档助手Agent 交互式控制台 v3.0 (LLM意图识别 + HTTP协议)")
    print("=" * 70)
    print(" 架构说明：")
    print("   DocAgent(8001) --HTTP--> DataAgent(8002)  [企业数据]")
    print("   DocAgent(8001) --HTTP--> WebAgent(8003)   [外部检索]")
    print("   必须先启动 DataAgent 和 WebAgent 服务")
    print("=" * 70)
    print(" 输入自然语言指令 | 'health' 检查Agent状态 | 'exit' 退出")
    print("=" * 70)

    user_info = {"user_id": "user-001", "user_name": "张三", "user_role": "admin"}

    while True:
        try:
            user_input = input("\n[DocAgent] 请输入指令: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ["exit", "quit", "q"]:
            print("再见！")
            break
        if user_input.lower() == "health":
            status = doc_agent.check_agent_health()
            print("\n[DocAgent] 依赖Agent状态:")
            print("[DocAgent]   企业数据Agent (8002): {}".format(
                "在线" if status["data_agent"] else "离线 - 请运行 python run_data_agent.py --server"))
            print("[DocAgent]   外部检索Agent (8003): {}".format(
                "在线" if status["web_agent"] else "离线 - 请运行 python run_web_agent.py --server"))
            continue
        if user_input.lower() == "help":
            print("\n 支持的指令:")
            print("  - 生成番茄小说数据分析报告")
            print("  - 读取表格数据，结合外部检索知识生成分析报告")
            print("  - health  检查Agent状态")
            print("  - exit    退出")
            continue

        print("\n[DocAgent] 正在使用LLM分析意图...")
        intent = intent_recognizer.analyze(user_input)
        print("[DocAgent] 意图识别结果:")
        print(json.dumps(intent, ensure_ascii=False, indent=2))

        if intent["task_type"] != "generate_report":
            print("[DocAgent] 不支持的任务类型: {}".format(intent["task_type"]))
            continue

        need_data = intent["call_data_agent"]["decision"] == "yes"
        need_web = intent["call_web_agent"]["decision"] == "yes"
        keyword = intent["call_web_agent"].get("keyword")

        if not need_data:
            print("[DocAgent] LLM判断不需要读取内部数据")
        if not need_web:
            print("[DocAgent] LLM判断不需要外部检索")

        # ---- 严格权限控制：调用前预检健康状态（通过initiate_task统一入口，确保Trace ID和审计日志正确生成） ----
        init_result = doc_agent.initiate_task(
            delegated_user=user_info,
            need_data=need_data,
            need_web=need_web,
            keyword=keyword
        )
        task_trace_id = init_result["trace_id"]
        health = init_result["health"]
        
        if need_data and not health["data_agent"]:
            print("[DocAgent] 企业数据Agent未启动！请先运行:")
            print("          python run_data_agent.py --server")
            print("[DocAgent] Trace ID: {} (请使用此ID查询审计日志)".format(task_trace_id))
            continue
        if need_web and not health["web_agent"]:
            print("[DocAgent] 外部检索Agent未启动！无法执行外部检索。")
            print("[DocAgent] 备选方案：请使用不含外部检索的指令，如：'生成番茄小说数据分析报告'")
            print("[DocAgent] 或先启动WebAgent: python run_web_agent.py --server")
            print("[DocAgent] 系统将降级为仅内部数据模式...")
            need_web = False  # 自动降级

        if need_data:
            print("[DocAgent] 正在通过HTTP委托企业数据Agent读取数据...")
        if need_web:
            kw_display = keyword if keyword else "番茄小说 热门"
            print("[DocAgent] 正在通过HTTP委托外部检索Agent搜索: {} ...".format(kw_display))

        result = doc_agent.generate_novel_analysis_report(
            delegated_user=user_info,
            keyword=keyword,
            need_web_search=need_web,
            trace_id=task_trace_id
        )

        print("\n[DocAgent] 执行完成！")
        if result.get("success"):
            # 如果有 WebAgent 降级警告，优先显示
            warning = (result.get("data") or {}).get("web_agent_warning")
            if warning:
                print("[DocAgent] {}".format(warning.replace("[DocAgent] ", "")))
            print("[DocAgent] 报告已生成并写入飞书文档")
            print("[DocAgent] 文档链接: {}".format(result["data"]["report_url"]))
            print("[DocAgent] Trace ID: {}".format(result.get("trace_id", "N/A")))
            try:
                summary_prompt = "根据以下执行结果生成友好的自然语言总结:\n" + json.dumps({
                    "success": True,
                    "report_url": result["data"]["report_url"]
                }, ensure_ascii=False)
                summary = llm_client.chat([
                    {"role": "system", "content": "你是友好的助手，用中文总结执行结果。"},
                    {"role": "user", "content": summary_prompt}
                ], timeout=60)
                print("\n[DocAgent] 结果总结:\n{}".format(summary))
            except Exception:
                pass
        else:
            print("[DocAgent] 执行失败: {}".format(result.get("error")))
            print("[DocAgent] 错误码: {}".format(result.get("code")))


def run_server():
    global doc_agent, intent_recognizer, llm_client
    doc_agent = DocAgent()
    intent_recognizer = IntentRecognizer()
    llm_client = get_llm_client()
    print("=" * 70)
    print(" 飞书文档助手Agent 服务 v3.0 (端口: 8001)")
    print(" API文档: http://localhost:8001/docs")
    print(" 健康检查: http://localhost:8001/health")
    print(" 架构: DocAgent --HTTP--> DataAgent(8002) + WebAgent(8003)")
    print("=" * 70)
    uvicorn.run(app, host="0.0.0.0", port=8001, timeout_keep_alive=180)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="飞书文档助手Agent v3.0")
    parser.add_argument("--server", action="store_true", help="API服务模式")
    args = parser.parse_args()

    if args.server:
        run_server()
    else:
        interactive_mode()
