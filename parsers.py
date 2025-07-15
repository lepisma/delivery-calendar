import re
from datetime import datetime, date, timedelta


def parse_delivery_date(delivery_date_str):
    """
    Parses various date string formats from Amazon into start and end datetime tuples.
    Returns (start_datetime, end_datetime). end_datetime is None for single-day events.
    If time is found, returns datetime objects with time. Otherwise returns date objects.
    """
    today = datetime.now().date()
    lower_str = delivery_date_str.lower()

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

    # --- Handle "today" ---
    if "today" in lower_str:
        if start_time and end_time:
            start_datetime = datetime.combine(today, start_time)
            end_datetime = datetime.combine(today, end_time)
            return (start_datetime, end_datetime)
        return (today, None)

    # --- Handle "tomorrow" ---
    if "tomorrow" in lower_str:
        tomorrow = today + timedelta(days=1)
        if start_time and end_time:
            start_datetime = datetime.combine(tomorrow, start_time)
            end_datetime = datetime.combine(tomorrow, end_time)
            return (start_datetime, end_datetime)
        return (tomorrow, None)

    # --- Handle weekdays e.g., "Arriving Sunday" ---
    if "arriving" in lower_str:
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for i, day_name in enumerate(weekdays):
            if day_name in lower_str:
                days_ahead = (i - today.weekday() + 7) % 7
                if days_ahead == 0: days_ahead = 7 # If it's today, assume next week
                target_date = today + timedelta(days=days_ahead)
                if start_time and end_time:
                    start_datetime = datetime.combine(target_date, start_time)
                    end_datetime = datetime.combine(target_date, end_time)
                    return (start_datetime, end_datetime)
                return (target_date, None)

    # --- Handle Date Ranges e.g., "16 July - 19 July" ---
    if '-' in lower_str and not time_match:  # Only if no time range was found
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
            target_date = dt.date()
            if start_time and end_time:
                start_datetime = datetime.combine(target_date, start_time)
                end_datetime = datetime.combine(target_date, end_time)
                return (start_datetime, end_datetime)
            return (target_date, None)
        except ValueError:
            continue

    return (None, None)


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
