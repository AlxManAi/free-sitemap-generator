"""Module for URL normalization and tracking parameter removal.

This module provides functions to normalize URLs according to SEO best practices:
- Lowercase scheme and host
- Optional www. prefix removal
- Fragment (#) removal
- Tracking parameter removal (utm_*, gclid, etc.)
- Preserving trailing slashes for CMS compatibility
"""

from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from typing import Optional


# Common tracking parameters to remove
TRACKING_PARAMS = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'gclid', 'yclid', 'fbclid', '_openstat', 'ref', 'source', 'medium',
    'campaign', 'term', 'content', 'mc_cid', 'mc_eid', '_ga', '_gid'
}

# Pagination parameters that should be preserved (not treated as tracking)
# These are common pagination parameter names used by various CMS and frameworks
PAGINATION_PARAMS = {
    'page', 'p', 'pagenum', 'pagenumber', 'pageno', 'offset', 'start',
    'per_page', 'limit', 'from', 'to', 'num', 'n', 'pg'
}


def normalize_url(
    url: str,
    strip_tracking: bool = True,
    remove_www: bool = False,
    preserve_trailing_slash: bool = True
) -> str:
    """Normalize a URL according to specified rules.
    
    Args:
        url: URL to normalize.
        strip_tracking: If True, remove tracking parameters from query string.
        remove_www: If True, remove www. prefix from host.
        preserve_trailing_slash: If True, preserve trailing slash in path.
    
    Returns:
        Normalized URL string.
    """
    if not url:
        return url
    
    # Parse URL
    parsed = urlparse(url)
    
    # Normalize scheme to lowercase
    scheme = parsed.scheme.lower() if parsed.scheme else ''
    
    # Normalize host to lowercase
    netloc = parsed.netloc.lower() if parsed.netloc else ''
    
    # Optionally remove www. prefix
    if remove_www and netloc.startswith('www.'):
        netloc = netloc[4:]
    
    # Normalize path (preserve trailing slash if needed)
    path = parsed.path
    if not preserve_trailing_slash and path.endswith('/') and len(path) > 1:
        path = path.rstrip('/')
    
    # Process query string - remove tracking parameters
    query = parsed.query
    if strip_tracking and query:
        query_params = parse_qs(query, keep_blank_values=True)
        
        # Remove tracking parameters (but preserve pagination parameters)
        filtered_params = {}
        for key, values in query_params.items():
            key_lower = key.lower()
            # Preserve pagination parameters
            if key_lower in PAGINATION_PARAMS:
                filtered_params[key] = values
            # Remove if it's a tracking parameter or starts with utm_
            elif not (key_lower in TRACKING_PARAMS or key_lower.startswith('utm_')):
                filtered_params[key] = values
        
        # Rebuild query string
        if filtered_params:
            # Reconstruct query string preserving original parameter order where possible
            query = urlencode(filtered_params, doseq=True)
        else:
            query = ''
    
    # Fragment is always removed (everything after #)
    fragment = ''
    
    # Reconstruct normalized URL
    normalized = urlunparse((scheme, netloc, path, parsed.params, query, fragment))
    
    return normalized


def normalize_for_visited(url: str, strip_tracking: bool = True, remove_www: bool = False) -> str:
    """Normalize URL for visited set comparison.
    
    This is used to determine if a URL has already been crawled.
    Removes fragments and optionally tracking parameters.
    
    Args:
        url: URL to normalize.
        strip_tracking: If True, remove tracking parameters.
        remove_www: If True, remove www. prefix.
    
    Returns:
        Normalized URL for deduplication.
    """
    return normalize_url(url, strip_tracking=strip_tracking, remove_www=remove_www, preserve_trailing_slash=True)


def normalize_for_sitemap(url: str, strip_tracking: bool = True, remove_www: bool = False) -> str:
    """Normalize URL for sitemap inclusion.
    
    This is the final normalized version that goes into the sitemap.
    Preserves trailing slashes for CMS compatibility.
    
    Args:
        url: URL to normalize.
        strip_tracking: If True, remove tracking parameters.
        remove_www: If True, remove www. prefix.
    
    Returns:
        Normalized URL for sitemap.
    """
    return normalize_url(url, strip_tracking=strip_tracking, remove_www=remove_www, preserve_trailing_slash=True)

