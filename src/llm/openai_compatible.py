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
            stream=kwargs.get("stream", False)
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
- keyword：要搜索的小说名称，如果没有则为null
- need_web_search：是否需要搜索网络信息，true/false

用户指令：{instruction}

返回JSON格式示例：
{{
    "task_type": "generate_report",
    "keyword": "都市风云",
    "need_web_search": true
}}
"""
        messages = [
            {"role": "system", "content": "你是一个指令解析助手，只返回JSON格式的解析结果。"},
            {"role": "user", "content": prompt}
        ]
        
        try:
            result = self.chat(messages)
            # 尝试解析JSON
            parsed = json.loads(result)
            # 校验字段
            if "task_type" not in parsed:
                parsed["task_type"] = "generate_report"
            if "keyword" not in parsed:
                parsed["keyword"] = None
            if "need_web_search" not in parsed:
                parsed["need_web_search"] = False
            return parsed
        except Exception as e:
            # 解析失败降级到默认规则
            return {
                "task_type": "generate_report",
                "keyword": None,
                "need_web_search": False
            }
