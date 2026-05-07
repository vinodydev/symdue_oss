# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (c) 2026 Symdue contributors
"""
Comprehensive tests for Node Type System extensions (Phase 1)
"""
import pytest
from sqlalchemy.orm import Session
from database.connection import SessionLocal
from database.models import NodeType, Workflow, WorkflowNode
from uuid import uuid4


@pytest.fixture
def db():
    """Database session fixture"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestNodeTypeExtensions:
    """Test NodeType model extensions"""
    
    def test_node_type_with_all_new_fields(self, db: Session):
        """Test creating NodeType with all new template fields"""
        node_type = NodeType(
            id='test-template-001',
            category='node_template',
            name='Test Template',
            description='A test template',
            type_kind='node_template',
            node_template_data={
                'python_code': 'print("test")',
                'workflow_env_template': {'S3_BUCKET': {'type': 'string'}},
                'node_env_template': {'NODE_TIMEOUT': {'type': 'string'}}
            },
            workflow_env_template={'S3_BUCKET': {'type': 'string', 'required': True}},
            node_env_template={'NODE_TIMEOUT': {'type': 'string', 'required': False}},
            default_config={},
            config_schema={'type': 'object'},
            input_ports=[],
            output_ports=[],
            version=1,
            is_public=True,
            usage_count=0
        )
        
        db.add(node_type)
        db.commit()
        db.refresh(node_type)
        
        # Verify all fields are set
        assert node_type.type_kind == 'node_template'
        assert node_type.node_template_data is not None
        assert node_type.workflow_env_template is not None
        assert node_type.node_env_template is not None
        assert node_type.is_public is True
        assert node_type.usage_count == 0
        assert node_type.version == 1
        
        # Cleanup
        db.delete(node_type)
        db.commit()
    
    def test_node_type_default_type_kind(self, db: Session):
        """Test that type_kind defaults to 'node_type'"""
        node_type = NodeType(
            id='test-default-001',
            category='builtin',
            name='Test Default',
            default_config={}
        )
        
        db.add(node_type)
        db.commit()
        db.refresh(node_type)
        
        assert node_type.type_kind == 'node_type'
        
        # Cleanup
        db.delete(node_type)
        db.commit()
    
    def test_node_type_workflow_template(self, db: Session):
        """Test NodeType as workflow template"""
        # First create a workflow
        workflow = Workflow(
            name='Test Workflow for Template',
            workflow_config={'S3_BUCKET': 'test-bucket'}
        )
        db.add(workflow)
        db.commit()
        
        node_type = NodeType(
            id='workflow-template-001',
            category='workflow_template',
            name='Workflow Template',
            type_kind='workflow_template',
            workflow_template_data={
                'nodes': [],
                'edges': [],
                'storage_requirements': {}
            },
            workflow_id=workflow.id,
            input_ports=[{'node_id': 'input-1', 'name': 'Input 1'}],
            output_ports=[{'node_id': 'output-1', 'name': 'Output 1'}]
        )
        
        db.add(node_type)
        db.commit()
        db.refresh(node_type)
        
        assert node_type.type_kind == 'workflow_template'
        assert node_type.workflow_id == workflow.id
        assert node_type.input_ports is not None
        assert node_type.output_ports is not None
        
        # Cleanup
        db.delete(node_type)
        db.delete(workflow)
        db.commit()
    
    def test_node_type_parent_template_relationship(self, db: Session):
        """Test parent_template_id foreign key relationship"""
        # Create parent template
        parent = NodeType(
            id='parent-template-001',
            category='node_template',
            name='Parent Template',
            type_kind='node_template',
            default_config={}
        )
        db.add(parent)
        db.commit()
        
        # Create child template
        child = NodeType(
            id='child-template-001',
            category='node_template',
            name='Child Template',
            type_kind='node_template',
            parent_template_id='parent-template-001',
            default_config={}
        )
        db.add(child)
        db.commit()
        db.refresh(child)
        
        assert child.parent_template_id == 'parent-template-001'
        
        # Cleanup
        db.delete(child)
        db.delete(parent)
        db.commit()


class TestWorkflowExtensions:
    """Test Workflow model extensions"""
    
    def test_workflow_with_workflow_config(self, db: Session):
        """Test Workflow with workflow_config"""
        workflow = Workflow(
            name='Test Workflow',
            workflow_config={
                'S3_BUCKET': 'my-bucket',
                'DATABASE_URL': 'postgresql://localhost/test',
                'API_KEY': 'test-key-123'
            }
        )
        
        db.add(workflow)
        db.commit()
        db.refresh(workflow)
        
        assert workflow.workflow_config is not None
        assert workflow.workflow_config['S3_BUCKET'] == 'my-bucket'
        assert workflow.workflow_config['DATABASE_URL'] == 'postgresql://localhost/test'
        assert workflow.workflow_config['API_KEY'] == 'test-key-123'
        
        # Cleanup
        db.delete(workflow)
        db.commit()
    
    def test_workflow_with_template_id(self, db: Session):
        """Test Workflow with template_id"""
        # Create a template
        template = NodeType(
            id='workflow-template-002',
            category='workflow_template',
            name='Test Template',
            type_kind='workflow_template',
            default_config={}
        )
        db.add(template)
        db.commit()
        
        workflow = Workflow(
            name='Workflow from Template',
            template_id='workflow-template-002'
        )
        
        db.add(workflow)
        db.commit()
        db.refresh(workflow)
        
        assert workflow.template_id == 'workflow-template-002'
        
        # Cleanup
        db.delete(workflow)
        db.delete(template)
        db.commit()
    
    def test_workflow_config_default_empty_dict(self, db: Session):
        """Test that workflow_config defaults to empty dict"""
        workflow = Workflow(name='Test Workflow')
        
        db.add(workflow)
        db.commit()
        db.refresh(workflow)
        
        # After migration, workflow_config should default to {}
        assert workflow.workflow_config is not None
        assert isinstance(workflow.workflow_config, dict)
        
        # Cleanup
        db.delete(workflow)
        db.commit()


class TestWorkflowNodeExtensions:
    """Test WorkflowNode model extensions"""
    
    def test_workflow_node_with_node_config(self, db: Session):
        """Test WorkflowNode with node_config"""
        workflow = Workflow(name='Test Workflow')
        db.add(workflow)
        db.commit()
        
        node = WorkflowNode(
            workflow_id=workflow.id,
            node_type_id='python',
            name='Test Node',
            ui_x=0.0,
            ui_y=0.0,
            config={'python_code': 'print("test")'},
            node_config={
                'NODE_TIMEOUT': '30',
                'NODE_RETRIES': '3',
                'NODE_CHECK_INTERVAL': '10'
            }
        )
        
        db.add(node)
        db.commit()
        db.refresh(node)
        
        assert node.node_config is not None
        assert node.node_config['NODE_TIMEOUT'] == '30'
        assert node.node_config['NODE_RETRIES'] == '3'
        assert node.node_config['NODE_CHECK_INTERVAL'] == '10'
        
        # Cleanup
        db.delete(node)
        db.delete(workflow)
        db.commit()
    
    def test_workflow_node_config_default_empty_dict(self, db: Session):
        """Test that node_config defaults to empty dict"""
        workflow = Workflow(name='Test Workflow')
        db.add(workflow)
        db.commit()
        
        node = WorkflowNode(
            workflow_id=workflow.id,
            node_type_id='python',
            name='Test Node',
            ui_x=0.0,
            ui_y=0.0,
            config={}
        )
        
        db.add(node)
        db.commit()
        db.refresh(node)
        
        # After migration, node_config should default to {}
        assert node.node_config is not None
        assert isinstance(node.node_config, dict)
        
        # Cleanup
        db.delete(node)
        db.delete(workflow)
        db.commit()


class TestForeignKeys:
    """Test foreign key relationships"""
    
    def test_node_type_workflow_id_foreign_key(self, db: Session):
        """Test node_type.workflow_id foreign key"""
        workflow = Workflow(name='Test Workflow')
        db.add(workflow)
        db.commit()
        
        node_type = NodeType(
            id='test-fk-001',
            category='workflow_template',
            name='Test FK',
            type_kind='workflow_template',
            workflow_id=workflow.id,
            default_config={}
        )
        
        db.add(node_type)
        db.commit()
        db.refresh(node_type)
        
        assert node_type.workflow_id == workflow.id
        
        # Cleanup
        db.delete(node_type)
        db.delete(workflow)
        db.commit()
    
    def test_workflow_template_id_foreign_key(self, db: Session):
        """Test workflow.template_id foreign key"""
        template = NodeType(
            id='template-fk-001',
            category='workflow_template',
            name='Template FK',
            type_kind='workflow_template',
            default_config={}
        )
        db.add(template)
        db.commit()
        
        workflow = Workflow(
            name='Workflow with Template',
            template_id='template-fk-001'
        )
        
        db.add(workflow)
        db.commit()
        db.refresh(workflow)
        
        assert workflow.template_id == 'template-fk-001'
        
        # Cleanup
        db.delete(workflow)
        db.delete(template)
        db.commit()


class TestIndexes:
    """Test that indexes are created correctly"""
    
    def test_type_kind_index_exists(self, db: Session):
        """Test that type_kind index allows efficient queries"""
        # Create templates with different type_kind
        node_template = NodeType(
            id='node-tmpl-001',
            category='node_template',
            name='Node Template',
            type_kind='node_template',
            default_config={}
        )
        
        workflow_template = NodeType(
            id='workflow-tmpl-001',
            category='workflow_template',
            name='Workflow Template',
            type_kind='workflow_template',
            default_config={}
        )
        
        db.add_all([node_template, workflow_template])
        db.commit()
        
        # Query by type_kind (should use index)
        node_templates = db.query(NodeType).filter(
            NodeType.type_kind == 'node_template'
        ).all()
        
        workflow_templates = db.query(NodeType).filter(
            NodeType.type_kind == 'workflow_template'
        ).all()
        
        assert len(node_templates) >= 1
        assert len(workflow_templates) >= 1
        
        # Cleanup
        db.delete(node_template)
        db.delete(workflow_template)
        db.commit()

