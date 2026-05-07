// SPDX-License-Identifier: AGPL-3.0-or-later
// Copyright (c) 2026 Symdue contributors
/**
 * Node Types view container: list or detail based on selection.
 */
import React from 'react';
import { NodeTypeList } from './NodeTypeList';
import { NodeTypeDetail } from './NodeTypeDetail';

interface NodeTypesViewProps {
  selectedNodeTypeId: string | null;
  setSelectedNodeTypeId: (id: string | null) => void;
  setCurrentView: (view: 'workspaces' | 'editor' | 'settings' | 'node_types') => void;
  setCurrentWorkspace: (id: string | null) => void;
}

export function NodeTypesView({
  selectedNodeTypeId,
  setSelectedNodeTypeId,
  setCurrentView,
  setCurrentWorkspace,
}: NodeTypesViewProps) {
  if (selectedNodeTypeId) {
    return (
      <NodeTypeDetail
        nodeTypeId={selectedNodeTypeId}
        onBack={() => setSelectedNodeTypeId(null)}
        setCurrentView={setCurrentView}
        setCurrentWorkspace={setCurrentWorkspace}
      />
    );
  }
  return (
    <NodeTypeList
      onSelectType={(id) => setSelectedNodeTypeId(id)}
    />
  );
}
