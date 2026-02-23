import requests
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, UpdaterHandler, Job
import logging
import concurrent.futures
from bs4 import BeautifulSoup
import re
import time
import random
import os
import json

# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

# User agents for bypassing restrictions
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15',
    'Googlebot/2.1 (+http://www.google.com/bot.html)',
    'Mozilla/5.0 (compatible; Bingbot/2.0; +http://www.bing.com/bingbot.htm)'
]

def get_random_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Referer': 'https://scholar.google.com/'
    }

# MULTIPLE SOURCES - Updated domains
SCI_HUB_DOMAINS = [
    "https://sci-hub.se/",
    "https://sci-hub.st/", 
    "https://sci-hub.ru/",
    "https://sci-hub.ee/",
    "https://sci-hub.wf/"
]

# Academic institutional proxies (often have subscriptions)
INSTITUTIONAL_PROXIES = [
    "https://libproxy.mit.edu/login?url=",
    "https://login.library.nyu.edu/login?url=",
    "https://ezproxy.stanford.edu/login?url="
]

# Alternative academic repositories
REPOSITORIES = [
    "https://arxiv.org/abs/",  # Preprints
    "https://www.researchgate.net/publication/",
    "https://www.academia.edu/",
    "https://zenodo.org/record/"
]

def load_bots():
    try:
        with open('bots.txt', 'r') as f:
            return set(line.strip() for line in f)
    except FileNotFoundError:
        return set()

def save_bots(bots):
    with open('bots.txt', 'w') as f:
        for bot in bots:
            f.write(f'{bot}\n')

def load_log_file(file_path):
    try:
        with open(file_path, 'r') as f:
            return {line.strip().split('|')[0]: line.strip().split('|')[1] for line in f}
    except FileNotFoundError:
        return {}

def save_log_file(file_path, log_data):
    with open(file_path, 'w') as f:
        for doi, pdf_url in log_data.items():
            f.write(f'{doi}|{pdf_url}\n')

class RotatingProxyPool:
    def __init__(self, max_bots=10000):
        self.max_bots = max_bots
        self.bots = load_bots()
        self.log_data = load_log_file('log.txt')

    def extend(self, new_bots):
        self.bots.update(new_bots)
        if len(self.bots) > self.max_bots:
            self.bots = list(self.bots)[:self.max_bots]
            save_bots(self.bots)

    def difference_update(self, bots_to_remove):
        self.bots.difference_update(bots_to_remove)
        save_bots(self.bots)

    def choice(self):
        return random.choice(list(self.bots))

    def __len__(self):
        return len(self.bots)

def get_proxy(bot_ip_list):
    bot_ip = random.choice(list(bot_ip_list))
    bot_ip_list.remove(bot_ip)
    return bot_ip

def add_to_log(doi, pdf_url):
    log_data = load_log_file('log.txt')
    log_data[doi] = pdf_url
    save_log_file('log.txt', log_data)

def brute_force_scihub(doi, bot_ip_list):
    """Aggressive Sci-Hub fetching with multiple domains and IP rotation"""
    proxy = get_proxy(bot_ip_list)
    for domain in SCI_HUB_DOMAINS:
        try:
            url = f"{domain}{doi}"
            response = requests.get(url, headers=get_random_headers(), timeout=15, proxies={'http': proxy, 'https': proxy})

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Multiple extraction methods
                pdf_sources = []

                # Method 1: Embedded PDF
                embed = soup.find('embed', {'type': 'application/pdf'})
                if embed and embed.get('src'):
                    pdf_src = embed['src']
                    if not pdf_src.startswith('http'):
                        pdf_src = domain + pdf_src.lstrip('/')
                    pdf_sources.append(pdf_src)

                # Method 2: Iframe PDF
                iframe = soup.find('iframe')
                if iframe and iframe.get('src') and 'pdf' in iframe['src'].lower():
                    pdf_src = iframe['src']
                    if not pdf_src.startswith('http'):
                        pdf_src = domain + pdf_src.lstrip('/')
                    pdf_sources.append(pdf_src)

                # Method 3: Direct PDF links in page
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if href.lower().endswith('.pdf'):
                        if not href.startswith('http'):
                            href = domain + href.lstrip('/')
                        pdf_sources.append(href)

                # Method 4: JavaScript redirect detection
                script_tags = soup.find_all('script')
                for script in script_tags:
                    if script.string:
                        matches = re.findall(r'\"?(https?://[^\"]+\.pdf)\"?', script.string)
                        pdf_sources.extend(matches)

                # Return first valid PDF
                for pdf_url in pdf_sources:
                    try:
                        # Verify it's actually a PDF
                        head = requests.head(pdf_url, headers=get_random_headers(), timeout=5, proxies={'http': proxy, 'https': proxy})
                        if 'application/pdf' in head.headers.get('content-type', '').lower():
                            add_to_log(doi, pdf_url)
                            return pdf_url
                    except:
                        continue

        except Exception as e:
            logger.debug(f"Sci-Hub {domain} failed: {e}")
            continue

    return None

def try_institutional_access(doi, bot_ip_list):
    """Attempt to access through institutional proxies with IP rotation"""
    publisher_urls = [
        f"https://doi.org/{doi}",
        f"https://www.nature.com/articles/{doi.split('/')[-1]}",
        f"https://www.science.org/doi/{doi}",
        f"https://journals.aps.org/prl/abstract/{doi}"
    ]

    proxy = get_proxy(bot_ip_list)
    for proxy in INSTITUTIONAL_PROXIES:
        for pub_url in publisher_urls:
            try:
                proxied_url = proxy + pub_url
                response = requests.get(proxied_url, headers=get_random_headers(), timeout=10, proxies={'http': proxy, 'https': proxy})

                # Look for PDF download button/links
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    # Common PDF link patterns
                    pdf_patterns = [
                        'a[href*=".pdf"]',
                        'a[href*="download/pdf"]',
                        'a[href*="fulltext.pdf"]',
                        'a:contains("PDF")',
                        'a:contains("Download PDF")'
                    ]

                    for pattern in pdf_patterns:
                        pdf_link = soup.select_one(pattern)
                        if pdf_link and pdf_link.get('href'):
                            pdf_url = pdf_link['href']
                            if not pdf_url.startswith('http'):
                                # Construct absolute URL
                                from urllib.parse import urljoin
                                pdf_url = urljoin(proxied_url, pdf_url)

                            # Verify PDF
                            head = requests.head(pdf_url, headers=get_random_headers(), timeout=5, proxies={'http': proxy, 'https': proxy})
                            if 'application/pdf' in head.headers.get('content-type', '').lower():
                                add_to_log(doi, pdf_url)
                                return pdf_url

            except Exception as e:
                logger.debug(f"Institutional proxy {proxy} failed: {e}")
                continue

    return None

def search_repositories(doi, bot_ip_list):
    """Search alternative academic repositories with IP rotation"""
    proxy = get_proxy(bot_ip_list)
    for repo in REPOSITORIES:
        try:
            search_url = f"{repo}{doi}"
            response = requests.get(search_url, headers=get_random_headers(), timeout=10, proxies={'http': proxy, 'https': proxy})

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                # Repository-specific extraction
                pdf_url = None

                if 'arxiv.org' in repo:
                    # arXiv direct PDF link format
                    pdf_url = response.url.replace('/abs/', '/pdf/') + '.pdf'
                elif 'researchgate.net' in repo:
                    # ResearchGate download button
                    download_btn = soup.find('a', {'data-testid': 'download-button'})
                    if download_btn:
                        pdf_url = download_btn.get('href')
                elif 'academia.edu' in repo:
                    # Academia.edu PDF link
                    pdf_link = soup.find('a', href=re.compile(r'\.pdf$'))
                    if pdf_link:
                        pdf_url = pdf_link['href']

                if pdf_url:
                    # Verify it's a PDF
                    head = requests.head(pdf_url, headers=get_random_headers(), timeout=5, proxies={'http': proxy, 'https': proxy})
                    if 'application/pdf' in head.headers.get('content-type', '').lower():
                        add_to_log(doi, pdf_url)
                        return pdf_url

        except Exception as e:
            logger.debug(f"Repository {repo} failed: {e}")
            continue

    return None

def try_direct_publisher(doi, bot_ip_list):
    """Sometimes publishers offer free PDFs with IP rotation"""
    proxy = get_proxy(bot_ip_list)
    try:
        # Try DOI resolver first
        doi_url = f"https://doi.org/{doi}"
        response = requests.get(doi_url, headers=get_random_headers(), timeout=10, allow_redirects=True, proxies={'http': proxy, 'https': proxy})

        final_url = response.url

        # Check if final URL has PDF
        if final_url.endswith('.pdf'):
            add_to_log(doi, final_url)
            return final_url

        # Look for PDF on publisher page
        soup = BeautifulSoup(response.text, 'html.parser')

        # Common publisher PDF selectors
        selectors = [
            'a.pdf-link',
            'a[href*="pdf" i]',
            '.article-pdf a',
            '.download-pdf',
            'a:contains("Full Text PDF")',
            'a.download'
        ]

        for selector in selectors:
            pdf_elem = soup.select_one(selector)
            if pdf_elem and pdf_elem.get('href'):
                pdf_url = pdf_elem['href']
                if not pdf_url.startswith('http'):
                    from urllib.parse import urljoin
                    pdf_url = urljoin(final_url, pdf_url)

                # Verify PDF
                head = requests.head(pdf_url, headers=get_random_headers(), timeout=5, proxies={'http': proxy, 'https': proxy})
                if 'application/pdf' in head.headers.get('content-type', '').lower():
                    add_to_log(doi, pdf_url)
                    return pdf_url

    except Exception as e:
        logger.debug(f"Direct publisher failed: {e}")
    return None

def get_paper_anywhere(doi, bot_ip_list):
    """Parallel brute force attack on all sources with IP rotation"""
    methods = [
        brute_force_scihub,
        try_institutional_access,
        search_repositories,
        try_direct_publisher
    ]

    # Run all methods in parallel for speed
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(methods)) as executor:
        future_to_method = {executor.submit(method, doi, bot_ip_list): method.__name__ for method in methods}

        for future in concurrent.futures.as_completed(future_to_method):
            result = future.result()
            if result:
                # Cancel remaining tasks since we found it
                executor.shutdown(wait=False)
                return result

    # If all parallel methods fail, try sequential fallback
    for method in methods:
        result = method(doi, bot_ip_list)
        if result:
            return result

    return None

def load_bots_file(file_path):
    try:
        with open(file_path, 'r') as f:
            return {line.strip(): '' for line in f}
    except FileNotFoundError:
        return {}

def save_bots_file(file_path, bot_data):
    with open(file_path, 'w') as f:
        for bot_ip, _ in bot_data.items():
            f.write(f'{bot_ip}\n')

class RotatingProxyManager:
    def __init__(self):
        self.bot_data = load_bots_file('bots.txt')
        self.current_ip_index = 0

    def rotate_proxy(self):
        bot_data = list(self.bot_data.items())
        self.current_ip_index = (self.current_ip_index + 1) % len(bot_data)
        return bot_data[self.current_ip_index][0]

    def add_bot(self, bot_ip):
        self.bot_data[bot_ip] = ''
        save_bots_file('bots.txt', self.bot_data)

def start(update, context):
    update.message.reply_text(
        '🔬 **ULTIMATE RESEARCH PAPER BOT** 🔬\n\n'
        'Send any DOI and I WILL get you the PDF.\n'
        'Using: Sci-Hub • Institutional Access • Repositories • Direct Sources\n\n'
        '*No paper is beyond reach.*\n'
        '**Access to information is a human right!**'
    )

def handle_doi(update, context):
    doi = update.message.text.strip()

    if not doi.startswith('10.'):
        update.message.reply_text("❌ Invalid DOI format. Must start with '10.'")
        return

    update.message.reply_text(
        f"🎯 Target acquired: {doi}\n"
        "🚀 Deploying multi-vector extraction with IP rotation...\n"
        "This may take 15-30 seconds."
    )

    start_time = time.time()
    bot_manager = RotatingProxyManager()
    bot_ip_list = RotatingProxyPool()
    pdf_url = get_paper_anywhere(doi, bot_ip_list.rotate_proxy())
    elapsed = time.time() - start_time

    if pdf_url:
        try:
            update.message.reply_document(
                document=pdf_url,
                filename=f"{doi.replace('/', '_')}.pdf",
                caption=(
                    f"✅ **SUCCESS** in {elapsed:.1f}s\n\n"
                    f"DOI: `{doi}`\n\n"
                    "📚 *Knowledge liberated*\n"
                    "🔓 *Access to information is a human right!*"
                )
            )
        except Exception as e:
            logger.error(f"Error sending PDF: {e}")
            update.message.reply_text(
                f"✅ **Paper captured** ({elapsed:.1f}s)\n\n"
                f"Direct download: {pdf_url}\n\n"
                "📚 Knowledge should be free for everyone!"
            )
    else:
        update.message.reply_text(
            f"❌ **Mission failed** ({elapsed:.1f}s)\n\n"
            f"Could not retrieve: {doi}\n\n"
            "Possible reasons:\n"
            "• Paper doesn't exist\n"
            "• All sources currently blocked\n"
            "• Extremely new/obscure publication\n\n"
            "Try again later or use manual methods."
        )

def job(context: UpdaterContext):
    bot_manager = RotatingProxyManager()
    bot_ip_list = RotatingProxyPool()
    new_bots = load_bots()
    bot_ip_list.extend(new_bots)
    save_bots_file('bots.txt', bot_manager.bot_data)

def error(update, context):
    logger.warning(f'Update {update} caused error {context.error}')

def main():
    TOKEN = '8653690124:AAE-pziVrFCa5RwrykfTXBWXOfa-RsnLzoc'

    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_doi))
    dp.add_error_handler(error)

    # Add job to load bots every hour
    job_queue = updater.job_queue
    job_queue.run_repeating(job, interval=3600, first=0)
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()


