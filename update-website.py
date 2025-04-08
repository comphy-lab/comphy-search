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
            "_teaching": "/teaching/"
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
    # Remove date prefix if present (e.g., "2025-01-21 ")
    text = re.sub(r'^\d{4}-\d{2}-\d{2}\s+', '', text)
    
    # Remove markdown link syntax if present [[text]]
    text = re.sub(r'\[\[(.*?)\]\]', r'\1', text)
    
    # Remove any other markdown formatting
    text = re.sub(r'[*_`]', '', text)
    
    # Keep special characters that are part of the title
    text = re.sub(r'[^\w\s\-\':]', '', text)
    
    # Replace spaces with +
    text = re.sub(r'\s+', '+', text)
    
    # Ensure special characters are properly encoded
    return urllib.parse.quote_plus(text)

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
    Generate a URL for a file based on repository configuration and file path
    
    Args:
        repo_config: Repository configuration dictionary
        file_path: Path to the file (Path object)
        permalink: Optional permalink from frontmatter
        
    Returns:
        Full URL to the resource
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
    
    # Default handling for other types
    path_no_ext = str(rel_path.with_suffix(''))
    return f"{base_url}/{path_no_ext}/"

# =====================================================================
# CONTENT PROCESSING FUNCTIONS
# =====================================================================

# Process a single markdown file based on repository type
def process_markdown_file(repo_config, file_path, search_db):
    print(f"  - {file_path.relative_to(get_repo_dir(repo_config))}")
    
    try:
        content = file_path.read_text(encoding='utf-8')
        front_matter, content = parse_frontmatter(content)
        
        # Get permalink if available in frontmatter
        permalink = front_matter.get('permalink')
        
        # Generate URL for this file
        url = get_file_url(repo_config, file_path, permalink)
        
        # Get title from frontmatter or filename
        title = front_matter.get('title')
        if not title:
            title = file_path.stem.replace('-', ' ').capitalize()
            
            # For blogs, remove date prefix from title if present
            if repo_config["type"] == "blog" and re.match(r'^\d{4}-\d{2}-\d{2}-', title):
                title = re.sub(r'^\d{4}-\d{2}-\d{2}-', '', title)
        
        # Get repository type for entry type
        repo_type = repo_config["type"]
        
        # Split content by headers to create individual entries
        if content.strip():
            # First, try finding headers with regex
            sections = re.split(r'^#+\s+', content, flags=re.MULTILINE)
            
            # Process content before first header (if any)
            if sections and sections[0].strip():
                clean_content = re.sub(r'<[^>]+>', ' ', sections[0])
                clean_content = re.sub(r'\s+', ' ', clean_content).strip()
                
                if len(clean_content) >= 50:
                    entry = {
                        'title': title,
                        'content': clean_content,
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
                
                # Create entry for the section
                section_title = f"{title} - {header}" if title.lower() != header.lower() else header
                entry = {
                    'title': section_title,
                    'content': clean_content,
                    'url': f"{url}#{anchor}",
                    'type': f"{repo_type}_section",
                    'priority': get_priority(repo_config, file_path)
                }
                search_db.append(entry)
                
                # Also create entries for individual paragraphs
                paragraphs = re.split(r'\n\n+', clean_content)
                for para in paragraphs:
                    para = para.strip()
                    if not para:
                        continue
                    if len(para) < 100:  # Only include substantial paragraphs
                        continue
                    if para.startswith('```') or para.startswith('<'):  # Skip code blocks and HTML
                        continue
                    
                    entry = {
                        'title': section_title,
                        'content': para,
                        'url': f"{url}#{anchor}",
                        'type': f"{repo_type}_paragraph",
                        'priority': get_priority(repo_config, file_path)
                    }
                    search_db.append(entry)
        
        # Special processing for different repository types
        if repo_config["type"] == "website":
            process_website_specific(repo_config, file_path, front_matter, content, search_db)
        elif repo_config["type"] == "blog":
            process_blog_specific(repo_config, file_path, front_matter, content, url, title, search_db)
        elif repo_config["type"] == "docs":
            process_docs_specific(repo_config, file_path, front_matter, content, search_db)
            
    except Exception as e:
        print(f"Error processing file {file_path}: {e}")

# Determine priority based on repo type and file location
def get_priority(repo_config, file_path):
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
            if dir_name in path_str:
                return priority
        
        # Root HTML files (like index.html, about.html, news.html) get medium priority
        if file_path.suffix.lower() == '.html' and len(rel_path.parts) == 1:
            return 5  # Medium priority for root HTML files
            
        # Root markdown files get medium priority
        if file_path.suffix.lower() == '.md' and len(rel_path.parts) == 1:
            return 5  # Medium priority for root markdown files
            
        # Default priority for other website content
        return 6
            
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
    
    # Research content specific processing
    elif "_research/" in path_str:
        # Process paper entries (h3 tags with ids)
        soup = BeautifulSoup(content, 'html.parser')
        h3_tags = soup.find_all('h3')
        
        for h3 in h3_tags:
            if 'id' not in h3.attrs:
                continue
                
            id_attr = h3['id']
            
            # Try to extract paper number and title
            match = re.match(r'\[([\d]+)\](.*)', h3.text)
            if not match:
                continue
                
            number, title = match.groups()
            
            # Find content until next h3 or end
            section_content = ''
            current = h3.next_sibling
            while current and (not hasattr(current, 'name') or current.name != 'h3'):
                if hasattr(current, 'string') and current.string:
                    section_content += str(current)
                elif hasattr(current, 'get_text'):
                    section_content += current.get_text()
                current = current.next_sibling
            
            # Extract tags
            tags = []
            tag_match = re.search(r'<tags>(.*?)</tags>', section_content, re.DOTALL)
            if tag_match:
                tag_content = tag_match.group(1)
                tags = re.findall(r'<span>(.*?)</span>', tag_content)
            
            # Clean HTML tags for content
            clean_content = re.sub(r'<[^>]+>', ' ', section_content)
            clean_content = re.sub(r'\s+', ' ', clean_content).strip()
            
            # Get permalink from frontmatter or default
            permalink = front_matter.get('permalink', '/research/')
            
            # Create entry for paper
            entry = {
                'title': f"[{number}]{title.strip()}",
                'content': clean_content,
                'url': f"{repo_config['url']}{permalink}#{id_attr}",
                'type': 'paper',
                'tags': tags,
                'priority': 3  # Medium priority for papers
            }
            search_db.append(entry)
            
            # Check if this is a featured paper
            if 'Featured' in tags:
                # Boost priority for featured papers
                entry['priority'] = 2
    
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
                    'priority': 2  # Medium-high priority for teaching content
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
def process_repository(repo_config, search_db):
    repo_dir = get_repo_dir(repo_config)
    
    print(f"Processing {repo_config['type']} repository at {repo_dir}")
    
    # Clone or update the repository
    if not clone_or_update_repo(repo_config):
        print(f"Failed to clone or update repository: {repo_config['repo_url']}")
        return
    
    if not repo_dir.exists():
        print(f"Repository directory not found: {repo_dir}")
        return
    
    # Get all markdown files in the repository
    if repo_config["type"] == "blog" and repo_config.get("blog_settings", {}).get("post_dir"):
        # For blogs with posts directory structure
        post_dir = repo_dir / repo_config["blog_settings"]["post_dir"]
        if post_dir.exists():
            md_files = list(post_dir.glob('**/*.md'))
        else:
            # Fallback to searching all markdown files
            md_files = list(repo_dir.glob('**/*.md'))
    else:
        # For other repository types, get all markdown files
        md_files = list(repo_dir.glob('**/*.md'))
    
    # Filter out README.md files and other files to skip
    md_files = [f for f in md_files if f.name.lower() != 'readme.md']
    
    print(f"Found {len(md_files)} markdown files to process")
    
    # Process each markdown file
    for file_path in md_files:
        process_markdown_file(repo_config, file_path, search_db)
    
    # For website repositories, also process HTML files in the root directory
    if repo_config["type"] == "website":
        html_files = list(repo_dir.glob('*.html'))
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

def main():
    try:
        print(f"Starting search index generation")
        
        # Initialize search database
        search_db = []
        
        # Process each repository
        for repo_config in REPOSITORIES:
            process_repository(repo_config, search_db)
        
        # Write to JSON file in the current directory
        output_file = Path(OUTPUT_PATH)
        
        # Write to JSON file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(search_db, f, indent=2)
        
        print(f"Generated search database with {len(search_db)} entries")
        print(f"Written search database to {output_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

if __name__ == "__main__":
    main()