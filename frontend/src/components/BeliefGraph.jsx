import React, { useRef, useEffect, useCallback, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

export default function BeliefGraph({ beliefs, conflicts, onNodeClick }) {
  const graphRef = useRef();
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });

  useEffect(() => {
    // Transform beliefs into nodes
    const nodes = beliefs.map(b => {
      const isDeprecated = b.status === 'deprecated';
      return {
        id: b.id,
        name: b.proposition,
        val: b.confidence * 10, // Size based on confidence
        confidence: b.confidence,
        status: b.status,
        color: b.status === 'conflicted' ? '#ef4444' : (isDeprecated ? '#4b5563' : '#3b82f6'),
        opacity: isDeprecated ? 0.15 : Math.max(0.2, b.confidence)
      };
    });

    // Create links from 'derived_from' and 'conflicts_with'
    const links = [];
    
    beliefs.forEach(b => {
      // Lineage links
      if (b.derived_from) {
        b.derived_from.forEach(sourceId => {
          if (beliefs.find(n => n.id === sourceId)) {
            links.push({
              source: sourceId,
              target: b.id,
              type: 'derived',
              color: 'rgba(255, 255, 255, 0.2)',
              width: 1
            });
          }
        });
      }
    });

    // Conflict links
    conflicts.forEach(c => {
      if (c.status === 'pending') {
        links.push({
          source: c.belief_a_id,
          target: c.belief_b_id,
          type: 'conflict',
          color: '#ef4444',
          width: 3,
          dash: [4, 4]
        });
      }
    });

    setGraphData({ nodes, links });
  }, [beliefs, conflicts]);

  const paintNode = useCallback((node, ctx, globalScale) => {
    const label = node.name;
    const fontSize = 12/globalScale;
    ctx.font = `${fontSize}px Inter, sans-serif`;
    
    // Draw Node Circle
    ctx.beginPath();
    ctx.arc(node.x, node.y, 5, 0, 2 * Math.PI, false);
    
    // Use opacity based on confidence
    ctx.globalAlpha = node.opacity;
    ctx.fillStyle = node.color;
    ctx.fill();
    
    if (node.status === 'conflicted') {
      ctx.lineWidth = 2;
      ctx.strokeStyle = '#fff';
      ctx.stroke();
    }

    ctx.globalAlpha = 1;

    // Draw Label text
    const textWidth = ctx.measureText(label).width;
    const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2);
    
    ctx.fillStyle = 'rgba(10, 10, 12, 0.8)';
    ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y + 8 - bckgDimensions[1] / 2, ...bckgDimensions);

    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = `rgba(255, 255, 255, ${Math.max(0.4, node.opacity)})`;
    ctx.fillText(label, node.x, node.y + 8);
  }, []);

  return (
    <ForceGraph2D
      ref={graphRef}
      graphData={graphData}
      nodeCanvasObject={paintNode}
      linkColor={link => link.color}
      linkWidth={link => link.width}
      linkLineDash={link => link.type === 'conflict' ? [4, 4] : null}
      backgroundColor="#0a0a0c"
      onNodeClick={onNodeClick}
      d3AlphaDecay={0.02}
      d3VelocityDecay={0.3}
    />
  );
}
