# Scrapy settings for solidworks_scraper project (Phase 05 - Examples Crawler)
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://docs.scrapy.org/en/latest/topics/settings.html
#     https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://docs.scrapy.org/en/latest/topics/spider-middleware.html

from pathlib import Path

BOT_NAME = "solidworks_scraper"

SPIDER_MODULES = ["solidworks_scraper.spiders"]
NEWSPIDER_MODULE = "solidworks_scraper.spiders"

ADDONS: dict[str, str] = {}


# Crawl responsibly by identifying yourself (and your website) on the user-agent
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Obey robots.txt rules
# NOTE: Set to False for testing. The SolidWorks documentation is publicly accessible,
# but robots.txt may be overly restrictive. Use responsibly and with appropriate delays.
ROBOTSTXT_OBEY = False

# Concurrency and throttling settings - Be polite!
CONCURRENT_REQUESTS = 5
CONCURRENT_REQUESTS_PER_DOMAIN = 5
DOWNLOAD_DELAY = 0.1  # 0.1 second delay between requests

# Disable cookies (enabled by default)
# COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
# TELNETCONSOLE_ENABLED = False

# Override the default request headers:
# DEFAULT_REQUEST_HEADERS = {
#    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
#    "Accept-Language": "en",
# }

# Enable or disable spider middlewares
# See https://docs.scrapy.org/en/latest/topics/spider-middleware.html
# SPIDER_MIDDLEWARES = {
#    "solidworks_scraper.middlewares.SolidworksScraperSpiderMiddleware": 543,
# }

# Enable or disable downloader middlewares
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html
# DOWNLOADER_MIDDLEWARES = {
#    "solidworks_scraper.middlewares.SolidworksScraperDownloaderMiddleware": 543,
# }

# Enable or disable extensions
# See https://docs.scrapy.org/en/latest/topics/extensions.html
# EXTENSIONS = {
#    "scrapy.extensions.telnet.TelnetConsole": None,
# }

# Configure item pipelines
# See https://docs.scrapy.org/en/latest/topics/item-pipeline.html
ITEM_PIPELINES = {
    "solidworks_scraper.pipelines.HtmlSavePipeline": 300,
    "solidworks_scraper.pipelines.MetadataLogPipeline": 400,
}

# Enable and configure the AutoThrottle extension (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/autothrottle.html
# AUTOTHROTTLE_ENABLED = True
# The initial download delay
# AUTOTHROTTLE_START_DELAY = 5
# The maximum download delay to be set in case of high latencies
# AUTOTHROTTLE_MAX_DELAY = 60
# The average number of requests Scrapy should be sending in parallel to
# each remote server
# AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
# Enable showing throttling stats for every response received:
# AUTOTHROTTLE_DEBUG = False

# Enable and configure HTTP caching (disabled by default)
# See https://docs.scrapy.org/en/latest/topics/downloader-middleware.html#httpcache-middleware-settings
# HTTPCACHE_ENABLED = True
# HTTPCACHE_EXPIRATION_SECS = 0
# HTTPCACHE_DIR = "httpcache"
# HTTPCACHE_IGNORE_HTTP_CODES = []
# HTTPCACHE_STORAGE = "scrapy.extensions.httpcache.FilesystemCacheStorage"

# Set settings whose default value is deprecated to a future-proof value
FEED_EXPORT_ENCODING = "utf-8"

# Custom settings for SolidWorks API examples crawler
# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Output directories
OUTPUT_DIR = PROJECT_ROOT / "output"
HTML_OUTPUT_DIR = OUTPUT_DIR / "html"
METADATA_OUTPUT_DIR = PROJECT_ROOT / "metadata"

# Create output directories if they don't exist
HTML_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
METADATA_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Log level
LOG_LEVEL = "INFO"

# Configure logging to exclude verbose scraped item output
# This prevents HTML content from being dumped in logs
LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "loggers": {
        "scrapy.core.scraper": {
            "level": "WARNING",  # Don't log DEBUG "Scraped from" messages with full item content
        },
    },
}

# Disable downloading of non-HTML resources
# Only accept HTML content types
DEFAULT_REQUEST_HEADERS = {
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en",
}

# Duplicate filtering
DUPEFILTER_CLASS = "scrapy.dupefilters.RFPDupeFilter"
DUPEFILTER_DEBUG = True

# URL boundaries configuration
ALLOWED_DOMAINS = ["help.solidworks.com"]
BASE_URL_PATH = "/2026/english/api/"

# HTTP error handling - retry on common errors
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# Download timeout
DOWNLOAD_TIMEOUT = 30

# Disable media downloads
MEDIA_ALLOW_REDIRECTS = False

# Memory usage optimization
REACTOR_THREADPOOL_MAXSIZE = 10

# Enable HTTP compression
COMPRESSION_ENABLED = True
