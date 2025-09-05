from typing import Dict, List, Optional, Any
from atlassian import Confluence
from markdownify import markdownify
import re
from dataclasses import dataclass


@dataclass
class PageInfo:
    id: str
    title: str
    version: int
    content: str
    parent_id: Optional[str] = None
    space_key: str = ""


class ConfluenceClient:
    def __init__(self, url: str, api_token: str):
        self.confluence = Confluence(
            url=url,
            token=api_token,
            cloud=True
        )
    
    def get_space_pages(self, space_key: str, limit: int = 500) -> List[Dict[str, Any]]:
        """Get all pages in a space"""
        pages = self.confluence.get_all_pages_from_space(
            space=space_key,
            start=0,
            limit=limit,
            expand='version,ancestors'
        )
        return pages
    
    def get_page_content(self, page_id: str) -> PageInfo:
        """Get page content with version info"""
        page = self.confluence.get_page_by_id(
            page_id=page_id,
            expand='body.storage,version,ancestors,space'
        )
        
        # Convert HTML to Markdown
        html_content = page['body']['storage']['value']
        markdown_content = self._html_to_markdown(html_content)
        
        parent_id = None
        if page.get('ancestors'):
            parent_id = page['ancestors'][-1]['id']
        
        return PageInfo(
            id=page['id'],
            title=page['title'],
            version=page['version']['number'],
            content=markdown_content,
            parent_id=parent_id,
            space_key=page['space']['key']
        )
    
    def update_page_content(
        self, 
        page_id: str, 
        title: str, 
        markdown_content: str, 
        current_version: int,
        parent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update page content, checking version for conflicts"""
        # First check if the page version has changed
        current_page = self.confluence.get_page_by_id(page_id, expand='version')
        if current_page['version']['number'] != current_version:
            raise ValueError(
                f"Version conflict: expected {current_version}, "
                f"but remote is {current_page['version']['number']}"
            )
        
        # Convert markdown to HTML
        html_content = self._markdown_to_html(markdown_content)
        
        return self.confluence.update_page(
            page_id=page_id,
            title=title,
            body=html_content,
            parent_id=parent_id,
            version_comment="Updated via confluence-sync"
        )
    
    def create_page(
        self, 
        space_key: str, 
        title: str, 
        markdown_content: str,
        parent_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new page"""
        html_content = self._markdown_to_html(markdown_content)
        
        return self.confluence.create_page(
            space=space_key,
            title=title,
            body=html_content,
            parent_id=parent_id
        )
    
    def _html_to_markdown(self, html_content: str) -> str:
        """Convert Confluence HTML to Markdown"""
        # Clean up Confluence-specific HTML elements
        html_content = self._clean_confluence_html(html_content)
        
        # Convert to markdown
        markdown = markdownify(
            html_content,
            heading_style="ATX",
            bullets="-",
            wrap=True,
            wrap_width=80
        )
        
        return markdown.strip()
    
    def _markdown_to_html(self, markdown_content: str) -> str:
        """Convert Markdown to Confluence HTML (basic implementation)"""
        # This is a simplified implementation
        # For production, consider using a proper markdown parser like python-markdown
        html = markdown_content
        
        # Convert headers
        html = re.sub(r'^# (.*)', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.*)', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^### (.*)', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        
        # Convert bold and italic
        html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html)
        
        # Convert paragraphs
        paragraphs = html.split('\n\n')
        html = ''.join(f'<p>{p.strip()}</p>' for p in paragraphs if p.strip())
        
        return html
    
    def _clean_confluence_html(self, html: str) -> str:
        """Remove Confluence-specific HTML elements that don't translate well"""
        # Remove macro placeholders and other Confluence-specific elements
        html = re.sub(r'<ac:.*?</ac:.*?>', '', html, flags=re.DOTALL)
        html = re.sub(r'<ri:.*?/>', '', html)
        
        return html
    
    def test_connection(self) -> bool:
        """Test if credentials and connection work"""
        try:
            # Try to get current user info to test credentials
            self.confluence.get_current_user()
            return True
        except Exception:
            return False
    
    def get_user_spaces(self) -> List[Dict[str, Any]]:
        """Get spaces the user has access to"""
        try:
            spaces = self.confluence.get_all_spaces(
                space_type='global',
                limit=50,
                expand='description'
            )
            return spaces['results']
        except Exception:
            return []
    
    def get_space_info(self, space_key: str) -> Optional[Dict[str, Any]]:
        """Validate and get info for a specific space key"""
        try:
            space = self.confluence.get_space(space_key, expand='description')
            return space
        except Exception:
            return None