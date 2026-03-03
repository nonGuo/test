"""
LLM 客户端接口
支持多种 AI 模型提供商
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import os


class BaseLLMClient(ABC):
    """LLM 客户端基类"""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.model = kwargs.get("model", "default")
        self.temperature = kwargs.get("temperature", 0.7)
        self.max_tokens = kwargs.get("max_tokens", 4096)
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """
        生成文本响应
        
        Args:
            prompt: 输入提示词
            
        Returns:
            生成的文本
        """
        pass
    
    @abstractmethod
    def generate_json(self, prompt: str, **kwargs) -> Dict:
        """
        生成 JSON 响应
        
        Args:
            prompt: 输入提示词
            
        Returns:
            生成的 JSON 字典
        """
        pass


class QwenClient(BaseLLMClient):
    """通义千问客户端"""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(api_key, **kwargs)
        self.model = kwargs.get("model", "qwen-max")
        
        try:
            from openai import OpenAI
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
        except ImportError:
            raise ImportError("请安装 openai 库：pip install openai")
    
    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本响应"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一位专业的数仓测试专家。"},
                {"role": "user", "content": prompt}
            ],
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )
        return response.choices[0].message.content
    
    def generate_json(self, prompt: str, **kwargs) -> Dict:
        """生成 JSON 响应"""
        import json
        
        # 添加 JSON 格式要求
        json_prompt = f"{prompt}\n\n请输出 JSON 格式，不要包含其他解释。"
        
        response = self.generate(json_prompt, **kwargs)
        
        # 解析 JSON
        import re
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response
        
        return json.loads(json_str)


class OpenAIClient(BaseLLMClient):
    """OpenAI 客户端"""
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        super().__init__(api_key, **kwargs)
        self.model = kwargs.get("model", "gpt-4")
        
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("请安装 openai 库：pip install openai")
    
    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本响应"""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "你是一位专业的数仓测试专家。"},
                {"role": "user", "content": prompt}
            ],
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )
        return response.choices[0].message.content
    
    def generate_json(self, prompt: str, **kwargs) -> Dict:
        """生成 JSON 响应"""
        import json
        
        json_prompt = f"{prompt}\n\nPlease output JSON format only."
        response = self.generate(json_prompt, **kwargs)
        
        import re
        json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response
        
        return json.loads(json_str)


class LLMClientFactory:
    """LLM 客户端工厂"""
    
    @staticmethod
    def create(provider: str, **kwargs) -> BaseLLMClient:
        """
        创建 LLM 客户端
        
        Args:
            provider: 提供商名称 (qwen/openai)
            
        Returns:
            LLM 客户端实例
        """
        providers = {
            "qwen": QwenClient,
            "openai": OpenAIClient,
        }
        
        client_class = providers.get(provider.lower())
        if not client_class:
            raise ValueError(f"不支持的 LLM 提供商：{provider}")
        
        return client_class(**kwargs)
