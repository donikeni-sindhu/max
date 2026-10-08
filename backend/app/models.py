"""Row shapes shared with supabase/migrations and the widget types."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

MissionStatus = Literal[
    "created",
    "planning",
    "researching",
    "learning",
    "complete",
    "failed",
    "cancelled",
]
ConceptStatus = Literal["pending", "active", "done"]
ConceptLevel = Literal[1, 2, 3]

DEMO_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
DEMO_MISSION_ID = UUID("22222222-2222-4222-8222-222222222222")


class ActiveWindow(BaseModel):
    title: str | None = None
    process: str | None = None
    pid: int | None = None


class UiSummary(BaseModel):
    element_count: int = 0
    key_elements: list[str] = Field(default_factory=list)


class MissionSummary(BaseModel):
    resources_explored: int = 0
    concepts_identified: int = 0
    ready_to_read: bool = False


class BrowserState(BaseModel):
    open: bool = False
    url: str | None = None
    title: str | None = None
    tab: str | None = None
    tabs: list[str] = Field(default_factory=list)
    active_tab: str | None = None


class TargetPaper(BaseModel):
    title: str | None = None
    url: str | None = None


class PdfState(BaseModel):
    url: str | None = None
    title: str | None = None
    text_excerpt: str | None = None


class WorldResource(BaseModel):
    title: str
    url: str
    source: str | None = None
    score: float | None = None
    selected: bool = False


class WorldStateData(BaseModel):
    goal: str = ""
    active_window: ActiveWindow = Field(default_factory=ActiveWindow)
    browser: BrowserState = Field(default_factory=BrowserState)
    target_paper: TargetPaper = Field(default_factory=TargetPaper)
    pdf: PdfState = Field(default_factory=PdfState)
    current_knowledge: str = ""
    prerequisites: list[str] = Field(default_factory=list)
    resources: list[WorldResource] = Field(default_factory=list)
    ui_summary: UiSummary = Field(default_factory=UiSummary)
    summary: MissionSummary | None = None
    # Confirmation is mission state so observer events cannot hide the active approval prompt.
    pending_confirmation: str | None = None


class Profile(BaseModel):
    id: UUID
    display_name: str | None = None
    created_at: datetime


class Mission(BaseModel):
    id: UUID
    user_id: UUID
    goal: str
    target_title: str | None = None
    status: MissionStatus
    created_at: datetime
    updated_at: datetime


class WorldState(BaseModel):
    mission_id: UUID
    state: WorldStateData
    updated_at: datetime


class Concept(BaseModel):
    id: UUID
    mission_id: UUID
    name: str
    level: ConceptLevel
    explanation: str
    order_index: int
    status: ConceptStatus


class Resource(BaseModel):
    id: UUID
    mission_id: UUID
    concept_id: UUID | None = None
    title: str
    url: str
    source: str | None = None
    score: float | None = None
    selected: bool


class AgentEvent(BaseModel):
    id: int
    mission_id: UUID
    type: str
    message: str
    payload: dict[str, object]
    created_at: datetime


class CharacterState(BaseModel):
    user_id: UUID
    mood: str
    animation: str
    speech: str
    updated_at: datetime


class ConceptDraft(BaseModel):
    name: str
    level: int = Field(ge=1, le=3)
    explanation: str
    order_index: int
    status: ConceptStatus = "pending"
