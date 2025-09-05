import click
import getpass
import re
from pathlib import Path
from rich.console import Console
from rich.table import Table
from .config import Config
from .confluence_client import ConfluenceClient
from .sync import SyncManager

console = Console()


@click.group()
@click.option('--config', '-c', type=click.Path(exists=True, path_type=Path), 
              help='Path to configuration file')
@click.pass_context
def cli(ctx, config):
    """Confluence Sync - Sync Confluence pages with local markdown files"""
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config


def validate_url(url: str) -> str:
    """Validate and normalize Confluence URL"""
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    
    if not re.match(r'https?://[a-zA-Z0-9.-]+\.atlassian\.net/?$', url):
        raise click.BadParameter("URL must be a valid Atlassian domain (e.g., mycompany.atlassian.net)")
    
    return url.rstrip('/')


def validate_space_key(space_key: str) -> str:
    """Validate space key format"""
    if not re.match(r'^[A-Z0-9_]+$', space_key.upper()):
        raise click.BadParameter("Space key must contain only letters, numbers, and underscores")
    
    return space_key.upper()


@cli.command()
@click.option('--non-interactive', is_flag=True, help='Create template file instead of interactive setup')
@click.pass_context
def init(ctx, non_interactive):
    """Initialize a new confluence-sync configuration"""
    config_path = ctx.obj.get('config_path') or Path('confluence-sync.yml')
    
    if config_path.exists():
        console.print(f"[yellow]Configuration file already exists: {config_path}[/yellow]")
        if not click.confirm("Overwrite existing configuration?"):
            return
    
    config = Config(config_path)
    
    if non_interactive:
        config.save_template()
        console.print(f"[green]Created configuration template: {config_path}[/green]")
        console.print("\nPlease edit the configuration file with your Confluence details:")
        console.print(f"  • Confluence URL")
        console.print(f"  • API Token")
        console.print(f"  • Space Key")
        return
    
    # Interactive setup
    console.print("[bold blue]🔧 Confluence Sync Setup[/bold blue]")
    console.print("=" * 24)
    console.print()
    
    # Get Confluence domain
    while True:
        try:
            url = click.prompt("Enter your Confluence domain (e.g., mycompany.atlassian.net)")
            url = validate_url(url)
            break
        except click.BadParameter as e:
            console.print(f"[red]Error: {e}[/red]")
    
    # Get API token
    api_token = getpass.getpass("Enter your API token/PAT (will be hidden): ")
    if not api_token:
        console.print("[red]API token cannot be empty[/red]")
        return
    
    # Test connection
    console.print()
    with console.status("[yellow]Testing connection...[/yellow]"):
        try:
            client = ConfluenceClient(url, api_token)
            if not client.test_connection():
                console.print("[red]❌ Connection failed. Please check your URL and API token.[/red]")
                return
        except Exception as e:
            console.print(f"[red]❌ Connection failed: {e}[/red]")
            return
    
    console.print("[green]✅ Connected successfully![/green]")
    console.print()
    
    # Space selection
    console.print("How would you like to select your space?")
    console.print("  1) Enter a specific space key")
    console.print("  2) Browse available spaces")
    console.print()
    
    choice = click.prompt("Selection", type=click.Choice(['1', '2']), default='1')
    
    space_key = None
    if choice == '1':
        # Manual space key entry
        while True:
            try:
                space_key = click.prompt("Enter the space key")
                space_key = validate_space_key(space_key)
                
                # Validate space exists
                space_info = client.get_space_info(space_key)
                if space_info:
                    console.print(f"[green]✅ Found space: \"{space_info['name']}\" ({space_key})[/green]")
                    break
                else:
                    console.print(f"[red]Space '{space_key}' not found or not accessible[/red]")
                    if not click.confirm("Try a different space key?"):
                        return
            except click.BadParameter as e:
                console.print(f"[red]Error: {e}[/red]")
    
    elif choice == '2':
        # Browse available spaces
        console.print()
        with console.status("[yellow]Loading spaces...[/yellow]"):
            spaces = client.get_user_spaces()
        
        if not spaces:
            console.print("[red]No spaces found or unable to retrieve spaces[/red]")
            console.print("Falling back to manual entry...")
            space_key = click.prompt("Enter the space key")
            space_key = validate_space_key(space_key)
        else:
            console.print(f"[bold]📁 Available spaces:[/bold]")
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("#", style="dim", width=3)
            table.add_column("Key", style="cyan")
            table.add_column("Name", style="green")
            
            for i, space in enumerate(spaces[:20], 1):  # Limit to 20 spaces
                table.add_row(str(i), space['key'], space['name'])
            
            console.print(table)
            console.print()
            
            if len(spaces) > 20:
                console.print(f"[dim]Showing first 20 of {len(spaces)} spaces[/dim]")
            
            while True:
                try:
                    selection = click.prompt(f"Select a space (1-{min(len(spaces), 20)})", type=int)
                    if 1 <= selection <= min(len(spaces), 20):
                        space_key = spaces[selection - 1]['key']
                        console.print(f"[green]✅ Selected: \"{spaces[selection - 1]['name']}\" ({space_key})[/green]")
                        break
                    else:
                        console.print(f"[red]Please enter a number between 1 and {min(len(spaces), 20)}[/red]")
                except (ValueError, click.BadParameter):
                    console.print("[red]Please enter a valid number[/red]")
    
    # Local directory setup
    console.print()
    console.print("[bold]📂 Local Setup[/bold]")
    console.print("=" * 13)
    
    default_path = "docs"
    local_path = click.prompt("Local directory for markdown files", default=default_path)
    
    # Create directory if it doesn't exist
    local_dir = Path(local_path)
    if not local_dir.exists():
        if click.confirm(f"Create directory '{local_path}'?", default=True):
            local_dir.mkdir(parents=True, exist_ok=True)
            console.print(f"[green]✅ Created directory: {local_path}[/green]")
    
    # Configuration summary
    console.print()
    console.print("[bold]📝 Configuration Summary[/bold]")
    console.print("=" * 22)
    console.print(f"Confluence URL: {url}")
    console.print(f"Space: {space_key}")
    console.print(f"Local Path: {local_path}")
    console.print(f"Config File: {config_path}")
    console.print()
    
    if click.confirm("Save configuration?", default=True):
        config.save_interactive_config(url, api_token, space_key, local_path)
        console.print(f"[green]✅ Configuration saved to {config_path}[/green]")
        console.print()
        console.print("[bold]Next steps:[/bold]")
        console.print("  • Run [cyan]confluence-sync pull[/cyan] to download pages")
        console.print("  • Run [cyan]confluence-sync status[/cyan] to see sync status")
    else:
        console.print("[yellow]Configuration not saved[/yellow]")


@cli.command()
@click.pass_context
def pull(ctx):
    """Pull pages from Confluence to local markdown files"""
    try:
        config = Config(ctx.obj.get('config_path')).load()
        sync_manager = SyncManager(config)
        sync_manager.pull()
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("Run 'confluence-sync init' to create a configuration file.")
    except Exception as e:
        console.print(f"[red]Error during pull: {e}[/red]")


@cli.command()
@click.argument('files', nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.pass_context
def push(ctx, files):
    """Push local markdown files to Confluence"""
    try:
        config = Config(ctx.obj.get('config_path')).load()
        sync_manager = SyncManager(config)
        
        file_paths = list(files) if files else None
        sync_manager.push(file_paths)
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("Run 'confluence-sync init' to create a configuration file.")
    except Exception as e:
        console.print(f"[red]Error during push: {e}[/red]")


@cli.command()
@click.pass_context
def status(ctx):
    """Show sync status of local files"""
    try:
        config = Config(ctx.obj.get('config_path')).load()
        sync_manager = SyncManager(config)
        sync_manager.status()
    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("Run 'confluence-sync init' to create a configuration file.")
    except Exception as e:
        console.print(f"[red]Error getting status: {e}[/red]")


if __name__ == '__main__':
    cli()