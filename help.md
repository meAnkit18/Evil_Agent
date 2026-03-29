### Developer Help notes

# Create requirements.txt
Whenever you install something:
'''pip freeze > requirements.txt'''


# ⚠️ If using Docker (IMPORTANT)

Change this line:

const ws = new WebSocket("ws://localhost:8000/ws");

👉 to:

const ws = new WebSocket("ws://backend:8000/ws");

## Later Build
1. auto-learning agent (no manual memory calls)
2. skill extraction system
3. reflection loop (agent improves itself)