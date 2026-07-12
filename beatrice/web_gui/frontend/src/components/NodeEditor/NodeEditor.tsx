import React, { useState, useEffect } from 'react';
import { useGraph } from '../../store/context';
import { NodeEditorForm } from './NodeEditorForm';
import { TagsEditor } from './TagsEditor';
import { EdgeList } from './EdgeList';
import type { TagCount } from '../../api/types';

export const NodeEditor: React.FC = () => {
  const graph = useGraph();
  const [, forceUpdate] = useState(0);

  React.useEffect(() => {
    const unsub = graph.subscribe(() => forceUpdate((n) => n + 1));
    return unsub;
  }, [graph]);

  const selectedNode = graph.selectedNode;

  if (!selectedNode) {
    return (
      <div className="editor-placeholder">
        Выберите узел из списка или кликните на графе
      </div>
    );
  }

  return (
    <div className="panel-body" style={{ overflowY: 'auto' }}>
      <NodeEditorForm node={selectedNode} />
      <div style={{ borderTop: '1px solid var(--border)', margin: '12px 0' }} />
      <TagsEditor node={selectedNode} />
      <div style={{ borderTop: '1px solid var(--border)', margin: '12px 0' }} />
      <EdgeList nodeId={selectedNode.id} />
    </div>
  );
};

// ────── Подкомпоненты ──────

const DeleteConfirmDialog: React.FC<{
  nodeId: string;
  onConfirm: () => void;
  onCancel: () => void;
}> = ({ nodeId, onConfirm, onCancel }) => (
  <div className="dialog-overlay" onClick={(e) => e.target === e.currentTarget && onCancel()}>
    <div className="dialog">
      <h3>Удалить узел?</h3>
      <div className="confirm-text">
        Удалить узел <strong>{nodeId}</strong> и все его связи?<br />
        Это действие нельзя отменить.
      </div>
      <div className="dialog-actions">
        <button onClick={onCancel}>Отмена</button>
        <button className="btn-danger" onClick={onConfirm}>Удалить</button>
      </div>
    </div>
  </div>
);

const MoveDialog: React.FC<{
  oldId: string;
  onConfirm: (newId: string) => void;
  onCancel: () => void;
}> = ({ oldId, onConfirm, onCancel }) => {
  const [newId, setNewId] = useState(oldId);
  return (
    <div className="dialog-overlay" onClick={(e) => e.target === e.currentTarget && onCancel()}>
      <div className="dialog">
        <h3>Переименовать узел</h3>
        <div className="field">
          <label>Текущий ID</label>
          <input value={oldId} disabled />
        </div>
        <div className="field">
          <label>Новый ID</label>
          <input value={newId} onChange={(e) => setNewId(e.target.value)} autoFocus />
        </div>
        <div className="dialog-actions">
          <button onClick={onCancel}>Отмена</button>
          <button className="btn-primary" onClick={() => onConfirm(newId)}
            disabled={!newId.trim() || newId === oldId}>
            Переименовать
          </button>
        </div>
      </div>
    </div>
  );
};

export { DeleteConfirmDialog, MoveDialog };
