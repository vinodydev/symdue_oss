# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
#!/usr/bin/env python3
"""
Test database and schema setup after Phase 1 implementation
Tests database connection, models, and schema validation
"""
import sys
import os

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from uuid import UUID
from database.connection import get_db
from database.models import Workflow, WorkflowNode, WorkflowEdge
from schemas.edge import EdgeCreate
from pydantic import ValidationError

print("=" * 50)
print("Testing Database and Schema Setup")
print("=" * 50)

# Test 1: Database connection
print("\n1. Testing database connection...")
try:
    db = next(get_db())
    workflow_count = db.query(Workflow).count()
    print(f"   ✅ Database connection successful")
    print(f"   ✅ Workflows in database: {workflow_count}")
except Exception as e:
    print(f"   ❌ Database connection failed: {e}")
    sys.exit(1)

# Test 2: Schema validation - valid weight
print("\n2. Testing EdgeCreate schema - valid weight (0.5)...")
try:
    edge = EdgeCreate(
        source=UUID("123e4567-e89b-12d3-a456-426614174000"),
        target=UUID("123e4567-e89b-12d3-a456-426614174001"),
        weight=0.5
    )
    print(f"   ✅ EdgeCreate validation successful")
    print(f"   ✅ Weight: {edge.weight}")
except Exception as e:
    print(f"   ❌ Validation failed: {e}")
    sys.exit(1)

# Test 3: Schema validation - invalid weight (> 1.0)
print("\n3. Testing EdgeCreate schema - invalid weight (1.5)...")
try:
    edge = EdgeCreate(
        source=UUID("123e4567-e89b-12d3-a456-426614174000"),
        target=UUID("123e4567-e89b-12d3-a456-426614174001"),
        weight=1.5
    )
    print(f"   ❌ Should have rejected weight > 1.0")
    sys.exit(1)
except ValidationError:
    print(f"   ✅ Weight validation working - rejected weight > 1.0")
except Exception as e:
    print(f"   ❌ Unexpected error: {e}")
    sys.exit(1)

# Test 4: Schema validation - invalid weight (< 0.0)
print("\n4. Testing EdgeCreate schema - invalid weight (-0.5)...")
try:
    edge = EdgeCreate(
        source=UUID("123e4567-e89b-12d3-a456-426614174000"),
        target=UUID("123e4567-e89b-12d3-a456-426614174001"),
        weight=-0.5
    )
    print(f"   ❌ Should have rejected weight < 0.0")
    sys.exit(1)
except ValidationError:
    print(f"   ✅ Weight validation working - rejected weight < 0.0")
except Exception as e:
    print(f"   ❌ Unexpected error: {e}")
    sys.exit(1)

print("\n" + "=" * 50)
print("✅ All tests passed!")
print("=" * 50)

