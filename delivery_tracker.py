import os
import argparse
from ics import Calendar
import time
import schedule


def run_check():
    print("--- Starting Daily Delivery Check ---")
    output_dir = "./output"
    os.makedirs(output_dir, exist_ok=True)

    # Combined calendar for all vendors
    combined_calendar = Calendar()

    # --- Amazon ---
    amazon_email = os.getenv("AMAZON_EMAIL")
    amazon_password = os.getenv("AMAZON_PASSWORD")
    amazon_totp_secret = os.getenv("AMAZON_TOTP_SECRET")

    if amazon_email and amazon_password:
        print("🔍 Amazon credentials found. Running Amazon scraper...")
        from scrapers.amazon import scrape_amazon
        amazon_calendar = scrape_amazon(amazon_email, amazon_password, amazon_totp_secret)
        if amazon_calendar.events:
            # Add all Amazon events to the combined calendar
            for event in amazon_calendar.events:
                combined_calendar.events.add(event)
            print(f"✔️ Added {len(amazon_calendar.events)} Amazon events to combined calendar")
    else:
        print("⚠️ Amazon credentials not found. Skipping Amazon scraper.")

    # --- Bookswagon ---
    bookswagon_email = os.getenv("BOOKSWAGON_EMAIL")
    bookswagon_password = os.getenv("BOOKSWAGON_PASSWORD")

    if bookswagon_email and bookswagon_password:
        print("🔍 Bookswagon credentials found. Running Bookswagon scraper...")
        from scrapers.bookswagon import scrape_bookswagon
        bookswagon_calendar = scrape_bookswagon(bookswagon_email, bookswagon_password)
        if bookswagon_calendar.events:
            # Add all Bookswagon events to the combined calendar
            for event in bookswagon_calendar.events:
                combined_calendar.events.add(event)
            print(f"✔️ Added {len(bookswagon_calendar.events)} Bookswagon events to combined calendar")
            print(f"✔️ Added {len(amazon_calendar.events)} Amazon events to combined calendar")
    else:
        print("⚠️ Bookswagon credentials not found. Skipping Bookswagon scraper.")

        print("⚠️ Amazon credentials not found. Skipping Amazon scraper.")

    # Write combined calendar
    if combined_calendar.events:
        with open(os.path.join(output_dir, "deliveries.ics"), "w") as f:
            f.writelines(combined_calendar)
        print(f"✔️ Successfully wrote deliveries.ics with {len(combined_calendar.events)} total events")
    else:
        print("⚠️ No delivery events found from any vendor.")

    print("--- Daily Delivery Check Finished ---")


def main():
    parser = argparse.ArgumentParser(description="Multi-vendor delivery calendar generator")
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
