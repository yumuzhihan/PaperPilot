from enum import Enum
from pydantic import BaseModel, Field


class SectionStatus(Enum):
    PENDING = 0
    DRAFTED = 1
    RESEARCHING = 2
    WRITING = 3
    REVIEWING = 4
    FINISHED = 5


class PaperStatus(Enum):
    PLANNING = 0
    RESEARCHING = 1
    WRITING = 2
    REVIEWING = 3
    FINISHED = 4


class SectionContext(BaseModel):
    section_name: str = ""
    section_status: SectionStatus = SectionStatus.PENDING
    subsections: list["SectionContext"] = Field(default_factory=list)


class PaperContext(BaseModel):
    topic: str = ""
    title: str = ""
    outline: list[SectionContext] = Field(default_factory=list)
    bibliography: dict[str, str] = Field(default_factory=dict)
    current_section_index: int = 0
    drafts: dict[str, str] = Field(default_factory=dict)
    status: PaperStatus = PaperStatus.PLANNING
