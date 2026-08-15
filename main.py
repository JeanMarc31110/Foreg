import os
import threading
import time
import webbrowser
import uvicorn
from dotenv import load_dotenv

load_dotenv()

def open_browser():
    time.sleep(1.2)
    port = int(os.getenv("FORGE_PORT", "8765"))
    webbrowser.open(f"http://127.0.0.1:{port}")

if __name__ == "__main__":
    key = os.getenv("OPENAI_API_KEY", "")
    if not key or key.startswith("sk-votre"):
        print("\nERREUR : configurez OPENAI_API_KEY dans le fichier .env\n")
        input("Appuyez sur Entree pour fermer...")
        raise SystemExit(1)

    host = os.getenv("FORGE_HOST", "127.0.0.1")
    port = int(os.getenv("FORGE_PORT", "8765"))
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("forge.web:app", host=host, port=port, reload=False)
