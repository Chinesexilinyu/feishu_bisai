from typing import Dict
import os
import yaml
from .base import BaseLLM
from .rule_llm import RuleLLM
from .openai_compatible import OpenAICompatibleLLM

def _load_default_config() -> Dict:
    """加载默认配置文件"""
    secrets_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "config", "secrets.yaml"
    )
    with open(secrets_path, 'r', encoding='utf-8') as f:
        secrets = yaml.safe_load(f)
        return secrets.get("llm", {})

def get_llm_client(config: Dict = None) -> BaseLLM:
    """根据配置获取LLM客户端
    支持类型:
    - rule: 基于规则的本地解析，无需外部依赖
    - openai: 兼容OpenAI协议的服务，包括OpenAI、DeepSeek等
    - ollama: 本地部署的Ollama模型（本质也是OpenAI协议兼容）
    """
    if config is None:
        # 直接加载默认配置，不实例化抽象基类
        config = _load_default_config()
    
    llm_type = config.get("type", "rule").lower()
    
    if llm_type == "rule":
        return RuleLLM(config)
    elif llm_type in ["openai", "ollama"]:
        return OpenAICompatibleLLM(config)
    else:
        raise ValueError(f"不支持的LLM类型: {llm_type}，支持的类型: rule, openai, ollama")

