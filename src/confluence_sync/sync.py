import json
from pathlib import Path
from typing import Dict, List, Set, Optional
from rich.console import Console
from rich.progress import track
from .confluence_client import ConfluenceClient, PageInfo
from .config import SyncConfig

console = Console()


class MetadataStore:
    def __init__(self, store_path: Path):
        self.store_path = store_path
        self._metadata: Dict[str, Dict] = {}
    
    def load(self) -> None:
        if self.store_path.exists():
            with open(self.store_path) as f:
                self._metadata = json.load(f)
    
    def save(self) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.store_path, 'w') as f:
            json.dump(self._metadata, f, indent=2)
    
    def get_page_metadata(self, page_id: str) -> Optional[Dict]:
        return self._metadata.get(page_id)
    
    def set_page_metadata(self, page_id: str, title: str, version: int, file_path: str) -> None:
        self._metadata[page_id] = {
            'title': title,
            'version': version,
            'file_path': file_path
        }
    
    def remove_page(self, page_id: str) -> None:
        self._metadata.pop(page_id, None)
    
    def get_all_pages(self) -> Dict[str, Dict]:
        return self._metadata.copy()


class SyncManager:
    def __init__(self, config: SyncConfig):
        self.config = config
        self.client = ConfluenceClient(
            url=config.confluence.url,
            api_token=config.confluence.api_token
        )
        self.metadata_store = MetadataStore(config.local_path / '.confluence-sync' / 'metadata.json')
        self.metadata_store.load()
    
    def pull(self) -> None:
        """Pull all pages from Confluence space to local markdown files"""
        console.print(f"[blue]Pulling pages from space: {self.config.confluence.space_key}[/blue]")
        
        # Get all pages from the space
        pages = self.client.get_space_pages(self.config.confluence.space_key)
        
        console.print(f"Found {len(pages)} pages to sync")
        
        for page_data in track(pages, description="Syncing pages..."):
            page_info = self.client.get_page_content(page_data['id'])
            self._save_page_locally(page_info)
        
        self.metadata_store.save()
        console.print("[green]Pull completed successfully![/green]")
    
    def push(self, file_paths: Optional[List[Path]] = None) -> None:
        """Push local changes to Confluence with version conflict detection"""
        console.print("[blue]Pushing local changes to Confluence[/blue]")
        
        if file_paths is None:
            # Push all tracked files
            file_paths = self._get_all_tracked_files()
        
        conflicts = []
        successful_pushes = []
        
        for file_path in track(file_paths, description="Pushing files..."):
            try:
                if self._push_file(file_path):
                    successful_pushes.append(file_path)
            except ValueError as e:
                if "Version conflict" in str(e):
                    conflicts.append((file_path, str(e)))
                    console.print(f"[red]Version conflict for {file_path}: {e}[/red]")
                else:
                    console.print(f"[red]Error pushing {file_path}: {e}[/red]")
        
        if conflicts:
            console.print(f"\n[yellow]Push completed with {len(conflicts)} conflicts:[/yellow]")
            for file_path, error in conflicts:
                console.print(f"  • {file_path}: {error}")
            console.print("\n[yellow]Run 'pull' to sync remote changes before pushing again.[/yellow]")
        else:
            console.print(f"[green]Push completed successfully! Updated {len(successful_pushes)} pages.[/green]")
        
        self.metadata_store.save()
    
    def status(self) -> None:
        """Show sync status of local files"""
        console.print("[blue]Sync Status[/blue]")
        
        local_files = self._get_all_local_files()
        metadata = self.metadata_store.get_all_pages()
        
        # Files that exist locally but not in metadata (new files)
        new_files = []
        # Files that have been modified locally
        modified_files = []
        # Files that exist in metadata but not locally (deleted files)
        deleted_files = []
        
        for file_path in local_files:
            page_id = self._get_page_id_from_file(file_path)
            if page_id and page_id in metadata:
                # Check if file has been modified
                if self._is_file_modified(file_path, metadata[page_id]):
                    modified_files.append(file_path)
            else:
                new_files.append(file_path)
        
        # Check for deleted files
        for page_id, meta in metadata.items():
            file_path = Path(meta['file_path'])
            if not file_path.exists():
                deleted_files.append(file_path)
        
        if new_files:
            console.print(f"\n[green]New files ({len(new_files)}):[/green]")
            for f in new_files:
                console.print(f"  + {f}")
        
        if modified_files:
            console.print(f"\n[yellow]Modified files ({len(modified_files)}):[/yellow]")
            for f in modified_files:
                console.print(f"  M {f}")
        
        if deleted_files:
            console.print(f"\n[red]Deleted files ({len(deleted_files)}):[/red]")
            for f in deleted_files:
                console.print(f"  - {f}")
        
        if not new_files and not modified_files and not deleted_files:
            console.print("\n[green]Everything is up to date![/green]")
    
    def _save_page_locally(self, page_info: PageInfo) -> None:
        """Save a page to a local markdown file"""
        # Create safe filename from title
        safe_filename = self._sanitize_filename(page_info.title)
        file_path = self.config.local_path / f"{safe_filename}.md"
        
        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Add metadata header to the file
        content = self._create_file_content(page_info)
        
        # Write file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # Update metadata store
        self.metadata_store.set_page_metadata(
            page_info.id,
            page_info.title,
            page_info.version,
            str(file_path.relative_to(Path.cwd()))
        )
    
    def _push_file(self, file_path: Path) -> bool:
        """Push a single file to Confluence"""
        if not file_path.exists():
            console.print(f"[red]File not found: {file_path}[/red]")
            return False
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        page_info = self._parse_file_content(content, file_path)
        
        if page_info.id:
            # Update existing page
            self.client.update_page_content(
                page_id=page_info.id,
                title=page_info.title,
                markdown_content=page_info.content,
                current_version=page_info.version,
                parent_id=page_info.parent_id
            )
            
            # Update metadata with new version (increment by 1)
            self.metadata_store.set_page_metadata(
                page_info.id,
                page_info.title,
                page_info.version + 1,
                str(file_path.relative_to(Path.cwd()))
            )
        else:
            # Create new page
            result = self.client.create_page(
                space_key=self.config.confluence.space_key,
                title=page_info.title,
                markdown_content=page_info.content,
                parent_id=page_info.parent_id
            )
            
            # Update metadata with new page info
            self.metadata_store.set_page_metadata(
                result['id'],
                page_info.title,
                result['version']['number'],
                str(file_path.relative_to(Path.cwd()))
            )
        
        return True
    
    def _create_file_content(self, page_info: PageInfo) -> str:
        """Create file content with metadata header"""
        header = f"""---
confluence_id: {page_info.id}
confluence_title: {page_info.title}
confluence_version: {page_info.version}
confluence_parent_id: {page_info.parent_id or ""}
confluence_space_key: {page_info.space_key}
---

"""
        return header + page_info.content
    
    def _parse_file_content(self, content: str, file_path: Path) -> PageInfo:
        """Parse file content and extract metadata"""
        lines = content.split('\n')
        
        if lines[0] == '---':
            # Find end of metadata
            metadata_end = -1
            for i, line in enumerate(lines[1:], 1):
                if line == '---':
                    metadata_end = i
                    break
            
            if metadata_end > 0:
                # Extract metadata
                metadata = {}
                for line in lines[1:metadata_end]:
                    if ':' in line:
                        key, value = line.split(':', 1)
                        metadata[key.strip()] = value.strip()
                
                # Get content after metadata
                content_lines = lines[metadata_end + 1:]
                content = '\n'.join(content_lines).strip()
                
                return PageInfo(
                    id=metadata.get('confluence_id', ''),
                    title=metadata.get('confluence_title', file_path.stem),
                    version=int(metadata.get('confluence_version', 1)),
                    content=content,
                    parent_id=metadata.get('confluence_parent_id') or None,
                    space_key=metadata.get('confluence_space_key', self.config.confluence.space_key)
                )
        
        # No metadata found, treat as new file
        return PageInfo(
            id='',
            title=file_path.stem,
            version=1,
            content=content,
            space_key=self.config.confluence.space_key
        )
    
    def _sanitize_filename(self, title: str) -> str:
        """Create a safe filename from page title"""
        # Replace problematic characters
        safe_name = title.replace('/', '_').replace('\\', '_').replace(':', '_')
        safe_name = ''.join(c for c in safe_name if c.isalnum() or c in '-_. ')
        return safe_name.strip()
    
    def _get_all_tracked_files(self) -> List[Path]:
        """Get all files that are tracked in metadata"""
        metadata = self.metadata_store.get_all_pages()
        return [Path(meta['file_path']) for meta in metadata.values() if Path(meta['file_path']).exists()]
    
    def _get_all_local_files(self) -> List[Path]:
        """Get all markdown files in the local directory"""
        md_files = []
        for pattern in ['*.md', '*.markdown']:
            md_files.extend(self.config.local_path.rglob(pattern))
        
        # Filter out ignored files
        return [f for f in md_files if not self._is_ignored(f)]
    
    def _is_ignored(self, file_path: Path) -> bool:
        """Check if file should be ignored based on ignore patterns"""
        for pattern in self.config.ignore_patterns:
            if file_path.match(pattern):
                return True
        return False
    
    def _get_page_id_from_file(self, file_path: Path) -> Optional[str]:
        """Extract page ID from file content"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            page_info = self._parse_file_content(content, file_path)
            return page_info.id if page_info.id else None
        except Exception:
            return None
    
    def _is_file_modified(self, file_path: Path, metadata: Dict) -> bool:
        """Check if file has been modified since last sync"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            page_info = self._parse_file_content(content, file_path)
            
            # Compare title and version
            return (
                page_info.title != metadata.get('title') or
                page_info.version != metadata.get('version')
            )
        except Exception:
            return True  # Assume modified if we can't parse