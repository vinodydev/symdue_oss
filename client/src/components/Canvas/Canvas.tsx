// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Infinite canvas with zoom/pan — reference-matching architecture.
 * Nodes are plain HTML divs; SVG is used only for edges.
 */
import React, { useRef, useState, useCallback, useMemo } from 'react';
import { useAppStore } from '@/stores';
import { api } from '@/services/api';
import { Node } from '../Node/Node';
import { Edge } from '../Edge/Edge';
import { ZoomControls } from './ZoomControls';
import { ExecuteButton } from './ExecuteButton';

export function Canvas() {
  const {
    nodes,
    edges,
    transform,
    setTransform,
    currentWorkspaceId,
    selectedNodeId,
    selectedEdgeId,
    setSelectedNode,
    setSelectedEdge,
    addEdge,
    activeTool,
    updateNode,
  } = useAppStore();

  const containerRef = useRef<HTMLDivElement>(null);

  // --- interaction state (all local, matching reference) ---
  const [isPanning, setIsPanning] = useState(false);
  const [panOffset, setPanOffset] = useState({ x: 0, y: 0 });

  const [movingNodeId, setMovingNodeId] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });

  const [connectingSource, setConnectingSource] = useState<string | null>(null);
  const [connectingSourceHandle, setConnectingSourceHandle] = useState<'true' | 'false' | null>(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  // Debounce timer for node-position API calls
  const positionTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // --------------- helpers ---------------

  /** Convert a client-pixel position to canvas-space coordinates */
  const toCanvas = useCallback(
    (clientX: number, clientY: number) => {
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return { x: 0, y: 0 };
      return {
        x: (clientX - rect.left - transform.x) / transform.k,
        y: (clientY - rect.top - transform.y) / transform.k,
      };
    },
    [transform],
  );

  // --------------- canvas mouse handlers ---------------

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      // If the click lands on the background container or its grid div, start panning
      const target = e.target as HTMLElement;
      const isBackground =
        target === containerRef.current ||
        target.classList.contains('canvas-background');

      if (activeTool === 'pan' || (isBackground && activeTool === 'select')) {
        setIsPanning(true);
        setPanOffset({ x: e.clientX - transform.x, y: e.clientY - transform.y });
        e.preventDefault();
      }

      // Background click in select mode → deselect everything
      if (isBackground && activeTool === 'select' && e.button === 0) {
        setSelectedNode(null);
        setSelectedEdge(null);
        if (connectingSource) {
          setConnectingSource(null);
          setConnectingSourceHandle(null);
        }
      }
    },
    [activeTool, transform.x, transform.y, setSelectedNode, setSelectedEdge, connectingSource],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      // Always track canvas-space mouse position (needed for edge preview)
      const pos = toCanvas(e.clientX, e.clientY);
      setMousePos(pos);

      if (isPanning) {
        // Canvas panning
        setTransform({
          x: e.clientX - panOffset.x,
          y: e.clientY - panOffset.y,
          k: transform.k,
        });
      } else if (movingNodeId && activeTool === 'select') {
        // Node dragging
        const newX = pos.x - dragOffset.x;
        const newY = pos.y - dragOffset.y;
        updateNode(movingNodeId, { x: newX, y: newY });

        // Debounced API persist
        if (currentWorkspaceId) {
          if (positionTimerRef.current) clearTimeout(positionTimerRef.current);
          const nid = movingNodeId;
          positionTimerRef.current = setTimeout(() => {
            api
              .updateNodePosition(currentWorkspaceId, nid, { x: newX, y: newY })
              .catch((err) => console.error('Failed to persist node position:', err));
          }, 300);
        }
      }
    },
    [isPanning, panOffset, transform.k, setTransform, movingNodeId, activeTool, dragOffset, toCanvas, updateNode, currentWorkspaceId],
  );

  const handleMouseUp = useCallback(() => {
    setIsPanning(false);
    // Clear dragging unless we're in edge-creation mode (reference line 322)
    if (!connectingSource) setMovingNodeId(null);
  }, [connectingSource]);

  // Zoom with wheel (towards cursor)
  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault();
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      const newScale = Math.max(0.2, Math.min(3, transform.k * delta));
      const rect = containerRef.current?.getBoundingClientRect();
      if (rect) {
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        const sc = newScale / transform.k;
        setTransform({
          x: mx - (mx - transform.x) * sc,
          y: my - (my - transform.y) * sc,
          k: newScale,
        });
      }
    },
    [transform, setTransform],
  );

  // --------------- node interaction callbacks ---------------

  /** Single click → select + open properties */
  const handleNodeClick = useCallback(
    (e: React.MouseEvent, nodeId: string) => {
      if (activeTool !== 'select') return;
      e.stopPropagation();
      setSelectedNode(nodeId);
      setSelectedEdge(null);
    },
    [activeTool, setSelectedNode, setSelectedEdge],
  );

  /** Double click → start dragging */
  const handleNodeDoubleClick = useCallback(
    (e: React.MouseEvent, nodeId: string) => {
      if (activeTool !== 'select') return;
      e.stopPropagation();
      const node = nodes.find((n) => n.id === nodeId);
      if (!node) return;
      const pos = toCanvas(e.clientX, e.clientY);
      setMovingNodeId(nodeId);
      setDragOffset({ x: pos.x - node.x, y: pos.y - node.y });
    },
    [activeTool, nodes, toCanvas],
  );

  /** Output-port mousedown → start edge creation (optionally with source handle for condition nodes) */
  const handleStartEdgeCreation = useCallback((nodeId: string, sourceHandle?: 'true' | 'false') => {
    setConnectingSource(nodeId);
    setConnectingSourceHandle(sourceHandle ?? null);
  }, []);

  /** Mouse-up on a node → complete edge connection */
  const handleCompleteConnection = useCallback(
    async (targetNodeId: string) => {
      if (!connectingSource || !currentWorkspaceId) {
        setConnectingSource(null);
        setConnectingSourceHandle(null);
        setMovingNodeId(null);
        return;
      }
      if (connectingSource === targetNodeId) {
        setConnectingSource(null);
        setConnectingSourceHandle(null);
        return;
      }
      // Prevent duplicate edges (same source, target, and handle)
      const dup = edges.find(
        (e) =>
          e.source === connectingSource &&
          e.target === targetNodeId &&
          (e.source_handle ?? undefined) === (connectingSourceHandle ?? undefined)
      );
      if (!dup) {
        try {
          const payload: { source: string; target: string; weight: number; source_handle?: 'true' | 'false' } = {
            source: connectingSource,
            target: targetNodeId,
            weight: 1.0,
          };
          if (connectingSourceHandle) payload.source_handle = connectingSourceHandle;
          const newEdge = await api.createEdge(currentWorkspaceId, payload);
          addEdge(newEdge);
        } catch (err) {
          console.error('Failed to create edge:', err);
        }
      }
      setConnectingSource(null);
      setConnectingSourceHandle(null);
    },
    [connectingSource, connectingSourceHandle, currentWorkspaceId, edges, addEdge],
  );

  // --------------- drag & drop node creation ---------------

  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      const raw = e.dataTransfer.getData('application/node-type');
      if (!raw || !currentWorkspaceId) return;
      try {
        const nodeType = JSON.parse(raw);
        const pos = toCanvas(e.clientX, e.clientY);
        const isWorkflowTemplate = nodeType.type_kind === 'workflow_template';
        
        const newNode = await api.createNode(currentWorkspaceId, {
          node_type_id: nodeType.id,
          x: pos.x,
          y: pos.y,
          config_overrides: nodeType.default_config || {},
        });
        
        if (isWorkflowTemplate) {
          // Workflow templates expand into multiple nodes + edges — reload entire workspace
          const workspace = await api.getWorkspace(currentWorkspaceId);
          useAppStore.getState().setNodes(workspace.nodes || []);
          useAppStore.getState().setEdges(workspace.edges || []);
        } else {
          useAppStore.getState().addNode(newNode);
        }
      } catch (err) {
        console.error('Failed to create node:', err);
      }
    },
    [currentWorkspaceId, toCanvas],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  }, []);

  // --------------- edge-creation preview path ---------------

  const edgePreviewPath = useMemo(() => {
    if (!connectingSource) return null;
    const src = nodes.find((n) => n.id === connectingSource);
    if (!src) return null;
    const sx = src.x + 220;
    const sy = src.y + 60;
    const dx = Math.abs(mousePos.x - sx) * 0.5;
    return `M ${sx} ${sy} C ${sx + dx} ${sy}, ${mousePos.x - dx} ${mousePos.y}, ${mousePos.x} ${mousePos.y}`;
  }, [connectingSource, nodes, mousePos]);

  // --------------- early return ---------------

  if (!currentWorkspaceId) {
    return (
      <div className="flex items-center justify-center h-full text-slate-500">
        <div className="text-center">
          <p className="text-lg mb-2">No workspace selected</p>
          <p className="text-sm">Select a workspace from the sidebar to start</p>
        </div>
      </div>
    );
  }

  // --------------- render ---------------

  return (
    <div
      ref={containerRef}
      className="relative w-full h-full overflow-hidden bg-slate-950 canvas-container"
      style={{ cursor: activeTool === 'pan' ? 'grab' : connectingSource ? 'crosshair' : 'default' }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
      onWheel={handleWheel}
      onDrop={handleDrop}
      onDragOver={handleDragOver}
    >
      {/*
        Single CSS-transformed layer — contains grid bg, SVG edges, and HTML nodes.
        This is the reference architecture (code.jsx line 455).
      */}
      <div
        className="absolute inset-0 origin-top-left transition-transform duration-75 ease-out canvas-background"
        style={{
          transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.k})`,
          backgroundImage: 'radial-gradient(circle at 1px 1px, #1e293b 1px, transparent 0)',
          backgroundSize: '40px 40px',
        }}
        onClick={() => {
          if (activeTool === 'select') {
            setSelectedNode(null);
            setSelectedEdge(null);
          }
        }}
      >
        {/* SVG for edges only — pointer-events-none, edges opt-in individually */}
        <svg className="absolute inset-0 w-[10000px] h-[10000px] pointer-events-none overflow-visible">
          <defs>
            <marker id="arrow" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#475569" />
            </marker>
            <marker id="arrow-selected" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#6366f1" />
            </marker>
          </defs>

          {/* Rendered edges */}
          {edges.map((edge) => {
            const sourceNode = nodes.find((n) => n.id === edge.source);
            const targetNode = nodes.find((n) => n.id === edge.target);
            return (
              <Edge
                key={edge.id}
                edge={edge}
                sourceNode={sourceNode}
                targetNode={targetNode}
                isSelected={selectedEdgeId === edge.id}
              />
            );
          })}

          {/* Edge creation preview */}
          {edgePreviewPath && (
            <path
              d={edgePreviewPath}
              fill="none"
              stroke="#6366f1"
              strokeWidth={2}
              strokeDasharray="6"
              className="animate-[dash_1s_linear_infinite]"
            />
          )}
        </svg>

        {/* HTML nodes — plain divs, naturally receive hover/click */}
        {nodes.map((node) => (
          <Node
            key={node.id}
            node={node}
            isSelected={selectedNodeId === node.id}
            isConnecting={!!connectingSource}
            movingNodeId={movingNodeId}
            onClick={handleNodeClick}
            onDoubleClick={handleNodeDoubleClick}
            onMouseUp={handleCompleteConnection}
            onStartEdgeCreation={handleStartEdgeCreation}
          />
        ))}
      </div>

      {/* Floating UI (outside the transformed layer) */}
      <ExecuteButton />
      <ZoomControls />
    </div>
  );
}
