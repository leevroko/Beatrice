import React, { useState, useEffect } from 'react';
import { useGraph } from '../../store/context';
import type { NodeData, TagCount } from '../../api/types';

export const TagsEditor: React.FC<{ node: NodeData }> = ({ node }) => {
  const graph = useGraph();
  const [, forceUpdate] = useState(0);
  const [newTag, setNewTag] = useState('');
  const [tagStats, setTagStats] = useState<TagCount[]>([]);
  const [tags, setTags] = useState<string[]>(node.tags);

  useEffect(() => {
    setTags(node.tags);
  }, [node.id, node.tags]);

  useEffect(() => {
    const unsub = graph.subscribe(() => forceUpdate((n) => n + 1));
    // Load tag stats on mount
    loadTagStats();
    return unsub;
  }, [graph]);

  const loadTagStats = async () => {
    try {
      const result = await graph.ws.call('tag_list') as { tags?: TagCount[] } | TagCount[];
      if (Array.isArray(result)) {
        setTagStats(result);
      } else if (result && 'tags' in result) {
        setTagStats((result as { tags: TagCount[] }).tags || []);
      }
    } catch {
      // ignore
    }
  };

  const handleAddTag = async () => {
    const tag = newTag.trim();
    if (!tag) return;
    try {
      await graph.addTag([node.id], [tag]);
      setTags([...tags, tag]);
      setNewTag('');
      loadTagStats();
    } catch (e) {
      alert(`Ошибка: ${e}`);
    }
  };

  const handleRemoveTag = async (tag: string) => {
    try {
      await graph.removeTag([node.id], [tag]);
      setTags(tags.filter((t) => t !== tag));
      loadTagStats();
    } catch (e) {
      alert(`Ошибка: ${e}`);
    }
  };

  return (
    <div style={{ padding: '0 12px' }}>
      <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13, color: 'var(--text-secondary)' }}>
        Теги
      </div>
      <div className="tag-list">
        {tags.map((t) => (
          <span key={t} className="tag-badge">
            {t}
            <span className="tag-remove" onClick={() => handleRemoveTag(t)}>×</span>
          </span>
        ))}
        {tags.length === 0 && (
          <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>Нет тегов</span>
        )}
      </div>
      <div className="tag-add-row">
        <input
          value={newTag}
          onChange={(e) => setNewTag(e.target.value)}
          placeholder="Новый тег..."
          onKeyDown={(e) => e.key === 'Enter' && handleAddTag()}
        />
        <button className="btn-sm" onClick={handleAddTag} disabled={!newTag.trim()}>
          +
        </button>
      </div>

      {tagStats.length > 0 && (
        <div className="tags-stats">
          <div style={{ fontWeight: 500, marginBottom: 4 }}>Статистика тегов графа:</div>
          {tagStats.map((t) => (
            <div key={t.tag} className="tag-stat-row">
              <span>{t.tag}</span>
              <span>{t.count} узл{t.count === 1 ? '' : (t.count >= 2 && t.count <= 4 ? 'а' : 'ов')}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
