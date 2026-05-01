from fastapi import FastAPI
from pydantic import BaseModel
import yaml
import os
from src.agents.doc_agent import DocAgent
from src.agents.web_agent import WebAgent
from src.audit_service.query import AuditQuery
from src.llm import get_llm_client
from src.llm.intent_recognizer import IntentRecognizer

# 加载服务配置
def load_server_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "config", "secrets.yaml")
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        return config.get("server", {})

server_config = load_server_config()
HOST = server_config.get("host", "0.0.0.0")
PORT = server_config.get("port", 8000)

app = FastAPI(title="Agent身份与权限系统", version="1.0.0")

doc_agent = DocAgent()
web_agent = WebAgent()
audit_query = AuditQuery()
intent_recognizer = IntentRecognizer()

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

class QueryAuditRequest(BaseModel):
    trace_id: str = None
    get_denied: bool = False

@app.post("/api/generate-report", summary="正常委托流程：生成番茄小说数据分析报告")
async def generate_report(request: GenerateReportRequest):
    result = doc_agent.generate_novel_analysis_report(
        delegated_user={
            "user_id": request.user_id,
            "user_name": request.user_name,
            "user_role": request.user_role
        },
        keyword=request.keyword,
        need_web_search=request.need_web_search
    )
    return result

@app.post("/api/nl-execute", summary="自然语言指令驱动任务执行")
async def nl_execute(request: NLInstructionRequest):
    """使用LLM IntentRecognizer解析意图 → 委托对应Agent执行"""
    intent = intent_recognizer.analyze(request.instruction)

    if intent["task_type"] == "generate_report":
        call_web = intent["call_web_agent"]["decision"] == "yes"
        keyword = intent["call_web_agent"].get("keyword")
        # ---- 健康预检：WebAgent离线时自动降级 ----
        warning = None
        if call_web:
            health = doc_agent.check_agent_health()
            if not health["web_agent"]:
                warning = ("外部检索Agent(8003)未启动，无法获取外部公开信息。"
                           "系统已自动降级为仅使用企业多维表格内部数据生成报告。")
                call_web = False
        result = doc_agent.generate_novel_analysis_report(
            delegated_user={
                "user_id": request.user_id,
                "user_name": request.user_name,
                "user_role": request.user_role
            },
            keyword=keyword,
            need_web_search=call_web
        )
        response = {"intent": intent, **result, "instruction": request.instruction}
        if warning:
            response["web_agent_warning"] = warning
        return response
    elif intent["task_type"] == "test_unauthorized_access":
        result = web_agent.try_access_internal_data()
        return {"intent": intent, **result, "instruction": request.instruction}

    return {"success": False, "error": "不支持的指令类型", "intent": intent, "code": 400}

@app.post("/api/try-access-internal", summary="越权拦截演示：外部Agent尝试访问内部数据")
async def try_access_internal():
    result = web_agent.try_access_internal_data()
    return result

@app.get("/api/audit/trace/{trace_id}", summary="根据trace_id查询审计日志")
async def get_audit_by_trace(trace_id: str):
    logs = audit_query.query_by_trace_id(trace_id)
    return {"success": True, "data": logs}

@app.get("/api/audit/denied", summary="查询最近1小时的拒绝事件")
async def get_denied_events():
    logs = audit_query.query_denied_events(time_range_hours=1)
    return {"success": True, "data": logs}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host=HOST, 
        port=PORT,
        timeout_keep_alive=120,  # 长连接超时120秒
        timeout_graceful_shutdown=30
    )
