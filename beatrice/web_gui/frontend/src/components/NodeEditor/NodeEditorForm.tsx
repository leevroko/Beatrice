import React, { useState } from 'react';
import { useGraph } from '../../store/context';
import { DeleteConfirmDialog, MoveDialog } from './NodeEditor';
import type { NodeData } from '../../api/types';

export const NodeEditorForm: React.FC<{ node: NodeData }> = ({ node }) => {
  const graph = useGraph();
  const [, forceUpdate] = useState(0);
  const [label, setLabel] = useState(node.label);
  const [type, setType] = useState(node.type);
  const [desc, setDesc] = useState(node.desc);
  const [color, setColor] = useState(node.color || '#999');
  const [size, setSize] = useState(node.size || 10);
  const [note, setNote] = useState(node.note || '');
  const [showDelete, setShowDelete] = useState(false);
  const [showMove, setShowMove] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  // Reset form when node changes
  React.useEffect(() => {
    setLabel(node.label);
    setType(node.type);
    setDesc(node.desc);
    setColor(node.color || '#999');
    setSize(node.size || 10);
    setNote(node.note || '');
    setHasChanges(false);
  }, [node.id]);

  React.useEffect(() => {
    const unsub = graph.subscribe(() => forceUpdate((n) => n + 1));
    return unsub;
  }, [graph]);

  const markChanged = () => setHasChanges(true);

  const handleSave = async () => {
    try {
      await graph.updateNode(node.id, { label, type, desc, color, size, note });
      setHasChanges(false);
    } catch (e) {
      alert(`Ошибка: ${e}`);
    }
  };

  const handleDelete = async () => {
    try {
      await graph.removeNode(node.id);
      graph.selectNode(null);
      setShowDelete(false);
    } catch (e) {
      alert(`Ошибка: ${e}`);
    }
  };

  const handleMove = async (newId: string) => {
    try {
      await graph.moveNode(node.id, newId);
      setShowMove(false);
    } catch (e) {
      alert(`Ошибка: ${e}`);
    }
  };

  return (
    <div className="editor-form">
      <div className="field">
        <label>ID
          <button className="btn-sm" onClick={() => navigator.clipboard.writeText(node.id)}
            title="Копировать ID" style={{ marginLeft: 8, fontSize: 10, padding: '2px 6px' }}>
            📋
          </button>
        </label>
        <input value={node.id} disabled />
      </div>
      <div className="field">
        <label>Метка</label>
        <input value={label} onChange={(e) => { setLabel(e.target.value); markChanged(); }} />
      </div>
      <div className="field">
        <label>Тип</label>
        <input value={type} onChange={(e) => { setType(e.target.value); markChanged(); }} placeholder="Брокер, БД, ..." />
      </div>
      <div className="field">
        <label>Описание</label>
        <textarea value={desc} onChange={(e) => { setDesc(e.target.value); markChanged(); }} />
      </div>
      <div className="field-row">
        <div className="field">
          <label>Цвет</label>
          <input type="color" value={color}
            onChange={(e) => { setColor(e.target.value); markChanged(); }} />
        </div>
        <div className="field">
          <label>Размер</label>
          <input type="number" min={5} max={50} value={size}
            onChange={(e) => { setSize(Number(e.target.value)); markChanged(); }} />
        </div>
      </div>

      <div className="field">
        <label>Конспект (Obsidian URI)</label>
        <div style={{ display: 'flex', gap: 4 }}>
          <input value={note} onChange={(e) => { setNote(e.target.value); markChanged(); }}
            placeholder="obsidian://open?vault=NAME&file=Path/To/Note" style={{ flex: 1 }} />
          {node.note && (
            <button className="btn-sm" onClick={() => window.open(node.note, '_blank')} title="Открыть в Obsidian">
              📝 Открыть
            </button>
          )}
        </div>
      </div>

      <div className="editor-actions">
        <button className="btn-primary" onClick={handleSave} disabled={!hasChanges}>
          💾 Сохранить
        </button>
        <button onClick={() => setShowMove(true)}>✎ Переименовать</button>
        <button className="btn-danger" onClick={() => setShowDelete(true)}>
          🗑 Удалить
        </button>
      </div>

      {showDelete && (
        <DeleteConfirmDialog
          nodeId={node.id}
          onConfirm={handleDelete}
          onCancel={() => setShowDelete(false)}
        />
      )}
      {showMove && (
        <MoveDialog
          oldId={node.id}
          onConfirm={handleMove}
          onCancel={() => setShowMove(false)}
        />
      )}
    </div>
  );
};
