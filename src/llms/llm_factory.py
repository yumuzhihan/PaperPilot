from typing import Optional

from src.core import LLMInterface
from src.config import settings
from .ollama_llm import OllamaLLM
from .openai_llm import OpenAILLM
from .zhipu_llm import ZhipuLLM


class LLMFactory:
    _llm: Optional[LLMInterface] = None
    _llm_maps: dict[str, type[LLMInterface]] = {
        "ollama": OllamaLLM,
        "openai": OpenAILLM,
        "zhipu": ZhipuLLM,
    }

    def __init__(self) -> None:
        pass

    @staticmethod
    def get_llm() -> LLMInterface:
        llm_type = settings.LLM_PROVIDER

        if not llm_type in LLMFactory._llm_maps:
            raise ValueError(
                f"不支持 {llm_type}，所有支持模型提供方为:{LLMFactory._llm_maps.keys()}"
            )

        if LLMFactory._llm is None:
            LLMFactory._llm = LLMFactory._llm_maps[llm_type]()

        return LLMFactory._llm


llm_factory = LLMFactory()
