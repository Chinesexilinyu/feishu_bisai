#!/usr/bin/env python3
"""外部检索Agent - 支持独立API服务模式和LLM智能意图识别交互模式"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from pydantic import BaseModel
from src.agents.web_agent import WebAgent
from src.llm.intent_recognizer import IntentRecognizer
import uvicorn
import argparse
import json

app = FastAPI(title="外部检索Agent服务", version="3.0.0")
web_agent = WebAgent()

class SearchRequest(BaseModel):
    keyword: str

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "agent": "web-agent",
        "port": 8003,
        "features": ["web:search", "web:scrape"]
    }

@app.post("/search-novel-info", summary="搜索番茄小说相关信息")
async def search_novel_info(request: SearchRequest):
    result = web_agent.search_tomato_novel_info(keyword=request.keyword)
    return result

@app.post("/try-access-internal", summary="越权访问测试")
async def try_access_internal():
    result = web_agent.try_access_internal_data()
    return result


def interactive_mode():
    """LLM智能意图识别模式 — 自然语言+权限边界自动检测"""
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8') if hasattr(sys.stdout, 'buffer') else sys.stdout

    intent_recognizer = IntentRecognizer()

    print("=" * 70)
    print(" 外部检索Agent 交互式控制台 v3.0 (LLM意图识别)")
    print("=" * 70)
    print(" 此Agent负责: 外部网络公开信息搜索与抓取")
    print(" 具备权限: web:search, web:scrape")
    print(" 禁止操作: 访问飞书企业内部数据, 委托其他Agent")
    print("=" * 70)
    print(" 支持自然语言输入，Agent会通过LLM自动判断你的意图：")
    print("  - 如需搜索外部信息 → 自动执行多源检索")
    print("  - 如需读取内部数据 → 自动尝试访问并展示权限拦截结果")
    print(" 快捷命令: 'search <关键词>' | 'test-unauthorized' | 'health' | 'exit'")
    print("=" * 70)

    while True:
        try:
            user_input = input("\n[WebAgent] 请输入指令: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ["exit", "quit", "q"]:
            print("[WebAgent] 外部检索Agent 已退出")
            break

        # ---- 快捷命令保持向后兼容 ----
        if user_input.lower() == "help":
            print("\n 使用说明:")
            print("  - 自然语言: 直接输入如'读取表格数据，生成分析报告'/'搜索番茄小说热门信息'")
            print("  - search <关键词> : 直接搜索")
            print("  - test-unauthorized : 手动测试越权拦截")
            print("  - health            : 检查自身状态")
            print("  - exit              : 退出")
            continue

        if user_input.lower() == "health":
            print("\n[WebAgent] 自身状态: online (端口8003)")
            print("[WebAgent] 权限: web:search, web:scrape")
            print("[WebAgent] 禁止: 访问内部数据, 委托其他Agent")
            continue

        if user_input.lower() == "test-unauthorized":
            print("\n[WebAgent] 手动执行越权测试: 尝试访问飞书内部多维表格...")
            print("[WebAgent] 此操作应该被权限系统拦截，返回 403...")
            result = web_agent.try_access_internal_data()
            print("[WebAgent] 测试结果: success={}, code={}, error={}".format(
                result["success"], result["code"], result.get("error", "")))
            print("[WebAgent] Trace ID: {}".format(result.get("trace_id", "N/A")))
            if result["code"] == 403:
                print("[WebAgent] PASS: 越权访问被成功拦截，权限控制有效！")
                print("[WebAgent] 解释: WebAgent无'delegate:*'权限，DataAgent拒绝其委托请求。")
            else:
                print("[WebAgent] FAIL: 越权访问未被拦截，存在安全风险！")
            print("[WebAgent] 提示: 此操作的完整审计日志已写入 audit_logs.jsonl")
            continue

        if user_input.lower().startswith("search"):
            keyword = user_input[6:].strip() if len(user_input) > 6 else ""
            if not keyword:
                keyword = input("[WebAgent] 请输入搜索关键词: ").strip()
            if keyword:
                print("\n[WebAgent] 正在多源搜索: {} ...".format(keyword))
                result = web_agent.search_tomato_novel_info(keyword=keyword)
                print("[WebAgent] 搜索结果: success={}".format(result["success"]))
                if result["success"]:
                    print("[WebAgent] 搜索摘要: {}".format(result["data"]["summary"]))
                    cred = result["data"].get("credibility_summary", {})
                    print("[WebAgent] 可信度: 高{}条 / 中{}条 / 低{}条".format(
                        cred.get("high", 0), cred.get("medium", 0), cred.get("low", 0)))
                    for idx, item in enumerate(result["data"]["search_results"][:5], 1):
                        source_tag = item.get("source", "?")
                        cred_tag = item.get("credibility_level", "?")
                        print("[WebAgent]   {}. [{}|可信:{}] {}".format(
                            idx, source_tag, cred_tag, item["title"]))
                else:
                    print("[WebAgent] 搜索失败: {}".format(result.get("error")))
            continue

        # ---- LLM 意图识别：自然语言输入 ----
        print("\n[WebAgent] 正在使用LLM分析你的意图...")
        try:
            intent = intent_recognizer.analyze(user_input)
        except Exception as e:
            print("[WebAgent] LLM意图识别失败: {}".format(str(e)[:100]))
            continue

        print("[WebAgent] 意图识别结果:")
        print(json.dumps(intent, ensure_ascii=False, indent=2))

        need_data = intent["call_data_agent"]["decision"] == "yes"
        need_web = intent["call_web_agent"]["decision"] == "yes"
        keyword = intent["call_web_agent"].get("keyword")

        # ---- 自动执行：按意图分派 ----
        if need_data:
            print("\n[WebAgent] LLM判断: 你的需求需要访问企业内部数据(多维表格)。")
            print("[WebAgent] 外部检索Agent 无权限读取内部数据！")
            print("[WebAgent] 自动尝试访问企业数据Agent → 预期被权限系统拦截...")
            result = web_agent.try_access_internal_data()
            print("\n[WebAgent] ===== 权限拦截结果 =====")
            print("[WebAgent] success: {}".format(result["success"]))
            print("[WebAgent] HTTP code: {}".format(result.get("code")))
            print("[WebAgent] 错误原因: {}".format(result.get("error", "")))
            print("[WebAgent] Trace ID: {}".format(result.get("trace_id", "N/A")))

            if result["code"] == 403:
                print("\n[WebAgent] *** 权限控制生效 ***")
                print("[WebAgent] DataAgent正确拒绝了外部检索Agent的内部数据访问请求。")
                print("[WebAgent] 原因: WebAgent的capabilities中无'delegate:*'权限，")
                print("[WebAgent]        DelegationHandler检测到委托方无委托权限，返回DENY。")
                print("[WebAgent] 安全结论: 分权机制运行正常，内部数据未被泄露。")
            elif result["code"] == 401:
                print("[WebAgent] *** Token校验生效 ***")
                print("[WebAgent] 无效的身份Token被正确拦截。")
            else:
                print("[WebAgent] *** 异常结果 *** 需要排查权限系统。")

            print("\n[WebAgent] 建议: 如需读取内部数据，请使用飞书文档助手Agent:")
            print("[WebAgent]   python run_doc_agent.py")
            print("[WebAgent]   输入: '生成番茄小说数据分析报告'")

        if need_web:
            if not keyword:
                keyword = "番茄小说 热门"
            print("\n[WebAgent] LLM判断: 需要搜索外部网络信息。")
            print("[WebAgent] 正在执行多源聚合搜索: {} ...".format(keyword))
            result = web_agent.search_tomato_novel_info(keyword=keyword)
            if result["success"]:
                print("[WebAgent] 搜索成功: {}".format(result["data"]["summary"]))
                cred = result["data"].get("credibility_summary", {})
                print("[WebAgent] 可信度: 高{}条 / 中{}条 / 低{}条".format(
                    cred.get("high", 0), cred.get("medium", 0), cred.get("low", 0)))
                for idx, item in enumerate(result["data"]["search_results"][:5], 1):
                    print("[WebAgent]   {}. [{}|可信:{}] {}".format(
                        idx, item.get("source", "?"), item.get("credibility_level", "?"),
                        item["title"]))
            else:
                print("[WebAgent] 搜索失败: {}".format(result.get("error")))

        if not need_data and not need_web:
            print("\n[WebAgent] LLM判断: 你的输入不涉及数据访问或外部检索。")
            print("[WebAgent] 总结: {}".format(intent.get("summary", "未知意图")))


def run_server():
    """启动API服务模式"""
    print("=" * 70)
    print(" 外部检索Agent 服务 v3.0 (端口: 8003)")
    print(" API文档: http://localhost:8003/docs")
    print(" 健康检查: http://localhost:8003/health")
    print(" 架构: 多源聚合搜索 + 越权拦截演示")
    print("=" * 70)
    uvicorn.run(app, host="0.0.0.0", port=8003, timeout_keep_alive=180)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="外部检索Agent v3.0")
    parser.add_argument("--server", action="store_true", help="API服务模式")
    args = parser.parse_args()

    if args.server:
        run_server()
    else:
        interactive_mode()
