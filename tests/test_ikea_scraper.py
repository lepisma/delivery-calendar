import pytest
from datetime import datetime, date, timedelta
from scrapers.ikea import IkeaScraper


class TestIkeaScraperDateParsing:
    """Test IKEA delivery date parsing functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.scraper = IkeaScraper("test@example.com", "password")
    
    def test_parse_delivery_date_today(self):
        """Test parsing 'today' delivery dates."""
        today = datetime.now().date()
        expected = today.strftime('%Y-%m-%d')
        
        test_cases = [
            "Delivery today",
            "Arriving today",
            "Expected delivery today",
            "TODAY",
            "delivery today between 10am-2pm"
        ]
        
        for case in test_cases:
            result = self.scraper.parse_delivery_date(case)
            assert result == expected, f"Failed for case: {case}"
    
    def test_parse_delivery_date_tomorrow(self):
        """Test parsing 'tomorrow' delivery dates."""
        tomorrow = datetime.now().date() + timedelta(days=1)
        expected = tomorrow.strftime('%Y-%m-%d')
        
        test_cases = [
            "Delivery tomorrow",
            "Arriving tomorrow",
            "Expected delivery tomorrow",
            "TOMORROW",
            "delivery tomorrow 9am-1pm"
        ]
        
        for case in test_cases:
            result = self.scraper.parse_delivery_date(case)
            assert result == expected, f"Failed for case: {case}"
    
    def test_parse_delivery_date_relative_days(self):
        """Test parsing relative day formats."""
        today = datetime.now().date()
        
        test_cases = [
            ("Delivery in 3 days", 3),
            ("Arriving within 5 days", 5),
            ("Expected in 7 days", 7),
            ("Delivery within 1 day", 1),
            ("in 10 days", 10)
        ]
        
        for case, days in test_cases:
            expected = (today + timedelta(days=days)).strftime('%Y-%m-%d')
            result = self.scraper.parse_delivery_date(case)
            assert result == expected, f"Failed for case: {case}"
    
    def test_parse_delivery_date_weekdays(self):
        """Test parsing weekday delivery dates."""
        today = datetime.now().date()
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        
        for i, day_name in enumerate(weekdays):
            days_ahead = (i - today.weekday() + 7) % 7
            if days_ahead == 0:
                days_ahead = 7
            expected_date = today + timedelta(days=days_ahead)
            expected = expected_date.strftime('%Y-%m-%d')
            
            test_cases = [
                f"Delivery {day_name}",
                f"Arriving {day_name}",
                f"Expected {day_name.upper()}",
                f"delivery on {day_name}"
            ]
            
            for case in test_cases:
                result = self.scraper.parse_delivery_date(case)
                assert result == expected, f"Failed for case: {case} (expected {expected})"
    
    def test_parse_delivery_date_specific_formats(self):
        """Test parsing specific date formats."""
        test_cases = [
            # DD/MM/YYYY format
            ("Delivery 15/12/2024", "2024-12-15"),
            ("Arriving 03/01/2025", "2025-01-03"),
            ("Expected 25/06/2024", "2024-06-25"),
            
            # DD-MM-YYYY format
            ("Delivery 15-12-2024", "2024-12-15"),
            ("Arriving 03-01-2025", "2025-01-03"),
            
            # DD/MM/YY format
            ("Delivery 15/12/24", "2024-12-15"),
            ("Arriving 03/01/25", "2025-01-03"),
            
            # DD Month YYYY format
            ("Delivery 15 December 2024", "2024-12-15"),
            ("Arriving 3 Jan 2025", "2025-01-03"),
            ("Expected 25 Jun 2024", "2024-06-25"),
            ("delivery 1 february 2024", "2024-02-01"),
            
            # Month DD, YYYY format
            ("Delivery December 15, 2024", "2024-12-15"),
            ("Arriving Jan 3, 2025", "2025-01-03"),
            ("Expected June 25 2024", "2024-06-25"),
        ]
        
        for case, expected in test_cases:
            result = self.scraper.parse_delivery_date(case)
            assert result == expected, f"Failed for case: {case} (got {result}, expected {expected})"
    
    def test_parse_delivery_date_current_year_assumption(self):
        """Test parsing dates without year (assumes current year)."""
        current_year = datetime.now().year
        
        test_cases = [
            ("Delivery 15 December", f"{current_year}-12-15"),
            ("Arriving 3 Jan", f"{current_year}-01-03"),
            ("Expected 25 Jun", f"{current_year}-06-25"),
            ("delivery 1 feb", f"{current_year}-02-01"),
        ]
        
        for case, expected in test_cases:
            result = self.scraper.parse_delivery_date(case)
            assert result == expected, f"Failed for case: {case} (got {result}, expected {expected})"
    
    def test_parse_delivery_date_delivered_orders(self):
        """Test that delivered orders return None."""
        test_cases = [
            "Delivered 15/12/2024",
            "Already delivered",
            "DELIVERED",
            "Package delivered yesterday",
            "delivered on 3 Jan 2025"
        ]
        
        for case in test_cases:
            result = self.scraper.parse_delivery_date(case)
            assert result is None, f"Should return None for delivered order: {case}"
    
    def test_parse_delivery_date_invalid_formats(self):
        """Test parsing invalid or unparseable date formats."""
        test_cases = [
            "",
            None,
            "Invalid date",
            "Some random text",
            "Order details",
            "Track package",
            "123456789"
        ]
        
        for case in test_cases:
            result = self.scraper.parse_delivery_date(case)
            assert result is None, f"Should return None for invalid format: {case}"
    
    def test_parse_delivery_date_edge_cases(self):
        """Test edge cases in date parsing."""
        test_cases = [
            # Case insensitive
            ("DELIVERY TODAY", datetime.now().date().strftime('%Y-%m-%d')),
            ("delivery TOMORROW", (datetime.now().date() + timedelta(days=1)).strftime('%Y-%m-%d')),
            
            # Extra whitespace
            ("  delivery today  ", datetime.now().date().strftime('%Y-%m-%d')),
            ("   arriving tomorrow   ", (datetime.now().date() + timedelta(days=1)).strftime('%Y-%m-%d')),
            
            # Mixed with other text
            ("Your order will be delivered today at your address", datetime.now().date().strftime('%Y-%m-%d')),
            ("Package arriving tomorrow between 9am-5pm", (datetime.now().date() + timedelta(days=1)).strftime('%Y-%m-%d')),
        ]
        
        for case, expected in test_cases:
            result = self.scraper.parse_delivery_date(case)
            assert result == expected, f"Failed for edge case: {case}"


class TestIkeaScraperMethods:
    """Test IKEA scraper utility methods."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.scraper = IkeaScraper("test@example.com", "password")
    
    def test_extract_order_id(self):
        """Test order ID extraction."""
        test_cases = [
            ("Order #123456789", "123456789"),
            ("Order: ABC123DEF", "ABC123DEF"),
            ("Purchase #987654321", "987654321"),
            ("Your order 456789123 is ready", "456789123"),
            ("#IKEA123456", "IKEA123456"),
            ("Order number: 111222333", "111222333"),
            ("No order ID here", None),
            ("", None)
        ]
        
        for text, expected in test_cases:
            result = self.scraper._extract_order_id(text)
            assert result == expected, f"Failed for text: {text} (got {result}, expected {expected})"
    
    def test_extract_delivery_info(self):
        """Test delivery information extraction."""
        test_cases = [
            ("Your order will be delivered tomorrow", "delivered tomorrow"),
            ("Package arriving Monday", "arriving Monday"),
            ("Shipped yesterday", "shipped yesterday"),
            ("Expected delivery 15/12/2024", "expected delivery 15/12/2024"),
            ("Estimated arrival: 3 days", "estimated arrival: 3 days"),
            ("No delivery info", None),
            ("", None)
        ]
        
        for text, expected in test_cases:
            result = self.scraper._extract_delivery_info(text)
            if expected:
                assert result and expected.lower() in result.lower(), f"Failed for text: {text} (got {result}, expected to contain {expected})"
            else:
                assert result is None, f"Should return None for text: {text}"
    
    def test_get_output_filename(self):
        """Test output filename generation."""
        result = self.scraper.get_output_filename()
        assert result == "ikea_orders.ics"


class TestIkeaScraperInitialization:
    """Test IKEA scraper initialization."""
    
    def test_initialization_with_defaults(self):
        """Test scraper initialization with default parameters."""
        scraper = IkeaScraper("test@example.com", "password")
        assert scraper.email == "test@example.com"
        assert scraper.password == "password"
        assert scraper.output_dir == "output"
    
    def test_initialization_with_custom_output_dir(self):
        """Test scraper initialization with custom output directory."""
        scraper = IkeaScraper("test@example.com", "password", output_dir="custom_output")
        assert scraper.email == "test@example.com"
        assert scraper.password == "password"
        assert scraper.output_dir == "custom_output"
