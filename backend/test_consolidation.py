from axon_memory.engine import AxonMemory
import logging

logging.basicConfig(level=logging.INFO)

def test_consolidation():
    axon = AxonMemory()
    print("--- Starting Consolidation ---")
    axon.consolidate(scope="global")
    print("--- Consolidation Complete ---")
    
    # Check stats
    import requests
    try:
        # Note: API needs to be running. If not, we check DB directly.
        # Let's check DB directly via storage.
        beliefs = axon.get_beliefs()
        synthesis_nodes = [b for b in beliefs if b.node_type == "synthesis"]
        print(f"Total Synthesis Nodes: {len(synthesis_nodes)}")
        for sn in synthesis_nodes:
            print(f"Synthesis ID: {sn.id}")
            print(f"Synthesis Text: {sn.proposition}")
            print(f"Summarizes: {sn.synthesis_of}")
    except Exception as e:
        print(f"Error checking results: {e}")

if __name__ == "__main__":
    test_consolidation()
