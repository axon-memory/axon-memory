import json
from mcp.server.fastmcp import FastMCP
from axon_memory.engine import AxonMemory
from mcp.types import Tool, TextContent

mcp = FastMCP("axon-memory")
axon = AxonMemory()

@mcp.tool()
def believe(proposition: str, scope: str = "global", evidence: str = "", fast_mode: bool = False) -> str:
    """Store a belief in the epistemic memory."""
    belief = axon.believe(proposition=proposition, scope=scope, evidence=evidence, source="agent_inferred", fast_mode=fast_mode)
    return f"Stored belief '{proposition}' with id {belief.id} (confidence: {belief.confidence:.2f}, hub: {belief.hierarchy[0] if belief.hierarchy else 'unknown'})"

@mcp.tool()
def search_beliefs(query: str, scope: str = "global", top_k: int = 5, format: str = "text") -> str:
    """Search for relevant beliefs with composite ranking. Excludes hub/system nodes. Format can be 'text' or 'json'."""
    results = axon.search(query=query, scope=scope, top_k=top_k, node_types=['belief', 'synthesis'])
    if not results:
        return "[]" if format == "json" else "No relevant beliefs found."
    
    if format == "json":
        return json.dumps([b.model_dump(mode='json') for b in results])
        
    lines = []
    for b in results:
        conflict_note = " ⚠️ HAS CONFLICTS" if b.conflicts_with else ""
        lines.append(f"- [{b.hierarchy[0] if b.hierarchy else '?'}] {b.proposition} (confidence: {b.confidence:.2f}, importance: {b.importance:.2f}){conflict_note}")
    return "Beliefs:\n" + "\n".join(lines)

@mcp.tool()
def get_belief(belief_id: str) -> str:
    """Retrieve a specific belief by its ID."""
    b = axon.storage.get_belief(belief_id)
    if not b:
        return f"No belief found with id {belief_id}"
    b.confidence = axon._decay_confidence(b)
    return f"Belief: {b.proposition}\nConfidence: {b.confidence:.2f}\nSource: {b.source_type}\nStatus: {b.status}\nHub: {b.hierarchy[0] if b.hierarchy else 'unknown'}\nRelated: {len(b.related_to)} beliefs\nConflicts: {len(b.conflicts_with)} beliefs"

@mcp.tool()
def get_conflicts(scope: str = "global", format: str = "text") -> str:
    """List all pending conflicts that need resolution. Format can be 'text' or 'json'."""
    conflicts = axon.get_conflicts(scope=scope)
    if not conflicts:
        return "[]" if format == "json" else "No pending conflicts."
        
    if format == "json":
        return json.dumps([c.model_dump(mode='json') for c in conflicts])
        
    lines = []
    for c in conflicts:
        a = axon.storage.get_belief(c.belief_a_id)
        b = axon.storage.get_belief(c.belief_b_id)
        explanation = c.explanation or "No explanation"
        lines.append(f"- Conflict {c.id}:\n  A: \"{a.proposition if a else 'unknown'}\"\n  B: \"{b.proposition if b else 'unknown'}\"\n  Why: {explanation}")
    return "Pending Conflicts:\n" + "\n".join(lines)

@mcp.tool()
def resolve_conflict(conflict_id: str, keep: str = "a") -> str:
    """Resolve a conflict by keeping belief A or B. Set keep='a' or keep='b'."""
    resolution = "resolved_a" if keep.lower() == "a" else "resolved_b"
    try:
        axon.resolve_conflict(conflict_id, resolution)
        return f"Conflict {conflict_id} resolved. Kept belief {keep.upper()}."
    except ValueError as e:
        return f"Error: {e}"

@mcp.tool()
def merge_conflict(conflict_id: str, merged_proposition: str) -> str:
    """Resolve a conflict by merging both beliefs into a new one."""
    try:
        merged = axon.merge_conflict(conflict_id, merged_proposition)
        return f"Conflict {conflict_id} resolved. Created new merged belief: '{merged.proposition}' (ID: {merged.id})"
    except ValueError as e:
        return f"Error: {e}"

@mcp.tool()
def retract_belief(belief_id: str) -> str:
    """Retract/delete a belief from memory."""
    success = axon.delete_belief(belief_id)
    if success:
        return f"Belief {belief_id} retracted and deleted."
    return f"Belief {belief_id} not found."

@mcp.tool()
def consolidate_memory(scope: str = "global") -> str:
    """Run memory consolidation: groups beliefs, scans for conflicts, generates synthesis."""
    axon.consolidate(scope=scope)
    return "Memory consolidation complete."

@mcp.tool()
def remember_batch(facts: list, scope: str = "global", fast_mode: bool = False) -> str:
    """Store multiple beliefs at once for efficiency. Pass a list of fact strings."""
    beliefs_data = [{"proposition": f, "source_type": "agent_inferred"} for f in facts]
    results = axon.believe_batch(beliefs_data, scope=scope, fast_mode=fast_mode)
    lines = [f"  ✓ {b.proposition} (hub: {b.hierarchy[0] if b.hierarchy else '?'})" for b in results]
    return f"Stored {len(results)} beliefs:\n" + "\n".join(lines)

@mcp.tool()
def get_usage() -> str:
    """Check LLM usage budget — how many calls remaining this minute."""
    stats = axon.get_usage_stats()
    return (
        f"LLM Usage:\n"
        f"  Calls this minute: {stats['llm_calls_this_minute']}/{stats['max_per_minute']}\n"
        f"  Remaining: {stats['llm_calls_remaining']}\n"
        f"  Total calls: {stats['llm_calls_total']}\n"
        f"  Cache entries: {stats['cache_entries']}"
    )

def run_mcp():
    """Start the MCP server."""
    mcp.run()

if __name__ == "__main__":
    run_mcp()
