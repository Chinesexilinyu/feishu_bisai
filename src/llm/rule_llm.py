from typing import List, Dict
import jieba
from .base import BaseLLM

class RuleLLM(BaseLLM):
    """基于规则的LLM实现，无需依赖外部模型"""
    
    def __init__(self, config: Dict = None):
        super().__init__(config)
        self.novel_keywords = ["都市风云", "玄幻修仙传", "爱情故事集", "星际漫游", "密室逃脱", "乡村生活", "玄幻大陆", "都市职场", "青春言情", "未来科技"]
    
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        return "我是番茄小说分析助手，我可以帮你生成番茄小说数据分析报告。"
    
    def parse_instruction(self, instruction: str) -> Dict:
        """基于规则解析用户自然语言指令"""
        words = jieba.lcut(instruction)
        result = {
            "task_type": "generate_report",
            "keyword": None,
            "need_web_search": False
        }
        
        # 检测是否需要生成报告
        if any(word in words for word in ["生成", "制作", "写", "导出", "报告", "分析", "统计"]):
            result["task_type"] = "generate_report"
        
        # 检测是否需要搜索特定小说
        for keyword in self.novel_keywords:
            if keyword in instruction:
                result["keyword"] = keyword
                result["need_web_search"] = True
                break
        
        # 检测是否需要网络搜索
        if any(word in words for word in ["搜索", "查询", "找", "网络", "公开", "热度", "评论", "口碑", "外网", "检索", "外部", "知识", "结合"]):
            result["need_web_search"] = True
        
        # 检测是否越权测试
        if any(word in words for word in ["越权", "测试", "访问内部数据", "尝试读取表格"]):
            result["task_type"] = "test_unauthorized_access"
        
        return result
