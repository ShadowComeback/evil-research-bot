import logging
import random
import re
import time
import concurrent.futures
from typing import Optional, List, Dict
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# ====================
# 🐱 KITTY CONFIGURATION
# ====================
logging.basicConfig(
    format='🐾 %(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('kitty_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ====================
# 🎭 DISGUISE AGENTS
# ====================
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Googlebot/2.1 (+http://www.google.com/bot.html)',
    'Mozilla/5.0 (compatible; Bingbot/2.0; +http://www.bing.com/bingbot.htm)',
    'Mozilla/5.0 (compatible; DuckDuckBot-Https/1.1; https://duckduckgo.com/duckduckbot)'
]

def get_random_headers() -> Dict[str, str]:
    """Generate random headers for stealth mode"""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0'
    }

# ====================
# 🌐 KNOWLEDGE PORTALS
# ====================
SCI_HUB_DOMAINS = [
    "https://sci-hub.se/",
    "https://sci-hub.st/",
    "https://sci-hub.ru/",
    "https://sci-hub.ee/",
    "https://sci-hub.wf/",
    "https://sci-hub.do/",
    "https://sci-hub.shop/"
]

INSTITUTIONAL_PROXIES = [
    "https://libproxy.mit.edu/login?url=",
    "https://login.library.nyu.edu/login?url=",
    "https://ezproxy.stanford.edu/login?url=",
    "https://proxy.library.upenn.edu/login?url=",
    "https://library.harvard.edu/login?url="
]

REPOSITORIES = [
    "https://arxiv.org/abs/",
    "https://www.researchgate.net/publication/",
    "https://www.academia.edu/",
    "https://zenodo.org/record/",
    "https://www.semanticscholar.org/paper/",
    "https://www.ncbi.nlm.nih.gov/pmc/articles/"
]

# ====================
# 📚 PAPER HUNTER CLASSES
# ====================
class PaperHunter:
    """Smart kitty that hunts for papers"""
    
    @staticmethod
    def validate_doi(doi: str) -> bool:
        """Validate DOI format"""
        doi_pattern = r'^10\.\d{4,9}/[-._;()/:A-Z0-9]+$'
        return bool(re.match(doi_pattern, doi, re.IGNORECASE))
    
    @staticmethod
    def extract_pdf_from_html(soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """Extract PDF URL from HTML soup"""
        pdf_sources = []
        
        # Method 1: Embedded PDF
        for embed in soup.find_all('embed', {'type': 'application/pdf'}):
            if embed.get('src'):
                pdf_src = urljoin(base_url, embed['src'])
                pdf_sources.append(pdf_src)
        
        # Method 2: Iframe PDF
        for iframe in soup.find_all('iframe'):
            src = iframe.get('src', '')
            if src and '.pdf' in src.lower():
                pdf_src = urljoin(base_url, src)
                pdf_sources.append(pdf_src)
        
        # Method 3: Anchor PDF links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.lower().endswith('.pdf'):
                pdf_src = urljoin(base_url, href)
                pdf_sources.append(pdf_src)
        
        # Method 4: Button with PDF
        for button in soup.find_all(['button', 'input'], {'value': re.compile(r'\.pdf$', re.I)}):
            if button.get('value'):
                pdf_src = urljoin(base_url, button['value'])
                pdf_sources.append(pdf_src)
        
        # Method 5: Meta redirect
        meta_refresh = soup.find('meta', {'http-equiv': 'refresh'})
        if meta_refresh and meta_refresh.get('content'):
            content = meta_refresh['content']
            url_match = re.search(r'url=(.+)', content, re.I)
            if url_match and '.pdf' in url_match.group(1).lower():
                pdf_src = urljoin(base_url, url_match.group(1))
                pdf_sources.append(pdf_src)
        
        return pdf_sources[0] if pdf_sources else None
    
    @staticmethod
    def is_valid_pdf(url: str, proxy: str = None) -> bool:
        """Check if URL points to a valid PDF"""
        try:
            headers = get_random_headers()
            if proxy:
                proxies = {'http': proxy, 'https': proxy}
                response = requests.head(url, headers=headers, timeout=5, proxies=proxies)
            else:
                response = requests.head(url, headers=headers, timeout=5)
            
            content_type = response.headers.get('content-type', '').lower()
            return 'application/pdf' in content_type or url.lower().endswith('.pdf')
        except:
            return False

class ProxyManager:
    """Manages proxy rotation for stealth operations"""
    
    def __init__(self):
        self.proxies = self.load_proxies()
        self.current_index = 0
    
    @staticmethod
    def load_proxies() -> List[str]:
        """Load proxies from file"""
        try:
            with open('proxies.txt', 'r') as f:
                return [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            return []
    
    def get_proxy(self) -> Optional[str]:
        """Get next proxy in rotation"""
        if not self.proxies:
            return None
        
        proxy = self.proxies[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.proxies)
        return proxy

# ====================
# 🎯 PAPER FETCHING STRATEGIES
# ====================
def fetch_from_scihub(doi: str, proxy_manager: ProxyManager) -> Optional[str]:
    """Fetch paper from Sci-Hub"""
    hunter = PaperHunter()
    
    for domain in SCI_HUB_DOMAINS:
        try:
            proxy = proxy_manager.get_proxy()
            url = f"{domain}{doi}"
            logger.info(f"🐱 Trying Sci-Hub: {domain}")
            
            response = requests.get(
                url,
                headers=get_random_headers(),
                timeout=15,
                proxies={'http': proxy, 'https': proxy} if proxy else None
            )
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                pdf_url = hunter.extract_pdf_from_html(soup, domain)
                
                if pdf_url and hunter.is_valid_pdf(pdf_url, proxy):
                    logger.info(f"✅ Found PDF on Sci-Hub: {domain}")
                    return pdf_url
                    
        except Exception as e:
            logger.debug(f"Sci-Hub {domain} failed: {e}")
            continue
    
    return None

def fetch_from_repository(doi: str, proxy_manager: ProxyManager) -> Optional[str]:
    """Fetch from academic repositories"""
    hunter = PaperHunter()
    
    for repo_base in REPOSITORIES:
        try:
            proxy = proxy_manager.get_proxy()
            url = f"{repo_base}{doi}"
            logger.info(f"📚 Trying repository: {repo_base}")
            
            response = requests.get(
                url,
                headers=get_random_headers(),
                timeout=10,
                proxies={'http': proxy, 'https': proxy} if proxy else None
            )
            
            if response.status_code == 200:
                # Special handling for arXiv
                if 'arxiv.org' in repo_base:
                    pdf_url = url.replace('/abs/', '/pdf/') + '.pdf'
                    if hunter.is_valid_pdf(pdf_url, proxy):
                        return pdf_url
                
                # General repository handling
                soup = BeautifulSoup(response.text, 'html.parser')
                pdf_url = hunter.extract_pdf_from_html(soup, repo_base)
                
                if pdf_url and hunter.is_valid_pdf(pdf_url, proxy):
                    logger.info(f"✅ Found PDF in repository: {repo_base}")
                    return pdf_url
                    
        except Exception as e:
            logger.debug(f"Repository {repo_base} failed: {e}")
            continue
    
    return None

def fetch_from_publisher(doi: str, proxy_manager: ProxyManager) -> Optional[str]:
    """Try direct publisher access"""
    hunter = PaperHunter()
    
    try:
        proxy = proxy_manager.get_proxy()
        doi_url = f"https://doi.org/{doi}"
        logger.info(f"🏢 Trying publisher via DOI: {doi_url}")
        
        response = requests.get(
            doi_url,
            headers=get_random_headers(),
            timeout=10,
            allow_redirects=True,
            proxies={'http': proxy, 'https': proxy} if proxy else None
        )
        
        final_url = response.url
        
        # Check if it's already a PDF
        if final_url.lower().endswith('.pdf'):
            return final_url
        
        # Search for PDF on publisher page
        soup = BeautifulSoup(response.text, 'html.parser')
        pdf_url = hunter.extract_pdf_from_html(soup, final_url)
        
        if pdf_url and hunter.is_valid_pdf(pdf_url, proxy):
            logger.info(f"✅ Found PDF on publisher site")
            return pdf_url
            
    except Exception as e:
        logger.debug(f"Publisher fetch failed: {e}")
    
    return None

# ====================
# 🤖 TELEGRAM BOT HANDLERS
# ====================
def start_command(update: Update, context: CallbackContext):
    """Handle /start command"""
    welcome_message = """
🐱 *WELCOME TO PAPER KITTY BOT!* 🐱

I'm here to help you fetch academic papers! Just send me a DOI and I'll do my best to find it.

*How to use:*
1. Send any DOI (e.g., 10.1234/example.doi)
2. I'll search multiple sources
3. If found, I'll send you the PDF!

*Example DOIs:*
• 10.1038/nature12373
• 10.1126/science.1234567
• 10.1109/TVCG.2012.123

🔍 *I search in:*
• Sci-Hub portals
• Academic repositories
• Publisher sites
• Institutional proxies

*Note:* Always respect copyright laws in your jurisdiction.
"""
    update.message.reply_text(welcome_message, parse_mode='Markdown')

def handle_doi(update: Update, context: CallbackContext):
    """Handle DOI messages"""
    doi = update.message.text.strip()
    hunter = PaperHunter()
    
    if not hunter.validate_doi(doi):
        update.message.reply_text("""
❌ *Invalid DOI Format!* ❌

A valid DOI should look like:
• `10.1038/nature12373`
• `10.1126/science.1234567`
• `10.1109/TVCG.2012.123`

Please check and try again! 🐾
        """, parse_mode='Markdown')
        return
    
    # Send processing message
    processing_msg = update.message.reply_text(f"""
🎯 *Target Acquired!* 🎯

*DOI:* `{doi}`

🐱 *Kitty is on the hunt!* 
Searching through multiple sources...
This may take 10-20 seconds.
    """, parse_mode='Markdown')
    
    start_time = time.time()
    proxy_manager = ProxyManager()
    
    # Try fetching strategies
    strategies = [
        fetch_from_scihub,
        fetch_from_repository,
        fetch_from_publisher
    ]
    
    pdf_url = None
    for strategy in strategies:
        pdf_url = strategy(doi, proxy_manager)
        if pdf_url:
            break
    
    elapsed_time = time.time() - start_time
    
    if pdf_url:
        try:
            # Send the PDF
            update.message.reply_document(
                document=pdf_url,
                filename=f"{doi.replace('/', '_')}.pdf",
                caption=f"""
✅ *Paper Found!* ✅

*DOI:* `{doi}`
*Time:* {elapsed_time:.1f}s
*Source:* {pdf_url[:50]}...

📚 *Happy Reading!* 📚
🐾 Knowledge wants to be free!
                """,
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Error sending PDF: {e}")
            update.message.reply_text(f"""
✅ *Paper Found!* ✅

*DOI:* `{doi}`
*Time:* {elapsed_time:.1f}s

*Direct Download Link:*
{pdf_url}

📚 *Happy Reading!* 📚
🐾 Knowledge wants to be free!
            """, parse_mode='Markdown')
    else:
        update.message.reply_text(f"""
❌ *Paper Not Found* ❌

*DOI:* `{doi}`
*Time:* {elapsed_time:.1f}s

*Possible reasons:*
• Paper doesn't exist
• All sources are blocked
• Very new publication
• Restricted access

💡 *Try:*
1. Check the DOI format
2. Try again later
3. Use manual search
4. Contact your library

🐱 *Kitty tried their best!*
        """, parse_mode='Markdown')

def error_handler(update: Update, context: CallbackContext):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.message:
        update.message.reply_text("""
😿 *Oops! Kitty encountered an error!*

Something went wrong while processing your request.
Please try again in a few moments.

🐾 *Kitty is restarting...*
        """, parse_mode='Markdown')

# ====================
# 🚀 MAIN BOT SETUP
# ====================
def main():
    """Start the bot"""
    # Replace with your actual bot token
    TOKEN = '8653690124:AAE-pziVrFCa5RwrykfTXBWXOfa-RsnLzoc'
    
    # Create updater and dispatcher
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # Add handlers
    dp.add_handler(CommandHandler("start", start_command))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_doi))
    dp.add_error_handler(error_handler)
    
    # ASCII art for startup
    startup_art = """
    /\_/\
   ( o.o )
    > ^ <
    
    📚 Paper Kitty Bot is awake! 🐱
    Ready to fetch knowledge!
    """
    print(startup_art)
    
    # Start the bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
