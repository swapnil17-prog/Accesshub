"""WSGI entrypoint for `flask run` (FLASK_APP=wsgi.py) and Gunicorn (`wsgi:app`)."""

from dotenv import load_dotenv

load_dotenv()

from app import create_app  # noqa: E402  (env must be loaded before config import)

app = create_app()
