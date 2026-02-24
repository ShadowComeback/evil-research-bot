#!/usr/bin/env python3
"""
🐱 PAPER KITTY BOT - Academic Paper Fetcher
A cute bot that helps fetch research papers
"""

import logging
import random
import re
import time
import sys
from typing import Optional, Dict, List
from urllib.parse import urljoin

# Try to import required packages with fallbacks
try:
    import requests
    from bs4 import BeautifulSoup
    HAS_WEB_LIBS = True
except ImportError:
    HAS_WEB_LIBS = False
    print("❌ Missing required packages: requests, beautifulsoup4")
    print("💡 Install with: pip install requests beautifulsoup4")

try:
    from telegram import Update
    from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
    HAS_TELEGRAM = True
except ImportError as e:
    HAS_TELEGRAM = False
    print(f"❌ Telegram import error: {e}")
    print("💡 Try: pip install python-telegram-bot==13.7")

# ====================
# 🐱 KITTY LOGGING
# ====================
logging.basicConfig(
    format='🐾 %(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ====================
# 🎭 DISGUISE AGENTS
# ====================
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15',
    'Googlebot/2.1 (+http://www.google.com/bot.html)',
]

def get_random_headers() -> Dict[str, str]:
    """Generate cute headers for stealth mode"""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'DNT': '1',
        'Connection': 'keep-alive',
    }

# ====================
# 🌐 KNOWLEDGE PORTALS
# ====================
SCI_HUB_DOMAINS = [
    "https://sci-hub.se/",
    "https://sci-hub.st/",
    "https://sci-hub.ru/",
]

REPOSITORIES = [
    "https://arxiv.org/abs/",
    "https://www.researchgate.net/publication/",
    "https://zenodo.org/record/",
]

# ====================
# 📚 PAPER HUNTER
# ====================
class PaperHunterKitty:
    """A smart kitty that hunts for academic papers"""
    
    @staticmethod
    def validate_doi(doi: str) -> bool:
        """Check if DOI looks valid"""
        return doi.startswith('10.') and len(doi) > 10
    
    @staticmethod
    def extract_pdf_links(html: str, base_url: str) -> List[str]:
        """Extract all PDF links from HTML"""
        if not HAS_WEB_LIBS:
            return []
        
        soup = BeautifulSoup(html, 'html.parser')
        pdf_links = []
        
        # Look for embedded PDFs
        for embed in soup.find_all('embed'):
            src = embed.get('src', '')
            if src and '.pdf' in src.lower():
                pdf_links.append(urljoin(base_url, src))
        
        # Look for iframe PDFs
        for iframe in soup.find_all('iframe'):
            src = iframe.get('src', '')
            if src and '.pdf' in src.lower():
                pdf_links.append(urljoin(base_url, src))
        
        # Look for PDF links
        for link in soup.find_all('a', href=True):
            href = link['href']
            if '.pdf' in href.lower():
                pdf_links.append(urljoin(base_url, href))
        
        return pdf_links
    
    @staticmethod
    def verify_pdf_url(url: str) -> bool:
        """Check if URL is actually a PDF"""
        try:
            response = requests.head(url, headers=get_random_headers(), timeout=5)
            content_type = response.headers.get('content-type', '').lower()
            return 'application/pdf' in content_type or url.lower().endswith('.pdf')
        except:
            return False

def fetch_paper(doi: str) -> Optional[str]:
    """Main function to fetch a paper"""
    if not HAS_WEB_LIBS:
        return None
    
    hunter = PaperHunterKitty()
    
    if not hunter.validate_doi(doi):
        return None
    
    # Try Sci-Hub domains
    for domain in SCI_HUB_DOMAINS:
        try:
            url = f"{domain}{doi}"
            logger.info(f"🐱 Trying: {domain}")
            
            response = requests.get(url, headers=get_random_headers(), timeout=10)
            
            if response.status_code == 200:
                pdf_links = hunter.extract_pdf_links(response.text, domain)
                
                for pdf_url in pdf_links:
                    if hunter.verify_pdf_url(pdf_url):
                        logger.info(f"✅ Found PDF: {pdf_url[:50]}...")
                        return pdf_url
                        
        except Exception as e:
            logger.debug(f"Domain {domain} failed: {e}")
            continue
    
    # Try arXiv directly
    if doi.startswith('10.48550/arXiv.'):
        try:
            arxiv_id = doi.split('arXiv.')[-1]
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            
            if hunter.verify_pdf_url(pdf_url):
                return pdf_url
        except:
            pass
    
    return None

# ====================
# 🤖 TELEGRAM BOT
# ====================
def start_command(update: Update, context: CallbackContext):
    """Handle /start command"""
    welcome = """
🐱 *PAPER KITTY BOT* 🐱

Hello! I'm here to help you fetch research papers!

*How to use:*
Just send me a DOI and I'll try to find the PDF.

*Example DOIs:*
• 10.1038/nature12373
• 10.1126/science.1234567

*I search in:*
• Sci-Hub portals
• arXiv repository
• Other sources

📚 *Happy researching!* 📚
"""
    update.message.reply_text(welcome, parse_mode='Markdown')

def handle_message(update: Update, context: CallbackContext):
    """Handle DOI messages"""
    text = update.message.text.strip()
    
    # Check if it looks like a DOI
    if text.startswith('10.'):
        # Send processing message
        msg = update.message.reply_text(f"""
🔍 *Searching for paper...* 🔍

*DOI:* `{text}`

🐱 *Kitty is hunting...*
Please wait a moment!
        """, parse_mode='Markdown')
        
        # Try to fetch the paper
        pdf_url = fetch_paper(text)
        
        if pdf_url:
            try:
                # Send the PDF
                update.message.reply_document(
                    document=pdf_url,
                    filename=f"{text.replace('/', '_')}.pdf",
                    caption=f"""
✅ *Paper found!* ✅

*DOI:* `{text}`

📚 *Enjoy your reading!* 📚
                    """,
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Error sending PDF: {e}")
                update.message.reply_text(f"""
✅ *Paper found!* ✅

*DOI:* `{text}`

*Direct link:* {pdf_url}

📚 *Download manually!* 📚
                """, parse_mode='Markdown')
        else:
            update.message.reply_text(f"""
❌ *Paper not found* ❌

*DOI:* `{text}`

*Possible reasons:*
• DOI might be incorrect
• Paper not available
• Try again later

🐱 *Kitty tried their best!*
            """, parse_mode='Markdown')
    else:
        update.message.reply_text("""
📝 *Please send a DOI*

A DOI usually starts with `10.`

*Example:* `10.1038/nature12373`

Send a DOI and I'll search for the paper! 🐱
        """, parse_mode='Markdown')

def error_handler(update: Update, context: CallbackContext):
    """Handle errors gracefully"""
    logger.error(f"Error: {context.error}")
    
    if update and update.message:
        update.message.reply_text("""
😿 *Oops! Something went wrong!*

Please try again in a moment.

🐾 *Kitty is recovering...*
        """, parse_mode='Markdown')

# ====================
# 🚀 MAIN FUNCTION
# ====================
def main():
    """Start the bot"""
    
    # Check dependencies
    if not HAS_WEB_LIBS:
        print("""
❌ Missing web libraries!
Run: pip install requests beautifulsoup4
        """)
        sys.exit(1)
    
    if not HAS_TELEGRAM:
        print("""
❌ Missing telegram library!
Run: pip install python-telegram-bot==13.7
        """)
        sys.exit(1)
    
    # ASCII art (fixed escape sequence)
    startup_art = r"""
     /\_/\
    ( o.o )
     > ^ <
     
    📚 Paper Kitty Bot is starting! 🐱
    """
    print(startup_art)
    
    # Get bot token (you need to set this!)
    TOKEN = "8653690124:AAE-pziVrFCa5RwrykfTXBWXOfa-RsnLzoc"  # ⚠️ Replace with your bot token!
    
    if TOKEN == "8653690124:AAE-pziVrFCa5RwrykfTXBWXOfa-RsnLzoc":
        print("""
⚠️  WARNING: You need to set your bot token!
        
1. Create a bot with @BotFather on Telegram
2. Get your bot token
3. Replace "YOUR_BOT_TOKEN_HERE" with your actual token
        """)
        sys.exit(1)
    
    # Create bot
    updater = Updater(TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    
    # Add handlers
    dispatcher.add_handler(CommandHandler("start", start_command))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dispatcher.add_error_handler(error_handler)
    
    # Start bot
    print("🐱 Bot is starting...")
    updater.start_polling()
    
    # Keep running
    print("✅ Bot is running! Press Ctrl+C to stop.")
    updater.idle()

if __name__ == "__main__":
    main()
