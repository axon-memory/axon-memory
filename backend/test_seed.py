import time
from axon_memory.engine import AxonMemory

def seed():
    axon = AxonMemory()
    print("Seeding database...")
    
    # 1. User explicit
    b1 = axon.believe(
        proposition="User prefers dark mode",
        source="user_explicit",
        evidence="User clicked 'Always use dark mode' in settings.",
        confidence=1.0,
        tags=["ui", "preference"]
    )
    
    # 2. Agent inferred (slightly lower confidence, decays faster)
    b2 = axon.believe(
        proposition="User is currently working on a Python backend",
        source="agent_inferred",
        evidence="Observed multiple python files being created.",
        confidence=0.8,
        half_life_hrs=48.0,
        tags=["project"]
    )
    
    # 3. Create a conflict artificially
    # First belief
    b3 = axon.believe(
        proposition="The default database is PostgreSQL",
        source="agent_inferred",
        evidence="Found a pg connector string in old config.",
        confidence=0.6,
        tags=["architecture"]
    )
    
    # Second belief that conflicts
    b4 = axon.believe(
        proposition="The default database is SQLite",
        source="user_explicit",
        evidence="User explicitly requested SQLite in the prompt.",
        confidence=1.0,
        tags=["architecture"]
    )
    
    print("Database seeded with sample beliefs and conflicts.")

if __name__ == "__main__":
    seed()
