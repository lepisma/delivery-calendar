import os
import argparse
import time
import schedule
from scrapers.amazon import AmazonScraper
from scrapers.ikea import IkeaScraper

def run_check():
    print("--- Starting Daily Delivery Check ---")
    output_dir = "./output"
    os.makedirs(output_dir, exist_ok=True)

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
        success = amazon_scraper.run()
        if success:
            print("✔️ Successfully completed Amazon scraping")
        else:
            print("❌ Amazon scraping failed")
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
        success = ikea_scraper.run()
        if success:
            print("✔️ Successfully completed IKEA scraping")
        else:
            print("❌ IKEA scraping failed")
    else:
        print("⚠️ IKEA credentials not found. Skipping.")

    print("--- Daily Delivery Check Finished ---")

def main():
    parser = argparse.ArgumentParser(description="Amazon delivery calendar generator")
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
