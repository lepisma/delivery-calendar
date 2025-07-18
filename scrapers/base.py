"""
Base scraper class that defines the common interface for all retailer scrapers.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import os
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class Scraper(ABC):
    """
    Abstract base class for all retailer scrapers.
    
    Provides common functionality like browser setup, login handling,
    and output file generation while requiring subclasses to implement
    retailer-specific scraping logic.
    """
    
    def __init__(self, email: str, password: str, output_dir: str = "output"):
        """
        Initialize the scraper with credentials and output directory.
        
        Args:
            email: Login email for the retailer
            password: Login password for the retailer
            output_dir: Directory to save output files
        """
        self.email = email
        self.password = password
        self.output_dir = output_dir
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def setup_driver(self) -> webdriver.Chrome:
        """
        Setup and configure the Chrome WebDriver with appropriate options.
        
        Returns:
            Configured Chrome WebDriver instance
        """
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
        return self.driver
    
    def cleanup(self):
        """Clean up resources, particularly the WebDriver."""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.wait = None
    
    @abstractmethod
    def login(self) -> bool:
        """
        Login to the retailer's website.
        
        Returns:
            True if login successful, False otherwise
        """
        pass
    
    @abstractmethod
    def scrape_orders(self) -> List[Dict[str, Any]]:
        """
        Scrape order information from the retailer's website.
        
        Returns:
            List of order dictionaries containing order details
        """
        pass
    
    @abstractmethod
    def parse_delivery_date(self, date_text: str) -> Optional[str]:
        """
        Parse delivery date from retailer-specific text format.
        
        Args:
            date_text: Raw date text from the website
            
        Returns:
            Standardized date string in YYYY-MM-DD format, or None if parsing fails
        """
        pass
    
    @abstractmethod
    def get_output_filename(self) -> str:
        """
        Get the output filename for this scraper's results.
        
        Returns:
            Filename for the output ICS file
        """
        pass
    
    def run(self) -> bool:
        """
        Main execution method that orchestrates the scraping process.
        
        Returns:
            True if scraping completed successfully, False otherwise
        """
        try:
            self.logger.info(f"Starting {self.__class__.__name__}")
            
            # Setup browser
            self.setup_driver()
            
            # Login
            if not self.login():
                self.logger.error("Login failed")
                return False
            
            # Scrape orders
            orders = self.scrape_orders()
            if not orders:
                self.logger.info("No orders found")
                return True
            
            # Generate output file
            output_file = os.path.join(self.output_dir, self.get_output_filename())
            self.generate_ics_file(orders, output_file)
            
            self.logger.info(f"Successfully scraped {len(orders)} orders to {output_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Scraping failed: {str(e)}")
            return False
        finally:
            self.cleanup()
    
    def generate_ics_file(self, orders: List[Dict[str, Any]], output_file: str):
        """
        Generate an ICS calendar file from the scraped orders.
        
        Args:
            orders: List of order dictionaries
            output_file: Path to the output ICS file
        """
        from datetime import datetime
        
        ics_content = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Order Tracker//Order Tracker//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH"
        ]
        
        for order in orders:
            if order.get('delivery_date'):
                # Create a unique event ID
                event_id = f"{order.get('order_id', 'unknown')}@ordertracker.local"
                
                # Format the delivery date
                delivery_date = order['delivery_date'].replace('-', '')
                
                ics_content.extend([
                    "BEGIN:VEVENT",
                    f"UID:{event_id}",
                    f"DTSTART;VALUE=DATE:{delivery_date}",
                    f"SUMMARY:{order.get('title', 'Order Delivery')}",
                    f"DESCRIPTION:Order ID: {order.get('order_id', 'N/A')}\\nStatus: {order.get('status', 'N/A')}",
                    f"DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}",
                    "END:VEVENT"
                ])
        
        ics_content.append("END:VCALENDAR")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(ics_content))
