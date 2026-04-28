from .base_agent import BaseAgent
from .data_agent import DataAgent
import requests
from bs4 import BeautifulSoup

class WebAgent(BaseAgent):
    def __init__(self):
        super().__init__("web-agent")
        self.data_agent = DataAgent()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }

    def try_access_internal_data(self) -> dict:
        """尝试访问企业内部数据，用于越权拦截演示"""
        trace_id = self.trace_manager.new_trace()
        self.trace_manager.set_trace_id(trace_id)

        # 获取身份Token（没有委托用户）
        token, _ = self.get_identity_token(expires_in=3600)

        # 尝试请求DataAgent读取多维表格数据
        result = self.data_agent.handle_request(
            token=token,
            resource="feishu:bitable",
            action="read"
        )

        return {
            **result,
            "trace_id": trace_id
        }

    def search_tomato_novel_info(self, keyword: str) -> dict:
        """搜索番茄小说相关信息：热度、评论、排名等"""
        trace_id = self.trace_manager.get_trace_id()
        
        try:
            # 搜索番茄小说热度信息
            search_url = f"https://www.baidu.com/s?wd={keyword} 番茄小说 热度 评论"
            response = requests.get(search_url, headers=self.headers, timeout=10)
            
            if response.status_code != 200:
                return {"success": False, "error": "搜索失败", "code": 500}
            
            # 简单解析搜索结果
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            for item in soup.select('.result')[:3]:
                title = item.select_one('h3').get_text() if item.select_one('h3') else ""
                abstract = item.select_one('.c-abstract').get_text() if item.select_one('.c-abstract') else ""
                results.append({"title": title, "abstract": abstract})
            
            # 记录审计日志
            self.audit_logger.log_authorization_event(
                event_type="RESOURCE_ACCESS",
                decision="ALLOW",
                subject={"agent_id": self.agent_id, "agent_name": "外部检索Agent"},
                resource={"type": "web:search", "action": "read", "keyword": keyword},
                authorization={"requested_capability": "web:search", "reason": "CAPABILITY_MATCH"},
                trace_id=trace_id
            )
            
            return {
                "success": True,
                "data": {
                    "keyword": keyword,
                    "search_results": results,
                    "summary": f"已成功搜索到关于「{keyword}」的网络信息"
                },
                "code": 200
            }
        except Exception as e:
            return {"success": False, "error": str(e), "code": 500}
