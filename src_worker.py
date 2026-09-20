from app import app
from workers import wsgi

# Flask is executed through Cloudflare's WSGI adapter.
Default = wsgi.entrypoint(app)
