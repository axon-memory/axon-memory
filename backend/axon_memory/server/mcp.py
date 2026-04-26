from mcp.server.fastmcp import FastMCP
from ..engine import AxonMemory

mcp = FastMCP("axon-memory")
axon = AxonMemory()

@mcp.tool()
def believe(proposition: str, scope: str = "global", evidence: str = "") -> str:
    """Store a belief in the epistemic memory."""
    belief = axon.believe(proposition=proposition, scope=scope, evidence=evidence, source="agent_inferred")
    return f"Stored belief '{proposition}' with id {belief.id} (Initial confidence: {belief.confidence:.2f})"

@mcp.tool()
def search_beliefs(query: str, scope: str = "global") -> str:
    """Search for relevant beliefs."""
    results = axon.search(query=query, scope=scope, top_k=5)
    formatted = [f"- {b.proposition} (confidence: {b.confidence:.2f})" for b in results]
    return "Beliefs:\n" + "\n".join(formatted) if formatted else "No relevant beliefs found."

def run_mcp():
    mcp.run()

if __name__ == "__main__":
    run_mcp()
