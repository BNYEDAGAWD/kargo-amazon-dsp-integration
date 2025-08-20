"""Validation utilities for creative processing and campaign management."""
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from app.models.creative import CreativeFormat, ViewabilityPhase, ViewabilityVendor


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


class CreativeValidator:
    """Validator for creative configurations and processing."""
    
    # Regular expressions for tag detection
    IAS_TAG_PATTERNS = [
        r'<img[^>]*adsafeprotected[^>]*>',
        r'<script[^>]*ias[^>]*>.*?</script>',
        r'fw\.adsafeprotected\.com',
        r'pixel\.adsafeprotected\.com',
        r'ias\.tracking',
    ]
    
    DV_TAG_PATTERNS = [
        r'<img[^>]*doubleverify[^>]*>',
        r'<script[^>]*dvtp_src[^>]*>.*?</script>',
        r'<script[^>]*doubleVerify[^>]*>.*?</script>',
        r'tps\.doubleverify\.com',
    ]
    
    AMAZON_MACRO_PATTERNS = [
        r'\$\{AMAZON_CLICK_URL\}',
        r'\$\{AMAZON_IMPRESSION_URL\}',
        r'\$\{AMAZON_CAMPAIGN_ID\}',
        r'\$\{AMAZON_CREATIVE_ID\}',
        r'\$\{AMAZON_PLACEMENT_ID\}',
        r'\$\{CACHEBUSTER\}',
    ]
    
    @classmethod
    def validate_snippet_url(cls, url: str) -> bool:
        """Validate that the snippet URL is properly formatted."""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False
            
            # Check if it's a Kargo snippet URL
            if 'snippet.kargo.com' not in parsed.netloc:
                return False
            
            return True
        except Exception:
            return False
    
    @classmethod
    def validate_dimensions(cls, dimensions: str) -> Tuple[int, int]:
        """
        Validate and parse creative dimensions.
        
        Returns:
            Tuple of (width, height)
        
        Raises:
            ValidationError: If dimensions are invalid
        """
        try:
            if 'x' not in dimensions:
                raise ValidationError("Dimensions must be in format 'widthxheight'")
            
            width_str, height_str = dimensions.split('x', 1)
            width = int(width_str)
            height = int(height_str)
            
            if width <= 0 or height <= 0:
                raise ValidationError("Width and height must be positive numbers")
            
            return width, height
        except ValueError:
            raise ValidationError("Width and height must be valid numbers")
    
    @classmethod
    def validate_creative_format_dimensions(cls, format: CreativeFormat, dimensions: str) -> bool:
        """Validate that dimensions are appropriate for the creative format."""
        width, height = cls.validate_dimensions(dimensions)
        
        if format == CreativeFormat.RUNWAY:
            # Runway formats typically use banner dimensions
            valid_runway_sizes = [
                (320, 50), (728, 90), (300, 250), (160, 600), (970, 250)
            ]
            return (width, height) in valid_runway_sizes
        
        elif format in [CreativeFormat.INSTREAM_VIDEO, CreativeFormat.ENHANCED_PREROLL]:
            # Video formats can have companion banners
            valid_video_companion_sizes = [
                (300, 50), (320, 50), (300, 250), (728, 90)
            ]
            return (width, height) in valid_video_companion_sizes
        
        return True
    
    @classmethod
    def detect_ias_tags(cls, creative_code: str) -> List[str]:
        """Detect IAS tracking tags in creative code."""
        found_tags = []
        for pattern in cls.IAS_TAG_PATTERNS:
            matches = re.findall(pattern, creative_code, re.IGNORECASE | re.DOTALL)
            found_tags.extend(matches)
        return found_tags
    
    @classmethod
    def detect_dv_tags(cls, creative_code: str) -> List[str]:
        """Detect DoubleVerify tracking tags in creative code."""
        found_tags = []
        for pattern in cls.DV_TAG_PATTERNS:
            matches = re.findall(pattern, creative_code, re.IGNORECASE | re.DOTALL)
            found_tags.extend(matches)
        return found_tags
    
    @classmethod
    def detect_amazon_macros(cls, creative_code: str) -> List[str]:
        """Detect Amazon DSP macros in creative code."""
        found_macros = []
        for pattern in cls.AMAZON_MACRO_PATTERNS:
            matches = re.findall(pattern, creative_code)
            found_macros.extend(matches)
        return found_macros
    
    @classmethod
    def validate_phase_configuration(
        cls, 
        phase: ViewabilityPhase, 
        vendors: List[ViewabilityVendor],
        creative_code: str
    ) -> List[str]:
        """
        Validate viewability phase configuration against creative code.
        
        Returns:
            List of validation warnings/errors
        """
        warnings = []
        
        ias_tags = cls.detect_ias_tags(creative_code)
        dv_tags = cls.detect_dv_tags(creative_code)
        
        if phase == ViewabilityPhase.PHASE_1:
            # Phase 1: Should only have DV, no IAS
            if ViewabilityVendor.IAS in vendors:
                warnings.append("Phase 1 should not include IAS vendor")
            
            if ias_tags:
                warnings.append(f"Phase 1 creative contains IAS tags that should be removed: {len(ias_tags)} found")
            
            if ViewabilityVendor.DOUBLE_VERIFY in vendors and not dv_tags:
                warnings.append("Phase 1 configured for DV but no DV tags found in creative")
        
        elif phase == ViewabilityPhase.PHASE_2:
            # Phase 2: Should have both IAS (S2S) and DV
            if ViewabilityVendor.IAS not in vendors:
                warnings.append("Phase 2 should include IAS vendor for S2S integration")
            
            if ViewabilityVendor.DOUBLE_VERIFY not in vendors:
                warnings.append("Phase 2 should include DoubleVerify vendor")
            
            # In Phase 2, IAS tags should be minimal (S2S handles measurement)
            if len(ias_tags) > 2:
                warnings.append(f"Phase 2 creative has excessive IAS tags ({len(ias_tags)}), S2S should minimize client-side tags")
        
        return warnings
    
    @classmethod
    def validate_vast_structure(cls, vast_code: str) -> List[str]:
        """Validate VAST XML structure."""
        errors = []
        
        # Check for basic VAST structure
        if '<VAST' not in vast_code:
            errors.append("Missing VAST root element")
        
        if '<Ad>' not in vast_code and '<Ad ' not in vast_code:
            errors.append("Missing Ad element")
        
        if '<Creative>' not in vast_code and '<Creative ' not in vast_code:
            errors.append("Missing Creative element")
        
        # Check for tracking events
        if '<TrackingEvents>' not in vast_code:
            errors.append("Missing TrackingEvents element")
        
        # Check for required tracking events
        required_events = ['start', 'complete']
        for event in required_events:
            if f'event="{event}"' not in vast_code:
                errors.append(f"Missing required tracking event: {event}")
        
        return errors


class CampaignValidator:
    """Validator for campaign configurations."""
    
    @classmethod
    def validate_budget_allocation(
        cls, 
        total_budget: float, 
        line_item_budgets: List[float]
    ) -> List[str]:
        """Validate budget allocation across line items."""
        warnings = []
        
        if not line_item_budgets:
            return ["No line item budgets provided"]
        
        allocated_budget = sum(line_item_budgets)
        
        if allocated_budget > total_budget:
            warnings.append(
                f"Line item budgets (${allocated_budget:,.2f}) exceed total budget (${total_budget:,.2f})"
            )
        
        if allocated_budget < total_budget * 0.8:
            warnings.append(
                f"Line item budgets (${allocated_budget:,.2f}) are significantly under total budget (${total_budget:,.2f})"
            )
        
        return warnings
    
    @classmethod
    def validate_date_range(cls, start_date, end_date) -> List[str]:
        """Validate campaign date range."""
        errors = []
        
        if start_date >= end_date:
            errors.append("Start date must be before end date")
        
        from datetime import date, timedelta
        
        if start_date < date.today():
            errors.append("Start date cannot be in the past")
        
        if (end_date - start_date).days > 365:
            errors.append("Campaign duration cannot exceed 365 days")
        
        if (end_date - start_date).days < 1:
            errors.append("Campaign must run for at least 1 day")
        
        return errors
    
    @classmethod
    def validate_advertiser_id(cls, advertiser_id: str) -> bool:
        """Validate Amazon DSP advertiser ID format."""
        # Amazon DSP advertiser IDs are typically numeric
        return advertiser_id.isdigit() and len(advertiser_id) >= 4


class BulkSheetValidator:
    """Validator for bulk sheet data."""
    
    REQUIRED_ORDER_FIELDS = [
        'Advertiser ID*',
        'Order name*',
        'Active/Inactive',
        'Media Type',
        'Goal and Goal KPI*',
        'Flight budget and dates*'
    ]
    
    REQUIRED_LINE_ITEM_FIELDS = [
        'Advertiser ID*',
        'Order ID*',
        'Line type*',
        'Line name*',
        'Line start date',
        'Line end date',
        'Active/Inactive',
        'Supply source*',
        'Bid*',
        'Budget*'
    ]
    
    @classmethod
    def validate_bulk_sheet_structure(cls, bulk_data: Dict[str, Any]) -> List[str]:
        """Validate bulk sheet data structure."""
        errors = []
        
        # Check required sheets
        required_sheets = ['orders', 'display_line_items', 'creative_associations']
        for sheet in required_sheets:
            if sheet not in bulk_data or not bulk_data[sheet]:
                errors.append(f"Missing or empty required sheet: {sheet}")
        
        # Validate order data
        if 'orders' in bulk_data and bulk_data['orders']:
            order_data = bulk_data['orders'][0] if bulk_data['orders'] else {}
            for field in cls.REQUIRED_ORDER_FIELDS:
                if field not in order_data or not order_data[field]:
                    errors.append(f"Missing required order field: {field}")
        
        # Validate line item data
        if 'display_line_items' in bulk_data:
            for i, line_item in enumerate(bulk_data['display_line_items']):
                for field in cls.REQUIRED_LINE_ITEM_FIELDS:
                    if field not in line_item or not line_item[field]:
                        errors.append(f"Missing required field '{field}' in line item {i+1}")
        
        return errors