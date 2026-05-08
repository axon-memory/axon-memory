from mcp.server.fastmcp import FastMCP
from axon_memory.engine import AxonMemory
from mcp.types import Tool, TextContent

mcp = FastMCP("axon-memory")
axon = AxonMemory()

@mcp.tool()
def believe(proposition: str, scope: str = "global", evidence: str = "") -> str:
    """
    Store a belief in the epistemic memory.

    Parameters
    ----------
    proposition : str
        The textual proposition of the belief.
    scope : str, optional
        The scope of the belief (default is "global").
    evidence : str, optional
        Evidence supporting the belief (default is empty string).

    Returns
    -------
    str
        A message indicating the successful storage and initial confidence.
    """
    belief = axon.believe(proposition=proposition, scope=scope, evidence=evidence, source="agent_inferred")
    return f"Stored belief '{proposition}' with id {belief.id} (Initial confidence: {belief.confidence:.2f})"

@mcp.tool()
def search_beliefs(query: str, scope: str = "global") -> str:
    """
    Search for relevant beliefs.

    Parameters
    ----------
    query : str
        The search query.
    scope : str, optional
        The scope to restrict the search to (default is "global").

    Returns
    -------
    str
        A formatted string of relevant beliefs or a message if none found.
    """
    results = axon.search(query=query, scope=scope, top_k=5)
    formatted = [f"- {b.proposition} (confidence: {b.confidence:.2f})" for b in results]
    return "Beliefs:\n" + "\n".join(formatted) if formatted else "No relevant beliefs found."

@mcp.tool()
def consolidate_memory(scope: str = "global") -> str:
    """
    Performs periodic memory consolidation: groups beliefs, generates synthesis nodes, and identifies contradictions.

    Parameters
    ----------
    scope : str, optional
        The scope of memories to consolidate (default is "global").

    Returns
    -------
    str
        A message indicating consolidation is complete.
    """
    axon.consolidate(scope=scope)
    return "Memory consolidation complete."

def run_mcp():
    """
    Start the MCP server.
    """
    mcp.run()

if __name__ == "__main__":
    run_mcp()
