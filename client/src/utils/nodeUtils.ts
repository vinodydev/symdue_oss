import type { Node, Edge, NodeType } from '@/types';

/**
 * Get all upstream nodes (nodes that have edges pointing to this node).
 * 
 * @param nodeId - The target node ID
 * @param nodes - All nodes in the graph
 * @param edges - All edges in the graph
 * @returns Array of upstream nodes
 */
export function getUpstreamNodes(
  nodeId: string,
  nodes: Node[],
  edges: Edge[]
): Node[] {
  // Find all edges where this node is the target
  const incomingEdges = edges.filter((edge) => edge.target === nodeId);
  
  // Get source node IDs
  const upstreamIds = incomingEdges.map((edge) => edge.source);
  
  // Return the actual node objects
  return nodes.filter((node) => upstreamIds.includes(node.id));
}

/**
 * Check if a node type supports iterator mode.
 * 
 * @param nodeTypeId - The node type ID (e.g., "custom-llm")
 * @param nodeTypes - Array of node types (from API)
 * @returns True if the node type supports iterator
 */
export function supportsIterator(
  nodeTypeId: string,
  nodeTypes: NodeType[]
): boolean {
  const nodeType = nodeTypes.find((nt) => nt.id === nodeTypeId);
  if (!nodeType) return false;
  
  // Check config_schema for iterator support
  const schema = nodeType.config_schema || {};
  return schema.supports_iterator === true;
}

