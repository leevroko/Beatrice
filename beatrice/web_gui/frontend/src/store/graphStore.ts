/** Graph store — состояние графа на клиенте. */

import type {
  NodeData,
  EdgeData,
  GraphState,
  GraphStats,
  TypeColors,
  TagCount,
} from '../api/types';
import { WsClient } from '../api/websocket';

export class GraphStore {
  nodes = new Map<string, NodeData>();
  edges: EdgeData[] = [];
  orphans: string[] = [];
  types: TypeColors = {};
  louvainAvailable = false;
  stats: GraphStats | null = null;
  filePath = '';
  dirty = false;
  selectedNodeId: string | null = null;
  private _searchQuery = '';
  private _filterType = '';
  private _filterTag = '';
  private _showOrphansOnly = false;
  private _filterUntagged = false;
  private _filterWithoutTag = '';

  get searchQuery(): string { return this._searchQuery; }
  set searchQuery(v: string) { this._searchQuery = v; this.notify(); }
  get filterType(): string { return this._filterType; }
  set filterType(v: string) { this._filterType = v; this.notify(); }
  get filterTag(): string { return this._filterTag; }
  set filterTag(v: string) { this._filterTag = v; this.notify(); }
  get showOrphansOnly(): boolean { return this._showOrphansOnly; }
  set showOrphansOnly(v: boolean) { this._showOrphansOnly = v; this.notify(); }
  get filterUntagged(): boolean { return this._filterUntagged; }
  set filterUntagged(v: boolean) { this._filterUntagged = v; this.notify(); }
  get filterWithoutTag(): string { return this._filterWithoutTag; }
  set filterWithoutTag(v: string) { this._filterWithoutTag = v; this.notify(); }

  /** Установить выбранный узел с оповещением всех подписчиков. */
  selectNode(id: string | null): void {
    this.selectedNodeId = id;
    this.notify();
  }

  // Callbacks for React re-render
  private listeners = new Set<() => void>();

  constructor(public ws: WsClient) {
    // Subscribe to WS events
    this.ws.on('node_added', (ev) => {
      const n = ev.payload as unknown as NodeData;
      this.nodes.set(n.id, n);
      this.dirty = true;
      this.notify();
    });
    this.ws.on('node_removed', (ev) => {
      const { id } = ev.payload as { id: string };
      this.nodes.delete(id);
      if (this.selectedNodeId === id) this.selectNode(null);
      this.dirty = true;
      this.notify();
    });
    this.ws.on('node_updated', (ev) => {
      const n = ev.payload as unknown as NodeData;
      this.nodes.set(n.id, n);
      this.dirty = true;
      this.notify();
    });
    this.ws.on('node_moved', (ev) => {
      const { old_id, new_id } = ev.payload as { old_id: string; new_id: string };
      const nd = this.nodes.get(old_id);
      if (nd) {
        nd.id = new_id;
        this.nodes.set(new_id, nd);
        this.nodes.delete(old_id);
      }
      if (this.selectedNodeId === old_id) this.selectNode(new_id);
      this.dirty = true;
      this.notify();
    });
    this.ws.on('edge_added', (ev) => {
      const e = ev.payload as unknown as EdgeData;
      this.edges.push(e);
      this.dirty = true;
      this.notify();
    });
    this.ws.on('edge_removed', (ev) => {
      const { source, target } = ev.payload as { source: string; target: string };
      this.edges = this.edges.filter(
        (e) => !(e.source === source && e.target === target)
      );
      this.dirty = true;
      this.notify();
    });
    this.ws.on('edge_updated', (ev) => {
      const e = ev.payload as unknown as EdgeData;
      const idx = this.edges.findIndex(
        (x) => x.source === e.source && x.target === e.target
      );
      if (idx >= 0) this.edges[idx] = e;
      this.dirty = true;
      this.notify();
    });
    this.ws.on('tags_changed', () => {
      this.dirty = true;
      this.refresh();
    });
    this.ws.on('graph_updated', () => {
      this.dirty = false;
      this.refresh();
    });
    this.ws.on('file_saved', (ev) => {
      this.dirty = false;
      this.notify();
    });
  }

  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notify(): void {
    this.listeners.forEach((l) => l());
  }

  async init(path: string): Promise<void> {
    this.filePath = path;
    await this.refresh();
  }

  async refresh(): Promise<void> {
    try {
      const state = await this.ws.call<GraphState>('get_graph_state');
      this.nodes.clear();
      for (const n of state.nodes) {
        this.nodes.set(n.id, n);
      }
      this.edges = state.edges;
      this.orphans = state.orphans;
      this.types = state.types;
      this.louvainAvailable = state.louvainAvailable;
      this.stats = state.stats;
      this.notify();
    } catch (e) {
      console.error('Failed to refresh graph state:', e);
    }
  }

  // ────── Селекторы ──────

  get filteredNodes(): NodeData[] {
    let list = Array.from(this.nodes.values());
    if (this.searchQuery) {
      const q = this.searchQuery.toLowerCase();
      list = list.filter(
        (n) =>
          n.id.toLowerCase().includes(q) ||
          n.label.toLowerCase().includes(q)
      );
    }
    if (this.filterType) {
      list = list.filter((n) => n.type === this.filterType);
    }
    if (this.filterTag) {
      list = list.filter((n) => n.tags.includes(this.filterTag));
    }
    if (this.filterUntagged) {
      list = list.filter((n) => n.tags.length === 0);
    }
    if (this.filterWithoutTag) {
      const t = this.filterWithoutTag;
      list = list.filter((n) => !n.tags.includes(t));
    }
    if (this.showOrphansOnly) {
      const orphanSet = new Set(this.orphans);
      list = list.filter((n) => orphanSet.has(n.id));
    }
    return list;
  }

  get selectedNode(): NodeData | null {
    return this.selectedNodeId ? this.nodes.get(this.selectedNodeId) ?? null : null;
  }

  get allTypes(): string[] {
    return Object.keys(this.types).filter((t) => t !== 'unknown');
  }

  get allTags(): Set<string> {
    const tags = new Set<string>();
    for (const n of this.nodes.values()) {
      for (const t of n.tags) tags.add(t);
    }
    return tags;
  }

  // ────── Действия ──────

  async addNode(id: string, attrs: Partial<NodeData>): Promise<void> {
    await this.ws.call('add_node', { id, ...attrs });
  }

  async removeNode(id: string): Promise<void> {
    await this.ws.call('remove_node', { id });
  }

  async updateNode(id: string, attrs: Partial<NodeData>): Promise<void> {
    await this.ws.call('update_node', { id, ...attrs });
  }

  async moveNode(oldId: string, newId: string): Promise<void> {
    await this.ws.call('move_node', { old_id: oldId, new_id: newId });
  }

  async addEdge(source: string, target: string, relation = ''): Promise<void> {
    await this.ws.call('add_edge', { source, target, relation });
  }

  async removeEdge(source: string, target: string): Promise<void> {
    await this.ws.call('remove_edge', { source, target });
  }

  async addTag(nodeIds: string[], tags: string[]): Promise<void> {
    await this.ws.call('tag_add', { node_ids: nodeIds, tags });
  }

  async removeTag(nodeIds: string[], tags: string[]): Promise<void> {
    await this.ws.call('tag_remove', { node_ids: nodeIds, tags });
  }

  async save(): Promise<void> {
    await this.ws.call('save');
  }
}
