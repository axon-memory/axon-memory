import React, { useRef, useEffect, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

const NODE_RADIUS = 8; // all nodes same base radius

// Subtle color differentiation: hub = amber, synthesis = violet, belief = indigo
const NODE_COLOR = {
  hub:        '#f59e0b',   // amber — thematic cluster
  synthesis:  '#818cf8',   // violet — consolidated summary
  belief:     '#6366f1',   // indigo — atomic fact
  conflicted: '#f43f5e',   // rose
  deprecated: '#475569',   // slate
};

export default function BeliefGraph({ beliefs, conflicts, onNodeClick }) {
  const fgRef = useRef();
  const [data, setData] = useState({ nodes: [], links: [] });

  // Tune physics once data is set
  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    try {
      fg.d3Force('charge').strength(-500);
      fg.d3Force('link').distance(140);
    } catch (_) {}
  }, [data]);

  useEffect(() => {
    const ids = new Set(beliefs.map(b => b.id));

    const nodes = beliefs.map(b => ({
      id:        b.id,
      name:      b.proposition ?? '',
      node_type: b.node_type ?? 'belief',
      color: b.status === 'conflicted' ? NODE_COLOR.conflicted
           : b.status === 'deprecated' ? NODE_COLOR.deprecated
           : NODE_COLOR[b.node_type] ?? NODE_COLOR.belief,
    }));

    const links = [];
    beliefs.forEach(b => {
      // Hub spokes — more prominent white/amber lines
      if (b.belongs_to_hub && ids.has(b.belongs_to_hub)) {
        links.push({
          source: b.belongs_to_hub,
          target: b.id,
          color:  b.node_type === 'synthesis'
            ? 'rgba(129,140,248,0.6)'
            : 'rgba(255,255,255,0.28)',
          width: b.node_type === 'synthesis' ? 1.5 : 1.2,
          dashed: false,
        });
      }
      // Synthesis provenance — violet curved
      if (b.node_type === 'synthesis' && Array.isArray(b.synthesis_of)) {
        b.synthesis_of.forEach(sid => {
          if (ids.has(sid)) {
            links.push({
              source:    b.id,
              target:    sid,
              color:     'rgba(129,140,248,0.45)',
              width:     1.2,
              curvature: 0.25,
            });
          }
        });
      }

      // Related-to links — dashed white, de-duplicated
      if (Array.isArray(b.related_to)) {
        b.related_to.forEach(rid => {
          if (ids.has(rid) && b.id < rid) { // prevent double-drawing
            links.push({
              source:    b.id,
              target:    rid,
              color:     'rgba(251,191,36,0.55)', // amber-ish to signal 'related'
              width:     1.5,
              isRelated: true,
            });
          }
        });
      }
    });

    // Conflict links — dashed red
    conflicts.forEach(c => {
      if (c.status === 'pending') {
        links.push({
          source:     c.belief_a_id,
          target:     c.belief_b_id,
          color:      '#f43f5e',
          width:      2,
          isConflict: true,
        });
      }
    });

    setData({ nodes, links });
  }, [beliefs, conflicts]);

  // Custom draw: uniform circle + inline white label
  const paintNode = (node, ctx, globalScale) => {
    if (node.x == null) return;

    const r     = NODE_RADIUS;
    const color = node.color;

    // Circle fill
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();

    // Crisp border
    ctx.lineWidth   = 1.5 / globalScale;
    ctx.strokeStyle = 'rgba(255,255,255,0.35)';
    ctx.stroke();

    // White inline label to the right of the node
    const fontSize = Math.min(13, Math.max(9, 13 / globalScale));
    ctx.font         = `400 ${fontSize}px Inter, sans-serif`;
    ctx.textAlign    = 'left';
    ctx.textBaseline = 'middle';

    const raw   = node.name;
    const label = raw.length > 34 ? raw.slice(0, 34) + '…' : raw;

    ctx.fillStyle = 'rgba(255,255,255,0.85)';
    ctx.fillText(label, node.x + r + 6 / globalScale, node.y);
  };

  // Custom link renderer so we can draw dashed conflict lines
  const paintLink = (link, ctx, globalScale) => {
    const src = link.source;
    const tgt = link.target;
    if (src.x == null || tgt.x == null) return;

    ctx.beginPath();
    ctx.moveTo(src.x, src.y);
    ctx.lineTo(tgt.x, tgt.y);
    ctx.lineWidth   = (link.width ?? 1) / globalScale;
    ctx.strokeStyle = link.color ?? 'rgba(255,255,255,0.15)';

    if (link.isConflict || link.isRelated) {
      ctx.setLineDash([6 / globalScale, 4 / globalScale]);
    } else {
      ctx.setLineDash([]);
    }

    ctx.stroke();
    ctx.setLineDash([]); // reset
  };

  return (
    <ForceGraph2D
      ref={fgRef}
      graphData={data}
      nodeRelSize={NODE_RADIUS}
      nodeColor={n => n.color}
      linkColor={l => l.color}
      linkWidth={l => l.width ?? 1}
      backgroundColor="#0d0d14"
      onNodeClick={onNodeClick}
      nodeCanvasObject={paintNode}
      nodeCanvasObjectMode={() => 'replace'}
      linkCanvasObject={paintLink}
      linkCanvasObjectMode={() => 'replace'}
      nodePointerAreaPaint={(node, color, ctx) => {
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.arc(node.x, node.y, NODE_RADIUS + 8, 0, 2 * Math.PI);
        ctx.fill();
      }}
    />
  );
}
