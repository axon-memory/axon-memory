"""
Axon Memory Agent Demo
======================
A ReAct agent using Gemini function calling that demonstrates what it's like
for an AI agent to use Axon Memory as its persistent epistemic memory layer.

This agent simulates a coding assistant that:
1. Recalls past knowledge before answering
2. Stores new facts it learns
3. Detects and surfaces conflicts
4. Uses consolidation to synthesize knowledge
4. Uses consolidation to synthesize knowledge

Run with: uv run python agent_demo.py
Requires: backend API running on localhost:8000
"""

import os
import json
import time
import httpx
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

AXON_API = "http://localhost:8000"
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
http = httpx.Client(timeout=30)

# ── Tool Definitions (Axon Memory API as function declarations) ──────────

axon_tools = [
    types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="remember",
            description="Store a new belief/fact in long-term memory. Use this whenever you learn something new about the user's project, preferences, or technical decisions.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "proposition": types.Schema(type="STRING", description="The fact to remember, stated clearly as a proposition"),
                    "evidence": types.Schema(type="STRING", description="Why you believe this — what evidence supports it"),
                    "source": types.Schema(type="STRING", description="One of: user_explicit, agent_inferred, tool_result", enum=["user_explicit", "agent_inferred", "tool_result"]),
                },
                required=["proposition", "evidence", "source"],
            ),
        ),
        types.FunctionDeclaration(
            name="recall",
            description="Search long-term memory for relevant facts about a topic. Always do this before answering questions about the user's project.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "query": types.Schema(type="STRING", description="What to search for in memory"),
                },
                required=["query"],
            ),
        ),
        types.FunctionDeclaration(
            name="check_conflicts",
            description="Check if there are any unresolved contradictions in memory that need human review.",
            parameters=types.Schema(
                type="OBJECT",
                properties={},
            ),
        ),
        types.FunctionDeclaration(
            name="resolve_conflict",
            description="Resolve a contradiction in memory by choosing which belief to keep.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "conflict_id": types.Schema(type="STRING", description="The ID of the conflict to resolve"),
                    "keep": types.Schema(type="STRING", description="Which belief to keep: 'a' or 'b'"),
                },
                required=["conflict_id", "keep"],
            ),
        ),
        types.FunctionDeclaration(
            name="consolidate",
            description="Consolidate memory — synthesize related facts and scan for contradictions. Do this periodically.",
            parameters=types.Schema(
                type="OBJECT",
                properties={},
            ),
        ),
        types.FunctionDeclaration(
            name="get_memory_stats",
            description="Get an overview of the current state of memory — how many facts, conflicts, synthesis nodes.",
            parameters=types.Schema(
                type="OBJECT",
                properties={},
            ),
        ),
    ])
]

# ── Tool Execution (calls Axon Memory API) ───────────────────────────────

def execute_tool(name: str, args: dict) -> str:
    """Execute an Axon Memory tool call via the REST API."""
    try:
        if name == "remember":
            r = http.post(f"{AXON_API}/beliefs", json={
                "proposition": args["proposition"],
                "source_type": args.get("source", "agent_inferred"),
                "evidence": args.get("evidence", ""),
            })
            if r.status_code == 200:
                belief = r.json()
                return f"✓ Stored: \"{belief['proposition']}\"\n  ID: {belief['id']}\n  Confidence: {belief['confidence']:.0%}\n  Hub: {belief['hierarchy'][0] if belief.get('hierarchy') else 'unknown'}\n  Importance: {belief.get('importance', 0.5):.0%}"
            return f"✗ Failed to store: {r.text}"

        elif name == "recall":
            r = http.get(f"{AXON_API}/search", params={"q": args["query"], "top_k": 5})
            if r.status_code == 200:
                beliefs = r.json()
                if not beliefs:
                    return "No relevant memories found."
                lines = []
                for b in beliefs:
                    conflict_flag = " ⚠️ CONFLICTED" if b.get("conflicts_with") else ""
                    lines.append(
                        f"• [{b['hierarchy'][0] if b.get('hierarchy') else '?'}] "
                        f"\"{b['proposition']}\" "
                        f"(confidence: {b['confidence']:.0%}, "
                        f"importance: {b.get('importance', 0.5):.0%}, "
                        f"source: {b['source_type']})"
                        f"{conflict_flag}"
                    )
                return "Memories found:\n" + "\n".join(lines)
            return f"Search failed: {r.text}"

        elif name == "check_conflicts":
            r = http.get(f"{AXON_API}/conflicts")
            if r.status_code == 200:
                conflicts = r.json()
                if not conflicts:
                    return "No unresolved conflicts in memory. Knowledge base is consistent."
                lines = []
                for c in conflicts:
                    # Fetch both beliefs to show what conflicts
                    a = http.get(f"{AXON_API}/beliefs/{c['belief_a_id']}").json()
                    b = http.get(f"{AXON_API}/beliefs/{c['belief_b_id']}").json()
                    explanation = c.get("explanation", "No explanation")
                    lines.append(
                        f"⊘ Conflict {c['id']}:\n"
                        f"  A: \"{a['proposition']}\" (confidence: {a['confidence']:.0%})\n"
                        f"  B: \"{b['proposition']}\" (confidence: {b['confidence']:.0%})\n"
                        f"  Why: {explanation}"
                    )
                return f"{len(conflicts)} unresolved conflict(s):\n" + "\n".join(lines)
            return f"Failed to check conflicts: {r.text}"

        elif name == "resolve_conflict":
            resolution = "resolved_a" if args["keep"].lower() == "a" else "resolved_b"
            r = http.post(f"{AXON_API}/conflicts/{args['conflict_id']}/resolve", params={"resolution": resolution})
            if r.status_code == 200:
                return f"✓ Conflict resolved. Kept belief {args['keep'].upper()}."
            return f"✗ Failed to resolve: {r.text}"

        elif name == "consolidate":
            r = http.post(f"{AXON_API}/memory/consolidate")
            if r.status_code == 200:
                return "✓ Memory consolidated. Synthesis nodes updated and contradiction scan complete."
            return f"✗ Consolidation failed: {r.text}"

        elif name == "get_memory_stats":
            r = http.get(f"{AXON_API}/memory/stats")
            if r.status_code == 200:
                s = r.json()
                return (
                    f"Memory Status:\n"
                    f"  Total nodes: {s['total_nodes']}\n"
                    f"  Beliefs: {s['by_type'].get('belief', 0)}\n"
                    f"  Hubs: {s['by_type'].get('hub', 0)}\n"
                    f"  Synthesis: {s['by_type'].get('synthesis', 0)}\n"
                    f"  Pending conflicts: {s.get('pending_conflicts', 0)}\n"
                    f"  Health score: {s['health_score']:.0%}"
                )
            return f"Failed to get stats: {r.text}"

        return f"Unknown tool: {name}"
    except Exception as e:
        return f"Tool error: {e}"


# ── Agent Loop ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a coding assistant with persistent long-term memory powered by Axon Memory.

YOUR MEMORY WORKFLOW:
1. When the user asks about their project, ALWAYS use `recall` first to check what you already know.
2. When you learn new facts, use `remember` to store them.
3. Periodically use `check_conflicts` to surface contradictions.
4. When conflicts exist, present them to the user and use `resolve_conflict` based on their response.
5. Use `consolidate` when the conversation covers many topics.

IMPORTANT BEHAVIORS:
- You have persistent memory that survives across conversations.
- Always check memory before making claims about the user's project.
- Store important decisions, preferences, and architectural facts.
- When you detect a conflict, proactively tell the user about it.
- Be transparent about what you remember vs. what you're inferring.

You are having a natural conversation with the user. Use your tools naturally, not mechanically."""


def run_agent(user_messages: list[str]):
    """Run the agent through a sequence of user messages, simulating a conversation."""
    
    history = []
    
    print("=" * 70)
    print("  AXON MEMORY AGENT DEMO")
    print("  Simulating a coding assistant with persistent epistemic memory")
    print("=" * 70)
    
    for i, user_msg in enumerate(user_messages):
        print(f"\n{'─' * 70}")
        print(f"  USER [{i+1}/{len(user_messages)}]: {user_msg}")
        print(f"{'─' * 70}")
        
        history.append(types.Content(
            role="user",
            parts=[types.Part(text=user_msg)]
        ))
        
        # Agent loop — keep going until the model stops calling tools
        max_turns = 8
        for turn in range(max_turns):
            # Retry with backoff for rate limits
            for attempt in range(4):
                try:
                    response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=history,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_PROMPT,
                            tools=axon_tools,
                            temperature=0.3,
                        ),
                    )
                    break
                except Exception as e:
                    if "429" in str(e) and attempt < 3:
                        wait = 15 * (attempt + 1)
                        print(f"  ⏳ Rate limited, waiting {wait}s...")
                        time.sleep(wait)
                    else:
                        print(f"  ✗ API error: {e}")
                        break
            else:
                print("  ✗ Max retries exceeded, skipping.")
                break
            
            candidate = response.candidates[0]
            
            # Check if the model wants to call tools
            has_function_calls = False
            tool_results = []
            
            for part in candidate.content.parts:
                if part.function_call:
                    has_function_calls = True
                    fn = part.function_call
                    args = dict(fn.args) if fn.args else {}
                    
                    print(f"\n  🔧 TOOL: {fn.name}({json.dumps(args, indent=2) if args else ''})")
                    
                    result = execute_tool(fn.name, args)
                    print(f"  📋 RESULT:\n  {result.replace(chr(10), chr(10) + '  ')}")
                    
                    tool_results.append(types.Part(
                        function_response=types.FunctionResponse(
                            name=fn.name,
                            response={"result": result}
                        )
                    ))
            
            # Add model response to history
            history.append(candidate.content)
            
            if has_function_calls:
                # Add tool results and continue the loop
                history.append(types.Content(
                    role="user",
                    parts=tool_results
                ))
            else:
                # Model gave a text response — print it and move on
                text = candidate.content.parts[0].text if candidate.content.parts else ""
                print(f"\n  🤖 AGENT: {text}")
                break
    
    print(f"\n{'=' * 70}")
    print("  DEMO COMPLETE")
    print(f"{'=' * 70}")


# ── Demo Scenario ────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Simulate a realistic multi-turn conversation where the agent
    # builds up knowledge, encounters conflicts, and manages memory
    
    scenario = [
        # Turn 1: User provides project context — agent should store these facts
        "I'm working on a web app. The backend uses FastAPI and the database is PostgreSQL.",
        
        # Turn 2: User asks about knowledge — agent should recall
        "What do you know about my project?",
        
        # Turn 3: Conflicting fact — agent should store and detect conflict
        "Actually we switched to SQLite. Check for any conflicts in your memory.",
    ]
    
    run_agent(scenario)
