import os
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime, date
from parsers import parse_delivery_date


def parse_bookswagon_date(date_str):
    """
    Parse Bookswagon-specific date formats.
    Returns (start_date, end_date) tuple. end_date is None for single-day events.
    """
    if not date_str:
        return (None, None)
    
    today = datetime.now().date()
    clean_str = date_str.strip().lower()
    
    # Handle common Bookswagon date formats
    # Example: "Expected delivery: 15-20 July 2024"
    if "expected delivery" in clean_str:
        clean_str = clean_str.replace("expected delivery:", "").strip()
    
    # Handle date ranges like "15-20 July 2024"
    range_pattern = r'(\d{1,2})-(\d{1,2})\s+(\w+)\s+(\d{4})'
    range_match = re.search(range_pattern, clean_str)
    if range_match:
        start_day = int(range_match.group(1))
        end_day = int(range_match.group(2))
        month_name = range_match.group(3)
        year = int(range_match.group(4))
        
        try:
            start_date = datetime.strptime(f"{start_day} {month_name} {year}", '%d %B %Y').date()
            end_date = datetime.strptime(f"{end_day} {month_name} {year}", '%d %B %Y').date()
            # For ICS, end date is exclusive, so add one day
            return (start_date, end_date + timedelta(days=1))
        except ValueError:
            try:
                start_date = datetime.strptime(f"{start_day} {month_name} {year}", '%d %b %Y').date()
                end_date = datetime.strptime(f"{end_day} {month_name} {year}", '%d %b %Y').date()
                return (start_date, end_date + timedelta(days=1))
            except ValueError:
                pass
    
    # Handle single dates like "15 July 2024"
    single_date_patterns = [
        '%d %B %Y',
        '%d %b %Y',
        '%d-%m-%Y',
        '%d/%m/%Y'
    ]
    
    for pattern in single_date_patterns:
        try:
            parsed_date = datetime.strptime(clean_str, pattern).date()
            return (parsed_date, None)
        except ValueError:
            continue
    
    # Fallback to the generic parser
    return parse_delivery_date(date_str)


def scrape_bookswagon(username, password):
    """
    Logs into Bookswagon using provided credentials, scrapes order history,
    visits each order detail page, and returns an ICS calendar object.
    """
    print("🚀 Starting Bookswagon scraper...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 15)
    cal = Calendar()

    try:
        # Navigate to Bookswagon login page
        print("Navigating to Bookswagon login page...")
        driver.get("https://www.bookswagon.com/login")
        
        # Wait for login form to load
        print("Entering credentials...")
        email_field = wait.until(EC.presence_of_element_located((By.NAME, "email")))
        password_field = driver.find_element(By.NAME, "password")
        
        email_field.send_keys(username)
        password_field.send_keys(password)
        
        # Submit login form
        login_button = driver.find_element(By.XPATH, "//input[@type='submit' or @value='Login']")
        login_button.click()
        
        # Wait for successful login (check for account/profile page or orders link)
        try:
            wait.until(EC.any_of(
                EC.presence_of_element_located((By.LINK_TEXT, "My Orders")),
                EC.presence_of_element_located((By.PARTIAL_LINK_TEXT, "Orders")),
                EC.presence_of_element_located((By.XPATH, "//a[contains(@href, 'orders') or contains(@href, 'account')]"))
            ))
            print("Successfully logged into Bookswagon.")
        except TimeoutException:
            print("❌ Login may have failed. Continuing anyway...")
        
        # Navigate to orders page
        print("Navigating to orders page...")
        try:
            # Try multiple possible selectors for orders link
            orders_link = None
            possible_selectors = [
                (By.LINK_TEXT, "My Orders"),
                (By.PARTIAL_LINK_TEXT, "Orders"),
                (By.XPATH, "//a[contains(@href, 'orders')]"),
                (By.XPATH, "//a[contains(text(), 'Order')]")
            ]
            
            for selector_type, selector_value in possible_selectors:
                try:
                    orders_link = driver.find_element(selector_type, selector_value)
                    break
                except NoSuchElementException:
                    continue
            
            if orders_link:
                orders_link.click()
            else:
                # Fallback: try direct URL
                driver.get("https://www.bookswagon.com/account/orders")
                
        except Exception as e:
            print(f"⚠️ Could not find orders link, trying direct URL: {e}")
            driver.get("https://www.bookswagon.com/account/orders")
        
        # Wait for orders page to load
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        print("Orders page loaded.")
        
        # Parse the orders page
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Find order elements - try multiple possible selectors
        order_elements = []
        possible_order_selectors = [
            'div.order-item',
            'div.order',
            'tr.order-row',
            '.order-container',
            '[class*="order"]'
        ]
        
        for selector in possible_order_selectors:
            order_elements = soup.select(selector)
            if order_elements:
                print(f"Found {len(order_elements)} orders using selector: {selector}")
                break
        
        if not order_elements:
            # Fallback: look for any links that might be order details
            order_links = soup.find_all('a', href=re.compile(r'order|detail'))
            print(f"Fallback: Found {len(order_links)} potential order links")
            
            for link in order_links[:10]:  # Limit to first 10 to avoid too many requests
                try:
                    order_url = link.get('href')
                    if not order_url.startswith('http'):
                        order_url = 'https://www.bookswagon.com' + order_url
                    
                    print(f"Visiting order detail page: {order_url}")
                    driver.get(order_url)
                    
                    # Extract delivery information from order detail page
                    detail_soup = BeautifulSoup(driver.page_source, 'html.parser')
                    
                    # Look for delivery/shipping information
                    delivery_info = extract_delivery_info_from_page(detail_soup)
                    
                    if delivery_info:
                        book_title = delivery_info.get('title', 'Unknown Book')
                        delivery_date_str = delivery_info.get('delivery_date')
                        
                        if delivery_date_str:
                            start_date, end_date = parse_bookswagon_date(delivery_date_str)
                            
                            if start_date:
                                event = Event()
                                event.name = f"📚 Bookswagon: {book_title}"
                                event.begin = start_date
                                if end_date:
                                    event.end = end_date
                                
                                event.description = f"Order details: {order_url}"
                                
                                # Only make all-day if we don't have specific times
                                if isinstance(start_date, date) and not isinstance(start_date, datetime):
                                    event.make_all_day()
                                
                                cal.events.add(event)
                                print(f"✅ Added event: {event.name} on {event.begin}")
                            else:
                                print(f"⚠️ Could not parse delivery date: '{delivery_date_str}'")
                
                except Exception as e:
                    print(f"⚠️ Error processing order link {order_url}: {e}")
                    continue
        else:
            # Process found order elements
            for i, order_element in enumerate(order_elements[:10]):  # Limit to first 10 orders
                try:
                    # Look for order detail link within this order element
                    detail_link = order_element.find('a', href=re.compile(r'order|detail'))
                    
                    if detail_link:
                        order_url = detail_link.get('href')
                        if not order_url.startswith('http'):
                            order_url = 'https://www.bookswagon.com' + order_url
                        
                        print(f"Visiting order detail page {i+1}: {order_url}")
                        driver.get(order_url)
                        
                        # Extract delivery information from order detail page
                        detail_soup = BeautifulSoup(driver.page_source, 'html.parser')
                        
                        delivery_info = extract_delivery_info_from_page(detail_soup)
                        
                        if delivery_info:
                            book_title = delivery_info.get('title', 'Unknown Book')
                            delivery_date_str = delivery_info.get('delivery_date')
                            
                            if delivery_date_str:
                                start_date, end_date = parse_bookswagon_date(delivery_date_str)
                                
                                if start_date:
                                    event = Event()
                                    event.name = f"📚 Bookswagon: {book_title}"
                                    event.begin = start_date
                                    if end_date:
                                        event.end = end_date
                                    
                                    event.description = f"Order details: {order_url}"
                                    
                                    # Only make all-day if we don't have specific times
                                    if isinstance(start_date, date) and not isinstance(start_date, datetime):
                                        event.make_all_day()
                                    
                                    cal.events.add(event)
                                    print(f"✅ Added event: {event.name} on {event.begin}")
                                else:
                                    print(f"⚠️ Could not parse delivery date: '{delivery_date_str}'")
                    
                except Exception as e:
                    print(f"⚠️ Error processing order {i+1}: {e}")
                    continue

    except Exception as e:
        print(f"❌ An error occurred during Bookswagon scraping: {e}")
        driver.save_screenshot("bookswagon_error.png")

    finally:
        driver.quit()
        print("✅ Bookswagon scraper finished.")
        return cal


def extract_delivery_info_from_page(soup):
    """
    Extract delivery information from a Bookswagon order detail page.
    Returns a dictionary with 'title' and 'delivery_date' keys.
    """
    delivery_info = {}
    
    # Extract book title
    title_selectors = [
        'h1',
        '.product-title',
        '.book-title',
        '[class*="title"]',
        '.order-item-title'
    ]
    
    for selector in title_selectors:
        title_element = soup.select_one(selector)
        if title_element and title_element.get_text().strip():
            delivery_info['title'] = title_element.get_text().strip()
            break
    
    # Extract delivery date
    delivery_keywords = [
        'delivery', 'shipping', 'dispatch', 'expected', 'arrival', 'estimated'
    ]
    
    # Look for delivery information in various elements
    for keyword in delivery_keywords:
        # Search in text content
        elements = soup.find_all(text=re.compile(keyword, re.IGNORECASE))
        for element in elements:
            parent = element.parent if element.parent else element
            text = parent.get_text().strip()
            
            # Extract date from the text
            date_pattern = r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}\s+\w+\s+\d{2,4}|\d{1,2}-\d{1,2}\s+\w+\s+\d{2,4})'
            date_match = re.search(date_pattern, text)
            if date_match:
                delivery_info['delivery_date'] = date_match.group(1)
                break
        
        if 'delivery_date' in delivery_info:
            break
    
    # If no delivery date found, look for status information
    if 'delivery_date' not in delivery_info:
        status_selectors = [
            '.order-status',
            '.shipping-status',
            '[class*="status"]',
            '.delivery-info'
        ]
        
        for selector in status_selectors:
            status_element = soup.select_one(selector)
            if status_element:
                status_text = status_element.get_text().strip()
                # Look for dates in status text
                date_pattern = r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}\s+\w+\s+\d{2,4})'
                date_match = re.search(date_pattern, status_text)
                if date_match:
                    delivery_info['delivery_date'] = date_match.group(1)
                    break
    
    return delivery_info
