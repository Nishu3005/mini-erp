"""Entrypoint: create the app and run the dev server."""
import os

from app import create_app

app = create_app(os.environ.get("FLASK_CONFIG", "dev"))

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
