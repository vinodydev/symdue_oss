# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Comprehensive tests for template helper functions
"""
import pytest
from database.connection import SessionLocal
from database.models import Workflow, WorkflowNode, WorkflowEdge
from utils.template_helpers import (
    extract_env_vars_from_code,
    is_workflow_level_var,
    is_node_level_var,
    identify_input_nodes,
    identify_output_nodes,
    build_input_ports,
    build_output_ports,
    serialize_node,
    serialize_edge,
    detect_circular_dependency,
)
import uuid


@pytest.fixture
def db():
    """Database session fixture"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestExtractEnvVars:
    """Test environment variable extraction from Python code"""
    
    def test_extract_simple_os_environ_get(self):
        """Test extraction of os.environ.get() patterns"""
        code = '''
import os
bucket = os.environ.get("S3_BUCKET")
db_url = os.environ.get("DATABASE_URL")
'''
        env_vars = extract_env_vars_from_code(code)
        assert "S3_BUCKET" in env_vars
        assert "DATABASE_URL" in env_vars
    
    def test_extract_os_getenv(self):
        """Test extraction of os.getenv() patterns"""
        code = '''
import os
api_key = os.getenv("API_KEY")
timeout = os.getenv("NODE_TIMEOUT", "30")
'''
        env_vars = extract_env_vars_from_code(code)
        assert "API_KEY" in env_vars
        assert "NODE_TIMEOUT" in env_vars
    
    def test_extract_os_environ_bracket(self):
        """Test extraction of os.environ[] patterns"""
        code = '''
import os
bucket = os.environ["S3_BUCKET"]
'''
        env_vars = extract_env_vars_from_code(code)
        assert "S3_BUCKET" in env_vars
    
    def test_extract_mixed_patterns(self):
        """Test extraction with mixed patterns"""
        code = '''
import os
bucket = os.environ.get("S3_BUCKET")
db = os.environ["DATABASE_URL"]
key = os.getenv("API_KEY")
timeout = int(os.environ.get("NODE_TIMEOUT", "30"))
'''
        env_vars = extract_env_vars_from_code(code)
        assert len(env_vars) == 4
        assert "S3_BUCKET" in env_vars
        assert "DATABASE_URL" in env_vars
        assert "API_KEY" in env_vars
        assert "NODE_TIMEOUT" in env_vars
    
    def test_extract_empty_code(self):
        """Test extraction from empty code"""
        env_vars = extract_env_vars_from_code("")
        assert env_vars == set()
    
    def test_extract_invalid_code(self):
        """Test extraction from invalid Python code (should not crash)"""
        code = "this is not valid python code {"
        env_vars = extract_env_vars_from_code(code)
        # Should return empty set or whatever regex found
        assert isinstance(env_vars, set)


class TestEnvVarClassification:
    """Test environment variable classification"""
    
    def test_workflow_level_vars(self):
        """Test workflow-level variable classification"""
        workflow_vars = [
            "S3_BUCKET",
            "DATABASE_URL",
            "REDIS_URL",
            "MONGODB_HOST",
            "API_KEY",
            "OPENAI_API_KEY",
            "WEBHOOK_BASE_URL",
        ]
        
        for var in workflow_vars:
            assert is_workflow_level_var(var), f"{var} should be workflow-level"
    
    def test_node_level_vars(self):
        """Test node-level variable classification"""
        node_vars = [
            "NODE_TIMEOUT",
            "NODE_RETRIES",
            "NODE_CHECK_INTERVAL",
            "TIMEOUT",
            "RETRIES",
        ]
        
        for var in node_vars:
            assert is_node_level_var(var), f"{var} should be node-level"
    
    def test_ambiguous_vars(self):
        """Test variables that don't match clear patterns"""
        ambiguous = ["CUSTOM_VAR", "MY_SETTING", "USER_PREFERENCE"]
        
        for var in ambiguous:
            # Should default to workflow-level if not clearly node-level
            is_workflow = is_workflow_level_var(var)
            is_node = is_node_level_var(var)
            # At least one should be True, or both False (ambiguous)
            assert not (is_workflow and is_node), f"{var} cannot be both"


class TestNodeIdentification:
    """Test input/output node identification"""
    
    def test_identify_input_nodes(self, db):
        """Test identifying input nodes"""
        workflow = Workflow(name="Test Workflow")
        db.add(workflow)
        db.commit()
        
        # Create nodes
        node1 = WorkflowNode(
            workflow_id=workflow.id,
            node_type_id="input",
            name="Input 1",
            ui_x=0.0,
            ui_y=0.0,
            config={}
        )
        node2 = WorkflowNode(
            workflow_id=workflow.id,
            node_type_id="python",
            name="Process",
            ui_x=100.0,
            ui_y=0.0,
            config={}
        )
        db.add_all([node1, node2])
        db.commit()
        
        # Create edge: node1 -> node2
        edge = WorkflowEdge(
            workflow_id=workflow.id,
            source_node_id=node1.id,
            target_node_id=node2.id,
            weight=1.0
        )
        db.add(edge)
        db.commit()
        
        nodes = [node1, node2]
        edges = [edge]
        
        input_nodes = identify_input_nodes(nodes, edges)
        assert len(input_nodes) == 1
        assert input_nodes[0].id == node1.id
        
        # Cleanup
        db.delete(edge)
        db.delete(node2)
        db.delete(node1)
        db.delete(workflow)
        db.commit()
    
    def test_identify_output_nodes(self, db):
        """Test identifying output nodes"""
        workflow = Workflow(name="Test Workflow")
        db.add(workflow)
        db.commit()
        
        node1 = WorkflowNode(
            workflow_id=workflow.id,
            node_type_id="python",
            name="Process",
            ui_x=0.0,
            ui_y=0.0,
            config={}
        )
        node2 = WorkflowNode(
            workflow_id=workflow.id,
            node_type_id="output",
            name="Output 1",
            ui_x=100.0,
            ui_y=0.0,
            config={}
        )
        db.add_all([node1, node2])
        db.commit()
        
        edge = WorkflowEdge(
            workflow_id=workflow.id,
            source_node_id=node1.id,
            target_node_id=node2.id,
            weight=1.0
        )
        db.add(edge)
        db.commit()
        
        nodes = [node1, node2]
        edges = [edge]
        
        output_nodes = identify_output_nodes(nodes, edges)
        assert len(output_nodes) == 1
        assert output_nodes[0].id == node2.id
        
        # Cleanup
        db.delete(edge)
        db.delete(node2)
        db.delete(node1)
        db.delete(workflow)
        db.commit()
    
    def test_identify_multiple_inputs_outputs(self, db):
        """Test identifying multiple input/output nodes"""
        workflow = Workflow(name="Test Workflow")
        db.add(workflow)
        db.commit()
        
        # Create: input1 -> process -> output1
        #         input2 -> process -> output2
        input1 = WorkflowNode(workflow_id=workflow.id, node_type_id="input", name="Input 1", ui_x=0, ui_y=0, config={})
        input2 = WorkflowNode(workflow_id=workflow.id, node_type_id="input", name="Input 2", ui_x=0, ui_y=100, config={})
        process = WorkflowNode(workflow_id=workflow.id, node_type_id="python", name="Process", ui_x=100, ui_y=50, config={})
        output1 = WorkflowNode(workflow_id=workflow.id, node_type_id="output", name="Output 1", ui_x=200, ui_y=0, config={})
        output2 = WorkflowNode(workflow_id=workflow.id, node_type_id="output", name="Output 2", ui_x=200, ui_y=100, config={})
        
        db.add_all([input1, input2, process, output1, output2])
        db.commit()
        
        edges = [
            WorkflowEdge(workflow_id=workflow.id, source_node_id=input1.id, target_node_id=process.id, weight=1.0),
            WorkflowEdge(workflow_id=workflow.id, source_node_id=input2.id, target_node_id=process.id, weight=1.0),
            WorkflowEdge(workflow_id=workflow.id, source_node_id=process.id, target_node_id=output1.id, weight=1.0),
            WorkflowEdge(workflow_id=workflow.id, source_node_id=process.id, target_node_id=output2.id, weight=1.0),
        ]
        db.add_all(edges)
        db.commit()
        
        nodes = [input1, input2, process, output1, output2]
        input_nodes = identify_input_nodes(nodes, edges)
        output_nodes = identify_output_nodes(nodes, edges)
        
        assert len(input_nodes) == 2
        assert len(output_nodes) == 2
        assert {n.id for n in input_nodes} == {input1.id, input2.id}
        assert {n.id for n in output_nodes} == {output1.id, output2.id}
        
        # Cleanup
        for edge in edges:
            db.delete(edge)
        for node in nodes:
            db.delete(node)
        db.delete(workflow)
        db.commit()


class TestPortBuilding:
    """Test input/output port building"""
    
    def test_build_input_ports(self, db):
        """Test building input ports"""
        workflow = Workflow(name="Test")
        db.add(workflow)
        db.commit()
        
        node = WorkflowNode(
            workflow_id=workflow.id,
            node_type_id="input",
            name="Input Node",
            ui_x=0.0,
            ui_y=0.0,
            config={}
        )
        db.add(node)
        db.commit()
        
        ports = build_input_ports([node])
        assert len(ports) == 1
        assert ports[0]["node_id"] == str(node.id)
        assert ports[0]["node_name"] == "Input Node"
        assert ports[0]["node_type_id"] == "input"
        
        # Cleanup
        db.delete(node)
        db.delete(workflow)
        db.commit()
    
    def test_build_output_ports(self, db):
        """Test building output ports"""
        workflow = Workflow(name="Test")
        db.add(workflow)
        db.commit()
        
        node = WorkflowNode(
            workflow_id=workflow.id,
            node_type_id="output",
            name="Output Node",
            ui_x=0.0,
            ui_y=0.0,
            config={}
        )
        db.add(node)
        db.commit()
        
        ports = build_output_ports([node])
        assert len(ports) == 1
        assert ports[0]["node_id"] == str(node.id)
        assert ports[0]["node_name"] == "Output Node"
        
        # Cleanup
        db.delete(node)
        db.delete(workflow)
        db.commit()


class TestSerialization:
    """Test node and edge serialization"""
    
    def test_serialize_node(self, db):
        """Test node serialization"""
        workflow = Workflow(name="Test")
        db.add(workflow)
        db.commit()
        
        node = WorkflowNode(
            workflow_id=workflow.id,
            node_type_id="python",
            name="Test Node",
            ui_x=100.0,
            ui_y=200.0,
            config={"python_code": "print('test')"},
            node_config={"NODE_TIMEOUT": "30"}
        )
        db.add(node)
        db.commit()
        
        serialized = serialize_node(node)
        assert serialized["id"] == str(node.id)
        assert serialized["name"] == "Test Node"
        assert serialized["node_type_id"] == "python"
        assert serialized["ui_x"] == 100.0
        assert serialized["ui_y"] == 200.0
        assert serialized["config"]["python_code"] == "print('test')"
        assert serialized["node_config"]["NODE_TIMEOUT"] == "30"
        
        # Cleanup
        db.delete(node)
        db.delete(workflow)
        db.commit()
    
    def test_serialize_edge(self, db):
        """Test edge serialization"""
        workflow = Workflow(name="Test")
        db.add(workflow)
        db.commit()
        
        node1 = WorkflowNode(workflow_id=workflow.id, node_type_id="input", name="N1", ui_x=0, ui_y=0, config={})
        node2 = WorkflowNode(workflow_id=workflow.id, node_type_id="python", name="N2", ui_x=100, ui_y=0, config={})
        db.add_all([node1, node2])
        db.commit()
        
        edge = WorkflowEdge(
            workflow_id=workflow.id,
            source_node_id=node1.id,
            target_node_id=node2.id,
            weight=2.5
        )
        db.add(edge)
        db.commit()
        
        serialized = serialize_edge(edge)
        assert serialized["id"] == str(edge.id)
        assert serialized["source_node_id"] == str(node1.id)
        assert serialized["target_node_id"] == str(node2.id)
        assert serialized["weight"] == 2.5
        
        # Cleanup
        db.delete(edge)
        db.delete(node2)
        db.delete(node1)
        db.delete(workflow)
        db.commit()


class TestCircularDependency:
    """Test circular dependency detection"""
    
    def test_detect_self_reference(self, db):
        """Test detecting self-reference"""
        workflow_id = str(uuid.uuid4())
        assert detect_circular_dependency(workflow_id, workflow_id, db=db) is True
    
    def test_detect_no_circular(self, db):
        """Test detecting no circular dependency"""
        workflow1_id = str(uuid.uuid4())
        workflow2_id = str(uuid.uuid4())
        assert detect_circular_dependency(workflow1_id, workflow2_id, db=db) is False
    
    def test_detect_circular_chain(self, db):
        """Test detecting circular dependency in a chain"""
        workflow1_id = str(uuid.uuid4())
        workflow2_id = str(uuid.uuid4())
        workflow3_id = str(uuid.uuid4())
        
        # Create workflow2 that uses workflow3
        workflow2 = Workflow(id=workflow2_id, name="Workflow 2")
        db.add(workflow2)
        db.commit()
        
        node = WorkflowNode(
            workflow_id=workflow2.id,
            node_type_id="workflow_node",
            name="Sub Workflow",
            ui_x=0.0,
            ui_y=0.0,
            config={"workflow_id": workflow3_id}
        )
        db.add(node)
        db.commit()
        
        # workflow1 -> workflow2 -> workflow3 -> workflow1 (circular)
        # But we only check workflow2 -> workflow3, so should not detect yet
        # This is a simplified test - full circular detection would need workflow3 to reference workflow1
        result = detect_circular_dependency(workflow1_id, workflow2_id, db=db)
        # Should not detect circular yet (workflow3 doesn't reference workflow1)
        assert result is False
        
        # Cleanup
        db.delete(node)
        db.delete(workflow2)
        db.commit()

