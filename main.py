"""ALX Sitemap Generator - A PyQt6 desktop application for web crawling.

This module provides a GUI-based web crawler that discovers and lists all pages
within a specified domain, generating a comprehensive sitemap for SEO and
documentation purposes.
"""

import logging
import os
import sys
import time
from typing import Set, List, Optional, Callable
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QProgressBar, QTextEdit,
    QGroupBox, QSpinBox, QTabWidget, QMessageBox, QFileDialog, QCheckBox
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QClipboard

from sitemap_generator import generate_sitemap_xml, urls_to_text
from url_normalizer import normalize_for_visited, normalize_for_sitemap

# Configuration Constants
DEFAULT_MAX_DEPTH: int = 5
DEFAULT_MAX_URLS: int = 10000
DEFAULT_TIMEOUT: int = 5
DEFAULT_CRAWL_DELAY: float = 0.5  # Seconds between requests
USER_AGENT: str = 'SiteMapGeneratorBot/2.0 (+https://github.com/AlxManAi/free-sitemap-generator)'

# Configure logging
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    handlers=[
        logging.StreamHandler(),  # Console output
        logging.FileHandler('sitemap_generator.log', encoding='utf-8')  # File output
    ]
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
        sitemap_urls: List of discovered URLs from the last crawl.
        crawl_start_time: Timestamp when crawl started.
        max_depth_reached: Maximum depth actually reached during crawl.
    """

    def __init__(self) -> None:
        """Initialize the application window."""
        super().__init__()
        self.thread: Optional[CrawlerWorker] = None
        self.sitemap_urls: List[str] = []
        self.crawl_start_time: float = 0.0
        self.max_depth_reached: int = 0
        self.start_url: str = ""
        self.initUI()
        self.load_theme()

    def load_theme(self) -> None:
        """Load dark theme from QSS file."""
        # In PyInstaller bundle, look for theme in sys._MEIPASS first
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Running as compiled executable
            base_path = sys._MEIPASS
        else:
            # Running as script
            base_path = os.path.dirname(__file__)
        
        theme_path = os.path.join(base_path, 'dark_theme.qss')
        if os.path.exists(theme_path):
            try:
                with open(theme_path, 'r', encoding='utf-8') as f:
                    self.setStyleSheet(f.read())
                logger.info(f"Theme loaded from: {theme_path}")
            except Exception as e:
                logger.warning(f"Failed to load theme: {e}")
        else:
            logger.warning(f"Theme file not found at: {theme_path}")

    def initUI(self) -> None:
        """Initialize and configure the user interface components."""
        # Main vertical layout
        main_layout = QVBoxLayout()
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # URL Input Layout
        url_layout = QHBoxLayout()
        url_label = QLabel("URL:")
        url_label.setMinimumWidth(50)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Enter website URL (e.g., https://example.com)")
        self.generate_button = QPushButton("Start Crawl")
        self.generate_button.setMinimumWidth(120)
        self.generate_button.clicked.connect(self.start_crawl_process)
        self.stop_button = QPushButton("Stop Crawl")
        self.stop_button.setMinimumWidth(120)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_crawl_process)
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        url_layout.addWidget(self.generate_button)
        url_layout.addWidget(self.stop_button)
        main_layout.addLayout(url_layout)

        # Crawler Settings Group
        settings_group = QGroupBox("Crawler Settings")
        settings_layout = QHBoxLayout()
        
        # Max Depth
        depth_layout = QVBoxLayout()
        depth_label = QLabel("Max Depth:")
        self.max_depth_spin = QSpinBox()
        self.max_depth_spin.setMinimum(1)
        self.max_depth_spin.setMaximum(20)
        self.max_depth_spin.setValue(DEFAULT_MAX_DEPTH)
        depth_layout.addWidget(depth_label)
        depth_layout.addWidget(self.max_depth_spin)
        
        # Max URLs
        max_urls_layout = QVBoxLayout()
        max_urls_label = QLabel("Max URLs:")
        self.max_urls_spin = QSpinBox()
        self.max_urls_spin.setMinimum(0)
        self.max_urls_spin.setMaximum(1000000)
        self.max_urls_spin.setValue(DEFAULT_MAX_URLS)
        self.max_urls_spin.setSpecialValueText("Unlimited")
        max_urls_layout.addWidget(max_urls_label)
        max_urls_layout.addWidget(self.max_urls_spin)
        
        # Exclude Substrings
        exclude_layout = QVBoxLayout()
        exclude_label = QLabel("Exclude (substrings):")
        self.exclude_input = QLineEdit()
        self.exclude_input.setPlaceholderText("?utm_, /cart, /login (comma-separated)")
        exclude_layout.addWidget(exclude_label)
        exclude_layout.addWidget(self.exclude_input)
        
        # Strip tracking params checkbox
        self.strip_tracking_checkbox = QCheckBox("Strip tracking params (utm, gclid, yclid...)")
        self.strip_tracking_checkbox.setChecked(True)  # Enabled by default
        
        settings_layout.addLayout(depth_layout)
        settings_layout.addLayout(max_urls_layout)
        settings_layout.addLayout(exclude_layout)
        settings_layout.addStretch()
        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)
        main_layout.addWidget(self.strip_tracking_checkbox)

        # Tab Widget
        self.tab_widget = QTabWidget()
        
        # Log/Preview Tab
        self.log_text_area = QTextEdit()
        self.log_text_area.setReadOnly(True)
        self.tab_widget.addTab(self.log_text_area, "Log / Preview")
        
        # Stats Tab
        self.stats_text_area = QTextEdit()
        self.stats_text_area.setReadOnly(True)
        self.tab_widget.addTab(self.stats_text_area, "Stats")
        
        main_layout.addWidget(self.tab_widget)

        # Progress Bar with status label
        progress_layout = QVBoxLayout()
        self.progress_label = QLabel("Ready")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        main_layout.addLayout(progress_layout)

        # Export Buttons Layout
        export_layout = QHBoxLayout()
        export_layout.addStretch()
        
        self.save_xml_button = QPushButton("Save sitemap.xml")
        self.save_xml_button.setEnabled(False)
        self.save_xml_button.clicked.connect(self.save_sitemap_xml)
        
        self.save_txt_button = QPushButton("Save URLs list (.txt)")
        self.save_txt_button.setEnabled(False)
        self.save_txt_button.clicked.connect(self.save_urls_list)
        
        self.copy_clipboard_button = QPushButton("Copy URLs to clipboard")
        self.copy_clipboard_button.setEnabled(False)
        self.copy_clipboard_button.clicked.connect(self.copy_urls_to_clipboard)
        
        export_layout.addWidget(self.save_xml_button)
        export_layout.addWidget(self.save_txt_button)
        export_layout.addWidget(self.copy_clipboard_button)
        main_layout.addLayout(export_layout)

        self.setLayout(main_layout)
        self.setWindowTitle('ALX Sitemap Generator')
        self.setGeometry(300, 300, 900, 700)
        self.show()

    def start_crawl_process(self) -> None:
        """Validate URL input and start the crawling process in a background thread.

        Performs URL validation, initializes the crawler worker thread,
        and connects signals for real-time updates.
        """
        url_text = self.url_input.text().strip()
        parsed_url = urlparse(url_text)

        if not parsed_url.scheme or parsed_url.scheme not in ['http', 'https'] or not parsed_url.netloc:
            QMessageBox.warning(
                self,
                "Invalid URL",
                "Please enter a full URL including http:// or https:// and a domain name\n"
                "(e.g., https://example.com)"
            )
            return

        # Check if a crawl is already in progress
        if self.thread is not None and self.thread.isRunning():
            QMessageBox.warning(self, "Crawl in Progress", "A crawl is already in progress.")
            return

        url = parsed_url.geturl()  # Use the cleaned/re-assembled URL
        self.start_url = url

        # Get settings from UI
        max_depth = self.max_depth_spin.value()
        max_urls = self.max_urls_spin.value() if self.max_urls_spin.value() > 0 else 0
        exclude_text = self.exclude_input.text().strip()
        exclude_substrings = [s.strip() for s in exclude_text.split(',') if s.strip()] if exclude_text else []
        strip_tracking = self.strip_tracking_checkbox.isChecked()

        # Block UI elements
        self.url_input.setEnabled(False)
        self.generate_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.max_depth_spin.setEnabled(False)
        self.max_urls_spin.setEnabled(False)
        self.exclude_input.setEnabled(False)
        self.strip_tracking_checkbox.setEnabled(False)
        self.save_xml_button.setEnabled(False)
        self.save_txt_button.setEnabled(False)
        self.copy_clipboard_button.setEnabled(False)

        # Clear previous results
        self.sitemap_urls = []
        self.log_text_area.clear()
        self.stats_text_area.clear()
        self.crawl_start_time = time.time()
        self.max_depth_reached = 0

        # Update UI
        self.log_text_area.append(f"Starting crawl for: {url}")
        self.log_text_area.append(f"Settings: Max Depth={max_depth}, Max URLs={'Unlimited' if max_urls == 0 else max_urls}, Exclude={exclude_substrings if exclude_substrings else 'None'}, Strip Tracking={strip_tracking}\n")
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.progress_label.setText("Crawling...")

        # Start crawler
        self.thread = CrawlerWorker(
            url,
            max_depth=max_depth,
            max_urls=max_urls,
            exclude_substrings=exclude_substrings,
            strip_tracking=strip_tracking
        )
        self.thread.url_found_signal.connect(self.append_url_to_results)
        self.thread.finished_signal.connect(self.crawl_is_finished)
        self.thread.error_signal.connect(self.handle_crawl_error)
        self.thread.start()

    def append_url_to_results(self, url_str: str) -> None:
        """Append a discovered URL to the results text area.

        Args:
            url_str: The URL to append to results.
        """
        self.log_text_area.append(url_str)
        # Count URLs from log (more reliable than tracking separately)
        # Simple approach: count lines that look like URLs
        text = self.log_text_area.toPlainText()
        url_count = sum(1 for line in text.split('\n') 
                       if line.strip() and (line.startswith('http://') or line.startswith('https://')))
        self.progress_label.setText(f"Found {url_count} URLs...")

    def crawl_is_finished(self, sitemap_list: List[str]) -> None:
        """Handle completion of the crawl process.

        Args:
            sitemap_list: List of discovered URLs from the crawl.
        """
        self.sitemap_urls = sitemap_list
        # Update progress label with final count
        self.progress_label.setText(f"Found {len(sitemap_list)} URLs")
        elapsed_time = time.time() - self.crawl_start_time
        
        # Get stats from crawler
        crawler_stats = self.thread.crawler.stats if self.thread and hasattr(self.thread, 'crawler') else {}
        
        # Update log
        self.log_text_area.append("\n--- Crawling Finished ---")
        self.log_text_area.append(f"Found {len(sitemap_list)} unique URLs.")
        self.log_text_area.append(f"Time elapsed: {elapsed_time:.2f} seconds")

        # Update stats
        self.update_stats_tab(elapsed_time, crawler_stats)

        # Update progress bar
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_label.setText(f"Completed! Found {len(sitemap_list)} URLs in {elapsed_time:.1f}s")

        # Unblock UI elements
        self.url_input.setEnabled(True)
        self.generate_button.setEnabled(True)
        self.max_depth_spin.setEnabled(True)
        self.max_urls_spin.setEnabled(True)
        self.exclude_input.setEnabled(True)
        self.strip_tracking_checkbox.setEnabled(True)

        # Enable export buttons if we have URLs
        if len(sitemap_list) > 0:
            self.save_xml_button.setEnabled(True)
            self.save_txt_button.setEnabled(True)
            self.copy_clipboard_button.setEnabled(True)

        logger.info(f"Crawl completed. Found {len(sitemap_list)} URLs in {elapsed_time:.2f} seconds.")

    def update_stats_tab(self, elapsed_time: float, crawler_stats: Optional[dict] = None) -> None:
        """Update the stats tab with crawl statistics.

        Args:
            elapsed_time: Time elapsed during crawl in seconds.
            crawler_stats: Dictionary with crawler statistics.
        """
        if crawler_stats is None:
            crawler_stats = {}
        
        exclude_filters = ', '.join([s.strip() for s in self.exclude_input.text().split(',') if s.strip()]) if self.exclude_input.text().strip() else 'None'
        strip_tracking = "Yes" if self.strip_tracking_checkbox.isChecked() else "No"
        
        filtered_total = (
            crawler_stats.get('filtered_by_exclude', 0) +
            crawler_stats.get('filtered_by_tracking', 0) +
            crawler_stats.get('filtered_by_depth', 0) +
            crawler_stats.get('non_200_status', 0)
        )
        
        stats_text = f"""<h3>Crawl Statistics</h3>
<p><b>Start URL:</b> {self.start_url}</p>
<p><b>Total URLs Found:</b> {len(self.sitemap_urls)}</p>
<p><b>Max Depth Setting:</b> {self.max_depth_spin.value()}</p>
<p><b>Max URLs Setting:</b> {'Unlimited' if self.max_urls_spin.value() == 0 else self.max_urls_spin.value()}</p>
<p><b>Exclude Filters:</b> {exclude_filters}</p>
<p><b>Strip Tracking Params:</b> {strip_tracking}</p>
<p><b>Time Elapsed:</b> {elapsed_time:.2f} seconds</p>
<hr>
<h4>Filtered URLs</h4>
<p><b>Filtered by Exclude:</b> {crawler_stats.get('filtered_by_exclude', 0)}</p>
<p><b>Filtered by Tracking Params:</b> {crawler_stats.get('filtered_by_tracking', 0)}</p>
<p><b>Filtered by Max Depth:</b> {crawler_stats.get('filtered_by_depth', 0)}</p>
<p><b>Non-200 Status Codes:</b> {crawler_stats.get('non_200_status', 0)}</p>
<p><b>Total Filtered:</b> {filtered_total}</p>
"""
        self.stats_text_area.setHtml(stats_text)

    def handle_crawl_error(self, error_msg: str) -> None:
        """Handle errors that occur during the crawl process.

        Args:
            error_msg: Error message to display to the user.
        """
        self.log_text_area.append("\n--- CRAWLING ERROR ---")
        self.log_text_area.append(f"An error occurred: {error_msg}")
        self.log_text_area.append("Please check the URL or your network connection and try again.")
        
        QMessageBox.critical(
            self,
            "Crawl Error",
            f"An error occurred during crawling:\n\n{error_msg}\n\n"
            "Please check the URL or your network connection and try again."
        )
        
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Error occurred")
        
        # Unblock UI elements
        self.url_input.setEnabled(True)
        self.generate_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.max_depth_spin.setEnabled(True)
        self.max_urls_spin.setEnabled(True)
        self.exclude_input.setEnabled(True)
        self.strip_tracking_checkbox.setEnabled(True)
        
        logger.error(f"Crawl error: {error_msg}")
    
    def stop_crawl_process(self) -> None:
        """Stop the current crawling process."""
        if self.thread is not None and self.thread.isRunning():
            if hasattr(self.thread, 'crawler') and self.thread.crawler:
                self.thread.crawler.should_stop = True
            self.log_text_area.append("\n--- Stopping crawl (please wait) ---")
            self.progress_label.setText("Stopping...")
            logger.info("User requested crawl stop")

    def save_sitemap_xml(self) -> None:
        """Save sitemap as XML file."""
        if not self.sitemap_urls:
            QMessageBox.warning(self, "No URLs", "No URLs to save. Please run a crawl first.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Sitemap XML",
            "sitemap.xml",
            "XML Files (*.xml);;All Files (*)"
        )

        if file_path:
            try:
                xml_content = generate_sitemap_xml(self.sitemap_urls)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(xml_content)
                QMessageBox.information(self, "Success", f"Sitemap saved to:\n{file_path}")
                logger.info(f"Sitemap XML saved to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save sitemap:\n{str(e)}")
                logger.error(f"Failed to save sitemap: {e}")

    def save_urls_list(self) -> None:
        """Save URLs as plain text file."""
        if not self.sitemap_urls:
            QMessageBox.warning(self, "No URLs", "No URLs to save. Please run a crawl first.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save URLs List",
            "urls.txt",
            "Text Files (*.txt);;All Files (*)"
        )

        if file_path:
            try:
                text_content = urls_to_text(self.sitemap_urls)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(text_content)
                QMessageBox.information(self, "Success", f"URLs list saved to:\n{file_path}")
                logger.info(f"URLs list saved to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save URLs list:\n{str(e)}")
                logger.error(f"Failed to save URLs list: {e}")

    def copy_urls_to_clipboard(self) -> None:
        """Copy URLs list to clipboard."""
        if not self.sitemap_urls:
            QMessageBox.warning(self, "No URLs", "No URLs to copy. Please run a crawl first.")
            return

        try:
            text_content = urls_to_text(self.sitemap_urls)
            clipboard = QApplication.clipboard()
            clipboard.setText(text_content)
            QMessageBox.information(self, "Success", f"Copied {len(self.sitemap_urls)} URLs to clipboard.")
            logger.info(f"Copied {len(self.sitemap_urls)} URLs to clipboard")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to copy to clipboard:\n{str(e)}")
            logger.error(f"Failed to copy to clipboard: {e}")

class Crawler:
    """Recursive web crawler for generating sitemaps.

    Crawls a website starting from a base URL, discovering all pages
    within the same domain up to a specified depth.

    Attributes:
        base_url: The starting URL for the crawl.
        domain: The domain (netloc) extracted from base_url.
        max_depth: Maximum recursion depth for crawling.
        max_urls: Maximum number of URLs to collect (0 = unlimited).
        exclude_substrings: List of substrings to exclude from crawling.
        strip_tracking: Whether to strip tracking parameters from URLs.
        visited_urls: Set of normalized URLs already crawled.
        sitemap: Set of discovered URLs (final results).
        url_callback: Optional callback function for real-time URL reporting.
        crawl_delay: Delay in seconds between requests (rate limiting).
        robot_parser: Optional RobotFileParser for robots.txt compliance.
        respect_robots_txt: Whether to check robots.txt rules.
        should_stop: Flag to indicate if crawling should stop (e.g., max_urls reached).
        stats: Dictionary with crawl statistics.
    """

    def __init__(
        self,
        base_url: str,
        max_depth: int = 5,
        max_urls: int = 0,
        exclude_substrings: Optional[List[str]] = None,
        strip_tracking: bool = True,
        crawl_delay: float = DEFAULT_CRAWL_DELAY,
        respect_robots_txt: bool = False
    ) -> None:
        """Initialize the crawler.

        Args:
            base_url: Starting URL for crawl.
            max_depth: Maximum depth for recursive crawling (default: 5).
            max_urls: Maximum number of URLs to collect, 0 = unlimited (default: 0).
            exclude_substrings: List of substrings to exclude from URLs (default: None).
            strip_tracking: Whether to strip tracking parameters (default: True).
            crawl_delay: Delay between requests in seconds (default: 0.5).
            respect_robots_txt: Whether to respect robots.txt (default: False).
        """
        # Normalize base URL
        parsed_base = urlparse(base_url)
        self.base_url = base_url
        self.domain = parsed_base.netloc.lower()  # Store normalized domain
        self.max_depth = max_depth
        self.max_urls = max_urls
        self.exclude_substrings = exclude_substrings or []
        self.strip_tracking = strip_tracking
        self.visited_urls: Set[str] = set()
        self.sitemap: Set[str] = set()
        self.url_callback: Optional[Callable[[str], None]] = None
        self.crawl_delay = crawl_delay
        self.respect_robots_txt = respect_robots_txt
        self.robot_parser: Optional[RobotFileParser] = None
        self.should_stop = False
        # Create session for connection reuse
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
        self.stats = {
            'filtered_by_exclude': 0,
            'filtered_by_tracking': 0,
            'filtered_by_depth': 0,
            'filtered_by_max_urls': 0,
            'non_200_status': 0
        }

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

    def _should_exclude_url(self, url: str) -> bool:
        """Check if URL should be excluded based on exclude_substrings.

        Args:
            url: URL to check.

        Returns:
            True if URL should be excluded, False otherwise.
        """
        if not self.exclude_substrings:
            return False
        return any(substring in url for substring in self.exclude_substrings)

    def crawl(self, url: str, current_depth: int) -> None:
        """Recursively crawl a URL and discover linked pages.

        Args:
            url: URL to crawl.
            current_depth: Current depth in the crawl tree.
        """
        # Check if we should stop (max_urls reached)
        if self.should_stop:
            return

        # Normalize URL for visited check
        normalized_for_visited = normalize_for_visited(url, strip_tracking=self.strip_tracking)
        
        if normalized_for_visited in self.visited_urls or current_depth > self.max_depth:
            if current_depth > self.max_depth:
                self.stats['filtered_by_depth'] += 1
            return

        # Check exclude filter (before normalization to catch all variants)
        if self._should_exclude_url(url):
            self.stats['filtered_by_exclude'] += 1
            logger.debug(f"Skipping {url} (matches exclude filter)")
            return

        # Check robots.txt compliance
        if not self._can_fetch(url):
            logger.info(f"Skipping {url} (disallowed by robots.txt)")
            return

        self.visited_urls.add(normalized_for_visited)

        # Check max_urls limit before making request
        if self.max_urls > 0 and len(self.sitemap) >= self.max_urls:
            self.should_stop = True
            logger.info(f"Reached max_urls limit ({self.max_urls}). Stopping crawl.")
            return

        # Rate limiting - delay between requests
        if self.crawl_delay > 0 and len(self.visited_urls) > 1:
            time.sleep(self.crawl_delay)

        # Retry logic for temporary errors
        max_retries = 3
        retry_delay = 1.0  # Start with 1 second
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=DEFAULT_TIMEOUT)
                response.encoding = response.apparent_encoding  # Auto-detect encoding
                response.raise_for_status()
                break  # Success, exit retry loop
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.info(f"Retry {attempt + 1}/{max_retries} for {url} after {wait_time:.1f}s")
                    time.sleep(wait_time)
                    continue
                else:
                    # Last attempt failed
                    logger.warning(f"Failed to fetch {url} after {max_retries} attempts: {e}")
                    return
            except requests.exceptions.HTTPError as e:
                # Don't retry HTTP errors (4xx, 5xx), but log them
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
                self.stats['non_200_status'] += 1
                return
        
        # Check if we got a response (should always be true after successful retry loop)
        if 'response' not in locals():
            return  # Failed all retries
        
        # Explicitly check for status code 200
        if response.status_code != 200:
            self.stats['non_200_status'] += 1
            logger.warning(f"Skipping {url} (status code: {response.status_code})")
            return

        # Check if the response content is HTML
        content_type = response.headers.get('Content-Type', '')
        if 'text/html' not in content_type:
            logger.debug(f"Skipping non-HTML content at {url} (Content-Type: {content_type})")
            return

        # Check max_urls limit after successful fetch
        if self.max_urls > 0 and len(self.sitemap) >= self.max_urls:
            self.should_stop = True
            self.stats['filtered_by_max_urls'] += 1
            logger.info(f"Reached max_urls limit ({self.max_urls}). Stopping crawl.")
            return

        # Normalize URL for sitemap (preserves trailing slash, removes tracking params if enabled)
        normalized_for_sitemap = normalize_for_sitemap(url, strip_tracking=self.strip_tracking)
        self.sitemap.add(normalized_for_sitemap)
        if self.url_callback:
            self.url_callback(normalized_for_sitemap)
        logger.debug(f"Crawled (depth {current_depth}): {normalized_for_sitemap}")

        # Stop if max_urls reached
        if self.should_stop:
            return

        soup = BeautifulSoup(response.text, 'html.parser')

        for link in soup.find_all('a', href=True):
            # Stop if max_urls reached
            if self.should_stop:
                break
                
            href = link['href']

            # Resolve relative URLs
            absolute_url = urljoin(url, href)
            parsed_absolute_url = urlparse(absolute_url)

            # Basic validation
            if parsed_absolute_url.scheme not in ['http', 'https']:
                continue

            # Normalize netloc for comparison (lowercase, optionally remove www)
            netloc_normalized = parsed_absolute_url.netloc.lower()
            if netloc_normalized.startswith('www.') and self.domain.startswith('www.'):
                # Both have www, compare as is
                pass
            elif netloc_normalized.startswith('www.'):
                netloc_normalized = netloc_normalized[4:]
            
            domain_for_comparison = self.domain
            if domain_for_comparison.startswith('www.'):
                domain_for_comparison = domain_for_comparison[4:]
            
            if netloc_normalized != domain_for_comparison:
                continue

            # Check exclude filter for discovered links (before normalization)
            if self._should_exclude_url(absolute_url):
                self.stats['filtered_by_exclude'] += 1
                continue

            # Normalize URL for visited check
            normalized_for_visited = normalize_for_visited(absolute_url, strip_tracking=self.strip_tracking)
            
            # Check if tracking params were stripped (for statistics)
            if self.strip_tracking and absolute_url != normalized_for_visited:
                self.stats['filtered_by_tracking'] += 1

            if normalized_for_visited not in self.visited_urls and not self.should_stop:
                # Use original absolute_url for crawling (to preserve original URL structure)
                # but normalized_for_visited is used for deduplication
                self.crawl(absolute_url, current_depth + 1)

    def get_sitemap(self) -> List[str]:
        """Start the crawl and return the discovered sitemap.

        Clears any previous crawl state, performs the crawl starting
        from the base URL, and returns a sorted list of discovered URLs.

        Returns:
            Sorted list of unique URLs discovered during the crawl.
        """
        self.visited_urls.clear()
        self.sitemap.clear()
        self.should_stop = False
        self.stats = {
            'filtered_by_exclude': 0,
            'filtered_by_tracking': 0,
            'filtered_by_depth': 0,
            'filtered_by_max_urls': 0,
            'non_200_status': 0
        }
        logger.info(
            f"Starting crawl from {self.base_url} "
            f"(max_depth={self.max_depth}, max_urls={self.max_urls if self.max_urls > 0 else 'unlimited'}, "
            f"exclude_substrings={self.exclude_substrings}, strip_tracking={self.strip_tracking})"
        )
        self.crawl(self.base_url, 0)
        logger.info(f"Crawl completed. Found {len(self.sitemap)} URLs.")
        # Close session to free resources
        self.session.close()
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
        max_urls: int = 0,
        exclude_substrings: Optional[List[str]] = None,
        strip_tracking: bool = True,
        crawl_delay: float = DEFAULT_CRAWL_DELAY,
        respect_robots_txt: bool = False
    ) -> None:
        """Initialize the crawler worker thread.

        Args:
            start_url: Starting URL for the crawl.
            max_depth: Maximum crawl depth (default: 5).
            max_urls: Maximum number of URLs to collect, 0 = unlimited (default: 0).
            exclude_substrings: List of substrings to exclude from URLs (default: None).
            strip_tracking: Whether to strip tracking parameters (default: True).
            crawl_delay: Delay between requests in seconds (default: 0.5).
            respect_robots_txt: Whether to respect robots.txt (default: False).
        """
        super().__init__()
        self.start_url = start_url
        self.max_depth = max_depth
        self.max_urls = max_urls
        self.exclude_substrings = exclude_substrings
        self.strip_tracking = strip_tracking
        self.crawl_delay = crawl_delay
        self.respect_robots_txt = respect_robots_txt
        self.crawler = Crawler(
            self.start_url,
            self.max_depth,
            self.max_urls,
            self.exclude_substrings,
            self.strip_tracking,
            self.crawl_delay,
            self.respect_robots_txt
        )

    def run(self) -> None:
        """Execute the crawl in the background thread."""
        try:
            self.crawler.url_callback = self.url_found_signal.emit
            sitemap = self.crawler.get_sitemap()
            # Return both sitemap and stats
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
    app.setApplicationName("ALX Sitemap Generator")
    app.setApplicationVersion("2.0")
    app.setOrganizationName("JTGSYSTEMS")

    # Set application icon if available
    # In PyInstaller bundle, look for icon in sys._MEIPASS first
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running as compiled executable
        base_path = sys._MEIPASS
    else:
        # Running as script
        base_path = os.path.dirname(__file__)
    
    icon_path = os.path.join(base_path, 'assets', 'icon', 'app.ico')
    if os.path.exists(icon_path):
        from PyQt6.QtGui import QIcon
        app.setWindowIcon(QIcon(icon_path))

    window = SiteMapGeneratorApp()
    
    # Set window icon
    if os.path.exists(icon_path):
        from PyQt6.QtGui import QIcon
        window.setWindowIcon(QIcon(icon_path))
    
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
