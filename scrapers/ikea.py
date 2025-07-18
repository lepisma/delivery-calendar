"""
IKEA scraper implementation for IKEA India.
"""

import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional

from .base import Scraper


class IkeaScraper(Scraper):
    """
    IKEA India-specific scraper implementation.
    """
    
    def __init__(self, email: str, password: str, output_dir: str = "output"):
        """
        Initialize IKEA scraper with credentials.
        
        Args:
            email: IKEA login email
            password: IKEA login password
            output_dir: Directory to save output files
        """
        super().__init__(email, password, output_dir)
    
    def login(self) -> bool:
        """Login to IKEA India website."""
        try:
            # Navigate to IKEA India login page
            login_url = "https://www.ikea.com/in/en/profile/login/"
            self.driver.get(login_url)
            
            self.logger.info("Navigating to IKEA India login page...")
            
            # Wait for and click the login button to open the login form
            try:
                login_button = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-testid='login-button']"))
                )
                login_button.click()
                self.logger.info("Clicked login button...")
            except TimeoutException:
                # Try alternative selectors
                try:
                    login_button = self.wait.until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Log in')]"))
                    )
                    login_button.click()
                    self.logger.info("Clicked login button (alternative selector)...")
                except TimeoutException:
                    self.logger.error("Could not find login button")
                    return False
            
            # Wait for email field and enter email
            try:
                email_field = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[name='email'], #email"))
                )
                email_field.clear()
                email_field.send_keys(self.email)
                self.logger.info("Entered email...")
            except TimeoutException:
                self.logger.error("Could not find email field")
                return False
            
            # Wait for password field and enter password
            try:
                password_field = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password'], input[name='password'], #password"))
                )
                password_field.clear()
                password_field.send_keys(self.password)
                self.logger.info("Entered password...")
            except TimeoutException:
                self.logger.error("Could not find password field")
                return False
            
            # Submit the login form
            try:
                submit_button = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit'], input[type='submit'], [data-testid='login-submit']"))
                )
                submit_button.click()
                self.logger.info("Submitted login form...")
            except TimeoutException:
                # Try pressing Enter on password field as fallback
                try:
                    from selenium.webdriver.common.keys import Keys
                    password_field.send_keys(Keys.RETURN)
                    self.logger.info("Submitted login form via Enter key...")
                except Exception:
                    self.logger.error("Could not submit login form")
                    return False
            
            # Wait for successful login - check for profile/account indicators
            try:
                # Wait for either the purchases page or profile indicators
                self.wait.until(
                    lambda driver: (
                        "profile" in driver.current_url.lower() or
                        "account" in driver.current_url.lower() or
                        "purchases" in driver.current_url.lower() or
                        driver.find_elements(By.CSS_SELECTOR, "[data-testid='profile'], .profile, [href*='profile'], [href*='account']")
                    )
                )
                self.logger.info("Successfully logged into IKEA India")
                return True
                
            except TimeoutException:
                self.logger.error("Login appears to have failed - no profile indicators found")
                return False
                
        except Exception as e:
            self.logger.error(f"Login failed with error: {str(e)}")
            return False
    
    def scrape_orders(self) -> List[Dict[str, Any]]:
        """Scrape orders from IKEA India purchases page."""
        orders = []
        
        try:
            # Navigate to purchases page
            purchases_url = "https://www.ikea.com/in/en/purchases/"
            self.driver.get(purchases_url)
            self.logger.info("Navigating to IKEA purchases page...")
            
            # Wait for page to load
            time.sleep(3)
            
            # Look for order containers with various possible selectors
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Try multiple selectors for order containers
            order_selectors = [
                '.order-card',
                '.purchase-item',
                '.order-item',
                '[data-testid*="order"]',
                '.order',
                '.purchase',
                'article',
                '.card'
            ]
            
            order_elements = []
            for selector in order_selectors:
                elements = soup.select(selector)
                if elements:
                    order_elements = elements
                    self.logger.info(f"Found {len(elements)} order elements using selector: {selector}")
                    break
            
            if not order_elements:
                # Fallback: look for any elements containing order-related text
                all_elements = soup.find_all(['div', 'article', 'section'])
                order_elements = [
                    elem for elem in all_elements 
                    if elem.get_text() and any(keyword in elem.get_text().lower() 
                    for keyword in ['order', 'purchase', 'delivery', 'shipped', 'delivered'])
                ]
                self.logger.info(f"Fallback: Found {len(order_elements)} potential order elements")
            
            if not order_elements:
                self.logger.info("No orders found on the page")
                return orders
            
            for i, order_element in enumerate(order_elements):
                try:
                    order_text = order_element.get_text()
                    
                    # Skip if this doesn't look like an order
                    if len(order_text.strip()) < 20:
                        continue
                    
                    # Extract order ID
                    order_id = self._extract_order_id(order_text)
                    
                    # Extract product name/title
                    title = self._extract_product_title(order_element, order_text)
                    
                    # Extract delivery information
                    delivery_info = self._extract_delivery_info(order_text)
                    
                    # Skip delivered orders
                    if delivery_info and "delivered" in delivery_info.lower():
                        self.logger.info(f"⏩ Skipping delivered order: {title}")
                        continue
                    
                    # Parse delivery date
                    delivery_date = None
                    if delivery_info:
                        delivery_date = self.parse_delivery_date(delivery_info)
                    
                    if delivery_date or delivery_info:
                        order = {
                            'order_id': order_id or f"ikea-{i+1}",
                            'title': f"🛋️ IKEA: {title}" if title else f"🛋️ IKEA: Order {order_id or i+1}",
                            'start_date': delivery_date,
                            'status': delivery_info or "Unknown status"
                        }
                        orders.append(order)
                        self.logger.info(f"✅ Added IKEA order: {order['title']} - {delivery_info}")
                
                except Exception as e:
                    self.logger.warning(f"Error processing order element {i}: {str(e)}")
                    continue
            
            self.logger.info(f"Successfully scraped {len(orders)} IKEA orders")
        
        except Exception as e:
            self.logger.error(f"Error during IKEA order scraping: {str(e)}")
        
        return orders
    
    def _extract_order_id(self, text: str) -> Optional[str]:
        """Extract order ID from order text."""
        # Look for patterns like "Order #123456", "Order: 123456", etc.
    
        patterns = [
            r'order\s*number\s*[#:]?\s*([a-zA-Z0-9]*\d+[a-zA-Z0-9]*)',
            r'order\s*[#:]?\s*([a-zA-Z0-9]*\d+[a-zA-Z0-9]*)',
            r'purchase\s*[#:]?\s*([a-zA-Z0-9]*\d+[a-zA-Z0-9]*)',
            r'#([a-zA-Z0-9]{6,})',
            r'([0-9]{8,})'
        ]
    
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_product_title(self, element, text: str) -> Optional[str]:
        """Extract product title from order element."""
        # Try to find product name in various ways
        
        # Look for links that might contain product names
        links = element.find_all('a')
        for link in links:
            link_text = link.get_text().strip()
            if link_text and len(link_text) > 5 and not any(skip in link_text.lower() 
                for skip in ['order', 'details', 'view', 'track', 'more']):
                return link_text
        
        # Look for headings
        headings = element.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        for heading in headings:
            heading_text = heading.get_text().strip()
            if heading_text and len(heading_text) > 5:
                return heading_text
        
        # Look for elements with product-related classes
        product_selectors = ['.product-name', '.item-name', '.title', '.name']
        for selector in product_selectors:
            product_elem = element.select_one(selector)
            if product_elem:
                product_text = product_elem.get_text().strip()
                if product_text and len(product_text) > 5:
                    return product_text
        
        # Fallback: extract first meaningful line from text
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        for line in lines:
            if (len(line) > 10 and len(line) < 100 and 
                not any(skip in line.lower() for skip in ['order', 'purchase', 'delivery', 'status'])):
                return line
        
        return None
    
    def _extract_delivery_info(self, text: str) -> Optional[str]:
        """Extract delivery information from order text."""
        # Look for delivery-related information - order from most specific to least specific
        # Look for delivery-related information
        delivery_patterns = [
            r'(expected delivery[^.]*)',
            r'(estimated delivery[^.]*)',
            r'(expected arrival[^.]*)',
            r'(estimated arrival[^.]*)',
    
            r'(delivery(?!\s+info)(?!\s+details)[^.]*)',
        
            r'(arriving[^.]*)',
            r'(shipped[^.]*)',
            r'(delivered[^.]*)',
            r'(expected[^.]*)',
            r'(estimated[^.]*)'
        ]
        
        for pattern in delivery_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Look for date patterns
        date_patterns = [
            r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})',
            r'(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{2,4})',
            r'((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s+\d{2,4})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return f"Expected {match.group(1)}"
        
        return None
    
    def parse_delivery_date(self, date_text: str) -> Optional[date]:
        """Parse IKEA delivery date format."""
        if not date_text:
            return None
        
        today = datetime.now().date()
        lower_text = date_text.lower().strip()
        
        # Skip delivered orders - be more specific to avoid false positives
        if lower_text.startswith('delivered') or ' delivered ' in lower_text and 'will be delivered' not in lower_text:
            return None
        
        # Handle "today"
        if "today" in lower_text:
            return today
        
        # Handle "tomorrow"
        if "tomorrow" in lower_text:
            tomorrow = today + timedelta(days=1)
            return tomorrow
        
        # Handle relative days like "in 3 days", "within 5 days"
        days_match = re.search(r'(?:in|within)\s+(\d+)\s+days?', lower_text)
        if days_match:
            days = int(days_match.group(1))
            target_date = today + timedelta(days=days)
            return target_date
        
        # Handle weekdays
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for i, day_name in enumerate(weekdays):
            if day_name in lower_text:
                days_ahead = (i - today.weekday() + 7) % 7
                if days_ahead == 0:
                    days_ahead = 7
                target_date = today + timedelta(days=days_ahead)
                return target_date
        
        # Handle specific date formats - prioritize patterns with explicit years
        date_patterns = [
            # DD Month YYYY format (with explicit year)
            (r'(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{4})', '%d %b %Y'),
            # Month DD, YYYY format (with explicit year)
            (r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2}),?\s+(\d{4})', '%b %d %Y'),
            # DD/MM/YYYY, DD-MM-YYYY
            (r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})', '%d/%m/%Y'),
            # DD/MM/YY, DD-MM-YY
            (r'(\d{1,2})[-/](\d{1,2})[-/](\d{2})', '%d/%m/%y'),
            # DD Month (current year) - only after explicit year patterns
            (r'(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*(?!\s+\d{4})', '%d %b'),
        ]
        
        for pattern, date_format in date_patterns:
            match = re.search(pattern, lower_text)
            if match:
                try:
                    if date_format == '%d %b':
                        # For patterns without year, assume current year
                        date_str = f"{match.group(1)} {match.group(2)} {today.year}"
                        parsed_date = datetime.strptime(date_str, '%d %b %Y').date()
                    elif date_format == '%d %b %Y':
                        # DD Month YYYY format
                        date_str = f"{match.group(1)} {match.group(2)} {match.group(3)}"
                        parsed_date = datetime.strptime(date_str, '%d %b %Y').date()
                    elif date_format == '%b %d %Y':
                        # Month DD, YYYY format
                        date_str = f"{match.group(1)} {match.group(2)} {match.group(3)}"
                        parsed_date = datetime.strptime(date_str, '%b %d %Y').date()
                    elif date_format == '%d/%m/%Y':
                        # DD/MM/YYYY format
                        date_str = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"
                        parsed_date = datetime.strptime(date_str, '%d/%m/%Y').date()
                    elif date_format == '%d/%m/%y':
                        # DD/MM/YY format - handle 2-digit year
                        year = int(match.group(3))
                        if year < 50:
                            year += 2000
                        else:
                            year += 1900
                        date_str = f"{match.group(1)}/{match.group(2)}/{year}"
                        parsed_date = datetime.strptime(date_str, '%d/%m/%Y').date()
                    else:
                        continue
                    return parsed_date
                except ValueError:
                    continue
        return None
