# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Symdue contributors
"""
Schemas package
"""
# Import in order to resolve forward references
from schemas.workflow import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
    WorkflowDetail,
)
from schemas.node import (
    NodeCreate,
    NodeUpdate,
    NodePositionUpdate,
    NodeResponse,
)
from schemas.edge import (
    EdgeCreate,
    EdgeUpdate,
    EdgeResponse,
)
from schemas.run import (
    RunCreate,
    RunResponse,
)
from schemas.node_type import (
    NodeTypeCreate,
    NodeTypeResponse,
)
from schemas.llm_config import (
    LLMConfigCreate,
    LLMConfigUpdate,
    LLMConfigResponse,
)

# Update forward references after all imports
from pydantic import model_validator
WorkflowDetail.model_rebuild()

__all__ = [
    "WorkflowCreate",
    "WorkflowUpdate",
    "WorkflowResponse",
    "WorkflowDetail",
    "NodeCreate",
    "NodeUpdate",
    "NodePositionUpdate",
    "NodeResponse",
    "EdgeCreate",
    "EdgeUpdate",
    "EdgeResponse",
    "RunCreate",
    "RunResponse",
    "NodeTypeCreate",
    "NodeTypeResponse",
    "LLMConfigCreate",
    "LLMConfigUpdate",
    "LLMConfigResponse",
]
