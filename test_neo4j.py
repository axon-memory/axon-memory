import os
import time
from backend.axon_memory.neo4j_storage import Neo4jStorageLayer
from backend.axon_memory.models import Belief

# Wait for Neo4j to be ready
print("Waiting for neo4j to start...")
time.sleep(10)

storage = Neo4jStorageLayer()
b = Belief(proposition="The sky is blue", source_type="user_explicit")
emb = [0.1] * 768

print("Saving belief...")
storage.save_belief(b, emb)

print("Fetching belief...")
fetched = storage.get_belief(b.id)
print(f"Fetched: {fetched.proposition}, Tags: {fetched.tags}")

storage.close()
print("Success!")
