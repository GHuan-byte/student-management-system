"""Application entry point for the Foundation phase."""

from __future__ import annotations

import argparse
import os

from app import create_app


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments independently from app creation."""
    parser = argparse.ArgumentParser(description="Run Student Management System V2")
    parser.add_argument("--host", help="Host to bind the Flask development server")
    parser.add_argument("--port", type=int, help="Port to bind the Flask development server")
    return parser.parse_args()


def resolve_host_port(args: argparse.Namespace) -> tuple[str, int]:
    """Resolve host and port with CLI > environment > defaults precedence."""
    host = args.host or os.environ.get("FLASK_HOST") or "127.0.0.1"
    port_value = args.port or os.environ.get("FLASK_PORT") or 5001
    return host, int(port_value)


def main() -> None:
    """Create and run the Foundation application."""
    args = parse_args()
    host, port = resolve_host_port(args)
    app = create_app()
    app.run(host=host, port=port)


if __name__ == "__main__":
    main()
