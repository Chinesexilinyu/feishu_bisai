from typing import List, Dict
import json
from openai import OpenAI
from .base import BaseLLM

class OpenAICompatibleLLM(BaseLLM):
    """支持OpenAI协议的LLM实现，兼容OpenAI、DeepSeek、本地Ollama等"""
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        self.client = OpenAI(
            base_url=self.config.get("api_base"),
            api_key=self.config.get("api_key", "sk-xxxx")  # ollama不需要api_key
        )
        self.model_name = self.config.get("model_name", "gpt-3.5-turbo")

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=kwargs.get("temperature", 0.1),
            stream=kwargs.get("stream", False),
            timeout=kwargs.get("timeout", 120)  # 本地模型设置更长超时时间，默认120秒
        )
        return response.choices[0].message.content.strip()

    def parse_instruction(self, instruction: str) -> Dict:
        """使用LLM解析用户指令"""
        prompt = f"""
请解析用户的自然语言指令，返回JSON格式的结构化信息，只能返回JSON，不要返回其他内容。

支持的任务类型：
1. generate_report：生成番茄小说数据分析报告
2. test_unauthorized_access：测试越权访问内部数据

返回字段说明：
- task_type：任务类型，只能是上面两种之一
- keyword：要搜索的小说名称，如果没有具体小说名则为null。如果用户要求结合外部知识/搜索/检索，但未指定具体小说名，keyword可填null，need_web_search必须为true
- need_web_search：是否需要搜索网络信息。以下情况必须为true：
  * 用户提到"外部检索""外部知识""网络搜索""网络信息""结合外部""搜索""检索"
  * 用户指定了具体小说名（如"都市风云"）
  * 用户要求"综合分析""综合报告"
  以下情况可为false：
  * 用户仅要求生成报告但未提外部信息

用户指令：{instruction}

返回JSON格式示例1（需要网络搜索且有具体关键词）：
{{"task_type": "generate_report", "keyword": "都市风云", "need_web_search": true}}

返回JSON格式示例2（需要外部检索但无具体关键词）：
{{"task_type": "generate_report", "keyword": null, "need_web_search": true}}

返回JSON格式示例3（不需要外部检索）：
{{"task_type": "generate_report", "keyword": null, "need_web_search": false}}
"""
        messages = [
            {"role": "system", "content": "你是一个指令解析助手，只返回JSON格式的解析结果。你必须严格按照用户指令判断need_web_search。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            result = self.chat(messages)
            parsed = json.loads(result)
            if "task_type" not in parsed:
                parsed["task_type"] = "generate_report"
            if "keyword" not in parsed:
                parsed["keyword"] = None
            if "need_web_search" not in parsed:
                parsed["need_web_search"] = False
            return parsed
        except Exception as e:
            return {
                "task_type": "generate_report",
                "keyword": None,
                "need_web_search": False
            }
