"""抽取器：ParsedDocument -> PdecrCase。

- RuleBasedExtractor：正则/关键词，无需 LLM，作回退与冒烟。
- LlmExtractor：走 LLM 结构化输出，未配置时自动回退到规则抽取。
- get_extractor()：按环境挑一个可用的。
"""

from .pdecr_llm_extractor import LlmExtractor, get_extractor, llm_available
from .rule_based_extractor import RuleBasedExtractor

__all__ = ["LlmExtractor", "RuleBasedExtractor", "get_extractor", "llm_available"]
