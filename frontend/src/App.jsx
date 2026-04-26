import React, { useState, useEffect } from 'react';
import BeliefGraph from './components/BeliefGraph';
import { Activity, ShieldAlert, Clock, GitCommitHorizontal } from 'lucide-react';
import './index.css';

const API_URL = 'http://localhost:8000';

function App() {
  const [beliefs, setBeliefs] = useState([]);
  const [conflicts, setConflicts] = useState([]);
  const [selectedNode, setSelectedNode] = useState(null);
  const [traces, setTraces] = useState([]);

  const fetchData = async () => {
    try {
      const [bRes, cRes] = await Promise.all([
        fetch(`${API_URL}/beliefs`),
        fetch(`${API_URL}/conflicts`)
      ]);
      const bData = await bRes.json();
      const cData = await cRes.json();
      setBeliefs(bData);
      setConflicts(cData);
    } catch (e) {
      console.error("Failed to fetch data", e);
    }
  };

  useEffect(() => {
    fetchData();
    // Poll every 5s for demo purposes
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleNodeClick = async (node) => {
    const fullBelief = beliefs.find(b => b.id === node.id);
    setSelectedNode(fullBelief);
    try {
      const tRes = await fetch(`${API_URL}/traces/${node.id}`);
      const tData = await tRes.json();
      setTraces(tData);
    } catch (e) {
      console.error("Failed to fetch traces", e);
    }
  };

  return (
    <div className="dashboard-container">
      <div className="graph-container">
        <BeliefGraph 
          beliefs={beliefs} 
          conflicts={conflicts} 
          onNodeClick={handleNodeClick} 
        />
      </div>

      <div className="sidebar glass-panel fade-in">
        <div className="brand-title">
          <div className="brand-icon"></div>
          <h1 className="glass-header">Axon Memory</h1>
        </div>
        
        <div className="inspector-card">
          <div className="label">System Status</div>
          <div className="value" style={{ display: 'flex', gap: '16px', marginTop: '4px' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px'}}>
              <Activity size={14} color="var(--accent-blue)" /> {beliefs.length} Beliefs
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '4px'}}>
              <ShieldAlert size={14} color="var(--accent-red)" /> {conflicts.length} Conflicts
            </span>
          </div>
        </div>

        {selectedNode ? (
          <div className="inspector-card fade-in">
            <h2 style={{ fontSize: '1.2rem', marginBottom: '8px' }}>Provenance Inspector</h2>
            
            <div style={{ marginBottom: '12px' }}>
              <div className="label">Proposition</div>
              <div className="value">{selectedNode.proposition}</div>
              <span className={`badge badge-${selectedNode.status === 'active' ? 'active' : 'conflict'}`} style={{marginTop: '8px'}}>
                {selectedNode.status}
              </span>
            </div>

            <div style={{ marginBottom: '12px' }}>
              <div className="label">Confidence Score</div>
              <div className="value">{(selectedNode.confidence * 100).toFixed(1)}%</div>
              <div className="progress-bar-bg">
                <div 
                  className="progress-bar-fill" 
                  style={{ width: `${selectedNode.confidence * 100}%` }}
                ></div>
              </div>
            </div>

            <div style={{ marginBottom: '12px' }}>
              <div className="label">Source</div>
              <div className="value" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <GitCommitHorizontal size={14} color="var(--accent-purple)"/> 
                {selectedNode.source_type}
              </div>
              <div className="value" style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                {selectedNode.source_ref || "No explicit reference"}
              </div>
            </div>

            <div>
              <div className="label" style={{ marginBottom: '8px' }}>Trace History</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '150px', overflowY: 'auto' }}>
                {traces.map(t => (
                  <div key={t.id} style={{ fontSize: '0.8rem', paddingLeft: '8px', borderLeft: '2px solid var(--border-glass)'}}>
                    <div style={{ color: 'var(--text-secondary)' }}>
                      {new Date(t.timestamp).toLocaleTimeString()} - <span style={{color: 'var(--text-primary)'}}>{t.action}</span>
                    </div>
                    <div style={{ color: 'var(--text-secondary)' }}>{t.details}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* Conflict Resolution Block */}
            {conflicts.filter(c => c.status === 'pending' && (c.belief_a_id === selectedNode.id || c.belief_b_id === selectedNode.id)).map(c => {
              const isNodeA = c.belief_a_id === selectedNode.id;
              const opposingId = isNodeA ? c.belief_b_id : c.belief_a_id;
              const opposingBelief = beliefs.find(b => b.id === opposingId);
              
              const handleResolve = async (resolution) => {
                try {
                  await fetch(`${API_URL}/conflicts/${c.id}/resolve?resolution=${resolution}`, { method: 'POST' });
                  fetchData(); // Refresh all data
                  setSelectedNode(null); // Deselect to avoid stale state
                } catch (e) {
                  console.error("Failed to resolve conflict", e);
                }
              };

              return (
                <div key={c.id} style={{ marginTop: '16px', padding: '16px', background: 'rgba(239, 68, 68, 0.05)', border: '1px solid rgba(239, 68, 68, 0.2)', borderRadius: '8px' }}>
                  <div className="label" style={{ color: 'var(--accent-red)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <ShieldAlert size={14} /> Active Conflict
                  </div>
                  <div style={{ fontSize: '0.85rem', marginBottom: '12px', color: 'var(--text-secondary)' }}>
                    Conflicts with: <br/>
                    <strong style={{ color: 'var(--text-primary)' }}>"{opposingBelief?.proposition || 'Unknown belief'}"</strong>
                  </div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button 
                      className="button" 
                      style={{ flex: 1, fontSize: '0.8rem', padding: '6px' }}
                      onClick={() => handleResolve(isNodeA ? 'resolved_a' : 'resolved_b')}
                    >
                      Keep This
                    </button>
                    <button 
                      className="button button-danger" 
                      style={{ flex: 1, fontSize: '0.8rem', padding: '6px' }}
                      onClick={() => handleResolve(isNodeA ? 'resolved_b' : 'resolved_a')}
                    >
                      Reject This
                    </button>
                  </div>
                </div>
              );
            })}

          </div>
        ) : (
          <div className="inspector-card" style={{ opacity: 0.5, textAlign: 'center', padding: '32px' }}>
            Select a node on the canvas to inspect its epistemology.
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
