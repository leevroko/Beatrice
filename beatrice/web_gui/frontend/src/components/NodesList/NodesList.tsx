import React, { useState, useMemo } from 'react';
import { useGraph } from '../../store/context';

export const NodesList: React.FC = () => {
  const graph = useGraph();
  const [, forceUpdate] = useState(0);

  React.useEffect(() => {
    const unsub = graph.subscribe(() => forceUpdate((n) => n + 1));
    return unsub;
  }, [graph]);

  const nodes = graph.filteredNodes;
  const types = graph.allTypes;
  const tags = Array.from(graph.allTags).sort();

  return (
    <>
      <div className="filter-bar">
        <input
          placeholder="🔍 Поиск..."
          value={graph.searchQuery}
          onChange={(e) => { graph.searchQuery = e.target.value; }}
        />
        <select value={graph.filterType} onChange={(e) => {
          graph.filterType = e.target.value;
        }}>
          <option value="">Все типы</option>
          {types.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <select value={graph.filterTag} onChange={(e) => {
          graph.filterTag = e.target.value;
        }}>
          <option value="">Все теги</option>
          {tags.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <label>
          <input type="checkbox" checked={graph.filterUntagged}
            onChange={(e) => { graph.filterUntagged = e.target.checked; }} />
          Без тегов
        </label>
        <select value={graph.filterWithoutTag} onChange={(e) => {
          graph.filterWithoutTag = e.target.value;
        }}>
          <option value="">Не без тега</option>
          {tags.map((t) => <option key={t} value={t}>&times; {t}</option>)}
        </select>
        <label>
          <input type="checkbox" checked={graph.showOrphansOnly}
            onChange={(e) => { graph.showOrphansOnly = e.target.checked; }} />
          👻 Сироты
        </label>
        <select value={graph.filterNoNote} onChange={(e) => {
          graph.filterNoNote = e.target.value;
        }}>
          <option value="">Все конспекты</option>
          <option value="with">📝 С конспектом</option>
          <option value="without">📝 Без конспекта</option>
        </select>
      </div>
      <div className="panel-body">
        {nodes.map((n) => (
          <div
            key={n.id}
            className={`node-list-item ${graph.selectedNodeId === n.id ? 'selected' : ''}`}
            onClick={() => {
              graph.selectNode(n.id);
            }}
          >
            <span className="node-color-dot" style={{ background: n.color || '#999' }} />
            <span className="node-label">{n.label}</span>
            <span className="node-id">{n.id}</span>
            {n.isOrphan && <span style={{ color: '#ff6b6b' }}>👻</span>}
          </div>
        ))}
        {nodes.length === 0 && (
          <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 24 }}>
            Узлов не найдено
          </div>
        )}
      </div>
    </>
  );
};
