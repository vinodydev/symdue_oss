// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Node component — plain HTML div, matching reference architecture.
 * Rendered as an absolutely-positioned div inside the CSS-transformed canvas layer.
 */
import React, { useState, useCallback } from 'react';
import { useAppStore } from '@/stores';
import { api } from '@/services/api';
import type { Node as NodeType } from '@/types';
import { cn } from '@/utils/cn';
import { Database, Code, Cpu, History, Loader2, CheckCircle2, XCircle, Workflow, Clock } from 'lucide-react';
import { NodeContextMenu } from './NodeContextMenu';
import { PreFlightModal } from './PreFlightModal';

interface NodeProps {
  node: NodeType;
  isSelected: boolean;
  isConnecting: boolean;
  movingNodeId: string | null;
  onClick: (e: React.MouseEvent, nodeId: string) => void;
  onDoubleClick: (e: React.MouseEvent, nodeId: string) => void;
  onMouseUp: (nodeId: string) => void;
  onStartEdgeCreation: (nodeId: string, sourceHandle?: 'true' | 'false') => void;
}

const iconMap: Record<string, typeof Database> = {
  input: Database,
  'custom-python': Code,
  'condition-python': Code,
  'custom-llm': Cpu,
  memory: History,
  workflow_node: Workflow,
};

export function Node({
  node,
  isSelected,
  isConnecting: _isConnecting,
  movingNodeId,
  onClick,
  onDoubleClick,
  onMouseUp,
  onStartEdgeCreation,
}: NodeProps) {
  const {
    currentWorkspaceId,
    setSelectedNode,
    setCurrentWorkspace,
    setCurrentView,
    deleteNode,
    nodeStatuses,
    setPropertiesPanelOpen,
    activeTool,
  } = useAppStore();

  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null);
  const [showPreFlightModal, setShowPreFlightModal] = useState(false);

  const status = nodeStatuses[node.id] || 'idle';
  const IconComponent = iconMap[node.node_type_id] || iconMap[node.node_type_id.split('-')[0]] || Database;
  const isExecuting = status === 'running';
  const isSuccess = status === 'success';
  const isError = status === 'error';
  const isWaiting = status === 'waiting';
  const isBlocked = status === 'blocked';
  const isMoving = movingNodeId === node.id;
  const nodeName = node.name || node.node_type_id;

  const isConditionNode =
    node.node_type_id === 'condition-python' ||
    (node.node_type_id === 'custom-python' && node.config?.condition_mode === true);

  const getNodeContent = () => {
    if (node.node_type_id === 'input') return String(node.config?.value || '');
    if (node.node_type_id === 'custom-python' || node.node_type_id === 'condition-python') return node.config?.code || '';
    if (node.node_type_id === 'custom-llm') return node.config?.prompt || '';
    if (node.node_type_id === 'workflow_node') return node.config?.workflow_name ? `Workflow: ${node.config.workflow_name}` : 'Workflow';
    return '';
  };

  // --- event handlers ---

  /** Single click → select node + open properties panel */
  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      onClick(e, node.id);
      setPropertiesPanelOpen(true);
    },
    [onClick, node.id, setPropertiesPanelOpen],
  );

  /** Double click → start dragging (same for all nodes, including workflow_node) */
  const handleDoubleClick = useCallback(
    (e: React.MouseEvent) => {
      onDoubleClick(e, node.id);
    },
    [onDoubleClick, node.id],
  );

  /** Mouse-up on this node → complete edge connection */
  const handleMouseUp = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      onMouseUp(node.id);
    },
    [onMouseUp, node.id],
  );

  /** Context menu */
  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({ x: e.clientX, y: e.clientY });
  }, []);

  /** Delete node */
  const handleDelete = async () => {
    if (!currentWorkspaceId) return;
    if (!confirm('Delete this node and all connected edges?')) return;
    try {
      await api.deleteNode(currentWorkspaceId, node.id);
      deleteNode(node.id);
      setSelectedNode(null);
      setPropertiesPanelOpen(false);
    } catch (err) {
      console.error('Failed to delete node:', err);
      alert('Failed to delete node');
    }
  };

  /** Duplicate node */
  const handleDuplicate = async () => {
    if (!currentWorkspaceId) return;
    try {
      const newNode = await api.createNode(currentWorkspaceId, {
        node_type_id: node.node_type_id,
        x: node.x + 30,
        y: node.y + 30,
        config_overrides: { ...node.config },
      });
      useAppStore.getState().addNode(newNode);
    } catch (err) {
      console.error('Failed to duplicate node:', err);
      alert('Failed to duplicate node');
    }
  };

  /** Test / preflight */
  const handleTest = () => setShowPreFlightModal(true);

  /** Open linked workflow (workflow_node only) */
  const handleOpenWorkflow = () => {
    if (node.node_type_id === 'workflow_node' && node.config?.workflow_id) {
      setCurrentWorkspace(node.config.workflow_id);
      setCurrentView('editor');
    }
  };

  // --- render ---

  return (
    <>
      {/* Node as an absolutely-positioned HTML div (reference line 480) */}
      <div
        style={{ left: node.x, top: node.y }}
        className={cn(
          'absolute w-[220px] rounded-2xl border-2 transition-all backdrop-blur-md overflow-visible',
          isSelected
            ? 'border-indigo-500 shadow-2xl z-30 ring-4 ring-indigo-500/10'
            : 'border-slate-800 bg-slate-900/95 shadow-xl',
          isExecuting ? 'border-emerald-400 ring-8 ring-emerald-500/20 scale-105' : '',
          isSuccess ? 'border-emerald-500/60 ring-2 ring-emerald-500/10' : '',
          isError ? 'border-red-500/60 ring-2 ring-red-500/10' : '',
          isWaiting ? 'border-amber-400/60 ring-4 ring-amber-500/15' : '',
          isBlocked ? 'border-slate-600/40 opacity-60' : '',
          isMoving
            ? 'opacity-70 scale-[1.02] border-blue-500 animate-pulse'
            : 'cursor-pointer hover:border-slate-600',
        )}
        onClick={handleClick}
        onDoubleClick={handleDoubleClick}
        onMouseUp={handleMouseUp}
        onContextMenu={handleContextMenu}
      >
        {/* Header */}
        <div className="px-4 py-3 flex items-center justify-between border-b border-slate-800/50">
          <div className="flex items-center gap-2 pointer-events-none">
            <IconComponent
              size={14}
              className={cn(
                node.node_type_id === 'input'
                  ? 'text-emerald-500'
                  :                 node.node_type_id === 'custom-python'
                    ? 'text-yellow-500'
                    : node.node_type_id === 'condition-python'
                      ? 'text-amber-500'
                      : node.node_type_id === 'custom-llm'
                      ? 'text-purple-500'
                      : node.node_type_id === 'workflow_node'
                        ? 'text-cyan-500'
                        : 'text-blue-500',
              )}
            />
            <span className="text-[10px] font-black uppercase tracking-tighter text-slate-100">
              {nodeName}
            </span>
          </div>
          {isExecuting && <Loader2 size={12} className="text-emerald-400 animate-spin" />}
          {isSuccess && <CheckCircle2 size={12} className="text-emerald-500" />}
          {isError && <XCircle size={12} className="text-red-500" />}
          {isWaiting && <Clock size={12} className="text-amber-400 animate-pulse" />}
          {isBlocked && <Clock size={12} className="text-slate-500" />}
        </div>

        {/* Content preview */}
        <div className="p-3 pointer-events-none text-[9px] font-mono text-slate-500 line-clamp-2 italic">
          {getNodeContent()}
        </div>

        {/* Input port (left side) */}
        <div
          className="absolute left-[-8px] top-1/2 -translate-y-1/2 w-4 h-4 bg-slate-800 rounded-full border-2 border-slate-950 transition-all z-40 connection-port input-port hover:bg-emerald-500 cursor-crosshair"
        />

        {/* Output port(s) (right side) — single port or True/False for condition node */}
        {isConditionNode ? (
          <>
            <div
              className={cn(
                'absolute right-[-8px] top-[30%] -translate-y-1/2 w-4 h-4 rounded-full border-2 border-slate-950 transition-all z-40 connection-port output-port',
                activeTool === 'select' && !isExecuting
                  ? 'bg-emerald-800 hover:bg-emerald-500 cursor-crosshair'
                  : 'bg-slate-800 opacity-0 pointer-events-none',
              )}
              title="True branch"
              onMouseDown={(e) => {
                e.stopPropagation();
                onStartEdgeCreation(node.id, 'true');
              }}
            />
            <div
              className={cn(
                'absolute right-[-8px] top-[70%] -translate-y-1/2 w-4 h-4 rounded-full border-2 border-slate-950 transition-all z-40 connection-port output-port',
                activeTool === 'select' && !isExecuting
                  ? 'bg-rose-800 hover:bg-rose-500 cursor-crosshair'
                  : 'bg-slate-800 opacity-0 pointer-events-none',
              )}
              title="False branch"
              onMouseDown={(e) => {
                e.stopPropagation();
                onStartEdgeCreation(node.id, 'false');
              }}
            />
          </>
        ) : (
          <div
            className={cn(
              'absolute right-[-8px] top-1/2 -translate-y-1/2 w-4 h-4 bg-slate-800 rounded-full border-2 border-slate-950 transition-all z-40 connection-port output-port',
              activeTool === 'select' && !isExecuting
                ? 'hover:bg-indigo-500 cursor-crosshair'
                : 'opacity-0 pointer-events-none',
            )}
            onMouseDown={(e) => {
              e.stopPropagation();
              onStartEdgeCreation(node.id);
            }}
          />
        )}
      </div>

      {/* Context menu (portal-style, outside the node div) */}
      {contextMenu && (
        <NodeContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          onDelete={handleDelete}
          onDuplicate={handleDuplicate}
          onTest={handleTest}
          onOpenWorkflow={node.node_type_id === 'workflow_node' && node.config?.workflow_id ? handleOpenWorkflow : undefined}
          onClose={() => setContextMenu(null)}
        />
      )}

      {/* Pre-flight modal */}
      {showPreFlightModal && currentWorkspaceId && (
        <PreFlightModal
          node={node}
          workspaceId={currentWorkspaceId}
          onClose={() => setShowPreFlightModal(false)}
        />
      )}
    </>
  );
}
