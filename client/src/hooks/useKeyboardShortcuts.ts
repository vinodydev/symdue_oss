// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Keyboard shortcuts hook
 */
import { useEffect } from 'react';
import { useAppStore } from '@/stores';
import { api } from '@/services/api';

export function useKeyboardShortcuts() {
  const {
    currentWorkspaceId,
    selectedNodeId,
    selectedEdgeId,
    deleteNode,
    deleteEdge,
    setSelectedNode,
    setSelectedEdge,
  } = useAppStore();

  useEffect(() => {
    const isEditing = (target: EventTarget | null): boolean => {
      if (!target || !(target instanceof Node)) return false;
      const el = target as HTMLElement;
      if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) return true;
      const editable = el.closest('[contenteditable="true"], .cm-editor, .cm-content');
      return editable !== null;
    };

    const handleKeyDown = async (e: KeyboardEvent) => {
      // Delete key — don't trigger when typing in inputs, textareas, or code editor (CodeMirror)
      if (e.key === 'Delete' || e.key === 'Backspace') {
        if (isEditing(e.target)) return;

        if (selectedNodeId && currentWorkspaceId) {
          if (confirm('Are you sure you want to delete this node?')) {
            try {
              await api.deleteNode(currentWorkspaceId, selectedNodeId);
              deleteNode(selectedNodeId);
              setSelectedNode(null);
            } catch (error) {
              console.error('Failed to delete node:', error);
            }
          }
        } else if (selectedEdgeId && currentWorkspaceId) {
          if (confirm('Are you sure you want to delete this edge?')) {
            try {
              await api.deleteEdge(currentWorkspaceId, selectedEdgeId);
              deleteEdge(selectedEdgeId);
              setSelectedEdge(null);
            } catch (error) {
              console.error('Failed to delete edge:', error);
            }
          }
        }
      }

      // Escape key - deselect
      if (e.key === 'Escape') {
        setSelectedNode(null);
        setSelectedEdge(null);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentWorkspaceId, selectedNodeId, selectedEdgeId, deleteNode, deleteEdge, setSelectedNode, setSelectedEdge]);
}

