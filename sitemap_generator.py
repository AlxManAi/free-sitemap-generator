"""Module for generating XML sitemaps and text URL lists.

This module provides functions to convert lists of URLs into:
- XML sitemap format (Google standard)
- Plain text format (one URL per line)
"""

from datetime import datetime
from typing import List
from xml.etree.ElementTree import Element, tostring
from xml.dom import minidom


def generate_sitemap_xml(urls: List[str]) -> str:
    """Generate XML sitemap from a list of URLs.
    
    Creates a valid XML sitemap according to Google's sitemap protocol.
    Each URL entry includes <loc> and optionally <lastmod>, <changefreq>, <priority>.
    
    Args:
        urls: List of URLs to include in the sitemap.
    
    Returns:
        String containing the XML sitemap.
    """
    # Create root element with namespace
    urlset = Element('urlset')
    urlset.set('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')
    
    # Get current date for lastmod
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    # Add each URL to the sitemap
    for url in sorted(urls):
        url_elem = Element('url')
        
        # Location (required)
        loc = Element('loc')
        loc.text = url
        url_elem.append(loc)
        
        # Last modification date (optional, but recommended)
        lastmod = Element('lastmod')
        lastmod.text = current_date
        url_elem.append(lastmod)
        
        # Change frequency (optional)
        changefreq = Element('changefreq')
        changefreq.text = 'weekly'  # Default value
        url_elem.append(changefreq)
        
        # Priority (optional)
        priority = Element('priority')
        priority.text = '0.8'  # Default value
        url_elem.append(priority)
        
        urlset.append(url_elem)
    
    # Convert to string with proper formatting
    rough_string = tostring(urlset, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    
    # Return pretty-printed XML
    return reparsed.toprettyxml(indent='  ')


def urls_to_text(urls: List[str]) -> str:
    """Convert a list of URLs to a plain text format.
    
    Each URL is placed on a separate line, sorted alphabetically.
    
    Args:
        urls: List of URLs to convert.
    
    Returns:
        String with one URL per line.
    """
    return '\n'.join(sorted(urls))

