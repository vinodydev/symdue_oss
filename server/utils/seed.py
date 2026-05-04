"""
Seed base node types on application startup
"""
from database.connection import SessionLocal
from database.models import NodeType


def seed_base_node_types():
    """Seed base node types on application startup"""
    db = SessionLocal()
    
    try:
        base_types = [
            {
                "id": "input",
                "category": "input",
                "name": "Input Node",
                "description": "Entry point for data (Text, Image, or Date)",
                "icon": "database",
                "is_builtin": True,
                "default_config": {
                    "name": "Input",
                    "inputType": "text",
                    "value": ""
                },
                "config_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "inputType": {"type": "string", "enum": ["text", "image", "date"]},
                        "value": {"type": "string"}
                    }
                }
            },
            {
                "id": "custom-python",
                "category": "python",
                "name": "Python Script",
                "description": "Custom code execution with pip requirements",
                "icon": "code",
                "is_builtin": True,
                "default_config": {
                    "name": "Python Node",
                    "code": "",
                    "requirements": ""
                },
                "config_schema": {
                    "type": "object",
                    "supports_iterator": True,
                    "properties": {
                        "name": {"type": "string"},
                        "code": {"type": "string"},
                        "requirements": {"type": "string"}
                    }
                }
            },
            {
                "id": "condition-python",
                "category": "python",
                "name": "Condition",
                "description": "Python node with true/false branches. Return True or False; only the matching branch runs.",
                "icon": "code",
                "is_builtin": True,
                "default_config": {
                    "name": "Condition",
                    "code": "def main(inputs, context):\n    # Return True or False (or {\"branch\": \"true\"/\"false\"})\n    return True",
                    "requirements": "",
                    "condition_mode": True
                },
                "config_schema": {
                    "type": "object",
                    "supports_iterator": True,
                    "properties": {
                        "name": {"type": "string"},
                        "code": {"type": "string"},
                        "requirements": {"type": "string"},
                        "condition_mode": {"type": "boolean"}
                    }
                }
            },
            {
                "id": "custom-llm",
                "category": "llm",
                "name": "LLM Node",
                "description": "Connect to specialized AI model endpoints",
                "icon": "cpu",
                "is_builtin": True,
                "default_config": {
                    "name": "LLM Node",
                    "prompt": "",
                    "configId": None
                },
                "config_schema": {
                    "type": "object",
                    "supports_iterator": True,
                    "properties": {
                        "name": {"type": "string"},
                        "prompt": {"type": "string"},
                        "configId": {"type": "string", "nullable": True}
                    }
                }
            },
            {
                "id": "memory",
                "category": "memory",
                "name": "Memory Node",
                "description": "Persistent context retrieval across runs",
                "icon": "history",
                "is_builtin": True,
                "default_config": {
                    "name": "Memory Node"
                },
                "config_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"}
                    }
                }
            },
            {
                "id": "wait",
                "category": "Control",
                "name": "Wait",
                "description": "Pause execution until a signal is received on a channel",
                "icon": "clock",
                "is_builtin": True,
                "default_config": {
                    "channel": "",
                    "mode": "signal",
                    "signals": [],
                    "timeout": None
                },
                "config_schema": {
                    "type": "object",
                    "properties": {
                        "channel": {"type": "string"},
                        "mode": {"type": "string", "enum": ["signal", "any", "all", "time", "until"]},
                        "signals": {"type": "array", "items": {"type": "string"}},
                        "timeout": {"type": "string", "nullable": True},
                        "duration": {"type": "string", "nullable": True},
                        "until": {"type": "string", "nullable": True}
                    }
                }
            }
        ]
        
        for node_type_data in base_types:
            existing = db.query(NodeType).filter(
                NodeType.id == node_type_data["id"]
            ).first()
            
            if not existing:
                node_type = NodeType(**node_type_data)
                db.add(node_type)
        
        db.commit()
        print("✅ Base node types seeded successfully")
    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding node types: {e}")
        raise
    finally:
        db.close()
