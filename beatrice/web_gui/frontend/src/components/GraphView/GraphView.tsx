import React, { useRef, useEffect, useState, useCallback } from 'react';
import * as d3 from 'd3';
import { useGraph } from '../../store/context';

// Цвета Louvain-сообществ
const LOUVAIN_PALETTE = [
  '#e6194b', '#3cb44b', '#ffe119', '#4363d8', '#f58231', '#911eb4',
  '#42d4f4', '#f032e6', '#bfef45', '#fabed4', '#469990', '#dcbeff',
];

interface SimNode extends d3.SimulationNodeDatum {
  id: string;
  label: string;
  type: string;
  desc: string;
  color: string;
  size: number;
  tags: string[];
  isOrphan: boolean;
  note: string;
  community: number;
  communityColor: string;
}

interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  relation: string;
}

/** Все D3-состояние в одном ref — никаких пропавших замыканий. */
interface D3State {
  svg: d3.Selection<SVGSVGElement, unknown, null, undefined>;
  container: d3.Selection<SVGGElement, unknown, null, undefined>;
  linkGroup: d3.Selection<SVGGElement, unknown, null, undefined>;
  nodeGroup: d3.Selection<SVGGElement, unknown, null, undefined>;
  link: d3.Selection<SVGLineElement, SimLink, SVGGElement, unknown>;
  edgeLabel: d3.Selection<SVGTextElement, SimLink, SVGGElement, unknown>;
  nodeSel: d3.Selection<SVGGElement, SimNode, SVGGElement, unknown>;
  sim: d3.Simulation<SimNode, SimLink>;
  width: number;
  height: number;
}

function buildGraphData(graph: ReturnType<typeof useGraph>):
    { nodes: SimNode[]; links: SimLink[]; nodeMap: Map<string, SimNode> } {
  const nodes: SimNode[] = Array.from(graph.nodes.values()).map((n) => ({
    id: n.id,
    label: n.label,
    type: n.type,
    desc: n.desc,
    color: n.color || '#999',
    size: n.size || 10,
    tags: n.tags,
    isOrphan: n.isOrphan || false,
    note: n.note || '',
    community: n.community ?? 0,
    communityColor: LOUVAIN_PALETTE[(n.community ?? 0) % LOUVAIN_PALETTE.length],
  }));
  const nodeMap = new Map<string, SimNode>();
  nodes.forEach((n) => nodeMap.set(n.id, n));
  const links: SimLink[] = graph.edges
    .filter((e) => nodeMap.has(e.source) && nodeMap.has(e.target))
    .map((e) => ({
      source: nodeMap.get(e.source)!,
      target: nodeMap.get(e.target)!,
      relation: e.relation,
    } as SimLink));
  return { nodes, links, nodeMap };
}

export const GraphView: React.FC = () => {
  const graph = useGraph();
  const [, forceUpdate] = useState(0);
  const svgElRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const d3Ref = useRef<D3State | null>(null);

  // ────── React-состояние для UI-контролов ──────
  const [showDir, setShowDir] = useState(true);
  const [showLouvain, setShowLouvain] = useState(false);
  const [hiddenCommunities, setHiddenCommunities] = useState<Set<number>>(new Set());
  const [highlightedTags, setHighlightedTags] = useState<Set<string>>(new Set());
  const [tagColor, setTagColor] = useState('#e94560');
  const [showOrphans, setShowOrphans] = useState(true);
  const [graphNoteFilter, setGraphNoteFilter] = useState('');  // '' = все, 'with' = с конспектом, 'without' = без

  // ────── Один раз при монтировании: создаём SVG, zoom, simulation ──────
  useEffect(() => {
    if (!svgElRef.current || !containerRef.current) return;

    const svgEl = svgElRef.current;
    const containerEl = containerRef.current;
    const width = containerEl.clientWidth || 600;
    const height = containerEl.clientHeight || 400;

    const svg = d3.select(svgEl);
    svg.attr('width', width).attr('height', height);

    const container = svg.append('g');

    // Zoom
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 10])
      .on('zoom', (event) => container.attr('transform', event.transform));
    svg.call(zoom);

    // Arrow marker
    const defs = svg.append('defs');
    defs.append('marker')
      .attr('id', 'arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 25)
      .attr('refY', 0)
      .attr('markerWidth', 8)
      .attr('markerHeight', 8)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#555');

    const linkGroup = container.append('g');
    const nodeGroup = container.append('g');

    // Начальные данные (может быть пусто)
    const { nodes, links } = buildGraphData(graph);

    // Link
    const link = linkGroup
      .selectAll<SVGLineElement, SimLink>('line')
      .data(links)
      .join('line')
      .attr('stroke', '#555')
      .attr('stroke-width', 1.5)
      .attr('stroke-opacity', 0.6)
      .attr('marker-end', 'url(#arrow)');

    // Edge labels
    const edgeLabel = linkGroup
      .selectAll<SVGTextElement, SimLink>('text')
      .data(links)
      .join('text')
      .text((d) => d.relation)
      .attr('font-size', 9)
      .attr('fill', '#888')
      .attr('text-anchor', 'middle');

    // Nodes
    const nodeSel = nodeGroup
      .selectAll<SVGGElement, SimNode>('g')
      .data(nodes)
      .join('g')
      .call(
        d3.drag<SVGGElement, SimNode>()
          .on('start', (event, d) => {
            if (!event.active) sim.alphaTarget(0.3).restart();
            d.fx = d.x ?? 0;
            d.fy = d.y ?? 0;
          })
          .on('drag', (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on('end', (event, d) => {
            if (!event.active) sim.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      )
      .on('click', (event, d) => {
        event.stopPropagation();
        graph.selectNode(d.id);
      });

    // Circle
    nodeSel.append('circle')
      .attr('r', (d) => d.size)
      .attr('fill', (d) => d.color || '#999')
      .attr('stroke', (d) => d.isOrphan ? '#ff6b6b' : '#fff')
      .attr('stroke-width', (d) => d.isOrphan ? 3 : 1.5)
      .style('cursor', 'pointer');

    // Label
    nodeSel.append('text')
      .text((d) => d.label)
      .attr('dx', 0)
      .attr('dy', (d) => -(d.size) - 6)
      .attr('text-anchor', 'middle')
      .attr('font-size', 12)
      .attr('fill', '#fff')
      .style('pointer-events', 'none');

    // Tooltip on hover
    nodeSel.on('mouseover', function (event, d) {
      const existing = document.getElementById('graph-tooltip');
      if (existing) existing.remove();
      const div = document.createElement('div');
      div.id = 'graph-tooltip';
      div.className = 'graph-tooltip';
      div.innerHTML = `
        <div class="title">${d.label || d.id}</div>
        ${d.desc ? `<div class="sub">${d.desc}</div>` : ''}
        <div class="sub" style="margin-top:4px">Тип: ${d.type || '—'}</div>
        ${d.tags.length > 0 ? `<div class="sub">Теги: ${d.tags.join(', ')}</div>` : ''}
        ${d.note ? `<div class="sub" style="margin-top:4px">📝 <a href="${d.note}" target="_blank">Конспект</a></div>` : ''}
        ${d.isOrphan ? '<div class="sub" style="color:#ff6b6b;margin-top:4px">👻 Сирота</div>' : ''}
        <div class="sub" style="color:#666;margin-top:2px;font-size:10px">ID: ${d.id}</div>
      `;
      div.style.display = 'block';
      div.style.left = `${event.pageX + 16}px`;
      div.style.top = `${event.pageY - 10}px`;
      document.body.appendChild(div);
    })
    .on('mouseout', () => {
      const existing = document.getElementById('graph-tooltip');
      if (existing) existing.remove();
    });

    // Click on background → deselect
    svg.on('click', () => graph.selectNode(null));

    // Simulation
    const sim = d3.forceSimulation<SimNode>(nodes)
      .force('link', d3.forceLink<SimNode, SimLink>(links).id((d) => d.id).distance(150))
      .force('charge', d3.forceManyBody().strength(-400))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide<SimNode>().radius((d) => d.size + 15));

    // Tick handler — читает из d3Ref, а не из замыкания
    sim.on('tick', () => {
      const s = d3Ref.current;
      if (!s) return;
      s.link
        .attr('x1', (d) => (d.source as SimNode).x ?? 0)
        .attr('y1', (d) => (d.source as SimNode).y ?? 0)
        .attr('x2', (d) => (d.target as SimNode).x ?? 0)
        .attr('y2', (d) => (d.target as SimNode).y ?? 0);
      s.edgeLabel
        .attr('x', (d) => (((d.source as SimNode).x ?? 0) + ((d.target as SimNode).x ?? 0)) / 2)
        .attr('y', (d) => (((d.source as SimNode).y ?? 0) + ((d.target as SimNode).y ?? 0)) / 2 - 6);
      s.nodeSel.attr('transform', (d) => `translate(${d.x ?? 0},${d.y ?? 0})`);
    });

    d3Ref.current = {
      svg, container, linkGroup, nodeGroup,
      link, edgeLabel, nodeSel, sim,
      width, height,
    };

    // Начальные отображение
    applyVisualState(d3Ref.current);
    updateLegend();

    return () => {
      sim.stop();
      d3Ref.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ────── Синхронизация графа при изменении данных (add/remove узлов/рёбер) ──────
  useEffect(() => {
    const d3s = d3Ref.current;
    if (!d3s) return;
    const { nodeGroup, linkGroup, sim, width, height } = d3s;
    const { nodes, links } = buildGraphData(graph);

    // Data join для связей
    const newLink = linkGroup
      .selectAll<SVGLineElement, SimLink>('line')
      .data(links, (d: any) => `${(d.source as SimNode)?.id ?? d.source}-${(d.target as SimNode)?.id ?? d.target}`);
    newLink.exit().remove();
    const linkEnter = newLink.enter().append('line')
      .attr('stroke', '#555')
      .attr('stroke-width', 1.5)
      .attr('stroke-opacity', 0.6)
      .attr('marker-end', showDir ? 'url(#arrow)' : null);
    d3s.link = linkEnter.merge(newLink) as typeof d3s.link;

    // Data join для подписей рёбер
    const newLabel = linkGroup
      .selectAll<SVGTextElement, SimLink>('text')
      .data(links, (d: any) => `${(d.source as SimNode)?.id ?? d.source}-${(d.target as SimNode)?.id ?? d.target}`);
    newLabel.exit().remove();
    const labelEnter = newLabel.enter().append('text')
      .attr('font-size', 9)
      .attr('fill', '#888')
      .attr('text-anchor', 'middle');
    d3s.edgeLabel = labelEnter.merge(newLabel)
      .text((d) => d.relation) as typeof d3s.edgeLabel;

    // Data join для узлов
    const newNode = nodeGroup
      .selectAll<SVGGElement, SimNode>('g')
      .data(nodes, (d: any) => d.id);
    newNode.exit().remove();

    const nodeEnter = newNode.enter().append('g')
      .call(
        d3.drag<SVGGElement, SimNode>()
          .on('start', (event, d) => {
            if (!event.active) sim.alphaTarget(0.3).restart();
            d.fx = d.x ?? width / 2;
            d.fy = d.y ?? height / 2;
          })
          .on('drag', (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on('end', (event, d) => {
            if (!event.active) sim.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      )
      .on('click', (event, d) => {
        event.stopPropagation();
        graph.selectNode(d.id);
      })
      .on('mouseover', function (event, d) {
        // Tooltip
        const existing = document.getElementById('graph-tooltip');
        if (existing) existing.remove();
        const div = document.createElement('div');
        div.id = 'graph-tooltip';
        div.className = 'graph-tooltip';
        div.innerHTML = `
          <div class="title">${d.label || d.id}</div>
          ${d.desc ? `<div class="sub">${d.desc}</div>` : ''}
          <div class="sub" style="margin-top:4px">Тип: ${d.type || '—'}</div>
          ${d.tags.length > 0 ? `<div class="sub">Теги: ${d.tags.join(', ')}</div>` : ''}
          ${d.note ? `<div class="sub" style="margin-top:4px">📝 <a href="${d.note}" target="_blank">Конспект</a></div>` : ''}
          ${d.isOrphan ? '<div class="sub" style="color:#ff6b6b;margin-top:4px">👻 Сирота</div>' : ''}
          <div class="sub" style="color:#666;margin-top:2px;font-size:10px">ID: ${d.id}</div>
        `;
        div.style.display = 'block';
        div.style.left = `${event.pageX + 16}px`;
        div.style.top = `${event.pageY - 10}px`;
        document.body.appendChild(div);
      })
      .on('mouseout', () => {
        const existing = document.getElementById('graph-tooltip');
        if (existing) existing.remove();
      });

    nodeEnter.append('circle')
      .attr('r', (d) => d.size)
      .attr('fill', (d) => getFillColor(d))
      .attr('stroke', (d) => d.isOrphan ? '#ff6b6b' : '#fff')
      .attr('stroke-width', (d) => d.isOrphan ? 3 : 1.5)
      .style('cursor', 'pointer');

    nodeEnter.append('text')
      .text((d) => d.label)
      .attr('dx', 0)
      .attr('dy', (d) => -(d.size) - 6)
      .attr('text-anchor', 'middle')
      .attr('font-size', 12)
      .attr('fill', '#fff')
      .style('pointer-events', 'none');

    d3s.nodeSel = nodeEnter.merge(newNode) as typeof d3s.nodeSel;

    // Обновляем simulation
    // Сохраняем позиции существующих узлов ДО замены данных в симуляции
    const oldNodes = new Map<string, SimNode>();
    const currentSimNodes = sim.nodes() as SimNode[];
    currentSimNodes.forEach((n) => oldNodes.set(n.id, n));

    sim.nodes(nodes);
    const linkForce = sim.force('link') as d3.ForceLink<SimNode, SimLink>;
    linkForce.links(links);

    for (const n of nodes) {
      const old = oldNodes.get(n.id);
      if (old) {
        n.x = old.x;
        n.y = old.y;
        n.vx = old.vx ?? 0;
        n.vy = old.vy ?? 0;
      } else {
        // Новый узел — ставим рядом с центром
        n.x = width / 2 + (Math.random() - 0.5) * 100;
        n.y = height / 2 + (Math.random() - 0.5) * 100;
      }
    }
    sim.alpha(0.5).restart();

    applyVisualState(d3s);
    updateLegend();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph.nodes.size, graph.edges.length]);

  // ────── Применить все визуальные настройки (цвета, стрелки, сироты, выделение) ──────
  // Запускается при любом изменении UI-контролов или выделения — без пересоздания
  useEffect(() => {
    if (!d3Ref.current) return;
    applyVisualState(d3Ref.current);
    updateLegend();
  }, [showDir, showLouvain, hiddenCommunities, highlightedTags, tagColor,
      showOrphans, graphNoteFilter, graph.selectedNodeId]);

  // ────── Вспомогательные функции ──────

  function getFillColor(d: SimNode): string {
    if (highlightedTags.size > 0 && d.tags.some((t) => highlightedTags.has(t))) return tagColor;
    if (showLouvain) return d.communityColor;
    return d.color || '#999';
  }

  function applyVisualState(d3s: D3State): void {
    const selectedId = graph.selectedNodeId;
    const neighborSet = new Set<string>();
    if (selectedId && graph.nodes.has(selectedId)) {
      neighborSet.add(selectedId);
      for (const e of graph.edges) {
        if (e.source === selectedId) neighborSet.add(e.target);
        if (e.target === selectedId) neighborSet.add(e.source);
      }
    }

    // Стрелки
    d3s.link.attr('marker-end', showDir ? 'url(#arrow)' : null);

    // Цвета кругов + stroke + opacity
    d3s.nodeSel.each(function (d: SimNode) {
      const g = d3.select(this);
      const circle = g.select('circle');
      const text = g.select('text');

      // Fill
      circle.attr('fill', getFillColor(d));

    // Видимость сирот + скрытые сообщества
      if (!showOrphans && d.isOrphan) {
        g.style('display', 'none');
        return;
      }
      if (showLouvain && hiddenCommunities.has(d.community)) {
        g.style('display', 'none');
        return;
      }
      if (graphNoteFilter === 'without' && d.note) {
        g.style('display', 'none');
        return;
      }
      if (graphNoteFilter === 'with' && !d.note) {
        g.style('display', 'none');
        return;
      }
      g.style('display', null);

      // Highlight
      if (selectedId && d.id === selectedId) {
        circle.attr('stroke', '#e94560').attr('stroke-width', 3);
        g.style('opacity', null);
        if (!text.empty()) text.attr('fill', '#fff');
      } else if (selectedId && !neighborSet.has(d.id)) {
        g.style('opacity', '0.3');
        if (!text.empty()) text.attr('fill', '#555');
      } else {
        g.style('opacity', null);
        if (!text.empty()) text.attr('fill', '#fff');
        const baseStroke = d.isOrphan ? '#ff6b6b' : '#fff';
        const baseWidth = d.isOrphan ? 3 : 1.5;
        if (graphNoteFilter === 'without' && !d.note) {
          circle.attr('stroke', '#e94560').attr('stroke-width', 2)
                .attr('stroke-dasharray', '4,3');
        } else {
          circle.attr('stroke', baseStroke).attr('stroke-width', baseWidth)
                .attr('stroke-dasharray', null);
        }
      }
    });
  }

  function updateLegend(): void {
    const existing = document.getElementById('graph-legend');
    if (existing) existing.remove();

    const legend = document.createElement('div');
    legend.id = 'graph-legend';
    legend.className = 'legend';

    const ct = containerRef.current;
    if (!ct) return;

    if (showLouvain) {
      const usedComms = new Set(Array.from(graph.nodes.values()).map((n) => n.community ?? 0));
      const sorted = Array.from(usedComms).sort((a, b) => a - b);
      legend.innerHTML = sorted.map((i) =>
        `<div class="legend-item"><span class="legend-dot" style="background:${LOUVAIN_PALETTE[i % LOUVAIN_PALETTE.length]}"></span>Сообщество #${i + 1}</div>`
      ).join('');
    } else {
      const types = graph.types;
      legend.innerHTML = Object.entries(types)
        .filter(([k]) => k !== 'unknown')
        .map(([t, c]) =>
          `<div class="legend-item"><span class="legend-dot" style="background:${c}"></span>${t}</div>`
        ).join('');
    }

    ct.appendChild(legend);
  }

  const resetZoom = () => {
    if (!svgElRef.current) return;
    d3.select(svgElRef.current).transition().duration(750).call(
      d3.zoom<SVGSVGElement, unknown>().transform,
      d3.zoomIdentity
    );
  };

  const usedComms = Array.from(
    new Set(Array.from(graph.nodes.values()).map((n) => n.community ?? 0))
  ).sort((a, b) => a - b);

  const allTags = Array.from(graph.allTags).sort();

  return (
    <div ref={containerRef} className="graph-container">
      <div className="graph-controls">
        <button onClick={resetZoom}>⟲ Сбросить</button>
        <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#888' }}>
          <input type="checkbox" checked={showOrphans}
            onChange={(e) => setShowOrphans(e.target.checked)} />
          👻 Сироты
        </label>
        <button onClick={() => { setShowDir(!showDir); }}>
          {showDir ? '↔ Направления' : '↔ Без напр.'}
        </button>
        <button onClick={() => { setShowLouvain(!showLouvain); setHiddenCommunities(new Set()); }}>
          🧬 {showLouvain ? 'Типы' : 'Сообщества'}
        </button>
        {showLouvain && (
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center',
            width: '100%', padding: '4px 0', borderTop: '1px solid var(--border)',
          }}>
            <span style={{ fontSize: 11, color: '#888', marginRight: 4 }}>Сообщества:</span>
            <button className="btn-sm" onClick={() => setHiddenCommunities(new Set())}>
              Все
            </button>
            <button className="btn-sm" onClick={() => setHiddenCommunities(new Set(usedComms))}>
              Ничего
            </button>
            {usedComms.map((i) => {
              const hidden = hiddenCommunities.has(i);
              return (
                <label key={i} style={{
                  display: 'flex', alignItems: 'center', gap: 2,
                  fontSize: 11, cursor: 'pointer', color: hidden ? '#666' : '#eee',
                  background: hidden ? 'transparent' : LOUVAIN_PALETTE[i % LOUVAIN_PALETTE.length] + '33',
                  padding: '1px 6px', borderRadius: 4,
                }}>
                  <span style={{
                    display: 'inline-block', width: 8, height: 8, borderRadius: '50%',
                    background: LOUVAIN_PALETTE[i % LOUVAIN_PALETTE.length],
                    opacity: hidden ? 0.3 : 1,
                  }} />
                  <input
                    type="checkbox"
                    checked={!hidden}
                    onChange={() => {
                      const next = new Set(hiddenCommunities);
                      if (hidden) next.delete(i); else next.add(i);
                      setHiddenCommunities(next);
                    }}
                    style={{ width: 12, height: 12, accentColor: LOUVAIN_PALETTE[i % LOUVAIN_PALETTE.length] }}
                  />
                  #{i + 1}
                </label>
              );
            })}
          </div>
        )}
         {allTags.length > 0 && (
          <div style={{
            display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center',
            width: '100%', padding: '4px 0', borderTop: '1px solid var(--border)',
          }}>
            <span style={{ fontSize: 11, color: '#888', marginRight: 4 }}>Теги:</span>
            <button className="btn-sm" onClick={() => setHighlightedTags(new Set())}>
              Сброс
            </button>
            {allTags.map((t) => {
              const active = highlightedTags.has(t);
              return (
                <label key={t} style={{
                  display: 'flex', alignItems: 'center', gap: 2,
                  fontSize: 11, cursor: 'pointer',
                  color: active ? '#eee' : '#666',
                  background: active ? tagColor + '44' : 'transparent',
                  padding: '1px 6px', borderRadius: 4,
                }}>
                  <input
                    type="checkbox"
                    checked={active}
                    onChange={() => {
                      const next = new Set(highlightedTags);
                      if (active) next.delete(t); else next.add(t);
                      setHighlightedTags(next);
                    }}
                    style={{ width: 12, height: 12, accentColor: tagColor }}
                  />
                  {t}
                </label>
              );
            })}
          </div>
        )}
        <input type="color" value={tagColor}
          onChange={(e) => setTagColor(e.target.value)} />
        <select value={graphNoteFilter} onChange={(e) => setGraphNoteFilter(e.target.value)}
          style={{ fontSize: 11, padding: '3px 6px', maxWidth: 120 }}>
          <option value="">📝 Все конспекты</option>
          <option value="with">📝 С конспектом</option>
          <option value="without">📝 Без конспекта</option>
        </select>
      </div>

      <div className="graph-info">
        {graph.nodes.size} узлов · {graph.edges.length} рёбер · {graph.orphans.length} сирот
      </div>

      <svg ref={svgElRef} style={{ width: '100%', height: '100%' }} />
    </div>
  );
};
