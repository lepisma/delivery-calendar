import pytest
from datetime import datetime, date, timedelta
from amazon_orders import parse_delivery_date


class TestParseDeliveryDate:
    """Test suite for the parse_delivery_date function."""

    def test_arriving_today_no_time(self):
        """Test parsing 'Arriving today' without time."""
        result = parse_delivery_date("Arriving today")
        expected_date = datetime.now().date()
        assert result == (expected_date, None)

    def test_arriving_today_with_time(self):
        """Test parsing 'Arriving today' with time range."""
        result = parse_delivery_date("Arriving today 10am - 2pm")
        today = datetime.now().date()
        expected_start = datetime.combine(today, datetime.strptime("10am", "%I%p").time())
        expected_end = datetime.combine(today, datetime.strptime("2pm", "%I%p").time())
        assert result == (expected_start, expected_end)

    def test_arriving_today_with_minutes(self):
        """Test parsing 'Arriving today' with time range including minutes."""
        result = parse_delivery_date("Arriving today 10:30am - 2:15pm")
        today = datetime.now().date()
        expected_start = datetime.combine(today, datetime.strptime("10:30am", "%I:%M%p").time())
        expected_end = datetime.combine(today, datetime.strptime("2:15pm", "%I:%M%p").time())
        assert result == (expected_start, expected_end)

    def test_arriving_tomorrow_no_time(self):
        """Test parsing 'Arriving tomorrow' without time."""
        result = parse_delivery_date("Arriving tomorrow")
        expected_date = datetime.now().date() + timedelta(days=1)
        assert result == (expected_date, None)

    def test_arriving_tomorrow_with_time(self):
        """Test parsing 'Arriving tomorrow' with time range."""
        result = parse_delivery_date("Arriving tomorrow 9am - 1pm")
        tomorrow = datetime.now().date() + timedelta(days=1)
        expected_start = datetime.combine(tomorrow, datetime.strptime("9am", "%I%p").time())
        expected_end = datetime.combine(tomorrow, datetime.strptime("1pm", "%I%p").time())
        assert result == (expected_start, expected_end)

    def test_arriving_weekday_no_time(self):
        """Test parsing 'Arriving [weekday]' without time."""
        result = parse_delivery_date("Arriving Sunday")
        today = datetime.now().date()
        # Calculate next Sunday
        days_ahead = (6 - today.weekday() + 7) % 7
        if days_ahead == 0:
            days_ahead = 7
        expected_date = today + timedelta(days=days_ahead)
        assert result == (expected_date, None)

    def test_arriving_weekday_with_time(self):
        """Test parsing 'Arriving [weekday]' with time range."""
        result = parse_delivery_date("Arriving Friday 11am - 3pm")
        today = datetime.now().date()
        # Calculate next Friday
        days_ahead = (4 - today.weekday() + 7) % 7
        if days_ahead == 0:
            days_ahead = 7
        target_date = today + timedelta(days=days_ahead)
        expected_start = datetime.combine(target_date, datetime.strptime("11am", "%I%p").time())
        expected_end = datetime.combine(target_date, datetime.strptime("3pm", "%I%p").time())
        assert result == (expected_start, expected_end)

    def test_date_range_no_time(self):
        """Test parsing date ranges like '16 July - 19 July'."""
        current_year = datetime.now().year
        result = parse_delivery_date("16 July - 19 July")
        expected_start = date(current_year, 7, 16)
        expected_end = date(current_year, 7, 20)  # End date is exclusive, so add 1 day
        assert result == (expected_start, expected_end)

    def test_date_range_abbreviated_month(self):
        """Test parsing date ranges with abbreviated month names."""
        current_year = datetime.now().year
        result = parse_delivery_date("5 Dec - 8 Dec")
        expected_start = date(current_year, 12, 5)
        expected_end = date(current_year, 12, 9)  # End date is exclusive, so add 1 day
        assert result == (expected_start, expected_end)

    def test_specific_date_no_time(self):
        """Test parsing specific dates like '14 July 2025'."""
        result = parse_delivery_date("14 July 2025")
        expected_date = date(2025, 7, 14)
        assert result == (expected_date, None)

    def test_specific_date_current_year(self):
        """Test parsing specific dates without year (assumes current year)."""
        current_year = datetime.now().year
        result = parse_delivery_date("25 March")
        expected_date = date(current_year, 3, 25)
        assert result == (expected_date, None)

    def test_specific_date_with_time(self):
        """Test parsing specific dates with time range."""
        current_year = datetime.now().year
        result = parse_delivery_date("25 March 8am - 12pm")
        target_date = date(current_year, 3, 25)
        expected_start = datetime.combine(target_date, datetime.strptime("8am", "%I%p").time())
        expected_end = datetime.combine(target_date, datetime.strptime("12pm", "%I%p").time())
        assert result == (expected_start, expected_end)

    def test_delivered_order_skipped(self):
        """Test that delivered orders return None (should be skipped)."""
        result = parse_delivery_date("Delivered 9 July")
        current_year = datetime.now().year
        expected_date = date(current_year, 7, 9)
        assert result == (expected_date, None)

    def test_time_range_with_dash(self):
        """Test parsing time ranges with regular dash."""
        result = parse_delivery_date("Arriving today 2pm - 6pm")
        today = datetime.now().date()
        expected_start = datetime.combine(today, datetime.strptime("2pm", "%I%p").time())
        expected_end = datetime.combine(today, datetime.strptime("6pm", "%I%p").time())
        assert result == (expected_start, expected_end)

    def test_time_range_with_en_dash(self):
        """Test parsing time ranges with en-dash (–)."""
        result = parse_delivery_date("Arriving today 2pm – 6pm")
        today = datetime.now().date()
        expected_start = datetime.combine(today, datetime.strptime("2pm", "%I%p").time())
        expected_end = datetime.combine(today, datetime.strptime("6pm", "%I%p").time())
        assert result == (expected_start, expected_end)

    def test_time_range_no_spaces(self):
        """Test parsing time ranges without spaces around dash."""
        result = parse_delivery_date("Arriving today 10am-2pm")
        today = datetime.now().date()
        expected_start = datetime.combine(today, datetime.strptime("10am", "%I%p").time())
        expected_end = datetime.combine(today, datetime.strptime("2pm", "%I%p").time())
        assert result == (expected_start, expected_end)

    def test_invalid_date_format(self):
        """Test parsing invalid date formats returns None."""
        result = parse_delivery_date("Invalid date format")
        assert result == (None, None)

    def test_empty_string(self):
        """Test parsing empty string returns None."""
        result = parse_delivery_date("")
        assert result == (None, None)

    def test_case_insensitive(self):
        """Test that parsing is case insensitive."""
        result = parse_delivery_date("ARRIVING TODAY")
        expected_date = datetime.now().date()
        assert result == (expected_date, None)

    def test_mixed_case_with_time(self):
        """Test mixed case input with time range."""
        result = parse_delivery_date("Arriving TODAY 10AM - 2PM")
        today = datetime.now().date()
        expected_start = datetime.combine(today, datetime.strptime("10AM", "%I%p").time())
        expected_end = datetime.combine(today, datetime.strptime("2PM", "%I%p").time())
        assert result == (expected_start, expected_end)

    def test_time_parsing_failure_fallback(self):
        """Test that invalid time formats fall back to date-only parsing."""
        result = parse_delivery_date("Arriving today 25am - 30pm")  # Invalid times
        expected_date = datetime.now().date()
        assert result == (expected_date, None)

    def test_now_expected_by_date(self):
        """Test parsing 'now expected by [date]' format."""
        current_year = datetime.now().year
        result = parse_delivery_date("now expected by 19 july")
        expected_date = date(current_year, 7, 19)
        assert result == (expected_date, None)

    def test_now_expected_by_date_abbreviated(self):
        """Test parsing 'now expected by [date]' format with abbreviated month."""
        current_year = datetime.now().year
        result = parse_delivery_date("now expected by 25 dec")
        expected_date = date(current_year, 12, 25)
        assert result == (expected_date, None)

    def test_now_expected_by_case_insensitive(self):
        """Test that 'now expected by' parsing is case insensitive."""
        current_year = datetime.now().year
        result = parse_delivery_date("Now Expected By 15 March")
        expected_date = date(current_year, 3, 15)
        assert result == (expected_date, None)
