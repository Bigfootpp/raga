import typer
import uvicorn

from client.tui.tui import TUI

app = typer.Typer(
    name="raga",
    help="Raga - Adaptive agent.",
    add_completion=False
)

@app.command(help="Start the agent server")
def serve():
    uvicorn.run(
        "gateway.server:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )

@app.command(help="Launch the terminal interface")
def tui():
    app = TUI()
    app.run()

# TODO: Implement raga setup command to init .raga/config.toml with base_url, api_key, models and auto_fetch
def main():
    app()