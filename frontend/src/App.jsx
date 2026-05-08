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

// ── Search Bar ─────────────────────────────────────────────
function SearchBar({ onSearch, onClear }) {
  const [query, setQuery] = useState('');
  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim()) onSearch(query.trim());
  };
  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <input
        className="search-input"
        value={query}
        onChange={e => setQuery(e.target.value)}
        placeholder="Search beliefs…"
      />
      {query && (
        <button type="button" className="search-clear" onClick={() => { setQuery(''); onClear(); }}>✕</button>
      )}
      <button type="submit" className="search-btn" disabled={!query.trim()}>⌕</button>
    </form>
  );
}

// ── Inspector panel ────────────────────────────────────────
function Inspector({ node, traces, conflicts, beliefs, onResolve, onEdit, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [editProp, setEditProp] = useState('');
  const [editConf, setEditConf] = useState('');
  const [editTags, setEditTags] = useState('');

  useEffect(() => {
    if (node) {
      setEditProp(node.proposition);
      setEditConf(String(node.confidence));
      setEditTags((node.tags || []).join(', '));
      setEditing(false);
    }
  }, [node]);

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

  const handleSaveEdit = () => {
    const updates = {};
    if (editProp !== node.proposition) updates.proposition = editProp;
    const parsedConf = parseFloat(editConf);
    if (!isNaN(parsedConf) && parsedConf !== node.confidence) updates.confidence = Math.max(0, Math.min(1, parsedConf));
    const newTags = editTags.split(',').map(t => t.trim()).filter(Boolean);
    if (JSON.stringify(newTags) !== JSON.stringify(node.tags || [])) updates.tags = newTags;
    if (Object.keys(updates).length > 0) {
      onEdit(node.id, updates);
    }
    setEditing(false);
  };

  return (
    <div className="inspector">
      <div className="insp-header">
        <Badge type={node.node_type} status={node.status} />
        <span className={`status-dot ${node.status}`} title={node.status} />
        <div className="insp-actions">
          {node.node_type === 'belief' && !editing && (
            <>
              <button className="icon-btn" onClick={() => setEditing(true)} title="Edit">✎</button>
              <button className="icon-btn icon-btn-danger" onClick={() => onDelete(node.id)} title="Delete">✕</button>
            </>
          )}
        </div>
      </div>

      {editing ? (
        <div className="edit-form">
          <div className="field-group">
            <span className="field-label">Proposition</span>
            <textarea className="modal-textarea" value={editProp} onChange={e => setEditProp(e.target.value)} rows={3} />
          </div>
          <div className="field-group">
            <span className="field-label">Confidence (0-1)</span>
            <input className="modal-input" type="number" step="0.01" min="0" max="1" value={editConf} onChange={e => setEditConf(e.target.value)} />
          </div>
          <div className="field-group">
            <span className="field-label">Tags (comma-separated)</span>
            <input className="modal-input" value={editTags} onChange={e => setEditTags(e.target.value)} />
          </div>
          <div className="edit-actions">
            <button className="btn-cancel" onClick={() => setEditing(false)}>Cancel</button>
            <button className="btn-add" onClick={handleSaveEdit}>Save</button>
          </div>
        </div>
      ) : (
        <>
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
        </>
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
            {c.explanation && (
              <p className="conflict-explanation">{c.explanation}</p>
            )}
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
            <div className="conflict-merge" style={{ marginTop: '8px' }}>
              <input 
                type="text" 
                className="modal-input" 
                placeholder="Merge and resolve..." 
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && e.target.value.trim()) {
                    onResolve(c.id, 'merge', e.target.value.trim());
                    e.target.value = '';
                  }
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Hubs panel ────────────────────────────────────────────
function HubsPanel({ beliefs, collapsedHubs, onToggleHub }) {
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

// ── Activity panel ─────────────────────────────────────────
function ActivityPanel({ activity }) {
  return (
    <div className="hubs-list">
      {activity.length === 0 && <p className="empty-state" style={{fontSize:11}}>No recent activity.</p>}
      <div className="trace-list" style={{ padding: '0 8px' }}>
        {activity.map(t => (
          <div key={t.id} className="trace-item">
            <span className="trace-time">{fmt(t.timestamp)}</span>
            <span className="trace-action">{t.action}</span>
            {t.details && <span className="trace-detail">{t.details}</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Add Belief modal ──────────────────────────────────────
function AddBeliefModal({ onClose, onAdd, beliefs, currentScope }) {
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
    const success = await onAdd({ proposition: proposition.trim(), source, evidence: evidence.trim() || null, hubOverride });
    setLoading(false);
    if (success) {
      onClose();
    }
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
  const [health, setHealth]           = useState(null);
  const [selected, setSelected]       = useState(null);
  const [traces, setTraces]           = useState([]);
  const [activity, setActivity]       = useState([]);
  const [collapsedHubs, setCollapsed] = useState(new Set());
  const [activeTab, setActiveTab]     = useState('inspector');
  const [showAdd, setShowAdd]         = useState(false);
  const [consolidating, setConsolidating] = useState(false);
  const [toast, setToast]             = useState(null);
  const [searchResults, setSearchResults] = useState(null);
  const [currentScope, setCurrentScope]   = useState('global');
  const [vaults, setVaults]           = useState([]);

  const showToast = (msg, err = false) => {
    setToast({ msg, err });
    setTimeout(() => setToast(null), 3000);
  };

  const fetchAll = useCallback(async () => {
    try {
      const [bR, cR, sR, vR, hR, aR] = await Promise.all([
        fetch(`${API}/beliefs?scope=${currentScope}`),
        fetch(`${API}/conflicts?scope=${currentScope}`),
        fetch(`${API}/memory/stats?scope=${currentScope}`),
        fetch(`${API}/vaults`),
        fetch(`${API}/memory/health?scope=${currentScope}`),
        fetch(`${API}/traces?scope=${currentScope}&limit=50`),
      ]);
      if (bR.ok) setBeliefs(await bR.json());
      if (cR.ok) setConflicts(await cR.json());
      if (sR.ok) setStats(await sR.json());
      if (vR.ok) setVaults(await vR.json());
      if (hR.ok) setHealth(await hR.json());
      if (aR.ok) {
        const act = await aR.json();
        setActivity(act.traces || []);
      }
    } catch (e) { console.error(e); }
  }, [currentScope]);

  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 6000);
    return () => clearInterval(t);
  }, [fetchAll]);

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
      if (r.ok) setTraces(await r.json());
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
      const r = await fetch(`${API}/memory/consolidate?scope=${currentScope}`, { method: 'POST' });
      if (r.ok) {
        await fetchAll();
        showToast('Consolidation complete');
      } else {
        showToast('Consolidation failed', true);
      }
    } catch { showToast('Consolidation failed', true); }
    finally { setConsolidating(false); }
  };

  const handleResolve = async (cId, resolution, mergeText = null) => {
    try {
      let r;
      if (resolution === 'merge') {
        r = await fetch(`${API}/conflicts/${cId}/merge`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ merged_proposition: mergeText })
        });
      } else {
        r = await fetch(`${API}/conflicts/${cId}/resolve?resolution=${resolution}`, { method: 'POST' });
      }
      
      if (r.ok) {
        setSelected(null);
        await fetchAll();
        showToast('Conflict resolved');
      } else {
        showToast('Failed to resolve', true);
      }
    } catch { showToast('Failed to resolve', true); }
  };

  const handleAddBelief = async ({ proposition, source, evidence, hubOverride }) => {
    try {
      const body = { proposition, source_type: source, evidence, scope: currentScope };
      if (hubOverride && hubOverride !== 'auto' && hubOverride !== '__new__') {
        body.hub_override = hubOverride;
      }
      const r = await fetch(`${API}/beliefs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (r.ok) {
        await fetchAll();
        showToast('Belief added');
        return true;
      } else {
        const err = await r.json().catch(() => ({}));
        showToast(err.detail || 'Failed to add belief', true);
        return false;
      }
    } catch { 
      showToast('Connection failed. Backend may be down or CORS blocked.', true); 
      return false; 
    }
  };

  const handleEditBelief = async (beliefId, updates) => {
    try {
      const r = await fetch(`${API}/beliefs/${beliefId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      if (r.ok) {
        const updated = await r.json();
        setSelected(updated);
        await fetchAll();
        showToast('Belief updated');
      } else {
        showToast('Failed to update', true);
      }
    } catch { showToast('Failed to update', true); }
  };

  const handleDeleteBelief = async (beliefId) => {
    if (!confirm('Delete this belief permanently?')) return;
    try {
      const r = await fetch(`${API}/beliefs/${beliefId}`, { method: 'DELETE' });
      if (r.ok) {
        setSelected(null);
        await fetchAll();
        showToast('Belief deleted');
      } else {
        showToast('Failed to delete', true);
      }
    } catch { showToast('Failed to delete', true); }
  };

  const handleSearch = async (query) => {
    try {
      const r = await fetch(`${API}/search?q=${encodeURIComponent(query)}&scope=${currentScope}`);
      if (r.ok) {
        const results = await r.json();
        setSearchResults(results);
      }
    } catch { showToast('Search failed', true); }
  };

  const handleClearSearch = () => setSearchResults(null);

  const displayBeliefs = searchResults || beliefs;
  const numBeliefs   = stats?.by_type?.belief    ?? 0;
  const numHubs      = stats?.by_type?.hub        ?? 0;
  const numSynthesis = stats?.by_type?.synthesis  ?? 0;
  const numConflicts = stats?.pending_conflicts   ?? 0;

  const handleExport = () => {
    window.open(`${API}/memory/export?scope=${currentScope}`, '_blank');
  };

  const handleImport = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'application/json';
    input.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = async (ev) => {
        try {
          const data = JSON.parse(ev.target.result);
          const r = await fetch(`${API}/memory/import?scope=${currentScope}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
          });
          if (r.ok) {
            await fetchAll();
            showToast('Import successful');
          } else {
            showToast('Import failed', true);
          }
        } catch (err) {
          showToast('Invalid JSON file', true);
        }
      };
      reader.readAsText(file);
    };
    input.click();
  };

  return (
    <div className="app">
      {/* Graph */}
      <div className="graph-wrap">
        <BeliefGraph
          beliefs={displayBeliefs}
          conflicts={conflicts}
          collapsedHubs={collapsedHubs}
          onNodeClick={handleNodeClick}
        />
        {displayBeliefs.length === 0 && !searchResults && (
          <div className="onboarding-overlay">
            <h2>Welcome to Axon Memory</h2>
            <p>Your epistemic graph is currently empty.</p>
            <ol style={{textAlign: 'left', display: 'inline-block', color: 'var(--text-dim)'}}>
              <li>Click the <strong>+</strong> button below to add your first belief.</li>
              <li>Add related beliefs to watch them automatically group into <strong>Hubs</strong>.</li>
              <li>Add contradictory beliefs to test <strong>Auto-Resolution</strong> policies.</li>
            </ol>
          </div>
        )}
        <div className="canvas-hint">
          {searchResults ? `Showing ${searchResults.length} search results` : 'Scroll to zoom · Drag to pan · Click hub to collapse · Click belief to inspect'}
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

        {/* Scope selector */}
        <div className="scope-selector">
          <select
            className="scope-select"
            value={currentScope}
            onChange={e => { setCurrentScope(e.target.value); setSelected(null); setSearchResults(null); }}
          >
            <option value="global">🌐 global</option>
            {vaults.map(v => (
              <option key={v.id} value={v.name}>📦 {v.name} ({v.belief_count})</option>
            ))}
          </select>
        </div>

        {/* Search */}
        <div className="panel-section" style={{ paddingTop: 8, paddingBottom: 8 }}>
          <SearchBar onSearch={handleSearch} onClear={handleClearSearch} />
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
          
          {health && (
            <div className="health-indicators" style={{ marginTop: '12px', padding: '8px', background: '#1e1e1e', borderRadius: '4px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                <span style={{ fontSize: '12px', fontWeight: 'bold' }}>System Health</span>
                <span style={{ 
                  display: 'inline-block', width: '10px', height: '10px', borderRadius: '50%',
                  background: health.status === 'healthy' ? '#10b981' : health.status === 'needs_attention' ? '#f59e0b' : '#ef4444'
                }} title={health.status} />
              </div>
              <div style={{ fontSize: '11px', color: '#9ca3af', display: 'flex', justifyContent: 'space-between' }}>
                <span>Decay Risk: {(health.decay_risk_percent * 100).toFixed(0)}%</span>
                <span>Conflicts: {(health.conflict_ratio * 100).toFixed(0)}%</span>
              </div>
            </div>
          )}

          <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
            <button
              className={`consolidate-btn${consolidating ? ' busy' : ''}`}
              style={{ flex: 1 }}
              onClick={handleConsolidate}
              disabled={consolidating}
            >
              {consolidating ? '↻ Consolidating…' : '↺ Consolidate'}
            </button>
            <button className="consolidate-btn" style={{ flex: 0, padding: '0 8px' }} onClick={handleImport} title="Import">↓</button>
            <button className="consolidate-btn" style={{ flex: 0, padding: '0 8px' }} onClick={handleExport} title="Export">↑</button>
          </div>
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
          <button
            className={`tab-btn ${activeTab === 'activity' ? 'active' : ''}`}
            onClick={() => setActiveTab('activity')}
          >Activity</button>
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
              onEdit={handleEditBelief}
              onDelete={handleDeleteBelief}
            />
          ) : activeTab === 'hubs' ? (
            <HubsPanel
              beliefs={beliefs}
              collapsedHubs={collapsedHubs}
              onToggleHub={handleToggleHub}
            />
          ) : (
            <ActivityPanel activity={activity} />
          )}
        </div>
      </aside>

      {/* Add Belief Modal */}
      {showAdd && (
        <AddBeliefModal
          onClose={() => setShowAdd(false)}
          onAdd={handleAddBelief}
          beliefs={beliefs}
          currentScope={currentScope}
        />
      )}

      {/* Toast */}
      {toast && (
        <div className={`toast ${toast.err ? 'toast-err' : 'toast-ok'}`}>{toast.msg}</div>
      )}
    </div>
  );
}
