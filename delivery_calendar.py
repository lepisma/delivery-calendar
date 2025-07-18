import os
import argparse
import time
import schedule
from scrapers.amazon import AmazonScraper
from scrapers.ikea import IkeaScraper
from ics import Calendar, Event
from datetime import datetime, date


def generate_ics_file(orders, output_file):
    """Generate an ICS calendar file from combined orders using the ics library."""
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


def run_check():
    print("--- Starting Daily Delivery Check ---")
    output_dir = "./output"
    os.makedirs(output_dir, exist_ok=True)
    
    all_orders = []

    # --- Amazon ---
    amazon_email = os.getenv("AMAZON_EMAIL")
    amazon_password = os.getenv("AMAZON_PASSWORD")
    amazon_totp_secret = os.getenv("AMAZON_TOTP_SECRET")

    if amazon_email and amazon_password:
        amazon_scraper = AmazonScraper(
            email=amazon_email,
            password=amazon_password,
            totp_secret=amazon_totp_secret,
            output_dir=output_dir
        )
        amazon_orders = amazon_scraper.run()
        if amazon_orders:
            all_orders.extend(amazon_orders)
            print(f"✔️ Successfully scraped {len(amazon_orders)} Amazon orders")
        else:
            print("❌ Amazon scraping failed or no orders found")
    else:
        print("⚠️ Amazon credentials not found. Skipping.")

    # --- IKEA ---
    ikea_email = os.getenv("IKEA_EMAIL")
    ikea_password = os.getenv("IKEA_PASSWORD")

    if ikea_email and ikea_password:
        ikea_scraper = IkeaScraper(
            email=ikea_email,
            password=ikea_password,
            output_dir=output_dir
        )
        ikea_orders = ikea_scraper.run()
        if ikea_orders:
            all_orders.extend(ikea_orders)
            print(f"✔️ Successfully scraped {len(ikea_orders)} IKEA orders")
        else:
            print("❌ IKEA scraping failed or no orders found")
    else:
        print("⚠️ IKEA credentials not found. Skipping.")

    # Generate combined calendar file
    if all_orders:
        output_file = os.path.join(output_dir, "calendar.ics")
        generate_ics_file(all_orders, output_file)
        print(f"📅 Generated calendar with {len(all_orders)} total orders: {output_file}")
    else:
        print("⚠️ No orders found from any retailer")

    print("--- Daily Delivery Check Finished ---")


def main():
    parser = argparse.ArgumentParser(description="Delivery calendar generator")
    parser.add_argument("--interval", type=int, default=24,
                       help="Polling interval in hours (default: 24)")
    args = parser.parse_args()

    # Run the check once immediately
    run_check()

    # Schedule recurring checks
    schedule.every(args.interval).hours.do(run_check)
    print(f"Daily Delivery Check scheduled to run every {args.interval} hours.")
    print("Press Ctrl+C to stop the scheduler.")

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    main()
