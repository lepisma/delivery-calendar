import os
import pyotp
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from ics import Calendar, Event
from datetime import datetime, timedelta
import time
import schedule


def parse_delivery_date(delivery_date_str):
    """
    Parses various date string formats from Amazon into a start and end date tuple.
    Returns (start_date, end_date). end_date is None for single-day events.
    """
    today = datetime.now().date()
    lower_str = delivery_date_str.lower()

    # --- Handle "today" ---
    if "today" in lower_str:
        return (today, None)

    # --- Handle "tomorrow" ---
    if "tomorrow" in lower_str:
        return (today + timedelta(days=1), None)

    # --- Handle weekdays e.g., "Arriving Sunday" ---
    if "arriving" in lower_str:
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for i, day_name in enumerate(weekdays):
            if day_name in lower_str:
                days_ahead = (i - today.weekday() + 7) % 7
                if days_ahead == 0: days_ahead = 7 # If it's today, assume next week
                return (today + timedelta(days=days_ahead), None)

    # --- Handle Date Ranges e.g., "16 July - 19 July" ---
    if '-' in lower_str:
        clean_str = lower_str.replace("arriving ", "").strip()
        parts = [p.strip() for p in clean_str.split('-')]
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
    clean_str = lower_str.replace("delivered ", "").replace("arriving ", "").strip()
    for fmt in ('%d %B %Y', '%d %b %Y', '%d %B', '%d %b'):
        try:
            dt = datetime.strptime(clean_str, fmt)
            if dt.year == 1900: # If year was not in the format string
                dt = dt.replace(year=today.year)
            return (dt.date(), None)
        except ValueError:
            continue

    return (None, None)



# The function signature now accepts a third argument for the TOTP secret
def scrape_amazon(username, password, totp_secret):
    """
    Logs into Amazon using provided credentials and 2FA, scrapes orders,
    and returns an ICS calendar object.
    """
    print("🚀 Starting Amazon scraper...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(options=chrome_options)
    wait = WebDriverWait(driver, 15)
    cal = Calendar()

    try:
        url = "https://www.amazon.in/ap/signin?openid.pape.max_auth_age=0&openid.return_to=https%3A%2F%2Fwww.amazon.in%2Fyour-orders%2Forders%3Fref_%3Dnav_orders_first&openid.identity=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.assoc_handle=amzn_retail_yourorders_in&openid.mode=checkid_setup&language=en_IN&openid.claimed_id=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0%2Fidentifier_select&openid.ns=http%3A%2F%2Fspecs.openid.net%2Fauth%2F2.0"
        driver.get(url)

        print("Entering username...")
        email_field = wait.until(EC.presence_of_element_located((By.ID, "ap_email")))
        email_field.send_keys(username)
        driver.find_element(By.ID, "continue").click()

        print("Entering password...")
        password_field = wait.until(EC.presence_of_element_located((By.ID, "ap_password")))
        password_field.send_keys(password)
        driver.find_element(By.ID, "signInSubmit").click()

        # --- NEW: Handle 2FA/OTP ---
        try:
            # Check if Amazon is asking for the OTP
            otp_field = wait.until(EC.presence_of_element_located((By.ID, "auth-mfa-otpcode")))
            print("2FA required. Generating OTP...")
            
            if not totp_secret:
                raise ValueError("Amazon is asking for 2FA, but no TOTP_SECRET was provided.")

            totp = pyotp.TOTP(totp_secret)
            otp_code = totp.now()
            
            otp_field.send_keys(otp_code)
            print("Submitting OTP...")
            driver.find_element(By.ID, "auth-signin-button").click()

        except TimeoutException:
            # If the OTP field doesn't appear after a timeout, we assume 2FA wasn't required
            print("2FA not required for this session.")

        # --- End of new code ---

        wait.until(EC.title_contains("Your Orders"))
        print("Successfully logged into Amazon.")

        # ... (the rest of the script remains the same)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        order_cards = soup.find_all('div', class_='a-box-group a-spacing-base')
        print(f"Found {len(order_cards)} order cards on the page.")

        for card in order_cards:
            # First, find a container that reliably holds the delivery status
            delivery_status_container = card.find(lambda tag: (tag.name == 'div' or tag.name == 'span') and ("Arriving" in tag.text or "Delivered" in tag.text))

            if delivery_status_container:
                # Now, within that container, find the specific bolded span
                delivery_date_element = delivery_status_container.find('span', class_='a-text-bold')
            else:
                delivery_date_element = None # No delivery info found

            product_name_element = card.find('div', class_='yohtmlc-product-title')

            if delivery_date_element:
                product_name = product_name_element.text.strip() if product_name_element else "Unknown Product"
                delivery_date_str = delivery_date_element.text.strip()

                if "delivered" in delivery_date_str.lower():
                    product_name_element = card.find('div', class_='a-row').find('a', class_='a-link-normal')
                    product_name = product_name_element.text.strip() if product_name_element else "Unknown Product"
                    print(f"⏩ Skipping delivered item: {product_name} (Status: {delivery_date_str})")
                    continue

                start_date, end_date = parse_delivery_date(delivery_date_str)

                if start_date:
                    event = Event()
                    event.name = f"📦 Amazon: {product_name}"
                    event.begin = start_date
                    if end_date:
                        event.end = end_date
                    event.make_all_day()
                    cal.events.add(event)
                    print(f"✅ Added event: {event.name} on {event.begin}")
                else:
                    print(f"⚠️ Could not parse date: '{delivery_date_str}'")


    except Exception as e:
        print(f"❌ An error occurred during Amazon scraping: {e}")
        driver.save_screenshot("amazon_error.png")

    finally:
        driver.quit()
        print("✅ Amazon scraper finished.")
        return cal


def main():
    print("--- Starting Daily Delivery Check ---")
    output_dir = "./output"
    os.makedirs(output_dir, exist_ok=True)

    # --- Amazon ---
    amazon_email = os.getenv("AMAZON_EMAIL")
    amazon_password = os.getenv("AMAZON_PASSWORD")
    # Get the new secret from environment variables
    amazon_totp_secret = os.getenv("AMAZON_TOTP_SECRET")

    if amazon_email and amazon_password:
        # Pass the secret to the scraper function
        amazon_calendar = scrape_amazon(amazon_email, amazon_password, amazon_totp_secret)
        if amazon_calendar.events:
            with open(os.path.join(output_dir, "amazon_orders.ics"), "w") as f:
                f.writelines(amazon_calendar)
            print("✔️ Successfully wrote amazon_orders.ics")
    else:
        print("⚠️ Amazon credentials not found. Skipping.")

    print("--- Daily Delivery Check Finished ---")


if __name__ == "__main__":
    main()

    schedule.every(24).hours.do(main)
    print("Daily Delivery Check scheduled to run every 24 hours.")
    print("Press Ctrl+C to stop the scheduler.")

    while True:
        schedule.run_pending()
        time.sleep(1)
