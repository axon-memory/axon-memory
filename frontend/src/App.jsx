import React, { useState, useEffect, useCallback } from 'react';
import BeliefGraph from './components/BeliefGraph';
import './index.css';

const API = 'http://localhost:8000';

function fmt(ts) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

export default function App() {
  const [beliefs, setBeliefs]       = useState([]);
  const [conflicts, setConflicts]   = useState([]);
  const [stats, setStats]           = useState(null);
  const [selected, setSelected]     = useState(null);
  const [traces, setTraces]         = useState([]);
  const [consolidating, setConsolidating] = useState(false);
  const [toast, setToast]           = useState(null);

  const fetchAll = useCallback(async () => {
    try {
      const [bR, cR, sR] = await Promise.all([
        fetch(`${API}/beliefs`),
        fetch(`${API}/conflicts`),
        fetch(`${API}/memory/stats`),
      ]);
      setBeliefs(await bR.json());
      setConflicts(await cR.json());
      setStats(await sR.json());
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 6000);
    return () => clearInterval(t);
  }, [fetchAll]);

  const handleNodeClick = useCallback(async (node) => {
    const full = beliefs.find(b => b.id === node.id) ?? null;
    setSelected(full);
    setTraces([]);
    if (!full) return;
    try {
      const r = await fetch(`${API}/traces/${node.id}`);
      setTraces(await r.json());
    } catch {}
  }, [beliefs]);

  const handleConsolidate = async () => {
    setConsolidating(true);
    try {
      await fetch(`${API}/memory/consolidate`, { method: 'POST' });
      await fetchAll();
      showToast('Consolidation complete');
    } catch { showToast('Consolidation failed', true); }
    finally { setConsolidating(false); }
  };

  const handleResolve = async (cId, resolution) => {
    try {
      await fetch(`${API}/conflicts/${cId}/resolve?resolution=${resolution}`, { method: 'POST' });
      setSelected(null);
      await fetchAll();
      showToast('Conflict resolved');
    } catch { showToast('Failed to resolve', true); }
  };

  const showToast = (msg, err = false) => {
    setToast({ msg, err });
    setTimeout(() => setToast(null), 3000);
  };

  const nodeConflicts = selected
    ? conflicts.filter(c => c.status === 'pending' &&
        (c.belief_a_id === selected.id || c.belief_b_id === selected.id))
    : [];

  const totalBeliefs  = stats?.by_type?.belief    ?? 0;
  const totalConflicts = stats?.by_status?.conflicted ?? 0;

  return (
    <div className="app">
      {/* Graph */}
      <div className="graph-wrap">
        <BeliefGraph beliefs={beliefs} conflicts={conflicts} onNodeClick={handleNodeClick} />
      </div>

      {/* Sidebar */}
      <aside className="panel">

        {/* Header */}
        <div className="panel-header">
          <div className="header-dot" />
          <span className="header-title">Axon Memory</span>
        </div>

        {/* System status */}
        <div className="panel-section">
          <p className="section-label">System Status</p>

          {/* 4-cell stats grid */}
          <div className="stats-grid">
            <div className="stat-cell">
              <span className="stat-num" style={{ color: '#6366f1' }}>{stats?.by_type?.belief ?? 0}</span>
              <span className="stat-name">Beliefs</span>
            </div>
            <div className="stat-cell">
              <span className="stat-num" style={{ color: '#f59e0b' }}>{stats?.by_type?.hub ?? 0}</span>
              <span className="stat-name">Hubs</span>
            </div>
            <div className="stat-cell">
              <span className="stat-num" style={{ color: '#818cf8' }}>{stats?.by_type?.synthesis ?? 0}</span>
              <span className="stat-name">Synthesis</span>
            </div>
            <div className="stat-cell">
              <span className="stat-num" style={{ color: '#f43f5e' }}>{stats?.by_status?.conflicted ?? 0}</span>
              <span className="stat-name">Conflicts</span>
            </div>
          </div>

          <button
            className={`consolidate-btn${consolidating ? ' busy' : ''}`}
            onClick={handleConsolidate}
            disabled={consolidating}
          >
            {consolidating ? '↻ Consolidating…' : '↺ Consolidate Memory'}
          </button>
        </div>

        {/* Provenance Inspector */}
        <div className="panel-section flex-1">
          <p className="section-label">Provenance Inspector</p>

          {selected ? (
            <>
              {/* Proposition */}
              <div className="field-group">
                <span className="field-label">Proposition</span>
                <p className="proposition-text">{selected.proposition}</p>
                <span className={`status-badge ${selected.status === 'active' ? 'green' : 'red'}`}>
                  {selected.status.toUpperCase()}
                </span>
              </div>

              {/* Confidence */}
              <div className="field-group">
                <span className="field-label">Confidence Score</span>
                <p className="confidence-pct">{(selected.confidence * 100).toFixed(1)}%</p>
                <div className="conf-track">
                  <div className="conf-fill" style={{ width: `${selected.confidence * 100}%` }} />
                </div>
              </div>

              {/* Source */}
              <div className="field-group">
                <span className="field-label">Source</span>
                <div className="source-row">
                  <span className="source-icon">⇢</span>
                  <span className="source-type">{selected.source_type}</span>
                </div>
                {selected.source_ref && (
                  <p className="source-ref">{selected.source_ref}</p>
                )}
                {selected.tags?.length > 0 && (
                  <div className="tag-row">
                    {selected.tags.map(t => (
                      <span key={t} className="tag">#{t}</span>
                    ))}
                  </div>
                )}
              </div>

              {/* Trace history */}
              {traces.length > 0 && (
                <div className="field-group">
                  <span className="field-label">Trace History</span>
                  <div className="trace-list">
                    {traces.slice(0, 5).map(t => (
                      <div key={t.id} className="trace-item">
                        <span className="trace-time">{fmt(t.timestamp)}</span>
                        <span className="trace-action">{t.action}</span>
                        {t.details && <span className="trace-detail">{t.details}</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Conflicts */}
              {nodeConflicts.map(c => {
                const isA  = c.belief_a_id === selected.id;
                const other = beliefs.find(b => b.id === (isA ? c.belief_b_id : c.belief_a_id));
                return (
                  <div key={c.id} className="conflict-card">
                    <div className="conflict-header">
                      <span className="conflict-icon">⊘</span>
                      <span className="conflict-label">Active Conflict</span>
                    </div>
                    <p className="conflict-body">
                      Conflicts with:<br />
                      <em>"{other?.proposition ?? 'Unknown'}"</em>
                    </p>
                    <div className="conflict-actions">
                      <button
                        className="btn-keep"
                        onClick={() => handleResolve(c.id, isA ? 'resolved_a' : 'resolved_b')}
                      >Keep This</button>
                      <button
                        className="btn-reject"
                        onClick={() => handleResolve(c.id, isA ? 'resolved_b' : 'resolved_a')}
                      >Reject This</button>
                    </div>
                  </div>
                );
              })}
            </>
          ) : (
            <div className="empty-state">
              <p>Click any node on the graph to inspect its belief, source, and conflict history.</p>
            </div>
          )}
        </div>
      </aside>

      {/* Toast */}
      {toast && (
        <div className={`toast ${toast.err ? 'toast-err' : 'toast-ok'}`}>{toast.msg}</div>
      )}
    </div>
  );
}
