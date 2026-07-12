/** Типы данных графа и WebSocket JSON-RPC протокола. */

// ────── Данные ──────

export interface NodeData {
  id: string;
  label: string;
  type: string;
  desc: string;
  color: string;
  size: number;
  tags: string[];
  note?: string;
  community?: number;
  isOrphan?: boolean;
  degree?: number;
}

export interface EdgeData {
  source: string;
  target: string;
  relation: string;
  weight: number;
}

export interface EdgeWithLabels extends EdgeData {
  target_label?: string;
  target_type?: string;
  source_label?: string;
  source_type?: string;
}

export interface TypeColors {
  [typeName: string]: string;
}

export interface GraphStats {
  nodes: number;
  edges: number;
  density: number;
  orphans: number;
  louvainCommunities?: number;
  islands?: number;
  pagerankTop5?: { id: string; rank: number }[];
}

export interface GraphState {
  nodes: NodeData[];
  edges: EdgeData[];
  orphans: string[];
  types: TypeColors;
  louvainAvailable: boolean;
  stats: GraphStats;
}

export interface TagCount {
  tag: string;
  count: number;
}

export interface FileInfo {
  path: string;
  dirty: boolean;
  nodes: number;
  edges: number;
}

export interface NodeEdgeList {
  outgoing: EdgeWithLabels[];
  incoming: EdgeWithLabels[];
}

// ────── WebSocket JSON-RPC ──────

export interface JsonRpcRequest {
  jsonrpc: '2.0';
  method: string;
  params?: Record<string, unknown>;
  id: number;
}

export interface JsonRpcResponse {
  jsonrpc: '2.0';
  result?: unknown;
  error?: { code: number; message: string };
  id: number | null;
}

export interface JsonRpcEvent {
  jsonrpc: '2.0';
  method: 'event';
  params: {
    type: string;
    payload: Record<string, unknown>;
  };
}

export type WsMessage = JsonRpcResponse | JsonRpcEvent;

// ────── Louvain ──────

export interface Community {
  id: number;
  color: string;
  size: number;
  members: string[];
}

// ────── Ring / Islands / Neighbors ──────

export interface RingNode {
  id: string;
  depth: number;
  label: string;
  type: string;
}

export interface Island {
  id: number;
  size: number;
  isOrphan: boolean;
  members: { id: string; label: string; type: string }[];
}

export interface NeighborInfo {
  id: string;
  label: string;
  type: string;
  relation: string;
}
