// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Node type palette component - Matching reference design
 * Now includes tabs for Built-in, Node Templates, and Workflow Templates
 */
import React, { useState, useEffect } from 'react';
import type { NodeType } from '@/types';
import { Box, Database, Code, Cpu, History, Workflow, FileCode } from 'lucide-react';
import { api } from '@/services/api';
import { CreateNodeFromTemplateDialog } from '../Node/CreateNodeFromTemplateDialog';
import { CreateWorkflowFromTemplateDialog } from '../Workflow/CreateWorkflowFromTemplateDialog';
import { useAppStore } from '@/stores';
import { cn } from '@/utils/cn';

interface NodeTypePaletteProps {
  nodeTypes: NodeType[];
}

const iconMap: Record<string, React.ComponentType<{ size?: number; className?: string }>> = {
  'input': Database,
  'custom-python': Code,
  'condition-python': Code,
  'custom-llm': Cpu,
  'memory': History,
  'workflow_node': Workflow,
  database: Database,
  code: Code,
  cpu: Cpu,
  history: History,
  workflow: Workflow,
  default: Box,
};

type TabType = 'builtin' | 'node_templates' | 'workflow_templates';

export function NodeTypePalette({ nodeTypes }: NodeTypePaletteProps) {
  const [activeTab, setActiveTab] = useState<TabType>('builtin');
  const [nodeTemplates, setNodeTemplates] = useState<NodeType[]>([]);
  const [workflowTemplates, setWorkflowTemplates] = useState<NodeType[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<NodeType | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const { currentWorkspaceId } = useAppStore();

  // Load templates when tab changes
  useEffect(() => {
    if (activeTab === 'node_templates') {
      loadNodeTemplates();
    } else if (activeTab === 'workflow_templates') {
      loadWorkflowTemplates();
    }
  }, [activeTab]);

  const loadNodeTemplates = async () => {
    try {
      const templates = await api.getNodeTypes(undefined, undefined, 'node_template');
      setNodeTemplates(templates);
    } catch (err) {
      console.error('Failed to load node templates:', err);
    }
  };

  const loadWorkflowTemplates = async () => {
    try {
      const templates = await api.getNodeTypes(undefined, undefined, 'workflow_template');
      setWorkflowTemplates(templates);
    } catch (err) {
      console.error('Failed to load workflow templates:', err);
    }
  };

  const handleTemplateClick = (template: NodeType) => {
    if (!currentWorkspaceId) {
      alert('Please select a workspace first');
      return;
    }
    setSelectedTemplate(template);
    setShowCreateDialog(true);
  };

  const getIcon = (iconName: string | null, nodeTypeId: string) => {
    // Try to match by node type ID first
    const directMatch = iconMap[nodeTypeId] || iconMap[nodeTypeId.split('-')[0]];
    if (directMatch) return directMatch;
    
    // Fall back to icon name
    const IconComponent = iconName && iconMap[iconName] ? iconMap[iconName] : iconMap.default;
    return IconComponent;
  };

  // Filter built-in types
  const builtinTypes = nodeTypes.filter(t => t.is_builtin && (!t.type_kind || t.type_kind === 'node_type'));

  // Group types by category
  const groupedTypes = (types: NodeType[]) => {
    return types.reduce((acc, type) => {
      if (!acc[type.category]) {
        acc[type.category] = [];
      }
      acc[type.category].push(type);
      return acc;
    }, {} as Record<string, NodeType[]>);
  };

  const renderTypeList = (types: NodeType[], isTemplate = false) => {
    const grouped = groupedTypes(types);
    return (
      <div className="space-y-4">
        {Object.entries(grouped).map(([category, typeList]) => (
          <div key={category}>
            <h3 className="text-[10px] font-black text-slate-500 uppercase mb-2 tracking-widest">{category}</h3>
            <div className="space-y-1">
              {typeList.map((type) => {
                const IconComponent = getIcon(type.icon, type.id);
                // All types are draggable (backend handles node_template + workflow_template expansion)
                // Node templates also support click for advanced config (env vars, storages)
                const isNodeTemplate = type.type_kind === 'node_template';
                return (
                  <div
                    key={type.id}
                    className="flex items-center gap-2 p-2 rounded-lg transition-colors hover:bg-slate-800 cursor-move"
                    draggable
                    onDragStart={(e) => {
                      e.dataTransfer.setData('application/node-type', JSON.stringify(type));
                    }}
                    onClick={() => isNodeTemplate && handleTemplateClick(type)}
                    title={type.description || type.name}
                  >
                    <IconComponent size={16} className="text-slate-400 flex-shrink-0" />
                    <span className="text-sm text-slate-300 flex-1">{type.name}</span>
                    {isTemplate && type.usage_count !== undefined && (
                      <span className="text-xs text-slate-500">({type.usage_count})</span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="p-4">
      <h2 className="text-sm font-semibold text-slate-300 mb-4">Node Types</h2>
      
      {/* Tabs */}
      <div className="flex gap-2 mb-4 border-b border-slate-700">
        <button
          onClick={() => setActiveTab('builtin')}
          className={cn(
            "px-3 py-2 text-xs font-medium transition-colors border-b-2",
            activeTab === 'builtin'
              ? "text-blue-400 border-blue-400"
              : "text-slate-500 border-transparent hover:text-slate-300"
          )}
        >
          Built-in
        </button>
        <button
          onClick={() => setActiveTab('node_templates')}
          className={cn(
            "px-3 py-2 text-xs font-medium transition-colors border-b-2",
            activeTab === 'node_templates'
              ? "text-blue-400 border-blue-400"
              : "text-slate-500 border-transparent hover:text-slate-300"
          )}
        >
          Node Templates
        </button>
        <button
          onClick={() => setActiveTab('workflow_templates')}
          className={cn(
            "px-3 py-2 text-xs font-medium transition-colors border-b-2",
            activeTab === 'workflow_templates'
              ? "text-blue-400 border-blue-400"
              : "text-slate-500 border-transparent hover:text-slate-300"
          )}
        >
          Workflow Templates
        </button>
      </div>

      {/* Content */}
      <div className="max-h-[calc(100vh-300px)] overflow-y-auto">
        {activeTab === 'builtin' && renderTypeList(builtinTypes)}
        {activeTab === 'node_templates' && (
          nodeTemplates.length > 0 ? (
            renderTypeList(nodeTemplates, true)
          ) : (
            <p className="text-sm text-slate-500 text-center py-8">No node templates available</p>
          )
        )}
        {activeTab === 'workflow_templates' && (
          workflowTemplates.length > 0 ? (
            renderTypeList(workflowTemplates, true)
          ) : (
            <p className="text-sm text-slate-500 text-center py-8">No workflow templates available</p>
          )
        )}
      </div>

      {/* Create Dialogs */}
      {selectedTemplate && (
        <>
          {selectedTemplate.type_kind === 'node_template' && (
            <CreateNodeFromTemplateDialog
              open={showCreateDialog}
              template={selectedTemplate}
              workspaceId={currentWorkspaceId || ''}
              onClose={() => {
                setShowCreateDialog(false);
                setSelectedTemplate(null);
              }}
              onSuccess={(nodeId) => {
                setShowCreateDialog(false);
                setSelectedTemplate(null);
                // Refresh workspace to show new node
                window.location.reload();
              }}
            />
          )}
          {selectedTemplate.type_kind === 'workflow_template' && (
            <CreateWorkflowFromTemplateDialog
              open={showCreateDialog}
              template={selectedTemplate}
              onClose={() => {
                setShowCreateDialog(false);
                setSelectedTemplate(null);
              }}
              onSuccess={(workflowId) => {
                setShowCreateDialog(false);
                setSelectedTemplate(null);
                // Navigate to new workflow or refresh
                window.location.reload();
              }}
            />
          )}
        </>
      )}
    </div>
  );
}
