"""
Amazon scraper implementation.
"""

import re
import pyotp
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional, Tuple, Union

from .base import Scraper


def parse_delivery_date(delivery_date_str):
    """
    Parses various date string formats from Amazon into start and end datetime tuples.
    Returns (start_datetime, end_datetime). end_datetime is None for single-day events.
    If time is found, returns datetime objects with time. Otherwise returns date objects.
    """
    today = datetime.now().date()
    lower_str = delivery_date_str.lower()

    # --- Handle "Now expected by" ---
    if "now expected by" in lower_str:
        # Isolate the date part of the string
        date_part_str = lower_str.replace("now expected by", "").strip()
        # Parse dates like "19 July" or "19 Jul"
        for fmt in ('%d %B', '%d %b'):
            try:
                dt = datetime.strptime(date_part_str, fmt)
                # Assume current year if not specified
                target_date = dt.replace(year=today.year).date()
                return (target_date, None)
            except ValueError:
                continue

    # Extract time range if present (e.g., "10am - 2pm", "10:30am-2:30pm")
    time_pattern = r'(\d{1,2}(?::\d{2})?)\s*([ap]m)\s*[-–]\s*(\d{1,2}(?::\d{2})?)\s*([ap]m)'
    time_match = re.search(time_pattern, lower_str)

    start_time = None
    end_time = None

    if time_match:
        start_time_str = time_match.group(1) + time_match.group(2)
        end_time_str = time_match.group(3) + time_match.group(4)

        try:
            # Parse start time
            if ':' in start_time_str:
                start_time = datetime.strptime(start_time_str, '%I:%M%p').time()
            else:
                start_time = datetime.strptime(start_time_str, '%I%p').time()

            # Parse end time
            if ':' in end_time_str:
                end_time = datetime.strptime(end_time_str, '%I:%M%p').time()
            else:
                end_time = datetime.strptime(end_time_str, '%I%p').time()
        except ValueError:
            # If time parsing fails, fall back to no time
            start_time = None
            end_time = None

    # Remove time range from string for cleaner date parsing
    clean_str = lower_str
    if time_match:
        clean_str = re.sub(time_pattern, '', clean_str).strip()

    # --- Handle "today" ---
    if "today" in clean_str:
        if start_time and end_time:
            start_datetime = datetime.combine(today, start_time)
            end_datetime = datetime.combine(today, end_time)
            return (start_datetime, end_datetime)
        return (today, None)

    # --- Handle "tomorrow" ---
    if "tomorrow" in clean_str:
        tomorrow = today + timedelta(days=1)
        if start_time and end_time:
            start_datetime = datetime.combine(tomorrow, start_time)
            end_datetime = datetime.combine(tomorrow, end_time)
            return (start_datetime, end_datetime)
        return (tomorrow, None)

    # --- Handle weekdays e.g., "Arriving Sunday" ---
    if "arriving" in clean_str:
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for i, day_name in enumerate(weekdays):
            if day_name in clean_str:
                days_ahead = (i - today.weekday() + 7) % 7
                if days_ahead == 0:
                    days_ahead = 7
                target_date = today + timedelta(days=days_ahead)
                if start_time and end_time:
                    start_datetime = datetime.combine(target_date, start_time)
                    end_datetime = datetime.combine(target_date, end_time)
                    return (start_datetime, end_datetime)
                return (target_date, None)

    # --- Handle Date Ranges e.g., "16 July - 19 July" ---
    if '-' in clean_str and not time_match:
        clean_range_str = clean_str.replace("arriving ", "").strip()
        parts = [p.strip() for p in clean_range_str.split('-')]
        try:
            start_date_str = parts[0]
            end_date_str = parts[1]

            # Parse start date (e.g., '16 July')
            try:
                start_date = datetime.strptime(start_date_str, '%d %B').replace(year=today.year).date()
            except ValueError:
                start_date = datetime.strptime(start_date_str, '%d %b').replace(year=today.year).date()

            # Parse end date (e.g., '19 July')
            try:
                end_date = datetime.strptime(end_date_str, '%d %B %Y').date()
            except ValueError:
                try:
                    end_date = datetime.strptime(end_date_str, '%d %b %Y').date()
                except ValueError:
                    try:
                        end_date = datetime.strptime(end_date_str, '%d %B').replace(year=start_date.year).date()
                    except ValueError:
                        end_date = datetime.strptime(end_date_str, '%d %b').replace(year=start_date.year).date()

            # For ICS, the end date is exclusive, so add one day
            return (start_date, end_date + timedelta(days=1))
        except (ValueError, IndexError) as e:
            print(f"Could not parse range '{delivery_date_str}': {e}")
            return (None, None)

    # --- Handle Specific Dates e.g., "Delivered 9 July" or "14 July 2025" ---
    clean_date_str = clean_str.replace("delivered ", "").replace("arriving ", "").strip()
    for fmt in ('%d %B %Y', '%d %b %Y', '%d %B', '%d %b'):
        try:
            dt = datetime.strptime(clean_date_str, fmt)
            if dt.year == 1900:
                dt = dt.replace(year=today.year)
            target_date = dt.date()
            if start_time and end_time:
                start_datetime = datetime.combine(target_date, start_time)
                end_datetime = datetime.combine(target_date, end_time)
                return (start_datetime, end_datetime)
            return (target_date, None)
        except ValueError:
            continue

    return (None, None)


class AmazonScraper(Scraper):
    """
    Amazon-specific scraper implementation.
    """
    
    def __init__(self, email: str, password: str, totp_secret: Optional[str] = None, output_dir: str = "output", max_pages: int = 3):
        """
        Initialize Amazon scraper with credentials and optional TOTP secret.
        
        Args:
            email: Amazon login email
            password: Amazon login password
            totp_secret: Optional TOTP secret for 2FA
            output_dir: Directory to save output files
            max_pages: Maximum number of order pages to scrape
        """
        super().__init__(email, password, output_dir)
        self.totp_secret = totp_secret
        self.max_pages = max_pages
    
    def login(self) -> bool:
        """Login to Amazon website."""
        try:
            url = "https://www.amazon.in/ap/signin?openid.pape.max_auth_age=0&openid.return_to=https%3A%2F%2Fwww.amazon.in%2Fyour-orders%2Forders%3Fref_%3Dnav_orders_first&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.assoc_handle=amzn_retail_yourorders_in&openid.mode=checkid_setup&language=en_IN&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0"
            self.driver.get(url)

            self.logger.info("Entering username...")
            email_field = self.wait.until(EC.presence_of_element_located((By.ID, "ap_email")))
            email_field.send_keys(self.email)
            self.driver.find_element(By.ID, "continue").click()

            self.logger.info("Entering password...")
            password_field = self.wait.until(EC.presence_of_element_located((By.ID, "ap_password")))
            password_field.send_keys(self.password)
            self.driver.find_element(By.ID, "signInSubmit").click()

            # Handle 2FA/OTP if required
            try:
                otp_field = self.wait.until(EC.presence_of_element_located((By.ID, "auth-mfa-otpcode")))
                self.logger.info("2FA required. Generating OTP...")
                
                if not self.totp_secret:
                    raise ValueError("Amazon is asking for 2FA, but no TOTP_SECRET was provided.")

                totp = pyotp.TOTP(self.totp_secret)
                otp_code = totp.now()
                
                otp_field.send_keys(otp_code)
                self.logger.info("Submitting OTP...")
                self.driver.find_element(By.ID, "auth-signin-button").click()

            except TimeoutException:
                self.logger.info("2FA not required for this session.")

            self.wait.until(EC.title_contains("Your Orders"))
            self.logger.info("Successfully logged into Amazon.")
            return True
            
        except Exception as e:
            self.logger.error(f"Login failed: {str(e)}")
            return False
    
    def scrape_orders(self) -> List[Dict[str, Any]]:
        """Scrape orders from Amazon."""
        orders = []
        
        try:
            # Loop through multiple pages
            for page_num in range(1, self.max_pages + 1):
                self.logger.info(f"Scraping page {page_num}/{self.max_pages}...")
                
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                order_cards = soup.find_all('div', class_='a-box-group a-spacing-base')
                self.logger.info(f"Found {len(order_cards)} order cards on page {page_num}.")

                for card in order_cards:
                    # Find delivery status container
                    delivery_status_container = card.find(lambda tag: (tag.name == 'div' or tag.name == 'span') and ("Arriving" in tag.text or "Delivered" in tag.text or "expected" in tag.text))

                    if delivery_status_container:
                        delivery_date_element = delivery_status_container.find('span', class_='a-text-bold')
                    else:
                        delivery_date_element = None

                    if delivery_date_element:
                        delivery_date_str = delivery_date_element.text.strip()

                        if "delivered" in delivery_date_str.lower():
                            self.logger.info(f"⏩ Skipping delivered order (Status: {delivery_date_str})")
                            continue

                        start_date, end_date = parse_delivery_date(delivery_date_str)

                        if start_date:
                            # Find the order details link
                            order_link = None
                            order_link_element = card.find('a', href=lambda href: href and 'order-details' in href)
                            if not order_link_element:
                                order_link_element = card.find('a', string=lambda text: text and 'order details' in text.lower())
                            if not order_link_element:
                                order_link_element = card.find('a', href=lambda href: href and 'gp/your-account/order-details' in href)
                                
                            if order_link_element and order_link_element.get('href'):
                                order_link = order_link_element['href']
                                if order_link.startswith('/'):
                                    order_link = 'https://www.amazon.in' + order_link

                            # Find product elements
                            product_elements = card.find_all('div', class_='yohtmlc-product-title')
                            
                            if not product_elements:
                                product_elements = card.find_all('a', class_='a-link-normal')
                                product_elements = [elem for elem in product_elements if elem.text.strip() and len(elem.text.strip()) > 5]

                            if not product_elements:
                                # Fallback: create one order for the entire card
                                orders.append({
                                    'title': f"📦 Amazon: Unknown Product",
                                    'start_date': start_date,
                                    'end_date': end_date,
                                    'order_link': order_link,
                                    'status': delivery_date_str
                                })
                                self.logger.info(f"✅ Added order: Unknown Product on {start_date}")
                            else:
                                # Create separate orders for each product
                                for product_element in product_elements:
                                    product_name = product_element.text.strip()
                                    if product_name:
                                        orders.append({
                                            'title': f"📦 Amazon: {product_name}",
                                            'start_date': start_date,
                                            'end_date': end_date,
                                            'order_link': order_link,
                                            'status': delivery_date_str
                                        })
                                        self.logger.info(f"✅ Added order: {product_name} on {start_date}")
                        else:
                            self.logger.warning(f"⚠️ Could not parse date: '{delivery_date_str}'")

                # Navigate to next page
                if page_num < self.max_pages:
                    try:
                        next_button = self.driver.find_element(By.CSS_SELECTOR, "ul.a-pagination li.a-last a")
                        
                        if "a-disabled" in next_button.find_element(By.XPATH, "..").get_attribute("class"):
                            self.logger.info("Reached the last page of orders.")
                            break

                        self.logger.info("Navigating to the next page...")
                        next_button.click()
                        
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.CLASS_NAME, "a-box-group"))
                        )

                    except Exception as e:
                        self.logger.info(f"No more pages found or 'Next' button is not clickable: {e}")
                        break
                        
        except Exception as e:
            self.logger.error(f"Error during order scraping: {str(e)}")
            
        return orders
    
    def parse_delivery_date(self, date_text: str) -> Optional[str]:
        """Parse Amazon delivery date format."""
        start_date, end_date = parse_delivery_date(date_text)
        if start_date:
            if isinstance(start_date, datetime):
                return start_date.strftime('%Y-%m-%d')
            elif isinstance(start_date, date):
                return start_date.strftime('%Y-%m-%d')
        return None
    
    def get_output_filename(self) -> str:
        """Get output filename for Amazon orders."""
        return "amazon_orders.ics"
    
    def generate_ics_file(self, orders: List[Dict[str, Any]], output_file: str):
        """Generate an ICS calendar file from Amazon orders using the ics library."""
        cal = Calendar()
        
        for order in orders:
            if order.get('start_date'):
                event = Event()
                event.name = order['title']
                event.begin = order['start_date']
                
                if order.get('end_date'):
                    event.end = order['end_date']
                
                if order.get('order_link'):
                    event.description = f"Order details: {order['order_link']}"
                
                # Only make all-day if we don't have specific times
                if isinstance(order['start_date'], date) and not isinstance(order['start_date'], datetime):
                    event.make_all_day()
                
                cal.events.add(event)
        
        with open(output_file, 'w') as f:
            f.writelines(cal)
