# Claude Development Notes

This document contains learnings and insights from developing the confluence-sync project.

## Project Overview

Created a Python tool using uv that synchronizes Confluence pages with local markdown files, featuring version control to prevent conflicts.

## Key Technical Decisions

### Package Manager: uv
- Used uv instead of pip/poetry for modern Python dependency management
- Benefits: Faster installs, better dependency resolution, integrated virtual environments
- Installation: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Project initialization: `uv init --name confluence-sync --package`
- Dependency management: `uv sync`

### Dependencies Selected
- `atlassian-python-api>=3.41.0` - Official Atlassian API client
- `click>=8.1.7` - CLI framework for command-line interface  
- `pydantic>=2.5.0` - Data validation and configuration management
- `pyyaml>=6.0.1` - YAML configuration file parsing
- `rich>=13.7.0` - Beautiful terminal output and progress bars
- `markdownify>=0.11.6` - HTML to Markdown conversion

### Architecture Patterns

#### Configuration Management
- Used Pydantic models for type-safe configuration validation
- YAML configuration file with template generation
- Separation of Confluence credentials from sync settings

#### Version Control Strategy
- Store Confluence page version numbers in markdown file headers
- Check version before push to prevent overwriting remote changes
- Metadata stored in YAML frontmatter format:
  ```markdown
  ---
  confluence_id: 123456789
  confluence_title: My Page Title
  confluence_version: 5
  confluence_parent_id: 987654321
  confluence_space_key: MYSPACE
  ---
  ```

#### Data Flow Design
1. **Pull**: Confluence API → HTML → Markdown → Local files + metadata
2. **Push**: Local files → Markdown → HTML → Confluence API (with version check)
3. **Status**: Compare local file timestamps/content with stored metadata

### API Integration Patterns

#### Confluence API Wrapper
- Abstracted atlassian-python-api behind custom client class
- Centralized error handling and response parsing
- Separate methods for different operations (get, update, create)
- Built-in HTML/Markdown conversion pipeline

#### Error Handling Strategy
- Version conflicts raise specific ValueError exceptions
- File not found errors handled gracefully with user guidance
- API authentication errors bubble up with helpful messages

### CLI Design Principles

#### Command Structure
- `init` - Setup configuration template
- `pull` - Download from Confluence
- `push` - Upload to Confluence with conflict detection
- `status` - Show local vs remote state

#### User Experience
- Rich console output with colors and progress bars
- Clear error messages with actionable guidance
- Optional file targeting for push operations
- Configuration file auto-discovery with override option

### File Management Strategy

#### Local File Organization
- Sanitized filenames from page titles
- Configurable local directory path
- Ignore patterns to skip certain files
- Metadata tracking in hidden `.confluence-sync/` directory

#### Metadata Storage
- JSON file stores page ID → file path → version mapping
- Enables efficient status checking and conflict detection
- Persistent across sync operations

## Implementation Insights

### HTML to Markdown Conversion
- Confluence HTML contains proprietary macros and elements
- Need to clean HTML before markdown conversion
- Some formatting may be lost in round-trip conversion
- Consider more sophisticated markdown parser for production use

### Version Conflict Detection
- Simple integer version comparison works for basic conflict detection
- Could be enhanced with content checksums for better accuracy
- Remote changes always take precedence in conflicts

### File System Considerations
- Handle special characters in page titles for safe filenames
- Preserve directory structure for nested pages
- Support for different markdown file extensions

## Testing Strategy

### Manual Testing Approach
- Test CLI commands with `uv run confluence-sync`
- Verify configuration template generation
- Check help text and command structure
- Validate error handling with missing config

### Areas for Future Testing
- API authentication with real Confluence instance
- Version conflict scenarios
- Large file handling and performance
- Cross-platform file path handling

## Development Workflow

### Project Setup Process
1. Initialize uv project with package structure
2. Configure dependencies in pyproject.toml
3. Create modular source structure
4. Implement core functionality first, CLI last
5. Test basic functionality before adding complexity

### Code Organization
- Separate concerns: config, API client, sync logic, CLI
- Keep API interactions isolated in client class
- Use dataclasses for structured data (PageInfo)
- Rich console output for better UX

## Lessons Learned

### uv Package Manager
- Modern alternative to pip with better performance
- Integrated virtual environment management
- Good for new projects, migration from existing tools may require planning
- CLI tools work well with `uv run` prefix

### Confluence API Considerations
- HTML content requires cleaning before markdown conversion
- Version tracking essential for collaborative editing
- API rate limits may need consideration for large spaces
- Authentication via API tokens more reliable than OAuth for CLI tools

### CLI Design Best Practices
- Provide helpful error messages with next steps
- Use rich output for better visual feedback
- Support both global and targeted operations (push all vs push specific files)
- Configuration file template generation reduces setup friction

## Future Enhancements

### Potential Improvements
- Better HTML/Markdown conversion with proper parser
- Incremental sync based on modification timestamps
- Backup functionality before making changes
- Support for attachments and images
- Git-like diff views for changes
- Batch operations for large spaces
- Configuration validation with better error messages

### Performance Optimizations
- Parallel API requests for large page sets
- Caching of page metadata
- Delta sync instead of full downloads
- Compression of stored metadata

## Command Reference

```bash
# Project setup
uv init --name confluence-sync --package
uv sync

# Usage
uv run confluence-sync init
uv run confluence-sync pull
uv run confluence-sync push [file1.md file2.md]
uv run confluence-sync status
```

## Configuration Template

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