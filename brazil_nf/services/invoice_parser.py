"""
International Invoice PDF Parser.

Extracts invoice data from PDF files sent by international vendors
like GitHub, Microsoft, OpenAI, Anthropic, AWS, Google Cloud, etc.
"""

import re
from datetime import datetime
from io import BytesIO

import frappe
from frappe import _


# Vendor patterns for identification and data extraction
VENDOR_PATTERNS = {
    "github": {
        "identify": [r"github", r"gh-billing"],
        "name": "GitHub, Inc.",
        "country": "United States",
        "tax_id": "45-4013193",
        "email": "billing@github.com",
        "patterns": {
            "invoice_number": [r"Invoice\s*#?\s*([A-Z0-9-]+)", r"Invoice\s+Number[:\s]*([A-Z0-9-]+)"],
            "amount": [r"Amount\s+Due[:\s]*\$?([\d,]+\.?\d*)", r"Total[:\s]*\$?([\d,]+\.?\d*)"],
            "date": [r"Invoice\s+Date[:\s]*(\w+\s+\d{1,2},?\s+\d{4})", r"Date[:\s]*(\d{1,2}/\d{1,2}/\d{4})"],
            "billing_period": [r"Billing\s+Period[:\s]*(\w+\s+\d{1,2})\s*[-–]\s*(\w+\s+\d{1,2},?\s+\d{4})"],
        }
    },
    "microsoft": {
        "identify": [r"microsoft", r"azure", r"office\s*365", r"m365"],
        "name": "Microsoft Corporation",
        "country": "United States",
        "tax_id": "91-1144442",
        "email": "billing@microsoft.com",
        "patterns": {
            "invoice_number": [r"Invoice\s*(?:Number|#|No\.?)[:\s]*([A-Z0-9-]+)"],
            "amount": [r"Amount\s+Due[:\s]*\$?([\d,]+\.?\d*)", r"Total[:\s]*\$?([\d,]+\.?\d*)"],
            "date": [r"Invoice\s+Date[:\s]*(\d{1,2}/\d{1,2}/\d{4})", r"Date[:\s]*(\w+\s+\d{1,2},?\s+\d{4})"],
            "billing_period": [r"Service\s+Period[:\s]*(\d{1,2}/\d{1,2}/\d{4})\s*[-–]\s*(\d{1,2}/\d{1,2}/\d{4})"],
        }
    },
    "openai": {
        "identify": [r"openai", r"chatgpt"],
        "name": "OpenAI, LLC",
        "country": "United States",
        "tax_id": "",
        "email": "billing@openai.com",
        "patterns": {
            "invoice_number": [r"Invoice\s*#?\s*([A-Z0-9-]+)", r"Receipt\s*#?\s*([A-Z0-9-]+)"],
            "amount": [r"Amount\s+(?:Paid|Due|Charged)[:\s]*\$?([\d,]+\.?\d*)", r"Total[:\s]*\$?([\d,]+\.?\d*)"],
            "date": [r"(?:Invoice\s+)?Date[:\s]*(\w+\s+\d{1,2},?\s+\d{4})", r"Date[:\s]*(\d{1,2}/\d{1,2}/\d{4})"],
            "billing_period": [r"(?:Billing|Usage)\s+Period[:\s]*(\w+\s+\d{1,2})\s*[-–]\s*(\w+\s+\d{1,2},?\s+\d{4})"],
        }
    },
    "anthropic": {
        "identify": [r"anthropic", r"claude"],
        "name": "Anthropic PBC",
        "country": "United States",
        "tax_id": "",
        "email": "billing@anthropic.com",
        "patterns": {
            "invoice_number": [r"Invoice\s*#?\s*([A-Z0-9-]+)", r"Invoice\s+Number[:\s]*([A-Z0-9-]+)"],
            "amount": [r"Amount\s+(?:Due|Charged)[:\s]*\$?([\d,]+\.?\d*)", r"Total[:\s]*\$?([\d,]+\.?\d*)"],
            "date": [r"(?:Invoice\s+)?Date[:\s]*(\w+\s+\d{1,2},?\s+\d{4})", r"Date[:\s]*(\d{1,2}/\d{1,2}/\d{4})"],
            "billing_period": [r"(?:Billing|Usage)\s+Period[:\s]*(\w+\s+\d{1,2})\s*[-–]\s*(\w+\s+\d{1,2},?\s+\d{4})"],
        }
    },
    "aws": {
        "identify": [r"amazon\s+web\s+services", r"aws\.amazon", r"aws\s+inc"],
        "name": "Amazon Web Services, Inc.",
        "country": "United States",
        "tax_id": "20-4632786",
        "email": "aws-billing@amazon.com",
        "patterns": {
            "invoice_number": [r"Invoice\s+(?:Number|ID)[:\s]*([A-Z0-9-]+)"],
            "amount": [r"Total\s+(?:Amount|Due)[:\s]*\$?([\d,]+\.?\d*)", r"Amount\s+Due[:\s]*\$?([\d,]+\.?\d*)"],
            "date": [r"Invoice\s+Date[:\s]*(\w+\s+\d{1,2},?\s+\d{4})"],
            "billing_period": [r"Statement\s+Period[:\s]*(\w+\s+\d{1,2})\s*[-–]\s*(\w+\s+\d{1,2},?\s+\d{4})"],
        }
    },
    "google_cloud": {
        "identify": [r"google\s+cloud", r"gcp", r"google\s+llc.*cloud"],
        "name": "Google LLC",
        "country": "United States",
        "tax_id": "77-0493581",
        "email": "billing@google.com",
        "patterns": {
            "invoice_number": [r"Invoice\s+(?:number|#)[:\s]*([A-Z0-9-]+)"],
            "amount": [r"Amount\s+due[:\s]*\$?([\d,]+\.?\d*)", r"Total[:\s]*\$?([\d,]+\.?\d*)"],
            "date": [r"Invoice\s+date[:\s]*(\w+\s+\d{1,2},?\s+\d{4})"],
            "billing_period": [r"(?:Billing|Service)\s+period[:\s]*(\w+\s+\d{1,2})\s*[-–]\s*(\w+\s+\d{1,2},?\s+\d{4})"],
        }
    },
    "stripe": {
        "identify": [r"stripe", r"stripe\.com"],
        "name": "Stripe, Inc.",
        "country": "United States",
        "tax_id": "27-2186093",
        "email": "billing@stripe.com",
        "patterns": {
            "invoice_number": [r"Invoice\s*#?\s*([A-Z0-9-]+)"],
            "amount": [r"Amount\s+due[:\s]*\$?([\d,]+\.?\d*)", r"Total[:\s]*\$?([\d,]+\.?\d*)"],
            "date": [r"(?:Invoice\s+)?Date[:\s]*(\w+\s+\d{1,2},?\s+\d{4})"],
            "billing_period": [r"(?:Billing|Service)\s+period[:\s]*(\w+\s+\d{1,2})\s*[-–]\s*(\w+\s+\d{1,2},?\s+\d{4})"],
        }
    },
    "digitalocean": {
        "identify": [r"digitalocean", r"digital\s+ocean"],
        "name": "DigitalOcean, LLC",
        "country": "United States",
        "tax_id": "46-2995605",
        "email": "billing@digitalocean.com",
        "patterns": {
            "invoice_number": [r"Invoice\s*#?\s*([A-Z0-9-]+)"],
            "amount": [r"Amount\s+Due[:\s]*\$?([\d,]+\.?\d*)", r"Total[:\s]*\$?([\d,]+\.?\d*)"],
            "date": [r"(?:Invoice\s+)?Date[:\s]*(\w+\s+\d{1,2},?\s+\d{4})"],
            "billing_period": [r"(?:Billing|Service)\s+Period[:\s]*(\w+\s+\d{1,2})\s*[-–]\s*(\w+\s+\d{1,2},?\s+\d{4})"],
        }
    },
    "atlassian": {
        "identify": [r"atlassian", r"jira", r"confluence", r"bitbucket"],
        "name": "Atlassian Pty Ltd",
        "country": "Australia",
        "tax_id": "",
        "email": "billing@atlassian.com",
        "patterns": {
            "invoice_number": [r"Invoice\s*(?:Number|#)[:\s]*([A-Z0-9-]+)"],
            "amount": [r"Amount\s+Due[:\s]*\$?([\d,]+\.?\d*)", r"Total[:\s]*\$?([\d,]+\.?\d*)"],
            "date": [r"(?:Invoice\s+)?Date[:\s]*(\d{1,2}\s+\w+\s+\d{4})", r"Date[:\s]*(\w+\s+\d{1,2},?\s+\d{4})"],
            "billing_period": [r"(?:Billing|Subscription)\s+Period[:\s]*(\w+\s+\d{1,2})\s*[-–]\s*(\w+\s+\d{1,2},?\s+\d{4})"],
        }
    },
    "slack": {
        "identify": [r"slack\s+technologies", r"slack\.com"],
        "name": "Slack Technologies, LLC",
        "country": "United States",
        "tax_id": "46-4108682",
        "email": "billing@slack.com",
        "patterns": {
            "invoice_number": [r"Invoice\s*#?\s*([A-Z0-9-]+)"],
            "amount": [r"Amount\s+Due[:\s]*\$?([\d,]+\.?\d*)", r"Total[:\s]*\$?([\d,]+\.?\d*)"],
            "date": [r"(?:Invoice\s+)?Date[:\s]*(\w+\s+\d{1,2},?\s+\d{4})"],
            "billing_period": [r"(?:Billing|Service)\s+Period[:\s]*(\w+\s+\d{1,2})\s*[-–]\s*(\w+\s+\d{1,2},?\s+\d{4})"],
        }
    },
    "heroku": {
        "identify": [r"heroku", r"salesforce.*heroku"],
        "name": "Heroku, Inc.",
        "country": "United States",
        "tax_id": "",
        "email": "billing@heroku.com",
        "patterns": {
            "invoice_number": [r"Invoice\s*#?\s*([A-Z0-9-]+)"],
            "amount": [r"Total[:\s]*\$?([\d,]+\.?\d*)", r"Amount\s+Due[:\s]*\$?([\d,]+\.?\d*)"],
            "date": [r"(?:Invoice\s+)?Date[:\s]*(\w+\s+\d{1,2},?\s+\d{4})"],
            "billing_period": [r"(?:Billing|Usage)\s+Period[:\s]*(\w+\s+\d{1,2})\s*[-–]\s*(\w+\s+\d{1,2},?\s+\d{4})"],
        }
    },
    "vercel": {
        "identify": [r"vercel", r"vercel\.com"],
        "name": "Vercel Inc.",
        "country": "United States",
        "tax_id": "",
        "email": "billing@vercel.com",
        "patterns": {
            "invoice_number": [r"Invoice\s*#?\s*([A-Z0-9-]+)"],
            "amount": [r"Total[:\s]*\$?([\d,]+\.?\d*)", r"Amount\s+Due[:\s]*\$?([\d,]+\.?\d*)"],
            "date": [r"(?:Invoice\s+)?Date[:\s]*(\w+\s+\d{1,2},?\s+\d{4})"],
            "billing_period": [r"(?:Billing|Usage)\s+Period[:\s]*(\w+\s+\d{1,2})\s*[-–]\s*(\w+\s+\d{1,2},?\s+\d{4})"],
        }
    },
    "twilio": {
        "identify": [r"twilio"],
        "name": "Twilio Inc.",
        "country": "United States",
        "tax_id": "26-2574840",
        "email": "billing@twilio.com",
        "patterns": {
            "invoice_number": [r"Invoice\s*(?:Number|#)[:\s]*([A-Z0-9-]+)"],
            "amount": [r"Amount\s+Due[:\s]*\$?([\d,]+\.?\d*)", r"Total[:\s]*\$?([\d,]+\.?\d*)"],
            "date": [r"(?:Invoice\s+)?Date[:\s]*(\w+\s+\d{1,2},?\s+\d{4})"],
            "billing_period": [r"(?:Billing|Usage)\s+Period[:\s]*(\w+\s+\d{1,2})\s*[-–]\s*(\w+\s+\d{1,2},?\s+\d{4})"],
        }
    },
    "sendgrid": {
        "identify": [r"sendgrid", r"twilio\s+sendgrid"],
        "name": "Twilio SendGrid",
        "country": "United States",
        "tax_id": "",
        "email": "billing@sendgrid.com",
        "patterns": {
            "invoice_number": [r"Invoice\s*#?\s*([A-Z0-9-]+)"],
            "amount": [r"Amount\s+Due[:\s]*\$?([\d,]+\.?\d*)", r"Total[:\s]*\$?([\d,]+\.?\d*)"],
            "date": [r"(?:Invoice\s+)?Date[:\s]*(\w+\s+\d{1,2},?\s+\d{4})"],
            "billing_period": [r"(?:Billing|Usage)\s+Period[:\s]*(\w+\s+\d{1,2})\s*[-–]\s*(\w+\s+\d{1,2},?\s+\d{4})"],
        }
    },
}


class InvoiceParser:
    """Parser for international invoice PDFs."""

    def __init__(self):
        self.vendor_patterns = VENDOR_PATTERNS

    def parse_pdf(self, pdf_content):
        """
        Parse invoice data from PDF content.

        Args:
            pdf_content: PDF file content as bytes

        Returns:
            dict: Extracted invoice data or None
        """
        text = self._extract_text(pdf_content)
        if not text:
            return None

        # Identify vendor
        vendor_key, vendor_info = self._identify_vendor(text)

        if vendor_key:
            # Use vendor-specific patterns
            data = self._extract_with_vendor_patterns(text, vendor_key, vendor_info)
        else:
            # Use generic extraction
            data = self._extract_generic(text)

        if data and (data.get("invoice_number") or data.get("amount")):
            data["document_type"] = "Invoice"
            return data

        return None

    def _extract_text(self, pdf_content):
        """Extract text from PDF."""
        try:
            try:
                from pypdf import PdfReader
            except ImportError:
                try:
                    from PyPDF2 import PdfReader
                except ImportError:
                    frappe.logger().warning("pypdf/PyPDF2 not installed")
                    return None

            reader = PdfReader(BytesIO(pdf_content))
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text

        except Exception as e:
            frappe.logger().error(f"Error extracting PDF text: {str(e)}")
            return None

    def _identify_vendor(self, text):
        """Identify vendor from PDF text."""
        text_lower = text.lower()

        for vendor_key, vendor_info in self.vendor_patterns.items():
            for pattern in vendor_info["identify"]:
                if re.search(pattern, text_lower):
                    return vendor_key, vendor_info

        return None, None

    def _extract_with_vendor_patterns(self, text, vendor_key, vendor_info):
        """Extract data using vendor-specific patterns."""
        data = {
            "vendor_name": vendor_info["name"],
            "vendor_country": vendor_info["country"],
            "vendor_tax_id": vendor_info.get("tax_id", ""),
            "vendor_email": vendor_info.get("email", ""),
            "currency": "USD",  # Most US vendors use USD
        }

        patterns = vendor_info.get("patterns", {})

        # Extract invoice number
        for pattern in patterns.get("invoice_number", []):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data["invoice_number"] = match.group(1).strip()
                break

        # Extract amount
        for pattern in patterns.get("amount", []):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(",", "")
                try:
                    data["valor_original_currency"] = float(amount_str)
                    data["valor_total"] = float(amount_str)  # Will be converted later
                except ValueError:
                    pass
                break

        # Extract date
        for pattern in patterns.get("date", []):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                parsed_date = self._parse_date(date_str)
                if parsed_date:
                    data["data_emissao"] = parsed_date
                break

        # Extract billing period
        for pattern in patterns.get("billing_period", []):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                start_str = match.group(1).strip()
                end_str = match.group(2).strip() if match.lastindex >= 2 else None

                start_date = self._parse_date(start_str)
                if start_date:
                    data["billing_period_start"] = start_date

                if end_str:
                    end_date = self._parse_date(end_str)
                    if end_date:
                        data["billing_period_end"] = end_date
                break

        # Try to extract description/service from text
        data["invoice_description"] = self._extract_description(text, vendor_key)

        return data

    def _extract_generic(self, text):
        """Generic extraction when vendor is not recognized."""
        data = {
            "currency": "USD",
        }

        # Try to extract vendor name
        vendor_patterns = [
            r"(?:From|Vendor|Seller|Company)[:\s]*([A-Z][A-Za-z0-9\s,\.]+?)(?:\n|$)",
            r"^([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3}(?:\s+(?:Inc|LLC|Ltd|Corp|Corporation|Company)\.?))",
        ]
        for pattern in vendor_patterns:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                data["vendor_name"] = match.group(1).strip()[:140]
                break

        # Extract invoice number
        invoice_patterns = [
            r"Invoice\s*(?:Number|#|No\.?|ID)[:\s]*([A-Z0-9-]+)",
            r"(?:Receipt|Order)\s*(?:Number|#|No\.?|ID)[:\s]*([A-Z0-9-]+)",
        ]
        for pattern in invoice_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                data["invoice_number"] = match.group(1).strip()
                break

        # Extract amount
        amount_patterns = [
            r"(?:Total|Amount\s+Due|Grand\s+Total|Amount\s+Charged)[:\s]*[\$€£]?\s*([\d,]+\.?\d*)",
            r"[\$€£]\s*([\d,]+\.\d{2})",
        ]
        for pattern in amount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(",", "")
                try:
                    data["valor_original_currency"] = float(amount_str)
                    data["valor_total"] = float(amount_str)
                except ValueError:
                    pass
                break

        # Detect currency from symbols
        if "€" in text:
            data["currency"] = "EUR"
        elif "£" in text:
            data["currency"] = "GBP"

        # Extract date
        date_patterns = [
            r"(?:Invoice\s+)?Date[:\s]*(\w+\s+\d{1,2},?\s+\d{4})",
            r"(?:Invoice\s+)?Date[:\s]*(\d{1,2}/\d{1,2}/\d{4})",
            r"(?:Invoice\s+)?Date[:\s]*(\d{4}-\d{2}-\d{2})",
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                date_str = match.group(1).strip()
                parsed_date = self._parse_date(date_str)
                if parsed_date:
                    data["data_emissao"] = parsed_date
                break

        return data

    def _parse_date(self, date_str):
        """Parse date string into date object."""
        if not date_str:
            return None

        # Common date formats
        formats = [
            "%B %d, %Y",      # January 15, 2024
            "%B %d %Y",       # January 15 2024
            "%b %d, %Y",      # Jan 15, 2024
            "%b %d %Y",       # Jan 15 2024
            "%d %B %Y",       # 15 January 2024
            "%d %b %Y",       # 15 Jan 2024
            "%m/%d/%Y",       # 01/15/2024
            "%d/%m/%Y",       # 15/01/2024
            "%Y-%m-%d",       # 2024-01-15
            "%B %d",          # January 15 (need to add year)
            "%b %d",          # Jan 15 (need to add year)
        ]

        # Clean up the string
        date_str = date_str.strip().replace(",", "")

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                # If year is missing (1900), use current year
                if dt.year == 1900:
                    dt = dt.replace(year=datetime.now().year)
                return dt.date()
            except ValueError:
                continue

        return None

    def _extract_description(self, text, vendor_key=None):
        """Extract service description from invoice text."""
        # Look for common description patterns
        desc_patterns = [
            r"(?:Description|Service|Product|Item)[:\s]*([^\n]+)",
            r"(?:Subscription|Plan)[:\s]*([^\n]+)",
        ]

        descriptions = []
        for pattern in desc_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches[:3]:  # Limit to first 3 matches
                desc = match.strip()
                if len(desc) > 5 and len(desc) < 200:
                    descriptions.append(desc)

        if descriptions:
            return "; ".join(descriptions)

        # Use vendor name as fallback
        if vendor_key:
            return f"{VENDOR_PATTERNS[vendor_key]['name']} services"

        return None


def parse_invoice_pdf(pdf_content):
    """
    Convenience function to parse invoice PDF.

    Args:
        pdf_content: PDF file content as bytes

    Returns:
        dict: Extracted invoice data or None
    """
    parser = InvoiceParser()
    return parser.parse_pdf(pdf_content)


def is_international_invoice(text):
    """
    Check if PDF text looks like an international invoice (not Brazilian NF).

    Args:
        text: Extracted PDF text

    Returns:
        bool: True if appears to be international invoice
    """
    # If it has a chave de acesso (44 digits), it's Brazilian
    if re.search(r'\d{44}', text):
        return False

    # If it has CNPJ pattern, it's Brazilian
    if re.search(r'\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}', text):
        return False

    # Check for international invoice indicators
    international_indicators = [
        r"invoice",
        r"receipt",
        r"\$\s*\d",  # Dollar amounts
        r"€\s*\d",   # Euro amounts
        r"£\s*\d",   # Pound amounts
        r"USD|EUR|GBP",
        r"united\s+states|usa|ireland|netherlands",
    ]

    for pattern in international_indicators:
        if re.search(pattern, text, re.IGNORECASE):
            return True

    return False
