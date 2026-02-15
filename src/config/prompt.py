from enum import Enum


class PromptTemplate(Enum):
    """提示词模板"""

    SUMMARY = "summary"


class PromptManager:
    @staticmethod
    def get_prompt(prompt_template: PromptTemplate):
        if prompt_template == PromptTemplate.SUMMARY:
            return "请总结下面的内容："

        raise ValueError(f"未知的提示词模板: {prompt_template}")
