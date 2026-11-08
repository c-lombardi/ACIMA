# acima-unit: orders.contracts
"""Violation L002: a contract exposing a transport type."""
from http.server import BaseHTTPRequestHandler


class OrderEndpoint(BaseHTTPRequestHandler):
    """A contract type that can only be produced by an HTTP server."""

    def do_GET(self) -> None:
        """Not a contract; a delivery mechanism wearing one."""
