# Confluence Sync

[![PyPI version](https://badge.fury.io/py/confluence-sync.svg)](https://badge.fury.io/py/confluence-sync)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python tool to synchronize Confluence pages with local markdown files using version control to prevent conflicts.

## Features

- **Pull**: Download Confluence pages as markdown files to your local directory
- **Push**: Upload local markdown changes back to Confluence with version conflict detection
- **Status**: See which files have been modified locally or remotely
- **Version Control**: Prevents overwriting remote changes by checking page versions before pushing

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Clone the repository
git clone <repository-url>
cd confluence-sync

# Install dependencies
uv sync

# Install the CLI tool
uv pip install -e .
```

## Configuration

Create a configuration file using:

```bash
confluence-sync init
```

This creates a `confluence-sync.yml` file. Edit it with your Confluence details:

```yaml
confluence:
  url: "https://your-domain.atlassian.net"
  username: "your-email@domain.com"
  api_token: "your-api-token"
  space_key: "YOUR_SPACE_KEY"
local_path: "docs"
ignore_patterns:
  - "*.tmp"
  - ".git/*"
```

### Getting an API Token

1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Give it a label and copy the token
4. Use your email and the token for authentication

## Usage

### Pull pages from Confluence

```bash
confluence-sync pull
```

This downloads all pages from the specified space as markdown files.

### Check status

```bash
confluence-sync status
```

Shows which files are new, modified, or deleted locally.

### Push local changes

```bash
# Push all tracked files
confluence-sync push

# Push specific files
confluence-sync push docs/page1.md docs/page2.md
```

The push command will:
- Check for version conflicts before uploading
- Block the push if remote pages have been modified
- Show which files couldn't be pushed due to conflicts

### File Format

Each markdown file includes metadata in the header:

```markdown
---
confluence_id: 123456789
confluence_title: My Page Title
confluence_version: 5
confluence_parent_id: 987654321
confluence_space_key: MYSPACE
---

# Page Content

Your markdown content here...
```

## Version Control Workflow

1. **Pull** to get the latest pages from Confluence
2. **Edit** markdown files locally
3. **Status** to see what's changed
4. **Push** to upload changes
5. If there are conflicts, **pull** again to merge remote changes

## Project Structure

```
confluence-sync/
├── src/confluence_sync/
│   ├── __init__.py
│   ├── cli.py           # Command-line interface
│   ├── config.py        # Configuration management
│   ├── confluence_client.py  # Confluence API wrapper
│   └── sync.py          # Main sync logic
├── pyproject.toml       # Project configuration
└── README.md
```