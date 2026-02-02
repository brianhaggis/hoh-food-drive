"""
Food pantry lookup service using foodpantries.org data.
Finds local food pantries near show venues.
"""

import re
import json
import requests
from flask import current_app

# Keywords that indicate religious affiliation (for filtering preference)
RELIGIOUS_KEYWORDS = [
    'church', 'baptist', 'methodist', 'lutheran', 'catholic', 'adventist',
    'presbyterian', 'episcopal', 'pentecostal', 'assembly of god', 'chapel',
    'temple', 'synagogue', 'mosque', 'ministry', 'ministries', 'st.', 'saint',
    'christian', 'gospel', 'faith', 'grace', 'christ', 'jesus', 'lord',
    'salvation army', 'vincent de paul', 'depaul', 'worship', 'bible'
]

# State abbreviation to full name mapping
STATE_ABBREV = {
    'AL': 'alabama', 'AK': 'alaska', 'AZ': 'arizona', 'AR': 'arkansas',
    'CA': 'california', 'CO': 'colorado', 'CT': 'connecticut', 'DE': 'delaware',
    'FL': 'florida', 'GA': 'georgia', 'HI': 'hawaii', 'ID': 'idaho',
    'IL': 'illinois', 'IN': 'indiana', 'IA': 'iowa', 'KS': 'kansas',
    'KY': 'kentucky', 'LA': 'louisiana', 'ME': 'maine', 'MD': 'maryland',
    'MA': 'massachusetts', 'MI': 'michigan', 'MN': 'minnesota', 'MS': 'mississippi',
    'MO': 'missouri', 'MT': 'montana', 'NE': 'nebraska', 'NV': 'nevada',
    'NH': 'new-hampshire', 'NJ': 'new-jersey', 'NM': 'new-mexico', 'NY': 'new-york',
    'NC': 'north-carolina', 'ND': 'north-dakota', 'OH': 'ohio', 'OK': 'oklahoma',
    'OR': 'oregon', 'PA': 'pennsylvania', 'RI': 'rhode-island', 'SC': 'south-carolina',
    'SD': 'south-dakota', 'TN': 'tennessee', 'TX': 'texas', 'UT': 'utah',
    'VT': 'vermont', 'VA': 'virginia', 'WA': 'washington', 'WV': 'west-virginia',
    'WI': 'wisconsin', 'WY': 'wyoming', 'DC': 'washington-dc'
}


def is_secular(name):
    """Check if a pantry name appears to be secular (non-religious)."""
    name_lower = name.lower()
    for keyword in RELIGIOUS_KEYWORDS:
        if keyword in name_lower:
            return False
    return True


def extract_hours(description):
    """
    Extract and clean hours from a pantry description.
    Returns clean, formatted hours string or empty string if not found.
    """
    if not description:
        return ''

    # Normalize whitespace and newlines
    text = re.sub(r'\s+', ' ', description).strip()

    # Pattern to match day ranges or individual days with times
    # Captures: "Monday - Friday 8:30am to 3:30pm" or "Tuesday and Thursday 10:00 am - 3:00 pm"
    hours_pattern = r'''
        (
            (?:Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)
            (?:\s*[-–—,&]\s*|\s+(?:and|to|thru|through)\s+)?
            (?:Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)?
            \s*:?\s*
            \d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)?
            \s*[-–—to]+\s*
            \d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)?
        )
    '''

    matches = re.findall(hours_pattern, text, re.IGNORECASE | re.VERBOSE)

    if not matches:
        # Try simpler pattern
        simple_pattern = r'((?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*\s*[-–—]?\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)?[a-z]*\s*:?\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)?\s*[-–—to]+\s*\d{1,2}(?::\d{2})?\s*(?:am|pm)?)'
        matches = re.findall(simple_pattern, text, re.IGNORECASE)

    if not matches:
        return ''

    # Clean up each match
    cleaned = []
    for match in matches:
        hours = match.strip()
        # Fix missing space between day and time (e.g., "Thursday10:00" -> "Thursday 10:00")
        hours = re.sub(r'([a-zA-Z])(\d)', r'\1 \2', hours)
        # Normalize dashes
        hours = re.sub(r'\s*[-–—]+\s*', ' - ', hours)
        # Clean up "to" formatting
        hours = re.sub(r'\s+to\s+', ' - ', hours, flags=re.IGNORECASE)
        # Remove extra spaces
        hours = re.sub(r'\s+', ' ', hours).strip()
        cleaned.append(hours)

    # Join multiple hour ranges with semicolons
    result = '; '.join(cleaned)

    # Truncate if too long
    if len(result) > 120:
        result = result[:120] + '...'

    return result


def parse_pantry_html(html_content):
    """Parse pantry information from foodpantries.org HTML using JSON-LD data."""
    pantries = []

    # Extract JSON-LD structured data blocks
    json_ld_pattern = r'<script type="application/ld\+json">\s*(\{[^<]+\})\s*</script>'
    matches = re.findall(json_ld_pattern, html_content, re.DOTALL)

    for match in matches:
        try:
            data = json.loads(match)

            # Skip if not a local business type
            if data.get('@type') not in ['LocalBusiness', 'FoodEstablishment', 'Organization', None]:
                # If @type is missing, still try to parse
                if '@type' in data and data['@type'] not in ['LocalBusiness', 'FoodEstablishment', 'Organization']:
                    continue

            name = data.get('name', '')
            if not name or 'Add a Listing' in name:
                continue

            # Skip navigation/generic entries
            if any(skip in name.lower() for skip in ['food pantries', 'click here', 'view all']):
                continue

            pantry = {
                'name': name,
                'phone': data.get('telephone', ''),
                'is_secular': is_secular(name)
            }

            # Parse address from structured data
            address = data.get('address', {})
            if isinstance(address, dict):
                street = address.get('streetAddress', '')
                city = address.get('addressLocality', '')
                state = address.get('addressRegion', '')
                zipcode = address.get('postalCode', '')
                if street:
                    pantry['address'] = f"{street}, {city}, {state} {zipcode}".strip(', ')
            elif isinstance(address, str):
                pantry['address'] = address

            # Parse hours from description
            description = data.get('description', '')
            if description:
                hours = extract_hours(description)
                if hours:
                    pantry['hours'] = hours

            pantries.append(pantry)

        except (json.JSONDecodeError, KeyError, TypeError):
            continue

    return pantries


def fetch_pantries_for_city(city, state):
    """
    Fetch food pantries for a given city and state.

    Args:
        city: City name (e.g., "Huntsville")
        state: State abbreviation (e.g., "AL")

    Returns:
        List of pantry dicts with name, address, phone, hours, is_secular
    """
    # Normalize inputs
    state_upper = state.upper().strip()
    city_clean = city.lower().strip().replace(' ', '-').replace('.', '')

    # Get state abbreviation
    state_abbrev = state_upper.lower() if len(state_upper) == 2 else None
    if not state_abbrev:
        return []

    # Build URL
    url = f"https://www.foodpantries.org/ci/{state_abbrev}-{city_clean}"

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; HouseOfHamillFoodDrive/1.0)'
        }
        response = requests.get(url, headers=headers, timeout=15)

        if response.status_code != 200:
            current_app.logger.warning(f"Could not fetch pantries for {city}, {state}: HTTP {response.status_code}")
            return []

        pantries = parse_pantry_html(response.text)
        return pantries

    except requests.RequestException as e:
        current_app.logger.error(f"Error fetching pantries for {city}, {state}: {e}")
        return []


def get_recommended_pantries(city, state, count=3, prefer_secular=True):
    """
    Get recommended food pantries for a location.

    Args:
        city: City name
        state: State abbreviation
        count: Number of pantries to return (default 3)
        prefer_secular: If True, prioritize secular organizations

    Returns:
        List of pantry dicts, sorted with secular pantries first if preferred
    """
    all_pantries = fetch_pantries_for_city(city, state)

    if not all_pantries:
        return []

    if prefer_secular:
        # Sort with secular pantries first, but include religious ones if needed
        secular = [p for p in all_pantries if p.get('is_secular')]
        religious = [p for p in all_pantries if not p.get('is_secular')]

        # Prefer secular, fall back to religious
        result = secular[:count]
        if len(result) < count:
            result.extend(religious[:count - len(result)])
        return result
    else:
        return all_pantries[:count]


def format_hours(hours_str):
    """Format hours string for better readability - split onto separate lines."""
    if not hours_str:
        return ""

    formatted = hours_str.strip()

    # Split on semicolons (used to separate different day ranges)
    formatted = re.sub(r';\s*', '<br>', formatted)

    return formatted


def format_pantries_for_email(pantries):
    """Format pantry list for email HTML."""
    if not pantries:
        return "<p><em>Local food pantry information will be provided closer to the show date.</em></p>"

    html = "<ul style='margin: 10px 0; padding-left: 20px;'>"
    for p in pantries:
        html += f"<li style='margin-bottom: 15px;'>"
        html += f"<strong>{p['name']}</strong><br>"
        if p.get('address'):
            html += f"{p['address']}<br>"
        if p.get('phone'):
            html += f"Phone: {p['phone']}<br>"
        if p.get('hours'):
            formatted_hours = format_hours(p['hours'])
            html += f"<em style='font-size: 0.9em; line-height: 1.5;'>Hours: {formatted_hours}</em>"
        html += "</li>"
    html += "</ul>"
    return html


def clean_text(text):
    """Clean up scraped text - remove extra whitespace and weird characters."""
    if not text:
        return ''
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Remove common HTML artifacts
    text = re.sub(r'&[a-z]+;', ' ', text)
    # Remove excessive punctuation
    text = re.sub(r'[,\s]+$', '', text)
    return text


def format_phone(phone):
    """Format phone number consistently."""
    if not phone:
        return ''
    # Extract just digits
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    return phone.strip()


def format_pantries_for_display(pantries):
    """Format pantry list for frontend display."""
    if not pantries:
        return []

    result = []
    for p in pantries:
        name = clean_text(p.get('name', ''))
        if not name:
            continue

        # Clean up address - remove duplicate city/state if present
        address = clean_text(p.get('address', ''))

        # Clean up hours - truncate if too long
        hours = clean_text(p.get('hours', ''))
        if len(hours) > 100:
            hours = hours[:100] + '...'

        result.append({
            'name': name,
            'address': address,
            'phone': format_phone(p.get('phone', '')),
            'hours': hours,
            'is_secular': p.get('is_secular', False)
        })

    return result
