import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useGraph } from '../store/context';
import { NodesList } from './NodesList/NodesList';
import { NodeEditor } from './NodeEditor/NodeEditor';
import { GraphView } from './GraphView/GraphView';

type CollapsedState = {
  nodes: boolean;
  editor: boolean;
};

const MIN_WIDTH = 48;
const DEFAULT_NODES_WIDTH = 280;
const DEFAULT_EDITOR_WIDTH = 400;

export const Layout: React.FC = () => {
  const graph = useGraph();
  const [, forceUpdate] = useState(0);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [wsStatus, setWsStatus] = useState(false);

  // Column widths and collapse state
  const [nodesWidth, setNodesWidth] = useState(DEFAULT_NODES_WIDTH);
  const [editorWidth, setEditorWidth] = useState(DEFAULT_EDITOR_WIDTH);
  const [collapsed, setCollapsed] = useState<CollapsedState>({ nodes: false, editor: false });

  // Drag state
  const dragging = useRef<{ handle: 'nodes' | 'editor'; startX: number; startWidth: number } | null>(null);

  useEffect(() => {
    const unsub = graph.subscribe(() => forceUpdate((n) => n + 1));
    graph.ws.onStatusChange = setWsStatus;
    setWsStatus(graph.ws.connected);
    return unsub;
  }, [graph]);

  const handleSave = useCallback(async () => {
    try {
      await graph.save();
    } catch (e) {
      alert(`Ошибка сохранения: ${e}`);
    }
  }, [graph]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
      e.preventDefault();
      handleSave();
    }
  }, [handleSave]);

  // ────── Mouse drag handlers ──────

  const onMouseDown = useCallback((handle: 'nodes' | 'editor', e: React.MouseEvent) => {
    e.preventDefault();
    dragging.current = {
      handle,
      startX: e.clientX,
      startWidth: handle === 'nodes' ? nodesWidth : editorWidth,
    };
  }, [nodesWidth, editorWidth]);

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      const d = dragging.current;
      if (!d) return;
      const delta = e.clientX - d.startX;
      let w = Math.max(MIN_WIDTH, d.startWidth + delta);
      if (d.handle === 'nodes') {
        setNodesWidth(w);
      } else {
        setEditorWidth(w);
      }
    };
    const onMouseUp = () => {
      dragging.current = null;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    return () => {
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
    };
  }, []);

  const onDragStart = useCallback((handle: 'nodes' | 'editor', e: React.MouseEvent) => {
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    onMouseDown(handle, e);
  }, [onMouseDown]);

  // ────── Toggle collapse ──────

  const toggleNodes = useCallback(() => {
    setCollapsed((c) => ({ ...c, nodes: !c.nodes }));
  }, []);

  const toggleEditor = useCallback(() => {
    setCollapsed((c) => ({ ...c, editor: !c.editor }));
  }, []);

  const actualNodesWidth = collapsed.nodes ? MIN_WIDTH : nodesWidth;
  const actualEditorWidth = collapsed.editor ? MIN_WIDTH : editorWidth;

  return (
    <div className="app-layout" onKeyDown={handleKeyDown} tabIndex={-1}
      style={{
        gridTemplateColumns: `${actualNodesWidth}px 4px ${actualEditorWidth}px 4px 1fr`,
      }}>
      {/* Toolbar — spans all columns */}
      <div className="toolbar" style={{ gridColumn: '1 / -1' }}>
        <span className="toolbar-title">🔮 Beatrice</span>
        <span className={`toolbar-status ${wsStatus ? 'online' : 'offline'}`} />
        <span className="toolbar-path">
          {graph.filePath}
        </span>
        {graph.dirty && <span className="toolbar-dirty">● несохранено</span>}
        <button onClick={handleSave} disabled={!graph.dirty}>
          💾 Save
        </button>
        <button onClick={() => graph.reload()} disabled={!graph.filePath}>⟳ Reload</button>
        <button onClick={() => setShowAddDialog(true)}>+ Узел</button>
      </div>

      {/* Left panel: Nodes list */}
      <div className="panel" style={{ borderRight: 'none', overflow: collapsed.nodes ? 'hidden' : undefined }}>
        <div className="panel-header" style={collapsed.nodes ? { justifyContent: 'center', padding: '10px 0' } : undefined}>
          {!collapsed.nodes && <span>Узлы ({graph.nodes.size})</span>}
          <button className="btn-sm panel-collapse-btn" onClick={toggleNodes} title={collapsed.nodes ? 'Развернуть' : 'Свернуть'}>
            {collapsed.nodes ? '▶' : '◀'}
          </button>
        </div>
        {!collapsed.nodes && <NodesList />}
      </div>

      {/* Drag handle 1 */}
      <div
        className="resize-handle"
        onMouseDown={(e) => onDragStart('nodes', e)}
      />

      {/* Center panel: Node editor */}
      <div className="panel" style={{ borderRight: 'none', overflow: collapsed.editor ? 'hidden' : undefined }}>
        <div className="panel-header" style={collapsed.editor ? { justifyContent: 'center', padding: '10px 0' } : undefined}>
          <button className="btn-sm panel-collapse-btn" onClick={toggleEditor} title={collapsed.editor ? 'Развернуть' : 'Свернуть'}
            style={collapsed.editor ? { marginRight: 0 } : { marginRight: 'auto' }}>
            {collapsed.editor ? '◀' : '▶'}
          </button>
          {!collapsed.editor && (
            <span>{graph.selectedNode ? `Редактор: ${graph.selectedNode.id}` : 'Редактор'}</span>
          )}
        </div>
        {!collapsed.editor && <NodeEditor />}
      </div>

      {/* Drag handle 2 */}
      <div
        className="resize-handle"
        onMouseDown={(e) => onDragStart('editor', e)}
      />

      {/* Right panel: Graph view */}
      <div className="panel">
        <GraphView />
      </div>

      {/* Add node dialog */}
      {showAddDialog && (
        <AddNodeDialog onClose={() => setShowAddDialog(false)} />
      )}
    </div>
  );
};

const AddNodeDialog: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const graph = useGraph();
  const [id, setId] = useState('');
  const [label, setLabel] = useState('');
  const [type, setType] = useState('');

  const handleSubmit = async () => {
    if (!id.trim()) return;
    try {
      await graph.addNode(id.trim(), {
        label: label.trim() || id.trim(),
        type: type.trim(),
      });
      graph.selectNode(id.trim());
      onClose();
    } catch (e) {
      alert(`Ошибка: ${e}`);
    }
  };

  return (
    <div className="dialog-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="dialog">
        <h3>Добавить узел</h3>
        <div className="field">
          <label>ID *</label>
          <input value={id} onChange={(e) => setId(e.target.value)}
            placeholder="kafka, redis, ..." autoFocus />
        </div>
        <div className="field">
          <label>Метка</label>
          <input value={label} onChange={(e) => setLabel(e.target.value)}
            placeholder="Apache Kafka" />
        </div>
        <div className="field">
          <label>Тип</label>
          <input value={type} onChange={(e) => setType(e.target.value)}
            placeholder="Брокер, БД, ..." />
        </div>
        <div className="dialog-actions">
          <button onClick={onClose}>Отмена</button>
          <button className="btn-primary" onClick={handleSubmit}
            disabled={!id.trim()}>
            Добавить
          </button>
        </div>
      </div>
    </div>
  );
};
