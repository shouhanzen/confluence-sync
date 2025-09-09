#!/usr/bin/env python3
"""
Test script for confluence-sync init flow using environment variables.

Creates a .env file with your Confluence credentials:
CONFLUENCE_URL=https://mycompany.atlassian.net
CONFLUENCE_API_TOKEN=your_token_here
CONFLUENCE_SPACE_KEY=DOCS
CONFLUENCE_USERNAME=your@email.com  # Optional, only for legacy auth

Then run: python test_init.py
"""

import os
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from src.confluence_sync.config import Config
from src.confluence_sync.confluence_client import ConfluenceClient


def test_init_flow():
    """Test the complete init flow using environment variables"""
    
    # Load environment variables
    load_dotenv()
    
    # Get required environment variables
    url = os.getenv('CONFLUENCE_URL')
    api_token = os.getenv('CONFLUENCE_API_TOKEN') 
    space_key = os.getenv('CONFLUENCE_SPACE_KEY')
    username = os.getenv('CONFLUENCE_USERNAME')  # Optional
    
    if not url or not api_token:
        print("❌ Missing required environment variables:")
        print("   CONFLUENCE_URL")
        print("   CONFLUENCE_API_TOKEN")
        print("   CONFLUENCE_SPACE_KEY (optional, for space testing)")
        print("   CONFLUENCE_USERNAME (optional, for legacy auth)")
        return False
    
    print("🔧 Testing Confluence Sync Init Flow")
    print("=" * 35)
    print()
    
    # Normalize URL
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    url = url.rstrip('/')
    
    print(f"URL: {url}")
    if space_key:
        print(f"Space Key: {space_key}")
    else:
        print("Space Key: Not provided (will skip space-specific tests)")
    if username:
        print(f"Username: {username}")
        print("Auth Method: Username + API Token")
    else:
        print("Auth Method: API Token only")
    print()
    
    # Test connection
    print("🔗 Testing connection...")
    try:
        client = ConfluenceClient(url, api_token, username)
        print("   Created client successfully")
        
        # Try the connection test
        connection_result = client.test_connection()
        print(f"   Connection test result: {connection_result}")
        
        if not connection_result:
            print("❌ Connection failed - credentials may be invalid")
            print("   This could mean:")
            print("   • API token is expired or invalid")
            print("   • Token doesn't have required permissions")
            print("   • Your instance requires username+token auth instead of PAT-only")
            return False
        print("✅ Connection successful!")
    except Exception as e:
        print(f"❌ Connection failed with exception: {e}")
        print(f"   Exception type: {type(e).__name__}")
        return False
    
    # Test space discovery
    print()
    print("📁 Testing space discovery...")
    try:
        spaces = client.get_user_spaces()
        print(f"✅ Found {len(spaces)} accessible spaces")
        
        # Show first few spaces
        for i, space in enumerate(spaces[:5], 1):
            print(f"   {i}. {space['key']} - {space['name']}")
        if len(spaces) > 5:
            print(f"   ... and {len(spaces) - 5} more")
            
    except Exception as e:
        print(f"⚠️  Space discovery failed: {e}")
    
    # Test specific space validation (if space_key provided)
    if space_key:
        print()
        print(f"🎯 Testing space '{space_key}' validation...")
        try:
            space_info = client.get_space_info(space_key)
            if space_info:
                print(f"✅ Space found: \"{space_info['name']}\" ({space_key})")
            else:
                print(f"❌ Space '{space_key}' not found or not accessible")
                return False
        except Exception as e:
            print(f"❌ Space validation failed: {e}")
            return False
    
    # Test configuration save in temporary location
    print()
    print("💾 Testing configuration save...")
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test-confluence-sync.yml"
            config = Config(config_path)
            
            local_path = "test-docs"
            # Use first discovered space if no space_key provided
            test_space_key = space_key
            if not test_space_key and spaces:
                test_space_key = spaces[0]['key']
                print(f"   Using first discovered space: {test_space_key}")
            
            if test_space_key:
                config.save_interactive_config(url, api_token, test_space_key, local_path, username)
                
                # Verify config can be loaded back
                loaded_config = config.load()
                print(f"✅ Configuration saved and loaded successfully")
                print(f"   Config file: {config_path}")
                print(f"   URL: {loaded_config.confluence.url}")
                print(f"   Space: {loaded_config.confluence.space_key}")
                print(f"   Local path: {loaded_config.local_path}")
                if hasattr(loaded_config.confluence, 'username') and loaded_config.confluence.username:
                    print(f"   Username: {loaded_config.confluence.username}")
            else:
                print("⚠️  Skipping config test - no space key available")
            
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False
    
    # Test basic API operations (if we have a space to test with)
    test_space = space_key if space_key else (spaces[0]['key'] if spaces else None)
    
    if test_space:
        print()
        print(f"📄 Testing basic API operations with space '{test_space}'...")
        try:
            pages = client.get_space_pages(test_space, limit=5)
            print(f"✅ Retrieved {len(pages)} pages from space")
            
            if pages:
                # Test getting content for first page
                first_page = pages[0]
                page_info = client.get_page_content(first_page['id'])
                print(f"✅ Retrieved content for page: \"{page_info.title}\"")
                print(f"   Page ID: {page_info.id}")
                print(f"   Version: {page_info.version}")
                print(f"   Content length: {len(page_info.content)} chars")
            
        except Exception as e:
            print(f"❌ API operations failed: {e}")
            return False
    else:
        print()
        print("⚠️  Skipping API operations test - no space available")
    
    print()
    print("🎉 All tests passed! Init flow is working correctly.")
    print()
    print("Next steps:")
    print("  • Run 'uv run confluence-sync init' for interactive setup")
    print("  • Or run 'uv run confluence-sync init --non-interactive' for template")
    
    return True


if __name__ == "__main__":
    success = test_init_flow()
    exit(0 if success else 1)