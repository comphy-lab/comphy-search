#!/usr/bin/env python3
import json
import re
import os
import urllib.parse
from bs4 import BeautifulSoup
from pathlib import Path
import datetime
import subprocess
import shutil
from pathlib import PurePosixPath
from urllib.parse import quote

# =====================================================================
# CONFIGURATION - Modify these settings for your repositories
# =====================================================================

# Format: list of dictionaries with repository information
# Each repo needs:
#   - path: Local path where the repo is checked out (relative to GITHUB_WORKSPACE in Actions)
#   - url: Base URL where the site is published
#   - type: Type of repository (website, blog, docs, other)

REPOSITORIES = [
    {
        "repo_url": "https://github.com/comphy-lab/comphy-lab.github.io.git",  # GitHub repository URL
        "path": "comphy-lab.github.io",  # Local directory name
        "url": "https://comphy-lab.org",  # URL where the website is published
        "type": "website",  # Repository type
        # Optional: Custom directory mappings - maps directories to URL paths
        "directories": {
            "_team": "/team/",
            "_research": "/research/",
            "_teaching": "/teaching/",
            "_join-us": "/join/",
        }
    },
    {
        "repo_url": "https://github.com/comphy-lab/CoMPhy-Lab-Blogs.git",  # GitHub repository URL
        "path": "CoMPhy-Lab-Blogs",  # Local directory name
        "url": "https://blogs.comphy-lab.org",  # URL where the blog is published
        "type": "blog",  # Repository type
        # Optional: Blog-specific settings
        "blog_settings": {
            "post_dir": "_posts",  # Directory containing posts (standard Jekyll structure)
            "date_in_url": True,   # Whether to include date in URLs (Jekyll style: /YYYY/MM/DD/title/)
            "url_prefix": "/blog"  # Prefix for blog URLs
        }
    },
    {
        "repo_url": "https://github.com/comphy-lab/Viscoelastic3D",  # GitHub repository URL
        "path": "Viscoelastic3D",  # Local directory name
        "url": "https://comphy-lab.org/Viscoelastic3D",  # URL where the blog is published
        "type": "docs",  # Repository type
    },
    {
        "repo_url": "https://github.com/comphy-lab/Viscoelastic-Worthington-jets-and-droplets-produced-by-bursting-bubbles",  # GitHub repository URL
        "path": "Viscoelastic-Worthington-jets-and-droplets-produced-by-bursting-bubbles",  # Local directory name
        "url": "https://comphy-lab.org/Viscoelastic-Worthington-jets-and-droplets-produced-by-bursting-bubbles",  # URL where the blog is published
        "type": "docs",  # Repository type
    },
    {
        "repo_url": "https://github.com/comphy-lab/BurstingBubble_Herschel-Bulkley",  # GitHub repository URL
        "path": "BurstingBubble_Herschel-Bulkley",  # Local directory name
        "url": "https://comphy-lab.org/BurstingBubble_Herschel-Bulkley",  # URL where the blog is published
        "type": "docs",  # Repository type
    },
    {
        "repo_url": "https://github.com/comphy-lab/soapy",  # GitHub repository URL
        "path": "soapy",  # Local directory name
        "url": "https://comphy-lab.org/soapy",  # URL where the blog is published
        "type": "docs",  # Repository type
    },
    {
        "repo_url": "https://github.com/comphy-lab/HoleySheet",  # GitHub repository URL
        "path": "HoleySheet",  # Local directory name
        "url": "https://comphy-lab.org/HoleySheet",  # URL where the blog is published
        "type": "docs",  # Repository type
    },
    {
        "repo_url": "https://github.com/comphy-lab/MultiRheoFlow",
        "path": "MultiRheoFlow",
        "url": "https://comphy-lab.org/MultiRheoFlow",
        "type": "docs"
    },
    {
        "repo_url": "https://github.com/comphy-lab/fiber",
        "path": "fiber",
        "url": "https://comphy-lab.org/fiber",
        "type": "docs"
    },
    {
        "repo_url": "https://github.com/comphy-lab/JumpingBubbles",
        "path": "JumpingBubbles",
        "url": "https://comphy-lab.org/JumpingBubbles",
        "type": "docs"
    },
    {
        "repo_url": "https://github.com/comphy-lab/Drop-Impact",
        "path": "Drop-Impact",
        "url": "https://comphy-lab.org/Drop-Impact",
        "type": "docs"
    },
    {
        "repo_url": "https://github.com/comphy-lab/Asymmetries-in-coalescence",
        "path": "Asymmetries-in-coalescence",
        "url": "https://comphy-lab.org/Asymmetries-in-coalescence",
        "type": "docs"
    },
    # Add more repositories as needed
    # Example for documentation site:
    # {
    #     "repo_url": "https://github.com/comphy-lab/docs-repo.git",
    #     "path": "docs-repo",
    #     "url": "https://docs.comphy-lab.github.io",
    #     "type": "docs"
    # },
]

# Directory to store output files (in the current repo)
OUTPUT_PATH = "search_db.json"

# =====================================================================
# HELPER FUNCTIONS
# =====================================================================

# Helper function to generate proper anchor links
def generate_anchor(text):
    """
    Generate a proper anchor ID that matches Jekyll's auto-generated IDs.
    
    Args:
        text: The heading text to convert to an anchor
        
    Returns:
        A string containing the anchor ID
    """
    # Remove date prefix if present (e.g., "2025-01-21 ")
    text = re.sub(r'^\d{4}-\d{2}-\d{2}\s+', '', text)
    
    # Remove markdown link syntax if present [[text]]
    text = re.sub(r'\[\[(.*?)\]\]', r'\1', text)
    
    # Remove any other markdown formatting
    text = re.sub(r'[*_`]', '', text)
    
    # Keep alphanumeric characters, spaces, and hyphens
    text = re.sub(r'[^\w\s\-]', '', text)
    
    # Convert to lowercase
    text = text.lower()
    
    # Replace spaces with hyphens
    text = re.sub(r'\s+', '-', text)
    
    return text

# Parse markdown frontmatter to extract metadata
def parse_frontmatter(content):
    front_matter = {}
    content_text = content
    
    if content.startswith("---\n"):
        parts = content.split("---\n", 2)
        if len(parts) >= 3:
            yaml_text = parts[1]
            content_text = parts[2]
            
            for line in yaml_text.splitlines():
                if ":" in line:
                    key, value = [x.strip() for x in line.split(":", 1)]
                    front_matter[key] = value
    
    return front_matter, content_text

# Get the base directory for a repository
def get_repo_dir(repo_config):
    workspace = os.getenv('GITHUB_WORKSPACE', '.')
    return Path(workspace) / repo_config["path"]

# Clone or update a repository
def clone_or_update_repo(repo_config):
    repo_dir = get_repo_dir(repo_config)
    
    # If directory exists, update it
    if repo_dir.exists():
        print(f"Updating existing repository at {repo_dir}")
        try:
            subprocess.run(["git", "pull"], cwd=repo_dir, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error updating repository: {e}")
            return False
    
    # If directory doesn't exist, clone it
    print(f"Cloning repository to {repo_dir}")
    try:
        subprocess.run(["git", "clone", repo_config["repo_url"], str(repo_dir)], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error cloning repository: {e}")
        return False

# Clean up a repository
def cleanup_repo(repo_config):
    repo_dir = get_repo_dir(repo_config)
    if repo_dir.exists():
        print(f"Cleaning up repository at {repo_dir}")
        try:
            shutil.rmtree(repo_dir)
            return True
        except Exception as e:
            print(f"Error cleaning up repository: {e}")
            return False
    return True

# Get URL for a file within a repository
def get_file_url(repo_config, file_path, permalink=None):
    """
    Generates the public URL for a file based on repository configuration and file path.
    
    Handles different repository types ("blog", "website", "docs") with custom URL logic:
    - For blogs, supports date-based URLs and permalinks.
    - For websites, maps special directories and handles root files and redirects.
    - For documentation, preserves folder structure and appends `.html` as needed.
    - Falls back to a path-based URL for other types.
    
    Args:
        repo_config: Dictionary containing repository configuration, including type and base URL.
        file_path: Path object representing the file's location within the repository.
        permalink: Optional permalink string from frontmatter to override default URL generation.
    
    Returns:
        The full public URL as a string for the given file.
    """
    base_url = repo_config["url"].rstrip('/')
    repo_dir = get_repo_dir(repo_config)
    rel_path = file_path.relative_to(repo_dir)
    
    # If permalink is provided, use it
    if permalink:
        permalink = permalink.lstrip('/')
        return f"{base_url}/{permalink}"
    
    # Handle based on repository type
    if repo_config["type"] == "blog":
        # For Jekyll-style blogs with dates in filenames
        settings = repo_config.get("blog_settings", {})
        
        if settings.get("date_in_url", True) and re.match(r'^\d{4}-\d{2}-\d{2}-', file_path.stem):
            match = re.match(r'^(\d{4})-(\d{2})-(\d{2})-(.*)', file_path.stem)
            if match:
                year, month, day, slug = match.groups()
                url_prefix = settings.get("url_prefix", "")
                return f"{base_url}{url_prefix}/{year}/{month}/{day}/{slug}/"
                
        # Fall back to simple path-based URL
        path_no_ext = str(rel_path.with_suffix(''))
        return f"{base_url}/{path_no_ext}/"
        
    elif repo_config["type"] == "website":
        # Check if file is in a special directory
        dir_mappings = repo_config.get("directories", {})
        
        for dir_name, url_path in dir_mappings.items():
            if dir_name in str(rel_path):
                # File is in a mapped directory, construct URL accordingly
                # Extract the path after the directory
                parts = str(rel_path).split(dir_name + os.sep, 1)
                if len(parts) > 1:
                    file_name = Path(parts[1]).stem
                    
                    # Special handling for index files in special directories
                    if file_name.lower() == 'index':
                        return f"{base_url}{url_path}"
                    else:
                        return f"{base_url}{url_path}#{file_name.lower()}"
                else:
                    # File is directly in the mapped directory
                    return f"{base_url}{url_path}"
        
        # Special handling for root HTML files
        if file_path.suffix.lower() == '.html' and len(rel_path.parts) == 1:
            # For root HTML files like index.html, about.html, news.html
            file_name = file_path.stem
            if file_name.lower() == 'index':
                return base_url
            else:
                # Check if this is a redirect file
                try:
                    content = file_path.read_text(encoding='utf-8')
                    if 'meta http-equiv="refresh"' in content:
                        # Extract the redirect URL
                        match = re.search(r'url=([^"\'>\s]+)', content)
                        if match:
                            redirect = match.group(1)
                            if redirect.startswith('/#'):
                                # It's a section in the index page
                                return f"{base_url}{redirect[1:]}"  # Remove the leading /
                            elif redirect.startswith('/'):
                                return f"{base_url}{redirect}"
                            else:
                                return f"{base_url}/{redirect}"
                except Exception as e:
                    print(f"Warning: Could not parse redirect meta for {file_path}: {e}")
                    pass
                # Default to root URL with section
                return f"{base_url}#{file_name.lower()}"
        
        # Regular file in the root of the website
        if len(rel_path.parts) == 1:
            # Root level markdown file, like index.md
            file_name = rel_path.stem
            if file_name.lower() == "index":
                return base_url
            else:
                # For about.md, news.md, etc. - they should be at the root URL with section
                return f"{base_url}#{file_name.lower()}"
    
    elif repo_config["type"] == "docs":
        # For documentation files, we want to preserve the full folder structure
        # and generate URLs in the format base_url/FOLDER_NAME/filename.ext.html
        
        # Convert to POSIX path for consistent handling
        path_str = rel_path.as_posix()
        
        # If the file is in a docs directory, remove that prefix
        if path_str.startswith("docs/"):
            path_str = path_str[len("docs/"):]
            
        # Use PurePosixPath for reliable path handling
        p = PurePosixPath(path_str)
        dir_path, file_name = str(p.parent), p.name
        
        # Build, percent-encode and return the final URL
        # Only append .html if the file doesn't already end with it
        suffix = "" if file_name.endswith('.html') else ".html"
        target = f"{dir_path}/{file_name}{suffix}" if dir_path != "." else f"{file_name}{suffix}"
        return f"{base_url}/{quote(target)}"
    
    # Default handling for other types
    path_no_ext = str(rel_path.with_suffix(''))
    return f"{base_url}/{path_no_ext}/"

# =====================================================================
# CONTENT PROCESSING FUNCTIONS
# =====================================================================

def split_content_into_chunks(content, max_length=1000, original_title=None):
    """
    Split long content into meaningful chunks while preserving context.
    
    Args:
        content: The text content to split
        max_length: Maximum length for each chunk (default 1000 characters)
        original_title: Original title to help generate contextual chunk titles
        
    Returns:
        List of tuples containing (chunk_text, chunk_title)
    """
    if len(content) <= max_length:
        return [(content, None)]
    
    chunks = []
    current_chunk = []
    current_length = 0
    
    # Split by paragraphs first
    paragraphs = re.split(r'\n\n+', content)
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
            
        # If paragraph is too long, split by sentences
        if len(para) > max_length:
            sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', para)
            for sentence in sentences:
                if current_length + len(sentence) > max_length and current_chunk:
                    # Store current chunk
                    chunk_text = ' '.join(current_chunk).strip()
                    
                    # Generate a meaningful title for this chunk
                    chunk_title = generate_chunk_title(chunk_text, original_title)
                    chunks.append((chunk_text, chunk_title))
                    
                    current_chunk = []
                    current_length = 0
                
                current_chunk.append(sentence)
                current_length += len(sentence)
        else:
            if current_length + len(para) > max_length and current_chunk:
                # Store current chunk
                chunk_text = ' '.join(current_chunk).strip()
                
                # Generate a meaningful title for this chunk
                chunk_title = generate_chunk_title(chunk_text, original_title)
                chunks.append((chunk_text, chunk_title))
                
                current_chunk = []
                current_length = 0
            
            current_chunk.append(para)
            current_length += len(para)
    
    # Store any remaining content
    if current_chunk:
        chunk_text = ' '.join(current_chunk).strip()
        
        # Generate a meaningful title for this chunk
        chunk_title = generate_chunk_title(chunk_text, original_title)
        chunks.append((chunk_text, chunk_title))
    
    return chunks

def generate_chunk_title(chunk_text, original_title=None):
    """
    Generate a meaningful title for a content chunk based on its content.
    
    Args:
        chunk_text: The text content of the chunk
        original_title: The original title of the full content
        
    Returns:
        A string containing a meaningful title for the chunk
    """
    # Extract first sentence (up to 100 chars) for context
    first_sentence = chunk_text.split('.')[0] if '.' in chunk_text else chunk_text
    first_sentence = first_sentence[:100].strip()
    
    # Look for keywords or topics in the chunk
    keywords = []
    
    # Check for common section indicators
    if "introduction" in chunk_text.lower()[:200]:
        keywords.append("Introduction")
    elif "conclusion" in chunk_text.lower()[:200]:
        keywords.append("Conclusion")
    elif "summary" in chunk_text.lower()[:200]:
        keywords.append("Summary")
    elif "method" in chunk_text.lower()[:200]:
        keywords.append("Methods")
    elif "result" in chunk_text.lower()[:200]:
        keywords.append("Results")
    elif "example" in chunk_text.lower()[:200]:
        keywords.append("Examples")
    elif "definition" in chunk_text.lower()[:200]:
        keywords.append("Definitions")
    
    # For code chunks, identify language or pattern
    code_indicators = {
        "def ": "Python Function",
        "function ": "Function Definition",
        "class ": "Class Definition",
        "#include": "C/C++ Code",
        "int main": "C/C++ Main",
        "public class": "Java Code",
        "import ": "Import Statements",
        "npm": "Node.js",
        "const ": "JavaScript",
        "var ": "JavaScript",
        "let ": "JavaScript",
        "<html": "HTML",
        "<div": "HTML",
        "SELECT": "SQL Query",
        "FROM": "SQL Query"
    }
    
    for indicator, label in code_indicators.items():
        if indicator in chunk_text[:200]:
            keywords.append(label)
            break
    
    # Create title based on collected information
    if keywords and original_title:
        return f"{original_title}: {' - '.join(keywords)}"
    elif keywords:
        return ' - '.join(keywords)
    elif original_title:
        # Extract key topic from the first sentence if possible
        words = first_sentence.split()
        if len(words) > 3:
            key_phrase = ' '.join(words[:3]) + "..."
            return f"{original_title}: {key_phrase}"
        else:
            return f"{original_title}: Context"
    else:
        return "Content Section"

def process_docs_html_file(repo_config, file_path, search_db):
    """
    Processes a documentation HTML file and adds its content and code blocks to the search database.
    
    Parses the HTML file to extract the main content and title, splits the content into searchable chunks, and generates entries for both text and code sections. Handles files with compound extensions (e.g., `.c.html`) and assigns appropriate entry types and priorities.
    """
    print(f"  - {file_path.relative_to(get_repo_dir(repo_config))}")
    
    try:
        content = file_path.read_text(encoding='utf-8')
        
        # Parse HTML content
        soup = BeautifulSoup(content, 'html.parser')
        
        # Get title from HTML
        title_tag = soup.find('title')
        # For files like example.c.html, remove both .html and keep the .c
        base_name = file_path.stem  # removes .html
        if '.' in base_name:
            # This is a .c.html, .py.html, etc. file
            title = title_tag.text.strip() if title_tag else base_name.replace('-', ' ').capitalize()
        else:
            # Regular HTML file
            title = title_tag.text.strip() if title_tag else base_name.replace('-', ' ').capitalize()
        
        # Generate URL for this file using get_file_url
        url = get_file_url(repo_config, file_path)
        
        # Extract main content
        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content') or soup.find('div', id='content')
        
        if not main_content:
            # If no main content container found, use the body
            main_content = soup.find('body')
        
        if not main_content:
            print(f"  Warning: Could not find main content in {file_path}")
            return
        
        # Extract text content
        text_content = main_content.get_text(separator=' ', strip=True)
        
        # Clean up the text
        clean_content = re.sub(r'\s+', ' ', text_content).strip()
        
        if len(clean_content) >= 50:
            # Split content into chunks if it's too long
            content_chunks = split_content_into_chunks(clean_content, original_title=title)
            
            # Create entries for each chunk
            for i, (chunk, chunk_title) in enumerate(content_chunks):
                if chunk_title:
                    entry_title = chunk_title
                elif len(content_chunks) > 1:
                    # If no specific title was generated, create a meaningful one
                    if i == 0:
                        entry_title = f"{title} - Overview"
                    elif i == len(content_chunks) - 1:
                        entry_title = f"{title} - Additional Details"
                    else:
                        entry_title = f"{title} - Continued"
                else:
                    entry_title = title
                
                entry = {
                    'title': entry_title,
                    'content': chunk,
                    'url': url,
                    'type': 'docs_content',
                    'priority': get_priority(repo_config, file_path)
                }
                search_db.append(entry)
            
            # Process code blocks and function documentation
            code_blocks = main_content.find_all(['pre', 'code'])
            for block in code_blocks:
                code_content = block.get_text(strip=True)
                if len(code_content) >= 50:
                    # Try to detect what type of code it is
                    code_type = "Code Example"
                    if "def " in code_content[:100]:
                        code_type = "Function Definition"
                    elif "class " in code_content[:100]:
                        code_type = "Class Definition"
                    elif "#include" in code_content[:100]:
                        code_type = "C/C++ Code"
                    elif "public class" in code_content[:100]:
                        code_type = "Java Code"
                    
                    # Split code content if it's too long
                    code_chunks = split_content_into_chunks(code_content, max_length=500, original_title=f"{title} - {code_type}")
                    
                    for i, (chunk, chunk_title) in enumerate(code_chunks):
                        entry_title = chunk_title if chunk_title else f"{title} - {code_type}"
                        
                        # Extract function or class name if possible
                        if "def " in chunk[:100]:
                            match = re.search(r'def\s+(\w+)', chunk[:100])
                            if match:
                                func_name = match.group(1)
                                entry_title = f"{title} - Function: {func_name}"
                        elif "class " in chunk[:100]:
                            match = re.search(r'class\s+(\w+)', chunk[:100])
                            if match:
                                class_name = match.group(1)
                                entry_title = f"{title} - Class: {class_name}"
                        
                        entry = {
                            'title': entry_title,
                            'content': chunk,
                            'url': url,
                            'type': 'docs_code',
                            'priority': get_priority(repo_config, file_path)
                        }
                        search_db.append(entry)
    
    except Exception as e:
        print(f"Error processing documentation HTML file {file_path}: {e}")

def process_markdown_file(repo_config, file_path, search_db):
    print(f"  - {file_path.relative_to(get_repo_dir(repo_config))}")
    
    try:
        content = file_path.read_text(encoding='utf-8')
        front_matter, content_body = parse_frontmatter(content)
        
        # Get permalink if available in frontmatter
        permalink = front_matter.get('permalink')
        
        # Generate URL for this file
        url = get_file_url(repo_config, file_path, permalink)
        
        # Get title from frontmatter or filename
        page_title = front_matter.get('title')
        if not page_title:
            page_title = file_path.stem.replace('-', ' ').capitalize()
            
            # For blogs, remove date prefix from title if present
            if repo_config["type"] == "blog" and re.match(r'^\d{4}-\d{2}-\d{2}-', page_title):
                page_title = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', page_title)
        
        # Get repository type for entry type
        repo_type = repo_config["type"]
        
        # Special handling for research index file
        if repo_type == "website" and "_research" in str(file_path) and file_path.stem.lower() == "index":
            process_research_index(repo_config, url, content_body, search_db)
            return # Skip default processing for research index

        # Special handling for team index file
        is_team_index = False
        if repo_type == "website" and "_team" in str(file_path) and file_path.stem.lower() == "index":
            is_team_index = True
        
        # Split content by headers to create individual entries
        if content_body.strip():
            # First, try finding headers with regex
            # Use content_body here instead of the full content
            sections = re.split(r'^#+\s+', content_body, flags=re.MULTILINE)
            
            # Process content before first header (if any)
            if sections and sections[0].strip():
                clean_content = re.sub(r'<[^>]+>', ' ', sections[0])
                clean_content = re.sub(r'\s+', ' ', clean_content).strip()
                
                if len(clean_content) >= 50:
                    # Split long content into chunks with meaningful titles
                    content_chunks = split_content_into_chunks(clean_content, original_title=page_title)
                    
                    for chunk, chunk_title in content_chunks:
                        if chunk_title:
                            entry_title = chunk_title
                        elif len(content_chunks) > 1:
                            # If this is likely an introduction
                            entry_title = f"{page_title} - Introduction"
                        else:
                            entry_title = page_title
                        
                        entry = {
                            'title': entry_title,
                            'content': chunk,
                            'url': url,
                            'type': f"{repo_type}_content",
                            'priority': get_priority(repo_config, file_path)
                        }
                        search_db.append(entry)
            
            # Process remaining sections with headers
            for i, section in enumerate(sections[1:], 1):
                if not section.strip():
                    continue
                    
                # Extract header and content
                lines = section.splitlines()
                if not lines:
                    continue
                    
                header = lines[0].strip()
                section_content = '\n'.join(lines[1:]).strip()
                
                if not header or not section_content:
                    continue
                if len(section_content) < 50:  # Skip very short sections
                    continue
                
                # Skip navigation-like sections
                if re.match(r'^(navigation|menu|contents|index)$', header, re.IGNORECASE):
                    continue
                
                # Clean HTML tags for indexing
                clean_content = re.sub(r'<[^>]+>', ' ', section_content)
                clean_content = re.sub(r'\s+', ' ', clean_content).strip()
                
                # Generate anchor ID for section header
                anchor = generate_anchor(header)
                
                # Base section title
                section_title = f"{page_title} - {header}"
                
                # Special handling for team members and collaborators
                section_url = f"{url}#{anchor}"
                if is_team_index:
                    # Team members should have a higher priority
                    entry_priority = 1  # Highest priority
                else:
                    entry_priority = get_priority(repo_config, file_path)
                
                # Split long content into chunks with context-aware titles
                content_chunks = split_content_into_chunks(clean_content, original_title=section_title)
                
                for chunk, chunk_title in content_chunks:
                    # Use generated title or create a meaningful fallback
                    entry_title = chunk_title if chunk_title else section_title
                    
                    entry = {
                        'title': entry_title,
                        'content': chunk,
                        'url': section_url,
                        'type': f"{repo_type}_section",
                        'priority': entry_priority
                    }
                    search_db.append(entry)
    
    except Exception as e:
        print(f"Error processing file {file_path}: {e}")

def process_research_index(repo_config, base_url, content, search_db):
    """Process the _research/index.md file specifically for papers."""
    try:
        soup = BeautifulSoup(content, 'html.parser')
        h3_tags = soup.find_all('h3', id=True)
        
        print(f"  Found {len(h3_tags)} potential paper entries in research index.")
        
        for h3 in h3_tags:
            paper_id = h3.get('id')
            if not paper_id or not paper_id.isdigit(): # Check if ID is numeric (like '[15]')
                if paper_id != "thesis": # Allow specific non-numeric IDs like 'thesis'
                  continue

            # Extract title (full citation) from h3
            paper_title = h3.get_text(strip=True)
            
            # Construct URL: base_url should be something like https://comphy-lab.org/research/
            paper_url = f"{base_url}#{paper_id}"
            
            # Find the next sibling <tags> element
            tags_element = h3.find_next_sibling('tags')
            tags = []
            if tags_element:
                tags = re.findall(r'<span>(.*?)</span>', str(tags_element))
            
            # Determine priority - updated to move Featured papers to Priority 1
            priority = 1 if 'Featured' in tags else 2
            
            # Create entry (content is the same as title, no chunking)
            entry = {
                'title': paper_title,
                'content': paper_title,
                'url': paper_url,
                'type': 'paper',
                'tags': tags,
                'priority': priority
            }
            search_db.append(entry)
            # print(f"    Added paper entry: {paper_title[:50]}... URL: {paper_url}")

    except Exception as e:
        print(f"Error processing research index: {e}")

# Determine priority based on repo type and file location
def get_priority(repo_config, file_path):
    """
    Determines the indexing priority of a repository file.
    
    This function calculates a numerical priority based on the repository configuration
    and the file's location relative to the repository root. For website repositories, it
    first checks if the file is within any configured directory and returns a priority
    reflecting its order. If not, root-level HTML or markdown files receive a low priority
    (8) while all other website files are assigned the lowest priority (10). For blog
    repositories, files in the '_posts' directory with a date-formatted name are given a
    higher priority (2) if they are less than 90 days old; otherwise, they receive a medium
    priority (3). Documentation repositories assign a priority of 3 to files with 'api' in
    their path and 4 to all others. Non-specified repository types default to a priority
    of 4.
    
    Args:
        repo_config: A dictionary containing repository settings, including type and optional
                     directory mappings.
        file_path: A Path object representing the file to be prioritized.
    
    Returns:
        int: The calculated priority for the file.
    """
    repo_type = repo_config["type"]
    repo_dir = get_repo_dir(repo_config)
    rel_path = file_path.relative_to(repo_dir)
    path_str = str(rel_path)
    
    # Website repository special priorities
    if repo_type == "website":
        # Check if file is in a mapped directory
        dir_mappings = repo_config.get("directories", {})
        
        # Create a priority map based on the order of directories in the configuration
        priority_map = {}
        for i, dir_name in enumerate(dir_mappings.keys()):
            # Assign priorities starting from 1 (highest) in the order they appear in the config
            priority_map[dir_name] = i + 1
        
        # Check if file is in any of the mapped directories
        for dir_name, priority in priority_map.items():
            # Skip _research directory here, as it's handled specifically
            if dir_name == "_research": 
                continue 
            if dir_name in path_str:
                return priority
        
        # Root HTML files (like index.html, about.html, news.html) get low priority
        if file_path.suffix.lower() == '.html' and len(rel_path.parts) == 1:
            return 8  # Low priority for root HTML files
            
        # Root markdown files get low priority
        if file_path.suffix.lower() == '.md' and len(rel_path.parts) == 1:
            return 8  # Low priority for root markdown files
            
        # Default priority for other website content
        return 10  # Lowest priority for other website content
            
    # Blog posts (medium priority)
    elif repo_type == "blog":
        # Recent blog posts could get higher priority
        if "_posts/" in path_str and re.match(r'\d{4}-\d{2}-\d{2}', file_path.stem):
            # Extract date from filename
            date_match = re.match(r'(\d{4})-(\d{2})-(\d{2})', file_path.stem)
            if date_match:
                post_date = datetime.datetime(
                    int(date_match.group(1)),
                    int(date_match.group(2)),
                    int(date_match.group(3))
                )
                # If post is from last 3 months, give it higher priority
                if (datetime.datetime.now() - post_date).days < 90:
                    return 2
        return 3
        
    # Documentation (medium-low priority)
    elif repo_type == "docs":
        # API docs might get higher priority
        if "api" in path_str.lower():
            return 3
        return 4
        
    # Default priority for other content
    return 4

# Process website-specific elements
def process_website_specific(repo_config, file_path, front_matter, content, search_db):
    repo_dir = get_repo_dir(repo_config)
    rel_path = file_path.relative_to(repo_dir)
    path_str = str(rel_path)
    
    # Team member processing
    if "_team/" in path_str:
        # Team members are already processed in the general function
        pass
    
    # Research content specific processing - REMOVED, handled in process_markdown_file
    # elif "_research/" in path_str:
    #     pass
    
    # Teaching content specific processing
    elif "_teaching/" in path_str:
        # Process course details (div sections)
        soup = BeautifulSoup(content, 'html.parser')
        course_details = soup.find('div', class_='course-details')
        
        if course_details:
            detail_items = course_details.find_all('div', class_='course-details__item')
            
            for item in detail_items:
                heading = item.find('h4')
                detail_content = item.find('p')
                
                if not heading or not detail_content:
                    continue
                
                # Clean up heading (remove HTML tags)
                clean_heading = heading.get_text().strip()
                
                # Get title from frontmatter or filename
                title = front_matter.get('title')
                if not title:
                    title = file_path.stem.replace('-', ' ')
                    title = re.sub(r'^\d{4}-', '', title)
                
                # Get permalink from frontmatter or default
                permalink = front_matter.get('permalink', '/teaching/')
                
                # Create entry for course detail
                entry = {
                    'title': f"{title} - {clean_heading}",
                    'content': detail_content.get_text().strip(),
                    'url': f"{repo_config['url']}{permalink}",
                    'type': 'teaching_detail',
                    'priority': 3  # Updated: Medium priority for teaching content
                }
                search_db.append(entry)

# Process blog-specific elements
def process_blog_specific(repo_config, file_path, front_matter, content, url, title, search_db):
    # Clean up the content first (removing metadata lines)
    clean_content = re.sub(r'^(created|status|modified|author|date published):.*$', '', content, flags=re.MULTILINE)
    clean_content = re.sub(r'\n+', '\n', clean_content).strip()
    
    # Split content into paragraphs
    paragraphs = re.split(r'\n\n+', clean_content)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    
    # Process paragraphs for blog content
    for para in paragraphs:
        # Skip code blocks and HTML
        if para.startswith('```') or para.startswith('<'):
            continue
        if re.match(r'^[\s#*\-]+$', para):  # Skip lines that are just formatting
            continue
        
        # Split long paragraphs into smaller chunks
        if len(para) > 300:
            # Split by sentences
            sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', para)
            current_chunk = []
            current_length = 0
            
            for sentence in sentences:
                if current_length + len(sentence) > 300:
                    # Store current chunk if not empty
                    if current_chunk:
                        chunk_text = ' '.join(current_chunk).strip()
                        if len(chunk_text) >= 50:  # Only store substantial chunks
                            search_db.append({
                                'title': title,
                                'content': chunk_text,
                                'url': url,
                                'type': 'blog_excerpt',
                                'priority': get_priority(repo_config, file_path)
                            })
                        current_chunk = []
                        current_length = 0
                
                current_chunk.append(sentence)
                current_length += len(sentence)
            
            # Store any remaining content
            if current_chunk:
                chunk_text = ' '.join(current_chunk).strip()
                if len(chunk_text) >= 50:
                    search_db.append({
                        'title': title,
                        'content': chunk_text,
                        'url': url,
                        'type': 'blog_excerpt',
                        'priority': get_priority(repo_config, file_path)
                    })
        else:
            # For shorter paragraphs, store as is if substantial
            if len(para) >= 50:
                search_db.append({
                    'title': title,
                    'content': para,
                    'url': url,
                    'type': 'blog_excerpt',
                    'priority': get_priority(repo_config, file_path)
                })

# Process documentation-specific elements
def process_docs_specific(repo_config, file_path, front_matter, content, search_db):
    # Add specialized processing for documentation sites
    # This is a placeholder - customize based on your docs structure
    pass
    
# Process files from a repository
def should_exclude_file(file_path):
    """
    Check if a file should be excluded from processing.
    
    Args:
        file_path: Path object representing the file
        
    Returns:
        bool: True if file should be excluded, False otherwise
    """
    # Convert to string for easier path checking
    path_str = str(file_path)
    
    # List of paths/patterns to exclude
    exclude_patterns = [
        '.github/',  # GitHub specific files
        '.git/',     # Git directory
        'basilisk/', # Basilisk code directory
    ]
    
    return any(pattern in path_str for pattern in exclude_patterns)

def process_repository(repo_config, search_db):
    """
    Processes a repository by type, extracting and indexing content for the search database.
    
    Depending on the repository type ('docs', 'blog', or 'website'), this function locates relevant content files (HTML or markdown), processes them using the appropriate handlers, and adds structured entries to the search database. After processing, the local repository directory is cleaned up.
    """
    repo_dir = get_repo_dir(repo_config)
    
    print(f"Processing {repo_config['type']} repository at {repo_dir}")
    
    # Clone or update the repository
    if not clone_or_update_repo(repo_config):
        print(f"Failed to clone or update repository: {repo_config['repo_url']}")
        return
    
    if not repo_dir.exists():
        print(f"Repository directory not found: {repo_dir}")
        return
    
    # Different processing based on repository type
    if repo_config["type"] == "docs":
        # For documentation repositories, ONLY process HTML files in the docs directory
        docs_dir = repo_dir / "docs"
        if docs_dir.exists():
            # Find all HTML files in docs directory
            html_files = list(docs_dir.glob('**/*.html'))
            # Filter out excluded files
            html_files = [f for f in html_files if not should_exclude_file(f)]
            print(f"Found {len(html_files)} documentation HTML files in docs directory to process")
            
            for file_path in html_files:
                process_docs_html_file(repo_config, file_path, search_db)
        else:
            print(f"Warning: docs directory not found in {repo_dir}")
            cleanup_repo(repo_config)  # Clean up before returning
            return  # Skip processing if docs directory doesn't exist
            
    elif repo_config["type"] == "blog":
        # For blogs with posts directory structure
        if repo_config.get("blog_settings", {}).get("post_dir"):
            post_dir = repo_dir / repo_config["blog_settings"]["post_dir"]
            if post_dir.exists():
                md_files = list(post_dir.glob('**/*.md'))
            else:
                # Fallback to searching all markdown files
                md_files = list(repo_dir.glob('**/*.md'))
        else:
            # For other repository types, get all markdown files
            md_files = list(repo_dir.glob('**/*.md'))
        
        # Filter out README.md files and excluded files
        md_files = [f for f in md_files if f.name.lower() != 'readme.md' and not should_exclude_file(f)]
        print(f"Found {len(md_files)} markdown files to process")
        
        # Process each markdown file
        for file_path in md_files:
            process_markdown_file(repo_config, file_path, search_db)
            
    elif repo_config["type"] == "website":
        # Process markdown files
        md_files = list(repo_dir.glob('**/*.md'))
        md_files = [f for f in md_files if f.name.lower() != 'readme.md' and not should_exclude_file(f)]
        print(f"Found {len(md_files)} markdown files to process")
        
        for file_path in md_files:
            process_markdown_file(repo_config, file_path, search_db)
        
        # Also process HTML files in the root directory
        html_files = list(repo_dir.glob('*.html'))
        html_files = [f for f in html_files if not should_exclude_file(f)]
        print(f"Found {len(html_files)} HTML files in root directory to process")
        
        for file_path in html_files:
            process_html_file(repo_config, file_path, search_db)
    
    # Clean up the repository after processing
    cleanup_repo(repo_config)

# Process HTML files from the root directory
def process_html_file(repo_config, file_path, search_db):
    print(f"  - {file_path.relative_to(get_repo_dir(repo_config))}")
    
    try:
        content = file_path.read_text(encoding='utf-8')
        
        # Check if this is a redirect file
        if 'meta http-equiv="refresh"' in content:
            # Skip redirect files as they don't contain actual content
            return
        
        # Parse HTML content
        soup = BeautifulSoup(content, 'html.parser')
        
        # Get title from HTML
        title_tag = soup.find('title')
        title = title_tag.text.strip() if title_tag else file_path.stem.replace('-', ' ').capitalize()
        
        # Generate URL for this file
        url = get_file_url(repo_config, file_path)
        base_url = repo_config["url"].rstrip('/')
        
        # For Jekyll sites, look for sections with IDs
        sections = soup.find_all(['section', 'div'], class_='target-section', id=True)
        if sections:
            for section in sections:
                section_id = section.get('id')
                if not section_id:
                    continue
                
                # Get section title from first heading or use ID
                section_title = None
                heading = section.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                if heading:
                    section_title = heading.get_text(strip=True)
                if not section_title:
                    section_title = section_id.replace('-', ' ').capitalize()
                
                # Extract text content from section
                text_content = section.get_text(separator=' ', strip=True)
                
                # Clean up the text
                clean_content = re.sub(r'\s+', ' ', text_content).strip()
                
                if len(clean_content) >= 50:
                    # Create entry for the section
                    entry = {
                        'title': f"{title} - {section_title}",
                        'content': clean_content,
                        'url': f"{base_url}#{section_id}",  # Use base URL for sections
                        'type': f"{repo_config['type']}_section",
                        'priority': get_priority(repo_config, file_path)
                    }
                    search_db.append(entry)
                    
                    # Process subsections (h2, h3, h4 tags within the section)
                    for heading in section.find_all(['h2', 'h3', 'h4']):
                        heading_text = heading.get_text(strip=True)
                        if not heading_text:
                            continue
                        
                        # Find content until next heading
                        section_content = ''
                        current = heading.next_sibling
                        while current and (not hasattr(current, 'name') or current.name not in ['h2', 'h3', 'h4']):
                            if hasattr(current, 'string') and current.string:
                                section_content += str(current)
                            elif hasattr(current, 'get_text'):
                                section_content += current.get_text()
                            current = current.next_sibling
                        
                        # Clean HTML tags for content
                        clean_section = re.sub(r'<[^>]+>', ' ', section_content)
                        clean_section = re.sub(r'\s+', ' ', clean_section).strip()
                        
                        if len(clean_section) >= 50:
                            # Generate anchor ID for subsection header
                            anchor = generate_anchor(heading_text)
                            
                            # Create entry for the subsection
                            subsection_title = f"{title} - {section_title} - {heading_text}"
                            entry = {
                                'title': subsection_title,
                                'content': clean_section,
                                'url': f"{base_url}#{section_id}-{anchor}",  # Use base URL for subsections
                                'type': f"{repo_config['type']}_subsection",
                                'priority': get_priority(repo_config, file_path)
                            }
                            search_db.append(entry)
                            
                    # Also process any markdown content that will be loaded into this section
                    if section_id == 'about-content':
                        # Look for aboutCoMPhy.md
                        about_file = file_path.parent / 'aboutCoMPhy.md'
                        if about_file.exists():
                            process_markdown_file(repo_config, about_file, search_db)
                    elif section_id == 'news-content':
                        # Look for News.md
                        news_file = file_path.parent / 'News.md'
                        if news_file.exists():
                            process_markdown_file(repo_config, news_file, search_db)
        else:
            # Extract main content (excluding navigation, footer, etc.)
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content') or soup.find('div', id='content')
            
            if not main_content:
                # If no main content container found, use the body
                main_content = soup.find('body')
            
            if not main_content:
                print(f"  Warning: Could not find main content in {file_path}")
                return
            
            # Extract text content
            text_content = main_content.get_text(separator=' ', strip=True)
            
            # Clean up the text
            clean_content = re.sub(r'\s+', ' ', text_content).strip()
            
            if len(clean_content) >= 50:
                # Create entry for the entire page
                entry = {
                    'title': title,
                    'content': clean_content,
                    'url': url,
                    'type': f"{repo_config['type']}_content",
                    'priority': get_priority(repo_config, file_path)
                }
                search_db.append(entry)
    
    except Exception as e:
        print(f"Error processing HTML file {file_path}: {e}")

# =====================================================================
# MAIN FUNCTION
# =====================================================================

def deduplicate_entries(search_db):
    """
    Remove duplicate search entries based on title, content, and URL.
    
    Given a list of search entries where each entry is a dictionary containing
    the keys 'title', 'content', and 'url', this function returns a new list that
    preserves the original order while keeping only the first occurrence of each
    unique entry.
    """
    seen = set()
    unique_entries = []
    
    for entry in search_db:
        # Create a unique key for each entry
        key = (entry['title'], entry['content'], entry['url'])
        if key not in seen:
            seen.add(key)
            unique_entries.append(entry)
    
    return unique_entries

def fix_urls(search_db):
    """
    Cleans and normalizes URLs in the search database entries to ensure consistency.
    
    This function fixes common URL issues, including removing duplicate hash symbols, correcting special cases for AboutComphy content, normalizing section identifiers, updating team member anchors, removing trailing slashes from `.html` URLs, and standardizing encoded spaces in URL fragments.
    
    Args:
        search_db: List of search database entries, each containing a 'url' key.
    
    Returns:
        The updated search database with normalized URLs.
    """
    for entry in search_db:
        url = entry['url']
        
        # Fix multiple hash symbols (take only the first section)
        if url.count('#') > 1:
            base_url, _, rest = url.partition('#')
            section, _, _ = rest.partition('#')
            entry['url'] = f"{base_url}#{section}"
        
        # Special case for AboutComphy.md content
        if "aboutcomphy" in url.lower():
            if "comphy-lab.org" in url:
                entry['url'] = "https://comphy-lab.org/#about"
        
        # Fix urls with /index.html or /index
        if "/index.html#" in url:
            entry['url'] = url.replace("/index.html#", "/#")
        elif "/index#" in url:
            entry['url'] = url.replace("/index#", "/#")
        
        # Fix team URLs
        if "/team/#index" in url:
            # Extract proper anchor from title if available
            if 'title' in entry and ' - ' in entry['title']:
                # Title format is typically "Our Team & Collaborators - Person Name (Role)"
                person_part = entry['title'].split(' - ', 1)[1]
                # Generate anchor from person name using Jekyll-style formatting
                anchor = generate_anchor(person_part)
                entry['url'] = url.replace("#index", f"#{anchor}")
            # Special case for section headers
            elif 'title' in entry and entry['title'] == "Our Team & Collaborators - Present Team":
                entry['url'] = url.replace("#index", "#present-team")
            elif 'title' in entry and entry['title'] == "Our Team & Collaborators - Active Collaborations":
                entry['url'] = url.replace("#index", "#active-collaborations")
            elif 'title' in entry and entry['title'] == "Our Team & Collaborators - Our Alumni":
                entry['url'] = url.replace("#index", "#our-alumni")
            # Default case - just remove the #index
            else:
                entry['url'] = url.replace("#index", "")
        
        # Remove trailing slashes from HTML files
        if url.endswith('.html/'):
            entry['url'] = url[:-1]
        
        # Fix any remaining encoded space in URLs (convert %20 or + to hyphens in fragments)
        if ('#' in url) and ('+' in url or '%20' in url):
            base_url, hash_tag, fragment = url.partition('#')
            
            # If this is a team member URL, ensure proper formatting
            if '/team/' in base_url:
                # Replace encoded spaces with hyphens
                clean_fragment = fragment.replace('+', '-').replace('%20', '-')
                # Replace multiple hyphens with a single hyphen
                clean_fragment = re.sub(r'-+', '-', clean_fragment)
                # Ensure it's lowercase
                clean_fragment = clean_fragment.lower()
            else:
                # For non-team URLs, just fix the encoding
                clean_fragment = fragment.replace('+', '%20')
                
            entry['url'] = f"{base_url}#{clean_fragment}"
    
    return search_db

def main():
    """
    Main entry point for generating the search index JSON file.
    
    Initializes an empty search database, processes each repository configuration,
    deduplicates entries, and writes the final search database to the JSON file
    specified by OUTPUT_PATH. If an error occurs during processing or file operations,
    the function prints an error message and traceback, then exits with a nonzero
    status.
    """
    try:
        print(f"Starting search index generation")
        
        # Initialize search database
        search_db = []
        
        # Process each repository
        for repo_config in REPOSITORIES:
            process_repository(repo_config, search_db)
        
        # Deduplicate entries before writing to JSON
        search_db = deduplicate_entries(search_db)
        
        # Post-process to fix URLs
        search_db = fix_urls(search_db)
        
        # Sort the database by priority (lower numbers = higher priority)
        search_db = sorted(search_db, key=lambda x: x.get('priority', 10))
        
        # Write to JSON file in the current directory
        output_file = Path(OUTPUT_PATH)
        
        # Write to JSON file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(search_db, f, indent=2)
        
        print(f"Generated search database with {len(search_db)} entries")
        print(f"Written search database to {output_file}")
        print(f"Database sorted by priority (highest priority entries first)")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()