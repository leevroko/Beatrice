import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useGraph } from '../store/context';
import { NodesList } from './NodesList/NodesList';
import { NodeEditor } from './NodeEditor/NodeEditor';
import { GraphView } from './GraphView/GraphView';

export const Layout: React.FC = () => {
  const graph = useGraph();
  const [, forceUpdate] = useState(0);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [wsStatus, setWsStatus] = useState(false);

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

  return (
    <div className="app-layout" onKeyDown={handleKeyDown} tabIndex={-1}>
      {/* Toolbar */}
      <div className="toolbar">
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
      <div className="panel" style={{ borderRight: '1px solid var(--border)' }}>
        <div className="panel-header">Узлы ({graph.nodes.size})</div>
        <NodesList />
      </div>

      {/* Center panel: Node editor */}
      <div className="panel" style={{ borderRight: '1px solid var(--border)' }}>
        <div className="panel-header">
          {graph.selectedNode ? `Редактор: ${graph.selectedNode.id}` : 'Редактор'}
        </div>
        <NodeEditor />
      </div>

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
