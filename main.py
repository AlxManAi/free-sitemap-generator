"""Free Sitemap Generator - A PyQt6 desktop application for web crawling.

This module provides a GUI-based web crawler that discovers and lists all pages
within a specified domain, generating a comprehensive sitemap for SEO and
documentation purposes.
"""

import logging
import sys
import time
from typing import Set, List, Optional, Callable
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QProgressBar, QTextEdit
)
from PyQt6.QtCore import QThread, pyqtSignal

# Configuration Constants
DEFAULT_MAX_DEPTH: int = 3
DEFAULT_TIMEOUT: int = 5
DEFAULT_CRAWL_DELAY: float = 0.5  # Seconds between requests
USER_AGENT: str = 'SiteMapGeneratorBot/2.0 (+https://github.com/jtgsystems/free-sitemap-generator)'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SiteMapGeneratorApp(QWidget):
    """Main GUI application window for the Site Map Generator.

    Provides a user interface for entering URLs, initiating crawls,
    and displaying results with real-time progress updates.

    Attributes:
        thread: Optional CrawlerWorker thread for background crawling.
        url_input: QLineEdit widget for URL entry.
        generate_button: QPushButton to start crawl process.
        progress_bar: QProgressBar showing crawl progress.
        results_text_area: QTextEdit displaying discovered URLs and results.
    """

    def __init__(self) -> None:
        """Initialize the application window."""
        super().__init__()
        self.thread: Optional[CrawlerWorker] = None
        self.initUI()

    def initUI(self) -> None:
        """Initialize and configure the user interface components."""
        # Main vertical layout
        main_layout = QVBoxLayout()

        # URL Input Layout
        url_layout = QHBoxLayout()
        url_label = QLabel("URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter website URL")
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        main_layout.addLayout(url_layout)

        # Button
        self.generate_button = QPushButton("Generate Site Map")
        self.generate_button.clicked.connect(self.start_crawl_process) # Connect button
        main_layout.addWidget(self.generate_button)

        # Progress Bar
        self.progress_bar = QProgressBar()
        main_layout.addWidget(self.progress_bar)

        # Text Area for Site Map / Errors
        self.results_text_area = QTextEdit()
        self.results_text_area.setReadOnly(True) # Make it read-only for now
        main_layout.addWidget(self.results_text_area)

        self.setLayout(main_layout)
        self.setWindowTitle('Site Map Generator')
        self.setGeometry(300, 300, 600, 400) # x, y, width, height
        self.show()

    def start_crawl_process(self) -> None:
        """Validate URL input and start the crawling process in a background thread.

        Performs URL validation, initializes the crawler worker thread,
        and connects signals for real-time updates.
        """
        url_text = self.url_input.text().strip()
        parsed_url = urlparse(url_text)

        if not parsed_url.scheme or parsed_url.scheme not in ['http', 'https'] or not parsed_url.netloc:
            self.results_text_area.setText(
                "Error: Invalid URL. Please enter a full URL including "
                "http:// or https:// and a domain name (e.g., http://example.com)."
            )
            return

        # Check if a crawl is already in progress
        if self.thread is not None and self.thread.isRunning():
            self.results_text_area.append("\n⚠ Warning: A crawl is already in progress.")
            return

        url = parsed_url.geturl()  # Use the cleaned/re-assembled URL

        self.generate_button.setEnabled(False)
        self.results_text_area.clear()
        self.results_text_area.append(f"Starting crawl for: {url}\n")
        self.progress_bar.setRange(0, 0)  # Indeterminate progress

        self.thread = CrawlerWorker(url, max_depth=DEFAULT_MAX_DEPTH)
        self.thread.url_found_signal.connect(self.append_url_to_results)
        self.thread.finished_signal.connect(self.crawl_is_finished)
        self.thread.error_signal.connect(self.handle_crawl_error)
        self.thread.start()

    def append_url_to_results(self, url_str: str) -> None:
        """Append a discovered URL to the results text area.

        Args:
            url_str: The URL to append to results.
        """
        self.results_text_area.append(url_str)

    def crawl_is_finished(self, sitemap_list: List[str]) -> None:
        """Handle completion of the crawl process.

        Args:
            sitemap_list: List of discovered URLs from the crawl.
        """
        self.results_text_area.append("\n--- Crawling Finished ---")
        self.results_text_area.append(f"Found {len(sitemap_list)} unique URLs.")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.generate_button.setEnabled(True)
        logger.info(f"Crawl completed. Found {len(sitemap_list)} URLs.")

    def handle_crawl_error(self, error_msg: str) -> None:
        """Handle errors that occur during the crawl process.

        Args:
            error_msg: Error message to display to the user.
        """
        self.results_text_area.append("\n--- CRAWLING ERROR ---")
        self.results_text_area.append(f"An error occurred: {error_msg}")
        self.results_text_area.append("Please check the URL or your network connection and try again.")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.generate_button.setEnabled(True)
        logger.error(f"Crawl error: {error_msg}")

class Crawler:
    """Recursive web crawler for generating sitemaps.

    Crawls a website starting from a base URL, discovering all pages
    within the same domain up to a specified depth.

    Attributes:
        base_url: The starting URL for the crawl.
        domain: The domain (netloc) extracted from base_url.
        max_depth: Maximum recursion depth for crawling.
        visited_urls: Set of normalized URLs already crawled.
        sitemap: Set of discovered URLs (final results).
        url_callback: Optional callback function for real-time URL reporting.
        crawl_delay: Delay in seconds between requests (rate limiting).
        robot_parser: Optional RobotFileParser for robots.txt compliance.
        respect_robots_txt: Whether to check robots.txt rules.
    """

    def __init__(
        self,
        base_url: str,
        max_depth: int = 5,
        crawl_delay: float = DEFAULT_CRAWL_DELAY,
        respect_robots_txt: bool = False
    ) -> None:
        """Initialize the crawler.

        Args:
            base_url: Starting URL for crawl.
            max_depth: Maximum depth for recursive crawling (default: 5).
            crawl_delay: Delay between requests in seconds (default: 0.5).
            respect_robots_txt: Whether to respect robots.txt (default: False).
        """
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc
        self.max_depth = max_depth
        self.visited_urls: Set[str] = set()
        self.sitemap: Set[str] = set()
        self.url_callback: Optional[Callable[[str], None]] = None
        self.crawl_delay = crawl_delay
        self.respect_robots_txt = respect_robots_txt
        self.robot_parser: Optional[RobotFileParser] = None

        if self.respect_robots_txt:
            self._init_robot_parser()

    def _init_robot_parser(self) -> None:
        """Initialize robots.txt parser for the domain."""
        try:
            self.robot_parser = RobotFileParser()
            robots_url = f"{urlparse(self.base_url).scheme}://{self.domain}/robots.txt"
            self.robot_parser.set_url(robots_url)
            self.robot_parser.read()
            logger.info(f"Loaded robots.txt from {robots_url}")
        except Exception as e:
            logger.warning(f"Failed to load robots.txt: {e}. Proceeding without robots.txt compliance.")
            self.robot_parser = None

    def _can_fetch(self, url: str) -> bool:
        """Check if URL can be fetched according to robots.txt.

        Args:
            url: URL to check.

        Returns:
            True if URL can be fetched, False otherwise.
        """
        if not self.respect_robots_txt or self.robot_parser is None:
            return True
        return self.robot_parser.can_fetch(USER_AGENT, url)

    def crawl(self, url: str, current_depth: int) -> None:
        """Recursively crawl a URL and discover linked pages.

        Args:
            url: URL to crawl.
            current_depth: Current depth in the crawl tree.
        """
        if url in self.visited_urls or current_depth > self.max_depth:
            return

        # Check robots.txt compliance
        if not self._can_fetch(url):
            logger.info(f"Skipping {url} (disallowed by robots.txt)")
            return

        self.visited_urls.add(url)

        # Rate limiting - delay between requests
        if self.crawl_delay > 0 and len(self.visited_urls) > 1:
            time.sleep(self.crawl_delay)

        try:
            headers = {'User-Agent': USER_AGENT}
            response = requests.get(url, timeout=DEFAULT_TIMEOUT, headers=headers)
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code
            error_message = f"HTTP {status_code} - {e.response.reason}"
            if status_code == 403:
                error_message += " (Access forbidden)"
            elif status_code == 404:
                error_message += " (Page not found)"
            elif 400 <= status_code < 500:
                error_message += " (Client error)"
            elif 500 <= status_code < 600:
                error_message += " (Server error)"
            logger.warning(f"Error fetching {url}: {error_message}")
            return
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout fetching {url} after {DEFAULT_TIMEOUT} seconds")
            return
        except requests.exceptions.ConnectionError:
            logger.warning(f"Connection error fetching {url}")
            return
        except requests.RequestException as e:
            logger.warning(f"Request error fetching {url}: {e}")
            return

        # Check if the response content is HTML
        content_type = response.headers.get('Content-Type', '')
        if 'text/html' not in content_type:
            logger.debug(f"Skipping non-HTML content at {url} (Content-Type: {content_type})")
            return

        self.sitemap.add(url)
        if self.url_callback:
            self.url_callback(url)
        logger.debug(f"Crawled (depth {current_depth}): {url}")

        soup = BeautifulSoup(response.text, 'html.parser')

        for link in soup.find_all('a', href=True):
            href = link['href']

            # Resolve relative URLs
            absolute_url = urljoin(url, href)
            parsed_absolute_url = urlparse(absolute_url)

            # Basic validation and normalization
            if parsed_absolute_url.scheme not in ['http', 'https']:
                continue

            if parsed_absolute_url.netloc != self.domain:
                continue

            # Remove fragment and query parameters for visited check
            url_to_visit = parsed_absolute_url._replace(fragment="", query="").geturl()

            if url_to_visit not in self.visited_urls:
                self.crawl(url_to_visit, current_depth + 1)

    def get_sitemap(self) -> List[str]:
        """Start the crawl and return the discovered sitemap.

        Clears any previous crawl state, performs the crawl starting
        from the base URL, and returns a sorted list of discovered URLs.

        Returns:
            Sorted list of unique URLs discovered during the crawl.
        """
        self.visited_urls.clear()
        self.sitemap.clear()
        logger.info(f"Starting crawl from {self.base_url} (max_depth={self.max_depth})")
        self.crawl(self.base_url, 0)
        logger.info(f"Crawl completed. Found {len(self.sitemap)} URLs.")
        return sorted(list(self.sitemap))


class CrawlerWorker(QThread):
    """Background worker thread for running crawls without blocking the GUI.

    Signals:
        url_found_signal: Emitted when a URL is discovered (str).
        finished_signal: Emitted when crawl completes with sitemap (list).
        error_signal: Emitted on unexpected errors (str).
    """

    url_found_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(list)
    error_signal = pyqtSignal(str)

    def __init__(
        self,
        start_url: str,
        max_depth: int = 5,
        crawl_delay: float = DEFAULT_CRAWL_DELAY,
        respect_robots_txt: bool = False
    ) -> None:
        """Initialize the crawler worker thread.

        Args:
            start_url: Starting URL for the crawl.
            max_depth: Maximum crawl depth (default: 5).
            crawl_delay: Delay between requests in seconds (default: 0.5).
            respect_robots_txt: Whether to respect robots.txt (default: False).
        """
        super().__init__()
        self.start_url = start_url
        self.max_depth = max_depth
        self.crawl_delay = crawl_delay
        self.respect_robots_txt = respect_robots_txt
        self.crawler = Crawler(
            self.start_url,
            self.max_depth,
            self.crawl_delay,
            self.respect_robots_txt
        )

    def run(self) -> None:
        """Execute the crawl in the background thread."""
        try:
            self.crawler.url_callback = self.url_found_signal.emit
            sitemap = self.crawler.get_sitemap()
            self.finished_signal.emit(sitemap)
        except Exception as e:
            error_msg = f"Unexpected error during crawl: {type(e).__name__}: {str(e)}"
            logger.exception(f"Crawl failed: {error_msg}")
            self.error_signal.emit(error_msg)


def main() -> int:
    """Main entry point for the application.

    Returns:
        Exit code from the application.
    """
    app = QApplication(sys.argv)
    app.setApplicationName("Free Sitemap Generator")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("JTGSYSTEMS")

    window = SiteMapGeneratorApp()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
