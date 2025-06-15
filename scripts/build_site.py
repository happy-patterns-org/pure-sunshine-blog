#!/usr/bin/env python3
"""
Custom Static Site Generator for Pure Sunshine Blog
Replaces Jekyll with a simpler, more reliable Python-based build system.
"""

import os
import json
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape
import shutil


class PureSunshineBlogBuilder:
    """Static site generator for the Pure Sunshine blog."""
    
    def __init__(self, source_dir: str = ".", output_dir: str = "_site"):
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.config = self._load_config()
        self.posts = []
        
        # Setup Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.source_dir / "templates")),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
        # Add custom Jekyll-style filters
        self.jinja_env.filters['relative_url'] = self._relative_url_filter
        
        # Setup Markdown processor
        self.md = markdown.Markdown(extensions=['meta', 'codehilite', 'toc'])
    
    def _load_config(self) -> Dict[str, Any]:
        """Load site configuration from _config.yml."""
        config_path = self.source_dir / "_config.yml"
        if not config_path.exists():
            return {}
        
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    
    def _relative_url_filter(self, url: str) -> str:
        """Custom filter to mimic Jekyll's relative_url filter."""
        baseurl = self.config.get('baseurl', '')
        if url.startswith('/'):
            return f"{baseurl}{url}"
        return f"{baseurl}/{url}"
    
    def _parse_post(self, post_path: Path) -> Dict[str, Any]:
        """Parse a markdown post file."""
        with open(post_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split frontmatter and content
        if content.startswith('---\n'):
            parts = content.split('---\n', 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1]) or {}
                markdown_content = parts[2]
            else:
                frontmatter = {}
                markdown_content = content
        else:
            frontmatter = {}
            markdown_content = content
        
        # Convert markdown to HTML
        html_content = self.md.convert(markdown_content)
        
        # Extract filename info
        filename = post_path.stem
        if filename.count('-') >= 3:
            date_part = '-'.join(filename.split('-')[:3])
            title_part = '-'.join(filename.split('-')[3:])
            try:
                post_date = datetime.strptime(date_part, '%Y-%m-%d')
            except ValueError:
                post_date = datetime.now()
        else:
            post_date = datetime.now()
            title_part = filename
        
        # Build post object
        post = {
            'title': frontmatter.get('title', title_part.replace('-', ' ').title()),
            'date': frontmatter.get('date', post_date),
            'author': frontmatter.get('author', self.config.get('author', {}).get('name', 'Dr. Happy Patterns')),
            'categories': frontmatter.get('categories', []),
            'layout': frontmatter.get('layout', 'post'),
            'content': html_content,
            'excerpt': frontmatter.get('excerpt', html_content[:200] + '...' if len(html_content) > 200 else html_content),
            'url': self._generate_post_url(post_date, title_part),
            'filename': filename,
            'frontmatter': frontmatter
        }
        
        return post
    
    def _generate_post_url(self, date: datetime, title: str) -> str:
        """Generate URL for a post based on permalink pattern."""
        permalink = self.config.get('permalink', '/:year/:month/:day/:title/')
        
        replacements = {
            ':year': str(date.year),
            ':month': f"{date.month:02d}",
            ':day': f"{date.day:02d}",
            ':title': title
        }
        
        url = permalink
        for placeholder, value in replacements.items():
            url = url.replace(placeholder, value)
        
        return url
    
    def _load_posts(self):
        """Load all posts from _posts directory."""
        posts_dir = self.source_dir / "_posts"
        if not posts_dir.exists():
            return
        
        for post_file in posts_dir.glob("*.md"):
            try:
                post = self._parse_post(post_file)
                self.posts.append(post)
            except Exception as e:
                print(f"Error parsing post {post_file}: {e}")
        
        # Sort posts by date (newest first)
        self.posts.sort(key=lambda p: p['date'], reverse=True)
    
    def _render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render a Jinja2 template with context."""
        template = self.jinja_env.get_template(template_name)
        
        # Add site config and posts to context
        full_context = {
            'site': self.config,
            'posts': self.posts,
            **context
        }
        
        return template.render(full_context)
    
    def _write_file(self, path: Path, content: str):
        """Write content to a file, creating directories as needed."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def build(self):
        """Build the complete static site."""
        print("Building Pure Sunshine Blog...")
        
        # Clean output directory
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load posts
        self._load_posts()
        print(f"Loaded {len(self.posts)} posts")
        
        # Build index page
        self._build_index()
        
        # Build static pages
        self._build_pages()
        
        # Build individual posts
        self._build_posts()
        
        # Copy assets
        self._copy_assets()
        
        # Copy telemetry data if present
        self._copy_telemetry()
        
        print(f"Site built successfully in {self.output_dir}")
    
    def _build_index(self):
        """Build the main index.html page with last-N posts and tags."""
        # Get last N posts (default 5)
        max_posts = 5
        recent_posts = self.posts[:max_posts]
        
        # Extract all unique tags from posts
        all_tags = set()
        for post in self.posts:
            categories = post.get('categories', [])
            if isinstance(categories, list):
                all_tags.update(categories)
            elif isinstance(categories, str):
                all_tags.add(categories)
        
        # Check if index.md exists for additional content
        index_content = ""
        index_frontmatter = {}
        index_path = self.source_dir / "index.md"
        if index_path.exists():
            with open(index_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse frontmatter
            if content.startswith('---\n'):
                parts = content.split('---\n', 2)
                index_frontmatter = yaml.safe_load(parts[1]) if len(parts) >= 3 else {}
                markdown_content = parts[2] if len(parts) >= 3 else content
            else:
                markdown_content = content
            
            # Convert markdown
            index_content = self.md.convert(markdown_content)
        
        # Render with index template
        rendered = self._render_template("index.html", {
            'content': index_content,
            'recent_posts': recent_posts,
            'all_tags': sorted(all_tags),
            'page': index_frontmatter,
            'max_posts': max_posts
        })
        
        self._write_file(self.output_dir / "index.html", rendered)
    
    def _build_pages(self):
        """Build static pages (about.md, posts.md, etc.)."""
        for page_file in self.source_dir.glob("*.md"):
            if page_file.name == "index.md":
                continue  # Already handled
            
            with open(page_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse frontmatter
            if content.startswith('---\n'):
                parts = content.split('---\n', 2)
                frontmatter = yaml.safe_load(parts[1]) if len(parts) >= 3 else {}
                markdown_content = parts[2] if len(parts) >= 3 else content
            else:
                frontmatter = {}
                markdown_content = content
            
            # Convert markdown
            html_content = self.md.convert(markdown_content)
            
            # Determine output path
            permalink = frontmatter.get('permalink')
            if permalink:
                if permalink.endswith('/'):
                    output_path = self.output_dir / permalink.strip('/') / "index.html"
                else:
                    output_path = self.output_dir / permalink.lstrip('/')
            else:
                output_path = self.output_dir / f"{page_file.stem}.html"
            
            # Render with layout
            layout = frontmatter.get('layout', 'page')
            rendered = self._render_template(f"{layout}.html", {
                'content': html_content,
                'page': frontmatter
            })
            
            self._write_file(output_path, rendered)
    
    def _build_posts(self):
        """Build individual post pages."""
        for post in self.posts:
            # Determine output path from URL
            url = post['url'].strip('/')
            output_path = self.output_dir / url / "index.html"
            
            # Render with post layout
            rendered = self._render_template("post.html", {
                'content': post['content'],
                'page': post,
                'post': post
            })
            
            self._write_file(output_path, rendered)
    
    def _copy_assets(self):
        """Copy asset files to output directory."""
        assets_dir = self.source_dir / "assets"
        if assets_dir.exists():
            shutil.copytree(assets_dir, self.output_dir / "assets", dirs_exist_ok=True)
    
    def _copy_telemetry(self):
        """Copy telemetry JSON files for live dashboards."""
        telemetry_patterns = ["telemetry.json", "metrics.json", "kpi.json"]
        
        for pattern in telemetry_patterns:
            for telemetry_file in self.source_dir.glob(pattern):
                shutil.copy2(telemetry_file, self.output_dir / telemetry_file.name)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Build Pure Sunshine Blog")
    parser.add_argument("--source", "-s", default=".", help="Source directory")
    parser.add_argument("--output", "-o", default="_site", help="Output directory")
    
    args = parser.parse_args()
    
    builder = PureSunshineBlogBuilder(args.source, args.output)
    builder.build()


if __name__ == "__main__":
    main()