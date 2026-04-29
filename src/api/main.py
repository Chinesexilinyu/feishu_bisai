from fastapi import FastAPI
from pydantic import BaseModel
import yaml
import os
from src.agents.doc_agent import DocAgent
from src.agents.web_agent import WebAgent
from src.audit_service.query import AuditQuery
from src.llm import get_llm_client

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
llm_client = get_llm_client()

class GenerateReportRequest(BaseModel):
    user_id: str
    user_name: str
    user_role: str
    keyword: str = None

class NLInstructionRequest(BaseModel):
    user_id: str
    user_name: str
    user_role: str
    instruction: str

class QueryAuditRequest(BaseModel):
    trace_id: str = None
    get_denied: bool = False

def parse_nl_instruction(instruction: str) -> dict:
    """使用LLM解析自然语言指令"""
    return llm_client.parse_instruction(instruction)

@app.post("/api/generate-report", summary="正常委托流程：生成番茄小说数据分析报告")
async def generate_report(request: GenerateReportRequest):
    result = doc_agent.generate_novel_analysis_report(
        delegated_user={
            "user_id": request.user_id,
            "user_name": request.user_name,
            "user_role": request.user_role
        },
        keyword=request.keyword
    )
    return result

@app.post("/api/nl-execute", summary="自然语言指令驱动任务执行")
async def nl_execute(request: NLInstructionRequest):
    """支持自然语言指令，比如：'帮我生成番茄小说分析报告，包含都市风云的网络热度信息'"""
    parsed = parse_nl_instruction(request.instruction)
    
    if parsed["task_type"] == "generate_report":
        result = doc_agent.generate_novel_analysis_report(
            delegated_user={
                "user_id": request.user_id,
                "user_name": request.user_name,
                "user_role": request.user_role
            },
            keyword=parsed["keyword"] if parsed["need_web_search"] else None
        )
        return {
            **result,
            "parsed_instruction": parsed,
            "instruction": request.instruction
        }
    elif parsed["task_type"] == "test_unauthorized_access":
        result = web_agent.try_access_internal_data()
        return {
            **result,
            "parsed_instruction": parsed,
            "instruction": request.instruction
        }
    
    return {"success": False, "error": "不支持的指令类型", "code": 400}

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
    uvicorn.run(app, host=HOST, port=PORT)
