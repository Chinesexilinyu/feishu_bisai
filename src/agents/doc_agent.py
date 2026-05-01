"""飞书文档助手Agent - 协调者，通过HTTP协议与其他Agent通信"""
from .base_agent import BaseAgent
from src.utils.feishu_doc import create_doc as feishu_create_doc
from src.llm import get_llm_client
from src.llm.intent_recognizer import IntentRecognizer
import json
import requests


class DocAgent(BaseAgent):
    def __init__(self):
        super().__init__("doc-assistant")
        self.data_agent_url = "http://localhost:8002/handle-request"
        self.web_agent_url = "http://localhost:8003/search-novel-info"
        self.llm_client = get_llm_client()
        self.intent_recognizer = IntentRecognizer(self.llm_client)

    def check_agent_health(self) -> dict:
        """检查依赖Agent的健康状态"""
        status = {"data_agent": False, "web_agent": False}
        try:
            r = requests.get("http://localhost:8002/health", timeout=3)
            status["data_agent"] = r.status_code == 200
        except Exception:
            pass
        try:
            r = requests.get("http://localhost:8003/health", timeout=3)
            status["web_agent"] = r.status_code == 200
        except Exception:
            pass
        return status

    def call_data_agent(self, token: str, resource: str = "feishu:bitable", action: str = "read") -> dict:
        """通过HTTP委托DataAgent读取企业内部数据"""
        try:
            resp = requests.post(
                self.data_agent_url,
                json={"token": token, "resource": resource, "action": action},
                timeout=60
            )
            if resp.status_code != 200:
                return {"success": False, "error": f"DataAgent返回HTTP {resp.status_code}", "code": 503}
            return resp.json()
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error": "企业数据Agent未启动。请先运行: python run_data_agent.py --server",
                "code": 503
            }
        except requests.exceptions.Timeout:
            return {"success": False, "error": "企业数据Agent响应超时", "code": 504}
        except Exception as e:
            return {"success": False, "error": str(e), "code": 500}

    def call_web_agent(self, keyword: str) -> dict:
        """通过HTTP委托WebAgent搜索外部信息"""
        try:
            resp = requests.post(
                self.web_agent_url,
                json={"keyword": keyword},
                timeout=30
            )
            if resp.status_code != 200:
                return {"success": False, "error": f"WebAgent返回HTTP {resp.status_code}", "code": 503}
            return resp.json()
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error": "外部检索Agent未启动。请先运行: python run_web_agent.py --server",
                "code": 503
            }
        except requests.exceptions.Timeout:
            return {"success": False, "error": "外部检索Agent响应超时", "code": 504}
        except Exception as e:
            return {"success": False, "error": str(e), "code": 500}

    def generate_novel_analysis_report(self, delegated_user: dict, keyword: str = None,
                                        need_web_search: bool = False) -> dict:
        """生成番茄小说数据分析报告 - 通过HTTP委托DataAgent和WebAgent
        严格权限控制：调用WebAgent前必须通过健康检查确认其在线"""
        trace_id = self.trace_manager.new_trace()
        self.trace_manager.set_trace_id(trace_id)

        try:
            token, _ = self.get_identity_token(delegated_user=delegated_user, expires_in=7200)

            # ---- 权限控制：预检 WebAgent 健康状态，离线时优雅降级 ----
            web_agent_available = False
            web_result = None
            web_agent_warning = None
            if need_web_search:
                health = self.check_agent_health()
                web_agent_available = health["web_agent"]
                if not web_agent_available:
                    web_agent_warning = (
                        "[DocAgent] 外部检索Agent(8003)未启动，无法获取外部公开信息。"
                        " 系统自动降级：仅使用企业内部多维表格数据生成报告。"
                        " 如需外部检索，请先启动: python run_web_agent.py --server"
                    )
                    print(web_agent_warning)
                else:
                    search_kw = keyword if keyword else "番茄小说 热门"
                    web_result = self.call_web_agent(search_kw)
                    if not web_result["success"]:
                        print(f"[DocAgent] WARN: 外部检索请求失败: {web_result.get('error')}")
                        web_result = None

            internal_result = self.call_data_agent(token=token)
            if not internal_result["success"]:
                return {
                    "success": False,
                    "error": internal_result["error"],
                    "code": internal_result["code"],
                    "trace_id": trace_id
                }

            all_tables = internal_result["data"].get("tables", {})

            def _fmt(val):
                if val is None or val == "":
                    return ""
                return str(val)

            books_data = all_tables.get("热榜书籍表", {})
            books_records = books_data.get("records", [])
            books_fields = books_data.get("fields", [])
            books_md = "## 一、热榜书籍数据\n\n"
            if books_records:
                key_fields = ["书籍ID", "书籍名称", "作者", "类型", "上榜次数", "累计人气值"]
                header_fields = []
                for kf in key_fields:
                    for bf in books_fields:
                        if kf in bf or bf in kf:
                            header_fields.append(bf)
                            break
                if not header_fields and books_fields:
                    header_fields = books_fields[:6]
                books_md += "| " + " | ".join(header_fields) + " |\n"
                books_md += "|" + "|".join(["------"] * len(header_fields)) + "|\n"
                for rec in books_records:
                    row = [_fmt(rec.get(f, "")) for f in header_fields]
                    books_md += "| " + " | ".join(row) + " |\n"
            else:
                books_md += "_暂无热榜书籍数据_\n"

            authors_data = all_tables.get("热榜作者表", {})
            authors_records = authors_data.get("records", [])
            authors_fields = authors_data.get("fields", [])
            authors_md = "\n## 二、热榜作者数据\n\n"
            if authors_records:
                key_author_fields = ["作者名称", "作者ID", "书籍ID", "代表作", "上榜次数", "人气值", "粉丝数"]
                header_af = []
                for kf in key_author_fields:
                    for af in authors_fields:
                        if kf in af or af in kf:
                            header_af.append(af)
                            break
                if not header_af and authors_fields:
                    header_af = authors_fields[:6]
                authors_md += "| " + " | ".join(header_af) + " |\n"
                authors_md += "|" + "|".join(["------"] * len(header_af)) + "|\n"
                for rec in authors_records:
                    row = [_fmt(rec.get(f, "")) for f in header_af]
                    authors_md += "| " + " | ".join(row) + " |\n"
            else:
                authors_md += "_暂无热榜作者数据_\n"

            mau_data = all_tables.get("月活数据表", {})
            mau_records = mau_data.get("records", [])
            mau_fields = mau_data.get("fields", [])
            mau_md = "\n## 三、月活数据\n\n"
            if mau_records:
                key_mau_fields = ["统计月份", "月活用户数", "环比增长", "数据来源", "创建时间"]
                header_mf = []
                for kf in key_mau_fields:
                    for mf in mau_fields:
                        if kf in mf or mf in kf:
                            header_mf.append(mf)
                            break
                if not header_mf and mau_fields:
                    header_mf = mau_fields[:5]
                mau_md += "| " + " | ".join(header_mf) + " |\n"
                mau_md += "|" + "|".join(["------"] * len(header_mf)) + "|\n"
                for rec in mau_records:
                    row = [_fmt(rec.get(f, "")) for f in header_mf]
                    mau_md += "| " + " | ".join(row) + " |\n"
            else:
                mau_md += "_暂无月活数据_\n"

            web_search_results = []
            web_md = ""
            if web_result and web_result.get("success"):
                web_md = "\n## 四、网络公开信息\n\n"
                web_md += f"### 搜索关键词: {keyword}\n\n"
                for idx, item in enumerate(web_result["data"].get("search_results", []), 1):
                    web_md += f"#### {idx}. {item['title']}\n"
                    web_md += f"{item['abstract']}\n\n"
                    web_search_results.append({"title": item["title"], "abstract": item["abstract"]})

            raw_data_content = "# 番茄小说数据分析报告\n\n" + books_md + authors_md + mau_md + web_md

            llm_prompt = f"""
请作为专业的数据分析专家，根据提供的番茄小说内部运营数据（涵盖三张数据表）和网络公开信息，生成一份详细、专业的数据分析报告。
要求：
1. 结构清晰，包含总览、热榜书籍分析、热榜作者分析、月活趋势分析、综合建议等部分
2. 语言专业，适合企业内部汇报使用
3. 对热榜书籍表：分析热门类型分布、高人气书籍规律、上榜次数趋势
4. 对热榜作者表：分析高产作者、作者与书籍的关联关系
5. 对月活数据表：分析月活用户增长趋势、环比增长率变化
6. 如果有三张表的交叉关联情况，请进行交叉分析
7. 报告长度不少于1200字，使用Markdown格式

=== 热榜书籍数据 ===
{json.dumps(books_records, ensure_ascii=False, indent=2)}

=== 热榜作者数据 ===
{json.dumps(authors_records, ensure_ascii=False, indent=2)}

=== 月活数据 ===
{json.dumps(mau_records, ensure_ascii=False, indent=2)}

=== 网络搜索结果 ===
{json.dumps(web_search_results, ensure_ascii=False, indent=2) if web_search_results else "无"}
"""
            messages = [
                {"role": "system", "content": "你是专业的数据分析专家，擅长从多维度数据中生成高质量的业务分析报告。"},
                {"role": "user", "content": llm_prompt}
            ]

            llm_report = self.llm_client.chat(messages, timeout=180)
            final_report = llm_report + "\n\n---\n\n## 附录：原始数据\n\n" + raw_data_content

            doc_url = feishu_create_doc(title="番茄小说数据分析报告", content=final_report)

            return {
                "success": True,
                "data": {
                    "report_url": doc_url,
                    "internal_data": internal_result["data"],
                    "web_data": web_result["data"] if web_result and web_result.get("success") else None,
                    "web_agent_warning": web_agent_warning,
                },
                "code": 200,
                "trace_id": trace_id
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "code": 500,
                "trace_id": trace_id
            }
