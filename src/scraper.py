"""
Website scraper module for extracting content from URLs.
Handles recursive crawling with depth control and image extraction.
"""

import re
import logging
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Set, Optional, Tuple

import requests
from bs4 import BeautifulSoup
import validators

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WebScraper:
    """Scraper that extracts content from websites and handles recursive crawling."""
    
    def __init__(self, max_depth: int = 2, max_pages: int = 50, timeout: int = 10):
        """
        Initialize the scraper with configuration parameters.
        
        Args:
            max_depth: Maximum depth for recursive scraping (default: 2)
            max_pages: Maximum number of pages to scrape (default: 50)
            timeout: Request timeout in seconds (default: 10)
        """
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.timeout = timeout
        self.visited_urls: Set[str] = set()
        self.pages_scraped = 0
        
        # Headers to mimic a browser request
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL by removing fragments and trailing slashes."""
        parsed = urlparse(url)
        # Remove fragments and normalize
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        # Remove trailing slash if present
        if normalized.endswith('/'):
            normalized = normalized[:-1]
        return normalized
    
    def _is_valid_url(self, url: str, base_domain: str) -> bool:
        """Check if URL is valid and belongs to the same domain."""
        if not url or not validators.url(url):
            return False
        
        # Check if URL belongs to the same domain
        parsed_url = urlparse(url)
        parsed_base = urlparse(base_domain)
        
        return parsed_url.netloc == parsed_base.netloc
    
    def _extract_text_content(self, soup: BeautifulSoup) -> str:
        """Extract clean text content from HTML."""
        # Remove script and style elements
        for element in soup(["script", "style", "header", "footer", "nav"]):
            element.decompose()
        
        # Get text and normalize whitespace
        text = soup.get_text(separator=' ')
        # Remove extra whitespace and normalize
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """Extract all links from the page."""
        links = []
        base_domain = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
        
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            # Create absolute URL
            abs_url = urljoin(base_url, href)
            # Validate URL
            if self._is_valid_url(abs_url, base_domain):
                normalized_url = self._normalize_url(abs_url)
                links.append(normalized_url)
        
        return links
    
    def _extract_images(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """Extract all images from the page with their attributes."""
        images = []
        
        for img_tag in soup.find_all('img'):
            # Skip if no src attribute
            if not img_tag.get('src'):
                continue
                
            # Create absolute URL for image source
            src = img_tag['src']
            abs_src = urljoin(base_url, src)
            
            # Skip data URIs and invalid URLs
            if abs_src.startswith('data:') or not validators.url(abs_src):
                continue
                
            # Extract image attributes
            image_info = {
                'src': abs_src,
                'alt': img_tag.get('alt', ''),
                'width': img_tag.get('width', ''),
                'height': img_tag.get('height', ''),
                'title': img_tag.get('title', '')
            }
            
            images.append(image_info)
        
        return images
    
    def _extract_structured_data(self, soup: BeautifulSoup) -> Dict:
        """Extract structured data like meta tags."""
        structured_data = {}
        
        # Extract title
        title_tag = soup.find('title')
        if title_tag:
            structured_data['title'] = title_tag.text.strip()
        
        # Extract meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            structured_data['description'] = meta_desc['content'].strip()
        
        # Convert heading lists to comma-separated strings instead of nested dictionaries
        for i in range(1, 7):
            h_tags = soup.find_all(f'h{i}')
            if h_tags:
                # Join the headings into a single string instead of keeping as a list
                heading_text = ", ".join([tag.text.strip() for tag in h_tags])
                structured_data[f'h{i}_headings'] = heading_text
        
        return structured_data
    
    def _fetch_page(self, url: str) -> Optional[Tuple[str, BeautifulSoup]]:
        """Fetch a webpage and return its content."""
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            
            # Check if content is HTML
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type.lower():
                logger.warning(f"Skipping non-HTML content at {url}")
                return None
            
            html_content = response.text
            soup = BeautifulSoup(html_content, 'html5lib')
            return html_content, soup
            
        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return None
    
    def scrape_url(self, start_url: str) -> List[Dict]:
        """
        Scrape content from the given URL and its linked pages.
        
        Args:
            start_url: The URL to start scraping from
            
        Returns:
            List of dictionaries containing scraped content
        """
        if not validators.url(start_url):
            raise ValueError(f"Invalid URL: {start_url}")
        
        # Reset state for new scraping job
        self.visited_urls = set()
        self.pages_scraped = 0
        
        # Normalize the starting URL
        start_url = self._normalize_url(start_url)
        base_domain = f"{urlparse(start_url).scheme}://{urlparse(start_url).netloc}"
        
        # Initialize results list
        results = []
        
        # Queue for BFS (breadth-first search)
        queue = [(start_url, 0)]  # (url, depth)
        
        # Scrape pages breadth-first
        while queue and self.pages_scraped < self.max_pages:
            url, depth = queue.pop(0)
            
            # Skip if already visited or exceeds max depth
            if url in self.visited_urls or depth > self.max_depth:
                continue
            
            # Mark as visited
            self.visited_urls.add(url)
            
            # Fetch page content
            page_data = self._fetch_page(url)
            if not page_data:
                continue
                
            html_content, soup = page_data
            self.pages_scraped += 1
            
            # Extract content
            text_content = self._extract_text_content(soup)
            structured_data = self._extract_structured_data(soup)
            
            # Extract images - NEW
            images = self._extract_images(soup, url)
            
            # Create document
            document = {
                'url': url,
                'content': text_content,
                'images': images,  # Added images
                'metadata': {
                    **structured_data,
                    'depth': depth,
                    'html_length': len(html_content),
                    'image_count': len(images)  # Added image count
                }
            }
            
            results.append(document)
            logger.info(f"Scraped {url} (Page {self.pages_scraped}/{self.max_pages}, Images: {len(images)})")
            
            # Don't crawl deeper if at max depth
            if depth >= self.max_depth:
                continue
                
            # Add links to queue for next depth
            links = self._extract_links(soup, url)
            for link in links:
                if link not in self.visited_urls:
                    queue.append((link, depth + 1))
        
        logger.info(f"Scraping completed. Visited {len(self.visited_urls)} URLs, scraped {self.pages_scraped} pages.")
        return results