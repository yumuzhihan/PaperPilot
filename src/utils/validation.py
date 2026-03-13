import json
import re
from dataclasses import dataclass
from typing import Any

from src.models import SectionContext

from .json_extract import extract_json_from_text


CONTROL_PATTERNS = (
    r"tool_call",
    r"function_call",
    r"<\|.*?\|>",
    r"error calling .*? api",
    r"apierror",
    r"rate limit",
    r"traceback",
)

MIN_WRITING_LENGTH = 120
VALID_BIB_PATTERN = re.compile(r"@[a-zA-Z]+\s*\{\s*[^,\s]+\s*,.*?\n\}", re.DOTALL)


@dataclass
class ValidationResult:
    ok: bool
    content: str
    error: str | None = None
    data: Any | None = None


def contains_control_artifacts(text: str) -> bool:
    lowered = text.lower()
    return any(re.search(pattern, lowered, re.DOTALL) for pattern in CONTROL_PATTERNS)


def validate_planning_output(text: str) -> ValidationResult:
    stripped = text.strip()
    if "```" in stripped:
        return ValidationResult(False, stripped, "规划阶段输出包含 Markdown 代码块")
    if contains_control_artifacts(stripped):
        return ValidationResult(False, stripped, "规划阶段输出包含控制信息或错误文本")

    try:
        data = extract_json_from_text(stripped)
    except Exception as exc:
        return ValidationResult(False, stripped, f"规划阶段 JSON 解析失败: {exc}")

    if not isinstance(data, dict):
        return ValidationResult(False, stripped, "规划阶段必须返回 JSON object")
    if not isinstance(data.get("title"), str) or not data.get("title", "").strip():
        return ValidationResult(False, stripped, "规划阶段缺少有效 title")
    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        return ValidationResult(False, stripped, "规划阶段缺少有效 sections 列表")

    try:
        parsed_sections = [SectionContext(**item) for item in sections]
    except Exception as exc:
        return ValidationResult(False, stripped, f"规划阶段 sections 结构非法: {exc}")

    return ValidationResult(True, stripped, data=data | {"sections": parsed_sections})


def validate_research_output(text: str) -> ValidationResult:
    stripped = text.strip()
    if contains_control_artifacts(stripped):
        return ValidationResult(False, stripped, "研究阶段输出包含控制信息或错误文本")

    notes_match = re.search(r"<notes>(.*?)</notes>", stripped, re.DOTALL)
    refs_match = re.search(r"<references>(.*?)</references>", stripped, re.DOTALL)
    if not notes_match or not refs_match:
        return ValidationResult(
            False, stripped, "研究阶段缺少 <notes> 或 <references> 标签"
        )

    notes = notes_match.group(1).strip()
    references = refs_match.group(1).strip()
    if not notes:
        return ValidationResult(False, stripped, "研究阶段 <notes> 为空")
    if not references:
        return ValidationResult(False, stripped, "研究阶段 <references> 为空")

    bib_entries = [
        match.group(0).strip() for match in VALID_BIB_PATTERN.finditer(references)
    ]
    if not bib_entries:
        return ValidationResult(False, stripped, "研究阶段未提取到有效 BibTeX")

    return ValidationResult(
        True,
        stripped,
        data={"notes": notes, "references": references, "bib_entries": bib_entries},
    )


def validate_writing_output(text: str) -> ValidationResult:
    stripped = text.strip()
    if not stripped:
        return ValidationResult(False, stripped, "写作阶段输出为空")
    if len(stripped) < MIN_WRITING_LENGTH:
        return ValidationResult(False, stripped, "写作阶段输出过短")
    if "```" in stripped:
        return ValidationResult(False, stripped, "写作阶段输出包含 Markdown 代码块")
    if re.search(r"<notes>|</notes>|<references>|</references>", stripped):
        return ValidationResult(False, stripped, "写作阶段输出包含研究标签")
    if contains_control_artifacts(stripped):
        return ValidationResult(False, stripped, "写作阶段输出包含控制信息或错误文本")

    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, (dict, list)):
            return ValidationResult(False, stripped, "写作阶段输出误返回 JSON")
    except Exception:
        pass

    return ValidationResult(True, stripped)
