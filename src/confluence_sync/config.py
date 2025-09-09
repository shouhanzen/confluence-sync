from pathlib import Path
from typing import Optional
import yaml
from pydantic import BaseModel, Field


class ConfluenceConfig(BaseModel):
    url: str = Field(..., description="Confluence instance URL")
    api_token: str = Field(..., description="API token for authentication")
    space_key: str = Field(..., description="Confluence space key")
    username: Optional[str] = Field(None, description="Username for legacy authentication")


class SyncConfig(BaseModel):
    confluence: ConfluenceConfig
    local_path: Path = Field(default=Path("docs"), description="Local directory for markdown files")
    ignore_patterns: list[str] = Field(default_factory=list, description="Patterns to ignore during sync")
    

class Config:
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path("confluence-sync.yml")
        self._config: Optional[SyncConfig] = None
    
    def load(self) -> SyncConfig:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path) as f:
            config_data = yaml.safe_load(f)
        
        self._config = SyncConfig(**config_data)
        return self._config
    
    def save_template(self) -> None:
        template = {
            "confluence": {
                "url": "https://your-domain.atlassian.net",
                "api_token": "your-api-token",
                "space_key": "YOUR_SPACE_KEY"
            },
            "local_path": "docs",
            "ignore_patterns": [
                "*.tmp",
                ".git/*"
            ]
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(template, f, default_flow_style=False, indent=2)
    
    def save_interactive_config(self, url: str, api_token: str, space_key: str, local_path: str = "docs", username: Optional[str] = None) -> None:
        """Save configuration from interactive setup"""
        confluence_config = {
            "url": url,
            "api_token": api_token,
            "space_key": space_key
        }
        
        if username:
            confluence_config["username"] = username
        
        config_data = {
            "confluence": confluence_config,
            "local_path": local_path,
            "ignore_patterns": [
                "*.tmp", 
                ".git/*",
                ".DS_Store"
            ]
        }
        
        with open(self.config_path, 'w') as f:
            yaml.dump(config_data, f, default_flow_style=False, indent=2)
    
    @property
    def config(self) -> SyncConfig:
        if self._config is None:
            self._config = self.load()
        return self._config