"""Cloudflare build: intentionally no-op.

The original project used this module for Railway /data persistence. Cloudflare
Workers uses D1 for durable database state and R2 for durable media, so no local
filesystem bootstrap should run here.
"""
