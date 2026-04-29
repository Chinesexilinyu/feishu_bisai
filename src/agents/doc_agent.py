from .base_agent import BaseAgent
from .data_agent import DataAgent
from .web_agent import WebAgent
from src.utils.feishu_client import FeishuClient

class DocAgent(BaseAgent):
    def __init__(self):
        super().__init__("doc-assistant")
        self.data_agent = DataAgent()
        self.web_agent = WebAgent()
        self.feishu_client = FeishuClient()

    def generate_novel_analysis_report(self, delegated_user: dict, keyword: str = None) -> dict:
        """生成番茄小说数据分析报告
        三Agent协作流程：
        1. DocAgent理解用户意图，生成任务计划
        2. 委托WebAgent搜索指定小说的网络公开信息（热度、评论等）
        3. 委托DataAgent读取内部多维表格的小说运营数据
        4. 整合两份数据，生成结构化报告
        5. 调用飞书API写入文档，返回报告链接
        """
        trace_id = self.trace_manager.new_trace()
        self.trace_manager.set_trace_id(trace_id)

        try:
            # 获取身份Token
            token, _ = self.get_identity_token(delegated_user=delegated_user, expires_in=7200)

            # 1. 先委托WebAgent搜索网络上的番茄小说相关信息（如果有关键词）
            web_result = None
            if keyword:
                # 为委托调用生成新的Token，扩展信任链
                agent_info = self.static_policy.get_agent_info(self.web_agent.agent_id)
                delegate_token, _ = self.token_issuer.issue_token(
                    agent_id=self.web_agent.agent_id,
                    agent_role=agent_info["role"],
                    agent_name=agent_info["name"],
                    capabilities=["web:search"],
                    delegated_user=delegated_user,
                    expires_in=3600,
                    chain_of_trust=self.delegation_handler.extend_trust_chain(
                        existing_chain=self.token_validator.verify_token(token)["payload"]["chain_of_trust"],
                        from_agent_id=self.agent_id,
                        to_agent_id=self.web_agent.agent_id
                    ),
                    parent_token_id=self.token_validator.verify_token(token)["payload"]["jti"]
                )
                
                # 调用WebAgent搜索
                web_result = self.web_agent.search_tomato_novel_info(keyword)
                if not web_result["success"]:
                    return {
                        "success": False,
                        "error": f"获取网络信息失败: {web_result['error']}",
                        "code": web_result["code"],
                        "trace_id": trace_id
                    }

            # 2. 委托DataAgent读取多维表格的番茄小说内部数据
            internal_result = self.data_agent.handle_request(
                token=token,
                resource="feishu:bitable",
                action="read"
            )

            if not internal_result["success"]:
                return {
                    "success": False,
                    "error": f"获取内部数据失败: {internal_result['error']}",
                    "code": internal_result["code"],
                    "trace_id": trace_id
                }

            # 3. 生成报告内容
            internal_data = internal_result["data"]
            report_content = "# 番茄小说数据分析报告\n\n"
            report_content += "## 一、内部多维表格数据\n\n"
            report_content += "### 热榜书籍数据\n"
            report_content += "| 书籍ID | 书籍名称 | 作者 | 类型 | 上榜次数 | 累计人气值 |\n"
            report_content += "|--------|----------|------|------|----------|------------|\n"
            
            # 从record中提取值的辅助函数，兼容新旧两种字段名格式
            def _field(record, *keys):
                for k in keys:
                    if k in record:
                        val = record[k]
                        if isinstance(val, dict) and "value" in val:
                            v = val["value"]
                            if isinstance(v, list) and len(v) > 0:
                                if isinstance(v[0], dict) and "text" in v[0]:
                                    return v[0]["text"]
                                return str(v[0])
                            return str(v)
                        return str(val)
                return ""
            
            # 解析热榜书籍数据
            if "recordMap" in internal_data:
                for record in internal_data["recordMap"].values():
                    book_id = _field(record, "fldZgyQUic", "书籍ID")
                    book_name = _field(record, "fldsRbvAwB", "书籍名称")
                    author = _field(record, "fldVCpfYUs", "作者", "作者名称")
                    book_type = _field(record, "fldPzg2k5U", "书籍类型", "类型")
                    rank_count = _field(record, "fldNMWkbIT", "上榜次数")
                    popularity = _field(record, "fldoLJfFrD", "累计人气值", "人气值")
                    report_content += f"| {book_id} | {book_name} | {author} | {book_type} | {rank_count} | {popularity} |\n"

            # 添加网络搜索结果
            if web_result and web_result["success"]:
                report_content += "\n## 二、网络公开信息\n\n"
                report_content += f"### 搜索关键词: {keyword}\n\n"
                for idx, item in enumerate(web_result["data"]["search_results"], 1):
                    report_content += f"#### {idx}. {item['title']}\n"
                    report_content += f"{item['abstract']}\n\n"

            # 4. 写入飞书文档
            doc_url = self.feishu_client.create_doc(title="番茄小说数据分析报告", content=report_content)

            return {
                "success": True,
                "data": {
                    "report_url": doc_url,
                    "internal_data": internal_data,
                    "web_data": web_result["data"] if web_result and web_result["success"] else None
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
