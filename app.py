import os
import subprocess

port = os.environ.get("PORT", "7860")

subprocess.run([
    "streamlit",
    "run",
    "frontend/dashboard.py",
    "--server.port",
    port,
    "--server.address",
    "0.0.0.0"
])
