import React, { useState, useEffect, useRef } from 'react';
import { useGraph } from '../../store/context';
import type { EdgeWithLabels } from '../../api/types';

export const EdgeList: React.FC<{ nodeId: string }> = ({ nodeId }) => {
  const graph = useGraph();
  const [, forceUpdate] = useState(0);
  const [edges, setEdges] = useState<{ outgoing: EdgeWithLabels[]; incoming: EdgeWithLabels[] }>({
    outgoing: [], incoming: [],
  });
  const [showAdd, setShowAdd] = useState(false);

  useEffect(() => {
    loadEdges();
  }, [nodeId, graph.edges.length]);

  useEffect(() => {
    const unsub = graph.subscribe(() => forceUpdate((n) => n + 1));
    return unsub;
  }, [graph]);

  const loadEdges = async () => {
    try {
      const data = await graph.ws.call<{ outgoing: EdgeWithLabels[]; incoming: EdgeWithLabels[] }>(
        'list_edges_for_node', { id: nodeId }
      );
      setEdges(data);
    } catch {
      // ignore
    }
  };

  const handleRemoveEdge = async (source: string, target: string) => {
    try {
      await graph.removeEdge(source, target);
      loadEdges();
    } catch (e) {
      alert(`Ошибка: ${e}`);
    }
  };

  return (
    <div style={{ padding: '0 12px' }}>
      <div style={{
        fontWeight: 600, marginBottom: 8, fontSize: 13,
        color: 'var(--text-secondary)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <span>Связи</span>
        <button className="btn-sm" onClick={() => setShowAdd(true)}>+ Связь</button>
      </div>

      {/* Исходящие */}
      {edges.outgoing.length > 0 && (
        <>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Исходящие:</div>
          <table className="edge-table">
            <thead>
            <tr><th>→</th><th>Тип</th><th>Цель</th><th></th></tr>
            </thead>
            <tbody>
              {edges.outgoing.map((e, i) => (
                <tr key={`out-${i}`}>
                  <td style={{ color: 'var(--accent)' }}>→ {e.target}
                    <button className="btn-sm" onClick={() => navigator.clipboard.writeText(e.target)}
                      title="Копировать ID" style={{ fontSize: 10, padding: '1px 4px', marginLeft: 4 }}>
                      📋
                    </button>
                  </td>
                  <td><span className="edge-relation">{e.relation || '—'}</span></td>
                  <td>
                    <span
                      style={{ cursor: 'pointer', textDecoration: 'underline dotted', textUnderlineOffset: 2 }}
                      onMouseEnter={(ev) => { ev.currentTarget.style.color = 'var(--accent)'; }}
                      onMouseLeave={(ev) => { ev.currentTarget.style.color = ''; }}
                      onClick={() => graph.selectNode(e.target)}
                    >
                      {e.target_label || e.target}
                    </span>
                  </td>
                  <td>
                    <span className="edge-remove" onClick={() => handleRemoveEdge(e.source, e.target)}>
                      ×
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {/* Входящие */}
      {edges.incoming.length > 0 && (
        <>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4, marginTop: 8 }}>Входящие:</div>
          <table className="edge-table">
            <thead>
              <tr><th>←</th><th>Тип</th><th>Источник</th><th></th></tr>
            </thead>
            <tbody>
              {edges.incoming.map((e, i) => (
                <tr key={`in-${i}`}>
                  <td style={{ color: '#3cb44b' }}>← {e.source}
                    <button className="btn-sm" onClick={() => navigator.clipboard.writeText(e.source)}
                      title="Копировать ID" style={{ fontSize: 10, padding: '1px 4px', marginLeft: 4 }}>
                      📋
                    </button>
                  </td>
                  <td><span className="edge-relation">{e.relation || '—'}</span></td>
                  <td>
                    <span
                      style={{ cursor: 'pointer', textDecoration: 'underline dotted', textUnderlineOffset: 2 }}
                      onMouseEnter={(ev) => { ev.currentTarget.style.color = 'var(--accent)'; }}
                      onMouseLeave={(ev) => { ev.currentTarget.style.color = ''; }}
                      onClick={() => graph.selectNode(e.source)}
                    >
                      {e.source_label || e.source}
                    </span>
                  </td>
                  <td>
                    <span className="edge-remove" onClick={() => handleRemoveEdge(e.source, e.target)}>
                      ×
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {edges.outgoing.length === 0 && edges.incoming.length === 0 && (
        <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>Нет связей</div>
      )}

      {showAdd && (
        <AddEdgeDialog
          nodeId={nodeId}
          onClose={() => setShowAdd(false)}
          onDone={() => { setShowAdd(false); loadEdges(); }}
        />
      )}
    </div>
  );
};

const AddEdgeDialog: React.FC<{
  nodeId: string;
  onClose: () => void;
  onDone: () => void;
}> = ({ nodeId, onClose, onDone }) => {
  const graph = useGraph();
  const [direction, setDirection] = useState<'outgoing' | 'incoming'>('outgoing');
  const [query, setQuery] = useState('');
  const [selectedNode, setSelectedNode] = useState<{ id: string; label: string; type: string } | null>(null);
  const [relation, setRelation] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const otherNodes = Array.from(graph.nodes.values())
    .filter((n) => n.id !== nodeId);

  // Fuzzy filter: разбиваем query на символы, проверяем вхождение по порядку в id и label
  const filteredNodes = query.trim() === ''
    ? otherNodes.slice(0, 10)
    : otherNodes.filter((n) => {
        const q = query.toLowerCase();
        const id = n.id.toLowerCase();
        const label = n.label.toLowerCase();
        // Сначала точное вхождение подстроки
        if (id.includes(q) || label.includes(q)) return true;
        // Fuzzy: все символы query встречаются в id или label по порядку
        const fuzzyMatch = (s: string): boolean => {
          let qi = 0;
          for (let si = 0; si < s.length && qi < q.length; si++) {
            if (s[si] === q[qi]) qi++;
          }
          return qi === q.length;
        };
        return fuzzyMatch(id) || fuzzyMatch(label);
      }).slice(0, 20); // не больше 20 результатов

  const handleSubmit = async () => {
    if (!selectedNode) return;
    try {
      if (direction === 'outgoing') {
        await graph.addEdge(nodeId, selectedNode.id, relation);
      } else {
        await graph.addEdge(selectedNode.id, nodeId, relation);
      }
      onDone();
    } catch (e) {
      alert(`Ошибка: ${e}`);
    }
  };

  const handleSelect = (n: { id: string; label: string; type: string }) => {
    setSelectedNode(n);
    setQuery(`${n.label} (${n.id})`);
    setShowDropdown(false);
  };

  return (
    <div className="dialog-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="dialog">
        <h3>Добавить связь</h3>
        <div className="field">
          <label>Направление</label>
          <select value={direction} onChange={(e) => setDirection(e.target.value as 'outgoing' | 'incoming')}>
            <option value="outgoing">Исходящая ({nodeId} → ...)</option>
            <option value="incoming">Входящая (... → {nodeId})</option>
          </select>
        </div>
        <div className="field" style={{ position: 'relative' }}>
          <label>{direction === 'outgoing' ? 'Цель' : 'Источник'}</label>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setSelectedNode(null);
              setShowDropdown(true);
            }}
            onFocus={() => setShowDropdown(true)}
            onBlur={() => setTimeout(() => setShowDropdown(false), 200)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && filteredNodes.length > 0) {
                handleSelect(filteredNodes[0]);
              }
              if (e.key === 'Escape') setShowDropdown(false);
            }}
            placeholder="Введите id или название узла..."
            autoFocus
          />
          {showDropdown && filteredNodes.length > 0 && (
            <div style={{
              position: 'absolute', top: '100%', left: 0, right: 0,
              background: 'var(--bg-secondary)', border: '1px solid var(--border)',
              borderRadius: '0 0 6px 6px', maxHeight: 240, overflowY: 'auto',
              zIndex: 200, boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
            }}>
              {filteredNodes.map((n) => (
                <div
                  key={n.id}
                  onMouseDown={() => handleSelect(n)}
                  style={{
                    padding: '8px 12px', cursor: 'pointer',
                    borderBottom: '1px solid var(--border)',
                    fontSize: 13, display: 'flex', justifyContent: 'space-between',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--bg-tertiary)'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.background = ''; }}
                >
                  <span>
                    <span style={{
                      display: 'inline-block', width: 8, height: 8,
                      borderRadius: '50%', background: n.color || '#999',
                      marginRight: 8, verticalAlign: 'middle',
                    }} />
                    <span style={{ fontWeight: 500 }}>{n.label}</span>
                    <span style={{ color: 'var(--text-muted)', marginLeft: 6, fontSize: 11 }}>{n.id}</span>
                  </span>
                  {n.type && (
                    <span style={{ color: 'var(--text-secondary)', fontSize: 11 }}>{n.type}</span>
                  )}
                </div>
              ))}
              {filteredNodes.length === 20 && query.trim() !== '' && (
                <div style={{ padding: '6px 12px', fontSize: 11, color: 'var(--text-muted)', textAlign: 'center' }}>
                  … и ещё
                </div>
              )}
            </div>
          )}
          {selectedNode && (
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
              Выбран: <strong>{selectedNode.label}</strong> ({selectedNode.id})
              {selectedNode.type ? ` — ${selectedNode.type}` : ''}
            </div>
          )}
        </div>
        <div className="field">
          <label>Тип связи (необязательно)</label>
          <input value={relation} onChange={(e) => setRelation(e.target.value)}
            placeholder="использует, зависит от, ..." />
        </div>
        <div className="dialog-actions">
          <button onClick={onClose}>Отмена</button>
          <button className="btn-primary" onClick={handleSubmit} disabled={!selectedNode}>
            Добавить
          </button>
        </div>
      </div>
    </div>
  );
};
