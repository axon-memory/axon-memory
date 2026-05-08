import React, { useState, useEffect, useCallback } from 'react';
import BeliefGraph from './components/BeliefGraph';
import './index.css';

const API = 'http://localhost:8000';

function fmt(ts) {
  return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// ── Small UI atoms ─────────────────────────────────────────
function Badge({ type, status }) {
  const t   = status === 'conflicted' ? 'conflicted' : type;
  const cls = { hub: 'badge-hub', synthesis: 'badge-synthesis', belief: 'badge-belief', conflicted: 'badge-conflict' }[t] ?? 'badge-belief';
  const lbl = { hub: 'Hub', synthesis: 'Synthesis', belief: 'Belief', conflicted: 'Conflict' }[t] ?? t;
  return <span className={`type-badge ${cls}`}>{lbl}</span>;
}

function ProgressBar({ value, color }) {
  return (
    <div className="conf-track">
      <div className="conf-fill" style={{ width: `${(value * 100).toFixed(0)}%`, background: color }} />
    </div>
  );
}

// ── Inspector panel ────────────────────────────────────────
function Inspector({ node, traces, conflicts, beliefs, onResolve }) {
  if (!node) {
    return (
      <div className="empty-state">
        <p>Click any node to inspect its belief, confidence, source, and conflict history.</p>
      </div>
    );
  }

  const nodeConflicts = conflicts.filter(
    c => c.status === 'pending' && (c.belief_a_id === node.id || c.belief_b_id === node.id)
  );

  return (
    <div className="inspector">
      <div className="insp-header">
        <Badge type={node.node_type} status={node.status} />
        <span className={`status-dot ${node.status}`} title={node.status} />
      </div>

      <div className="field-group">
        <span className="field-label">Proposition</span>
        <p className="proposition-text">{node.proposition}</p>
      </div>

      <div className="field-group">
        <span className="field-label">Confidence · {(node.confidence * 100).toFixed(1)}%</span>
        <ProgressBar value={node.confidence} color="#6366f1" />
      </div>

      <div className="field-group">
        <span className="field-label">Importance · {((node.importance ?? 0.5) * 100).toFixed(0)}%</span>
        <ProgressBar value={node.importance ?? 0.5} color="#f59e0b" />
      </div>

      <div className="field-group">
        <span className="field-label">Source</span>
        <div className="source-row">
          <span className="source-icon">⇢</span>
          <span className="source-type">{node.source_type}</span>
        </div>
        {node.source_ref && <p className="source-ref">{node.source_ref}</p>}
        {node.tags?.length > 0 && (
          <div className="tag-row">{node.tags.map(t => <span key={t} className="tag">#{t}</span>)}</div>
        )}
      </div>

      {node.node_type === 'synthesis' && node.synthesis_of?.length > 0 && (
        <div className="field-group">
          <span className="field-label">Synthesised from</span>
          <span className="source-type">{node.synthesis_of.length} beliefs</span>
        </div>
      )}

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

      {nodeConflicts.map(c => {
        const isA  = c.belief_a_id === node.id;
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
              <button className="btn-keep"
                onClick={() => onResolve(c.id, isA ? 'resolved_a' : 'resolved_b')}>
                Keep This
              </button>
              <button className="btn-reject"
                onClick={() => onResolve(c.id, isA ? 'resolved_b' : 'resolved_a')}>
                Reject This
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Hubs panel ────────────────────────────────────────────
function HubsPanel({ beliefs, collapsedHubs, onToggleHub, onRenameHub }) {
  const hubs = beliefs.filter(b => b.node_type === 'hub');
  const childCount = {};
  beliefs.forEach(b => {
    if (b.belongs_to_hub) childCount[b.belongs_to_hub] = (childCount[b.belongs_to_hub] ?? 0) + 1;
  });

  return (
    <div className="hubs-list">
      {hubs.length === 0 && <p className="empty-state" style={{fontSize:11}}>No hubs yet. Add beliefs to generate hubs automatically.</p>}
      {hubs.map(hub => {
        const count     = childCount[hub.id] ?? 0;
        const collapsed = collapsedHubs.has(hub.id);
        return (
          <div key={hub.id} className={`hub-row ${collapsed ? 'collapsed' : ''}`}>
            <button
              className="hub-toggle"
              onClick={() => onToggleHub(hub.id)}
              title={collapsed ? 'Expand hub' : 'Collapse hub'}
            >
              {collapsed ? '▸' : '▾'}
            </button>
            <div className="hub-info">
              <span className="hub-name" style={{ color: '#fbbf24' }}>{hub.proposition}</span>
              <span className="hub-count">{count} node{count !== 1 ? 's' : ''}</span>
            </div>
            {collapsed && (
              <span className="hub-collapsed-badge">collapsed</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Add Belief modal ──────────────────────────────────────
function AddBeliefModal({ onClose, onAdd, beliefs }) {
  const hubs = beliefs.filter(b => b.node_type === 'hub');
  const [proposition, setProposition] = useState('');
  const [source, setSource]           = useState('user_explicit');
  const [evidence, setEvidence]       = useState('');
  const [hubOverride, setHubOverride] = useState('auto');
  const [loading, setLoading]         = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!proposition.trim()) return;
    setLoading(true);
    await onAdd({ proposition: proposition.trim(), source, evidence: evidence.trim() || null, hubOverride });
    setLoading(false);
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <span className="modal-title">Add Belief</span>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        <form onSubmit={handleSubmit}>
          <div className="modal-field">
            <label className="field-label">Proposition</label>
            <textarea
              className="modal-textarea"
              value={proposition}
              onChange={e => setProposition(e.target.value)}
              placeholder="e.g. The default cache TTL is 5 minutes"
              rows={3}
              autoFocus
            />
          </div>
          <div className="modal-field">
            <label className="field-label">Source</label>
            <select className="modal-select" value={source} onChange={e => setSource(e.target.value)}>
              <option value="user_explicit">user_explicit</option>
              <option value="agent_inferred">agent_inferred</option>
              <option value="tool_result">tool_result</option>
            </select>
          </div>
          <div className="modal-field">
            <label className="field-label">Evidence (optional)</label>
            <input
              className="modal-input"
              value={evidence}
              onChange={e => setEvidence(e.target.value)}
              placeholder="Context or citation"
            />
          </div>
          <div className="modal-field">
            <label className="field-label">
              Hub Assignment
              <span className="field-hint"> — auto-detected by default</span>
            </label>
            <select className="modal-select" value={hubOverride} onChange={e => setHubOverride(e.target.value)}>
              <option value="auto">🔮 Auto-detect</option>
              {hubs.map(h => (
                <option key={h.id} value={h.proposition}>{h.proposition}</option>
              ))}
              <option value="__new__">+ Create new hub…</option>
            </select>
          </div>
          {hubOverride === '__new__' && (
            <div className="modal-field">
              <label className="field-label">New Hub Name</label>
              <input
                className="modal-input"
                placeholder="e.g. Performance"
                onChange={e => setHubOverride(e.target.value || '__new__')}
              />
            </div>
          )}
          <div className="modal-actions">
            <button type="button" className="btn-cancel" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-add" disabled={loading || !proposition.trim()}>
              {loading ? 'Adding…' : 'Add Belief'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── App ────────────────────────────────────────────────────
export default function App() {
  const [beliefs, setBeliefs]         = useState([]);
  const [conflicts, setConflicts]     = useState([]);
  const [stats, setStats]             = useState(null);
  const [selected, setSelected]       = useState(null);
  const [traces, setTraces]           = useState([]);
  const [collapsedHubs, setCollapsed] = useState(new Set());
  const [activeTab, setActiveTab]     = useState('inspector'); // 'inspector' | 'hubs'
  const [showAdd, setShowAdd]         = useState(false);
  const [consolidating, setConsolidating] = useState(false);
  const [toast, setToast]             = useState(null);

  const showToast = (msg, err = false) => {
    setToast({ msg, err });
    setTimeout(() => setToast(null), 3000);
  };

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

  // Node click: hubs toggle collapse, others open inspector
  const handleNodeClick = useCallback(async (node) => {
    const full = beliefs.find(b => b.id === node.id);
    if (full?.node_type === 'hub') {
      setCollapsed(prev => {
        const next = new Set(prev);
        next.has(node.id) ? next.delete(node.id) : next.add(node.id);
        return next;
      });
      return;
    }
    setSelected(full ?? null);
    setActiveTab('inspector');
    setTraces([]);
    if (!full) return;
    try {
      const r = await fetch(`${API}/traces/${node.id}`);
      setTraces(await r.json());
    } catch {}
  }, [beliefs]);

  const handleToggleHub = useCallback((hubId) => {
    setCollapsed(prev => {
      const next = new Set(prev);
      next.has(hubId) ? next.delete(hubId) : next.add(hubId);
      return next;
    });
  }, []);

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

  const handleAddBelief = async ({ proposition, source, evidence, hubOverride }) => {
    try {
      const body = { proposition, source_type: source, evidence };
      // If hub override is set (not auto), we pass it as a tag hint for now
      // (full custom hub support requires a backend change — done below)
      if (hubOverride && hubOverride !== 'auto' && hubOverride !== '__new__') {
        body.hub_override = hubOverride;
      }
      await fetch(`${API}/beliefs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      await fetchAll();
      showToast('Belief added');
    } catch { showToast('Failed to add belief', true); }
  };

  const numBeliefs   = stats?.by_type?.belief    ?? 0;
  const numHubs      = stats?.by_type?.hub        ?? 0;
  const numSynthesis = stats?.by_type?.synthesis  ?? 0;
  const numConflicts = stats?.by_status?.conflicted ?? 0;

  return (
    <div className="app">
      {/* Graph */}
      <div className="graph-wrap">
        <BeliefGraph
          beliefs={beliefs}
          conflicts={conflicts}
          collapsedHubs={collapsedHubs}
          onNodeClick={handleNodeClick}
        />
        <div className="canvas-hint">
          Scroll to zoom · Drag to pan · Click hub to collapse · Click belief to inspect
        </div>
        <button className="fab" onClick={() => setShowAdd(true)} title="Add belief">+</button>
      </div>

      {/* Sidebar */}
      <aside className="panel">
        {/* Header */}
        <div className="panel-header">
          <div className="header-dot" />
          <div>
            <div className="header-title">Axon Memory</div>
            <div className="header-sub">Epistemic Engine</div>
          </div>
        </div>

        {/* Stats grid */}
        <div className="panel-section">
          <p className="section-label">Vault Status</p>
          <div className="stats-grid">
            <div className="stat-cell">
              <span className="stat-num" style={{ color: '#6366f1' }}>{numBeliefs}</span>
              <span className="stat-name">Beliefs</span>
            </div>
            <div className="stat-cell">
              <span className="stat-num" style={{ color: '#f59e0b' }}>{numHubs}</span>
              <span className="stat-name">Hubs</span>
            </div>
            <div className="stat-cell">
              <span className="stat-num" style={{ color: '#818cf8' }}>{numSynthesis}</span>
              <span className="stat-name">Synthesis</span>
            </div>
            <div className="stat-cell">
              <span className="stat-num" style={{ color: '#f43f5e' }}>{numConflicts}</span>
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

        {/* Tab bar */}
        <div className="tab-bar">
          <button
            className={`tab-btn ${activeTab === 'inspector' ? 'active' : ''}`}
            onClick={() => setActiveTab('inspector')}
          >Inspector</button>
          <button
            className={`tab-btn ${activeTab === 'hubs' ? 'active' : ''}`}
            onClick={() => setActiveTab('hubs')}
          >Hubs <span className="tab-count">{numHubs}</span></button>
        </div>

        {/* Tab content */}
        <div className="tab-content">
          {activeTab === 'inspector' ? (
            <Inspector
              node={selected}
              traces={traces}
              conflicts={conflicts}
              beliefs={beliefs}
              onResolve={handleResolve}
            />
          ) : (
            <HubsPanel
              beliefs={beliefs}
              collapsedHubs={collapsedHubs}
              onToggleHub={handleToggleHub}
              onRenameHub={() => {}}
            />
          )}
        </div>
      </aside>

      {/* Add Belief Modal */}
      {showAdd && (
        <AddBeliefModal
          onClose={() => setShowAdd(false)}
          onAdd={handleAddBelief}
          beliefs={beliefs}
        />
      )}

      {/* Toast */}
      {toast && (
        <div className={`toast ${toast.err ? 'toast-err' : 'toast-ok'}`}>{toast.msg}</div>
      )}
    </div>
  );
}
