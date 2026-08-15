from __future__ import annotations
from typing import List, Dict
from pydantic import BaseModel, Field

class ToolSpec(BaseModel):
    name: str
    purpose: str
    approval_required: bool = False
    implementation_hint: str = ""

class SubAgentSpec(BaseModel):
    name: str
    mission: str
    instructions: str

class TestCase(BaseModel):
    name: str
    input: str
    expected_behavior: str
    critical: bool = False

class AgentBlueprint(BaseModel):
    name: str
    slug: str
    version: str = "1.0.0"
    purpose: str
    target_users: List[str] = Field(default_factory=list)
    system_instructions: str
    autonomy_level: int = Field(default=2, ge=0, le=4)
    knowledge_topics: List[str] = Field(default_factory=list)
    tools: List[ToolSpec] = Field(default_factory=list)
    subagents: List[SubAgentSpec] = Field(default_factory=list)
    workflows: List[str] = Field(default_factory=list)
    permissions: Dict[str, str] = Field(default_factory=dict)
    tests: List[TestCase] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)
    deployment_notes: List[str] = Field(default_factory=list)

class AuditReport(BaseModel):
    score: int = Field(ge=0, le=100)
    verdict: str
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    critical_fixes: List[str] = Field(default_factory=list)
    improved_system_instructions: str = ""
