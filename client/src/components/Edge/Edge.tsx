// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Edge visual component with weight visualization
 */
import React, { useState, useCallback } from 'react';
import { useAppStore } from '@/stores';
import { api } from '@/services/api';
import type { Edge, Node } from '@/types';
import { cn } from '@/utils/cn';
import { EdgeContextMenu } from './EdgeContextMenu';

interface EdgeProps {
  edge: Edge;
  sourceNode: Node | undefined;
  targetNode: Node | undefined;
  isSelected: boolean;
}

export function Edge({ edge, sourceNode, targetNode, isSelected }: EdgeProps) {
  const { currentWorkspaceId, setSelectedEdge, deleteEdge, setPropertiesPanelOpen } = useAppStore();
  const [isHovered, setIsHovered] = useState(false);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null);

  if (!sourceNode || !targetNode) {
    return null;
  }

  // Condition nodes have two output ports at 30% and 70% of node height; others use center.
  const NODE_WIDTH = 220;
  const NODE_HEIGHT = 120; // Approximate; matches Node layout (top-[30%] / top-[70%])
  const isConditionSource =
    (sourceNode.node_type_id === 'condition-python' || sourceNode.config?.condition_mode === true) &&
    (edge.source_handle === 'true' || edge.source_handle === 'false');

  const x1 = sourceNode.x + NODE_WIDTH;
  const y1 = isConditionSource
    ? sourceNode.y + (edge.source_handle === 'true' ? 0.3 * NODE_HEIGHT : 0.7 * NODE_HEIGHT)
    : sourceNode.y + NODE_HEIGHT / 2;

  // Calculate edge path with bezier curve (matching reference: nodes are 220px wide)
  const x2 = targetNode.x; // Left side of target node
  const y2 = targetNode.y + 60; // Middle of node

  // Control points for bezier curve (smooth S-curve)
  const dx = x2 - x1;
  const controlOffset = Math.min(Math.abs(dx) * 0.5, 100);
  const cp1x = x1 + controlOffset;
  const cp1y = y1;
  const cp2x = x2 - controlOffset;
  const cp2y = y2;

  // Calculate midpoint for weight label (on the curve)
  const t = 0.5; // Midpoint parameter
  const midX = Math.pow(1 - t, 3) * x1 + 3 * Math.pow(1 - t, 2) * t * cp1x + 3 * (1 - t) * Math.pow(t, 2) * cp2x + Math.pow(t, 3) * x2;
  const midY = Math.pow(1 - t, 3) * y1 + 3 * Math.pow(1 - t, 2) * t * cp1y + 3 * (1 - t) * Math.pow(t, 2) * cp2y + Math.pow(t, 3) * y2;

  // Weight-based styling
  const getWeightColor = () => {
    if (edge.weight < 0.3) return '#ef4444'; // red
    if (edge.weight < 0.7) return '#eab308'; // yellow
    return '#22c55e'; // green
  };

  const getWeightThickness = () => {
    return Math.max(1, Math.min(4, edge.weight * 4));
  };

  const weightColor = getWeightColor();
  const thickness = getWeightThickness();

  const handleClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedEdge(edge.id);
  }, [edge.id, setSelectedEdge]);

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({ x: e.clientX, y: e.clientY });
  }, []);

  const handleDelete = async () => {
    if (!currentWorkspaceId) return;
    if (!confirm('Are you sure you want to delete this edge?')) {
      return;
    }
    try {
      await api.deleteEdge(currentWorkspaceId, edge.id);
      deleteEdge(edge.id);
      setSelectedEdge(null);
    } catch (error) {
      console.error('Failed to delete edge:', error);
      alert('Failed to delete edge');
    }
  };

  const handleEditWeight = () => {
    setSelectedEdge(edge.id);
    setPropertiesPanelOpen(true);
  };

  return (
    <g
      onClick={handleClick}
      onContextMenu={handleContextMenu}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{ cursor: 'pointer' }}
    >
      {/* Edge path with bezier curve - matching reference */}
      <path
        d={`M ${x1} ${y1} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${x2} ${y2}`}
        fill="none"
        stroke={isSelected ? '#6366f1' : '#475569'}
        strokeWidth={isSelected ? 4 : 2}
        markerEnd={isSelected ? "url(#arrow-selected)" : "url(#arrow)"}
        className={cn(
          'transition-all duration-200 pointer-events-none',
          isHovered || isSelected ? 'opacity-100' : 'opacity-60'
        )}
      />
      
      {/* Invisible hit area for easier clicking */}
      <path
        d={`M ${x1} ${y1} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${x2} ${y2}`}
        fill="none"
        stroke="transparent"
        strokeWidth="20"
        className="pointer-events-auto cursor-pointer"
      />

      {/* Weight label (show on hover or when selected) */}
      {(isHovered || isSelected) && (
        <g>
          <rect
            x={midX - 25}
            y={midY - 10}
            width={50}
            height={20}
            rx={4}
            fill="#0f172a"
            stroke={weightColor}
            strokeWidth={1}
            className="opacity-90"
          />
          <text
            x={midX}
            y={midY + 5}
            textAnchor="middle"
            className="text-[10px] fill-slate-200 font-mono font-bold"
          >
            {edge.weight.toFixed(1)}
          </text>
        </g>
      )}

      {/* Context menu */}
      {contextMenu && (
        <EdgeContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          onDelete={handleDelete}
          onEditWeight={handleEditWeight}
          onClose={() => setContextMenu(null)}
        />
      )}
    </g>
  );
}

