import argparse
from client.tui.tui import RagaTUI
import sys

def start_server():
    print("Starting Raga server...")


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

    subparsers.add_parser(
        "serve", help="Starts the agent server"
    )

    subparsers.add_parser("tui", help="Launches the terminal interface")

    args = parser.parse_args()

    if args.command == "serve":
        start_server()
    elif args.command == "tui":
        start_tui()
    else:
        parser.print_help()
        sys.exit(1)