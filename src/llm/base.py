from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import yaml
import os

class BaseLLM(ABC):
    def __init__(self, config: Dict = None):
        self.config = config or self._load_default_config()
    
    def _load_default_config(self) -> Dict:
        """加载默认配置文件"""
        secrets_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "config", "secrets.yaml"
        )
        with open(secrets_path, 'r', encoding='utf-8') as f:
            secrets = yaml.safe_load(f)
            return secrets.get("llm", {})

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """聊天接口"""
        pass

    @abstractmethod
    def parse_instruction(self, instruction: str) -> Dict:
        """解析用户自然语言指令，返回结构化任务信息
        返回格式：
        {
            "task_type": "generate_report/test_unauthorized_access",
            "keyword": "小说名称/None",
            "need_web_search": True/False
        }
        """
        pass
