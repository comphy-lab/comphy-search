# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains a search index generator for the CoMPhy Lab website ecosystem. It crawls multiple repositories, extracts content from markdown and HTML files, and builds a unified JSON search database.

## Commands

**Run the search database updater:**
```bash
python3 update-database.py
```

## Architecture

The project consists of a single Python script (`update-database.py`) that:

1. **Repository Processing**: Clones or updates 10 configured repositories including:
   - comphy-project.github.io (main website)
   - comphy-lab-swc.github.io (Software Carpentry)
   - comphy-lab-blog.github.io (blog)
   - Various project documentation sites

2. **Content Extraction**: 
   - Processes `.md` and `.html` files
   - Extracts titles from YAML frontmatter or HTML tags
   - Chunks content by sections (headers or paragraphs)
   - Generates proper URLs based on repository configuration

3. **Search Index Generation**:
   - Creates entries with title, content preview, URL, and type
   - Assigns priority (2 for main pages, 1 for sections)
   - Outputs to `search_db.json` with formatted JSON

## Key Implementation Details

- Uses BeautifulSoup4 for HTML parsing
- Handles Jekyll-style YAML frontmatter
- Special URL generation logic for different repository types
- Content is chunked to ~300 characters for search previews
- Ignores files in `temp_repos/` directory during processing