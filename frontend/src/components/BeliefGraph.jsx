import React, { useRef, useEffect, useState, useCallback } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

const NODE_RADIUS = 8;

const NODE_COLOR = {
  hub:        '#f59e0b',
  synthesis:  '#818cf8',
  belief:     '#6366f1',
  conflicted: '#f43f5e',
  deprecated: '#475569',
};

// Draw a single node onto the canvas
function drawNode(node, ctx, globalScale) {
  if (node.x == null) return;

  const r     = node.isHub ? (node.collapsed ? NODE_RADIUS + 4 : NODE_RADIUS) : NODE_RADIUS;
  const color = node.color;

  // Core circle
  ctx.beginPath();
  ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
  ctx.fillStyle = color;
  ctx.fill();

  // Border ring
  ctx.lineWidth   = 1.5 / globalScale;
  ctx.strokeStyle = 'rgba(255,255,255,0.3)';
  ctx.stroke();

  // Collapsed hub: show child count badge
  if (node.isHub && node.collapsed && node.childCount > 0) {
    const badge = String(node.childCount);
    const bR    = 7 / globalScale;
    const bx    = node.x + r * 0.65;
    const by    = node.y - r * 0.65;
    ctx.beginPath();
    ctx.arc(bx, by, bR, 0, 2 * Math.PI);
    ctx.fillStyle = '#1e1e2e';
    ctx.fill();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1 / globalScale;
    ctx.stroke();

    ctx.font         = `700 ${Math.max(7, 9 / globalScale)}px Inter, sans-serif`;
    ctx.textAlign    = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle    = color;
    ctx.fillText(badge, bx, by);
  }

  // Expand/collapse indicator chevron on hubs
  if (node.isHub) {
    const chevron = node.collapsed ? '▸' : '▾';
    ctx.font         = `400 ${Math.max(6, 8 / globalScale)}px Inter, sans-serif`;
    ctx.textAlign    = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle    = 'rgba(255,255,255,0.6)';
    ctx.fillText(chevron, node.x, node.y);
  }

  // Labels — hubs always, others at zoom > 2
  const showLabel = node.isHub || globalScale > 2;
  if (!showLabel) return;

  const raw      = node.name;
  const maxLen   = node.isHub ? 20 : 32;
  const label    = raw.length > maxLen ? raw.slice(0, maxLen) + '…' : raw;
  const fontSize = Math.max(9, Math.min(13, 13 / globalScale));
  const weight   = node.isHub ? '600' : '400';

  ctx.font         = `${weight} ${fontSize}px Inter, sans-serif`;
  ctx.textAlign    = 'left';
  ctx.textBaseline = 'middle';

  const tw   = ctx.measureText(label).width;
  const padX = 5, padY = 3;
  const bw   = tw + padX * 2;
  const bh   = fontSize + padY * 2;
  const bx   = node.x + r + 6 / globalScale;
  const by   = node.y - bh / 2;

  // label pill background
  ctx.fillStyle = 'rgba(13,13,20,0.88)';
  ctx.fillRect(bx, by, bw, bh);

  // left accent
  ctx.fillStyle = color;
  ctx.fillRect(bx, by, 2, bh);

  // text
  ctx.fillStyle    = node.isHub ? '#fbbf24' : '#e2e8f0';
  ctx.textBaseline = 'middle';
  ctx.fillText(label, bx + padX + 2, node.y);
}

// Draw a link (supports dashed styles)
function drawLink(link, ctx, globalScale) {
  const src = link.source;
  const tgt = link.target;
  if (!src || !tgt || src.x == null || tgt.x == null) return;

  ctx.beginPath();
  ctx.moveTo(src.x, src.y);
  ctx.lineTo(tgt.x, tgt.y);
  ctx.lineWidth   = (link.width ?? 1) / globalScale;
  ctx.strokeStyle = link.color ?? 'rgba(255,255,255,0.15)';

  if (link.dashed) {
    ctx.setLineDash([6 / globalScale, 4 / globalScale]);
  } else {
    ctx.setLineDash([]);
  }

  ctx.stroke();
  ctx.setLineDash([]);
}

export default function BeliefGraph({ beliefs, conflicts, collapsedHubs, onNodeClick }) {
  const fgRef = useRef();
  const [data, setData] = useState({ nodes: [], links: [] });

  // Tune physics after data is set
  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    try {
      fg.d3Force('charge').strength(-450);
      fg.d3Force('link').distance(l => l.isHubSpoke ? 130 : 90);
    } catch (_) {}
  }, [data]);

  useEffect(() => {
    const collapsed = collapsedHubs ?? new Set();
    const beliefMap = new Map(beliefs.map(b => [b.id, b]));

    // Count children per hub
    const childCount = {};
    beliefs.forEach(b => {
      if (b.belongs_to_hub) {
        childCount[b.belongs_to_hub] = (childCount[b.belongs_to_hub] ?? 0) + 1;
      }
    });

    // Filter visible nodes: always show hubs; hide children of collapsed hubs
    const visibleBeliefs = beliefs.filter(b => {
      if (b.node_type === 'hub') return true;
      return !collapsed.has(b.belongs_to_hub);
    });
    const visibleIds = new Set(visibleBeliefs.map(b => b.id));

    const nodes = visibleBeliefs.map(b => ({
      id:         b.id,
      name:       b.proposition,
      node_type:  b.node_type,
      isHub:      b.node_type === 'hub',
      collapsed:  b.node_type === 'hub' && collapsed.has(b.id),
      childCount: childCount[b.id] ?? 0,
      color: b.status === 'conflicted' ? NODE_COLOR.conflicted
           : b.status === 'deprecated' ? NODE_COLOR.deprecated
           : (NODE_COLOR[b.node_type] ?? NODE_COLOR.belief),
    }));

    const links = [];

    visibleBeliefs.forEach(b => {
      // Hub spokes
      if (b.belongs_to_hub && visibleIds.has(b.belongs_to_hub)) {
        links.push({
          source:     b.belongs_to_hub,
          target:     b.id,
          color:      b.node_type === 'synthesis'
            ? 'rgba(129,140,248,0.5)'
            : 'rgba(255,255,255,0.22)',
          width:      b.node_type === 'synthesis' ? 1.5 : 1,
          isHubSpoke: true,
        });
      }

      // Synthesis provenance
      if (b.node_type === 'synthesis' && Array.isArray(b.synthesis_of)) {
        b.synthesis_of.forEach(sid => {
          if (visibleIds.has(sid)) {
            links.push({
              source:    b.id,
              target:    sid,
              color:     'rgba(129,140,248,0.35)',
              width:     1.2,
              curvature: 0.25,
            });
          }
        });
      }

      // Related-to (de-duplicated)
      if (Array.isArray(b.related_to)) {
        b.related_to.forEach(rid => {
          if (visibleIds.has(rid) && b.id < rid) {
            links.push({
              source: b.id,
              target: rid,
              color:  'rgba(251,191,36,0.55)',
              width:  1.5,
              dashed: true,
            });
          }
        });
      }
    });

    // Conflict links
    conflicts.forEach(c => {
      if (c.status === 'pending' && visibleIds.has(c.belief_a_id) && visibleIds.has(c.belief_b_id)) {
        links.push({
          source: c.belief_a_id,
          target: c.belief_b_id,
          color:  '#f43f5e',
          width:  2,
          dashed: true,
        });
      }
    });

    setData({ nodes, links });
  }, [beliefs, conflicts, collapsedHubs]);

  return (
    <ForceGraph2D
      ref={fgRef}
      graphData={data}
      nodeVal={n => n.isHub ? 3.5 : 1}
      nodeColor={n => n.color}
      linkColor={l => l.color}
      linkWidth={l => l.width ?? 1}
      linkCurvature={l => l.curvature ?? 0}
      linkDirectionalParticles={l => l.dashed && l.color === '#f43f5e' ? 3 : 0}
      linkDirectionalParticleWidth={2}
      linkDirectionalParticleColor={() => '#f43f5e'}
      backgroundColor="#0d0d14"
      onNodeClick={onNodeClick}
      nodeCanvasObject={drawNode}
      nodeCanvasObjectMode={() => 'replace'}
      linkCanvasObject={drawLink}
      linkCanvasObjectMode={() => 'replace'}
      nodePointerAreaPaint={(node, color, ctx) => {
        const r = (node.isHub ? NODE_RADIUS + 4 : NODE_RADIUS) + 8;
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
        ctx.fill();
      }}
    />
  );
}
