"""Centralized error handling. Every error response — validation, auth,
not-found, rate-limit, or an unhandled exception — comes back in the same
shape: {"error": "human message", "code": "MACHINE_CODE"}."""
import logging
from flask import jsonify
from werkzeug.exceptions import HTTPException

logger = logging.getLogger('platform')


class ApiError(Exception):
    status_code = 400
    code = 'BAD_REQUEST'

    def __init__(self, message, status_code=None, code=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code


class ValidationError(ApiError):
    status_code = 400
    code = 'VALIDATION_ERROR'


class NotFoundError(ApiError):
    status_code = 404
    code = 'NOT_FOUND'


class ConflictError(ApiError):
    status_code = 409
    code = 'CONFLICT'


class AuthError(ApiError):
    status_code = 401
    code = 'UNAUTHORIZED'


class ForbiddenError(ApiError):
    status_code = 403
    code = 'FORBIDDEN'


class TrialExpiredError(ApiError):
    status_code = 402
    code = 'TRIAL_EXPIRED'


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def handle_api_error(err):
        return jsonify({'error': err.message, 'code': err.code}), err.status_code

    @app.errorhandler(HTTPException)
    def handle_http_error(err):
        # Covers Flask/Werkzeug-raised errors (404 on unknown route, 405, etc.)
        # and, notably, Flask-Limiter's 429s.
        code = {
            404: 'NOT_FOUND', 405: 'METHOD_NOT_ALLOWED', 429: 'RATE_LIMITED',
        }.get(err.code, 'HTTP_ERROR')
        return jsonify({'error': err.description or err.name, 'code': code}), err.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(err):
        logger.exception('Unhandled exception')
        return jsonify({'error': 'An unexpected error occurred.', 'code': 'INTERNAL_ERROR'}), 500


def configure_logging(app):
    import os
    from logging.handlers import RotatingFileHandler
    from config import Config

    os.makedirs(Config.LOG_DIR, exist_ok=True)
    level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)

    logger.setLevel(level)
    if not logger.handlers:
        file_handler = RotatingFileHandler(
            os.path.join(Config.LOG_DIR, 'platform.log'), maxBytes=2_000_000, backupCount=5
        )
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    @app.before_request
    def _start_timer():
        from flask import g
        import time
        g._request_start = time.time()

    @app.after_request
    def _log_request(response):
        from flask import g, request
        import time
        duration_ms = int((time.time() - getattr(g, '_request_start', time.time())) * 1000)
        logger.info(f'{request.method} {request.path} -> {response.status_code} ({duration_ms}ms)')
        return response

    return logger
