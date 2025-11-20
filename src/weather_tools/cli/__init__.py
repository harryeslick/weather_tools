"""Command-line interface for weather_tools."""

import typer

from weather_tools import __version__
from weather_tools.cli.geotiff import geotiff_app
from weather_tools.cli.local import local_app
from weather_tools.cli.metno import metno_app
from weather_tools.cli.silo import silo_app
from weather_tools.logging_utils import configure_logging


def version_callback(value: bool):
    """Print version and exit."""
    if value:
        typer.echo(f"weather-tools version {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="weather-tools",
    help="CLI tool for extracting weather data from SILO datasets (local netCDF files or API)",
    no_args_is_help=True,
)


@app.callback()
def main_callback(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
):
    """Main callback to handle global options."""
    pass


# Register subapps
app.add_typer(silo_app, name="silo")
app.add_typer(local_app, name="local")
app.add_typer(metno_app, name="metno")
app.add_typer(geotiff_app, name="geotiff")


def main():
    """Entry point for the CLI."""
    configure_logging()
    app()


if __name__ == "__main__":
    main()
