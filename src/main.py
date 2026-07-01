import argparse
from client.tui.tui import RagaTUI
import sys
import uvicorn

def start_server():
    uvicorn.run(
        "gateway.server:app",
        host="127.0.0.1", 
        port=8000, 
        reload=True
    )


def start_tui():
    app = RagaTUI()
    app.run()


def main():
    parser = argparse.ArgumentParser(
        description="Raga - Adaptive agent."
    )

    subparsers = parser.add_subparsers(
        dest="command", help="Available commands"
    )

    subparsers.add_parser("serve", help="Starts the agent server")

    subparsers.add_parser("tui", help="Launches the terminal interface")

    args = parser.parse_args()

    if args.command == "serve":
        start_server()
    elif args.command == "tui":
        start_tui()
    else:
        parser.print_help()
        sys.exit(1)