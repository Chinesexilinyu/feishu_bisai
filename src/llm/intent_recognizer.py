"""LLM驱动的意图识别器 - 输出JSON格式的yes/no决策，替代RuleLLM"""
from typing import Dict
import json
from .openai_compatible import OpenAICompatibleLLM


class IntentRecognizer:
    """使用LLM识别用户意图，输出结构化JSON决策"""

    def __init__(self, llm_client: OpenAICompatibleLLM = None):
        if llm_client is None:
            from . import get_llm_client
            self.llm = get_llm_client()
        else:
            self.llm = llm_client

    def analyze(self, instruction: str) -> Dict:
        """
        分析用户自然语言指令，返回JSON格式的意图决策。

        返回格式:
        {
            "task_type": "generate_report" | "test_unauthorized_access" | "unknown",
            "call_data_agent": {
                "decision": "yes" | "no",
                "reason": "原因说明"
            },
            "call_web_agent": {
                "decision": "yes" | "no",
                "reason": "原因说明",
                "keyword": "搜索关键词" | null
            },
            "summary": "对用户意图的一句话总结",
            "confidence": 0.0-1.0
        }
        """
        prompt = f"""
你是一个智能意图识别器。请分析用户指令，用JSON格式输出决策结果。只返回JSON，不要有其他内容。

你的任务是判断是否需要调用以下两个Agent：
1. 企业数据Agent (DataAgent): 负责读取飞书多维表格内部数据
2. 外部检索Agent (WebAgent): 负责搜索外部网络公开信息

判断规则：
- call_data_agent.decision="yes": 用户需要查看/分析企业内部数据、生成报告/统计、读取表格
- call_data_agent.decision="no": 用户只是闲聊、问系统能力、测试权限等不需要内部数据的场景
- call_web_agent.decision="yes": 用户提到"外部检索""外部知识""网络搜索""网络信息""结合外部""搜索""检索""网络热度""公开信息"
- call_web_agent.decision="no": 用户不需要外部信息
- call_web_agent.keyword: 如果decision="yes"，提取搜索关键词，没有具体关键词时填null

task_type可选值：
- "generate_report": 生成分析报告
- "test_unauthorized_access": 测试越权访问
- "unknown": 其他不支持的指令

返回JSON格式：
{{
    "task_type": "generate_report",
    "call_data_agent": {{"decision": "yes", "reason": "用户需要查看多维表格内部数据来生成报告"}},
    "call_web_agent": {{"decision": "yes", "reason": "用户明确要求结合外部检索知识", "keyword": null}},
    "summary": "用户要求读取表格数据并结合外部检索生成分析报告",
    "confidence": 0.95
}}

用户指令：{instruction}
"""
        messages = [
            {"role": "system", "content": "你是智能意图识别器，只输出JSON格式结果。decision必须为yes或no。"},
            {"role": "user", "content": prompt}
        ]

        try:
            result = self.llm.chat(messages, timeout=60)
            parsed = json.loads(result)
            return self._validate(parsed)
        except Exception:
            return self._default_parse(instruction)

    def _validate(self, parsed: Dict) -> Dict:
        """校验收到的JSON字段完整性和合法性"""
        default = self._default_parse("")
        if "task_type" not in parsed:
            parsed["task_type"] = default["task_type"]
        if "call_data_agent" not in parsed:
            parsed["call_data_agent"] = default["call_data_agent"]
        else:
            da = parsed["call_data_agent"]
            if da.get("decision") not in ("yes", "no"):
                da["decision"] = default["call_data_agent"]["decision"]
            if "reason" not in da:
                da["reason"] = ""
        if "call_web_agent" not in parsed:
            parsed["call_web_agent"] = default["call_web_agent"]
        else:
            wa = parsed["call_web_agent"]
            if wa.get("decision") not in ("yes", "no"):
                wa["decision"] = default["call_web_agent"]["decision"]
            if "reason" not in wa:
                wa["reason"] = ""
            if "keyword" not in wa:
                wa["keyword"] = None
        if "summary" not in parsed:
            parsed["summary"] = ""
        if "confidence" not in parsed:
            parsed["confidence"] = 0.5
        return parsed

    def _default_parse(self, instruction: str) -> Dict:
        """LLM不可用时的规则降级解析"""
        import jieba
        words = jieba.lcut(instruction)

        result = {
            "task_type": "generate_report",
            "call_data_agent": {"decision": "yes", "reason": "默认需要读取内部数据"},
            "call_web_agent": {"decision": "no", "reason": ""},
            "summary": "生成分析报告",
            "confidence": 0.3
        }

        external_triggers = {"搜索", "查询", "网络", "公开", "热度", "评论", "口碑",
                              "外网", "检索", "外部", "知识", "结合"}
        novel_keywords = ["都市风云", "玄幻修仙传", "爱情故事集", "星际漫游",
                           "密室逃脱", "乡村生活", "玄幻大陆", "都市职场", "青春言情", "未来科技"]

        if any(w in words for w in external_triggers):
            result["call_web_agent"] = {"decision": "yes", "reason": "检测到外部检索关键词"}

        for kw in novel_keywords:
            if kw in instruction:
                result["call_web_agent"]["keyword"] = kw
                result["call_web_agent"]["decision"] = "yes"
                break

        if any(w in words for w in {"越权", "测试访问", "尝试读取"}):
            result["task_type"] = "test_unauthorized_access"
            result["call_data_agent"] = {"decision": "no", "reason": "越权测试"}
            result["call_web_agent"] = {"decision": "no", "reason": "越权测试"}

        return result
