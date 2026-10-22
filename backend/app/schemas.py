from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    level: str = "intermediate"


class FindingStatusUpdate(BaseModel):
    status: str


class MemoryCreate(BaseModel):
    topic: str
    content: str
    verification_status: str = "unverified"
    sources: list[dict] | None = None
    confidence: float | None = None


class MemoryStatusUpdate(BaseModel):
    verification_status: str


class GitHubImport(BaseModel):
    url: str = Field(..., min_length=1)


class PrCommentRequest(BaseModel):
    changed_files: list[str] = Field(..., min_length=1)
