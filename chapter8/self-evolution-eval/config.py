"""
实验 8-6 配置模块：统一读取 API Key、构造 OpenAI 客户端。

支持三家可用的 OpenAI 兼容服务（按 PROVIDER 选择）：
- openai   （默认，读 OPENAI_API_KEY）
- moonshot （读 MOONSHOT_API_KEY，Kimi）
- ark      （读 ARK_API_KEY，火山方舟）

注意：OPENROUTER / ANTHROPIC / DEEPSEEK / SILICONFLOW 的 Key 当前不可用，请勿使用。
"""

import os
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


# 各 provider 的 base_url 与默认模型
_PROVIDERS = {
    "openai": {
        "key_env": "OPENAI_API_KEY",
        "base_url": None,  # OpenAI 官方默认地址
        "default_model": "gpt-4o-mini",
    },
    "moonshot": {
        "key_env": "MOONSHOT_API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
        "default_model": "kimi-k3",
    },
    "ark": {
        "key_env": "ARK_API_KEY",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "default_model": "doubao-seed-1-6-250615",
    },
}


class Config:
    # 被测 Agent（工具创造）默认模型
    PROVIDER: str = os.getenv("PROVIDER", "openai").lower()
    AGENT_MODEL: str = os.getenv("AGENT_MODEL", "gpt-4o-mini")
    # LLM-as-a-Judge 使用的模型（第 3 层工具创造质量打分）
    JUDGE_MODEL: str = os.getenv("JUDGE_MODEL", "gpt-4o-mini")
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.2"))

    @classmethod
    def provider_meta(cls) -> dict:
        if cls.PROVIDER not in _PROVIDERS:
            raise ValueError(
                f"未知 PROVIDER={cls.PROVIDER}，可选：{list(_PROVIDERS)}"
            )
        return _PROVIDERS[cls.PROVIDER]

    @classmethod
    def get_client(cls) -> OpenAI:
        """构造并返回 OpenAI 兼容客户端。"""
        meta = cls.provider_meta()
        api_key = os.getenv(meta["key_env"], "")
        if not api_key:
            raise RuntimeError(
                f"未找到 {meta['key_env']}，请在 .env 中设置或 export 到环境变量。"
            )
        kwargs = {"api_key": api_key}
        if meta["base_url"]:
            kwargs["base_url"] = meta["base_url"]
        return OpenAI(**kwargs)

    @classmethod
    def resolve_default_model(cls, override: Optional[str] = None) -> str:
        """在非 openai provider 下，若用户仍用 gpt-* 默认值，则回退到该 provider 的默认模型。"""
        if override:
            return override
        meta = cls.provider_meta()
        model = cls.AGENT_MODEL
        if cls.PROVIDER != "openai" and model.startswith("gpt-"):
            return meta["default_model"]
        return model
