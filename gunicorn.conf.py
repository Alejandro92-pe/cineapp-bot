"""Render's single web process; multiple threads leave room for playback and imports."""
import os

bind = '0.0.0.0:' + os.getenv('PORT', '10000')
workers = 1
threads = 4
timeout = 120
graceful_timeout = 30
accesslog = None  # Never log token-based legacy Telegram webhook paths.
errorlog = '-'
