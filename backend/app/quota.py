import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, List
import os

def load_cookies() -> Dict[str, str]:
    # Try loading cookies from cookies.txt in the backend folder or scraper root
    # Default path is in the scraper root folder
    cookie_paths = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "cookies.txt")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "cookies.txt")),
    ]
    
    for path in cookie_paths:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    cookie_string = f.read().strip()
                cookies = {}
                for line in cookie_string.split(";"):
                    if "=" in line:
                        name, value = line.strip().split("=", 1)
                        cookies[name] = value
                return cookies
            except Exception:
                pass
    return {}

def fetch_quota_from_boun(abbr: str, code: str, section: str, donem: str) -> Dict[str, Any]:
    url = "https://registration.boun.edu.tr/scripts/quotasearch.asp"
    params = {
        "abbr": abbr.upper(),
        "code": code.upper(),
        "section": section,
        "donem": donem
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:149.0) Gecko/20100101 Firefox/149.0",
        "Referer": "https://registration.boun.edu.tr/"
    }
    
    cookies = load_cookies()
    session = requests.Session()
    if cookies:
        session.cookies.update(cookies)
        
    try:
        response = session.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Boun uses Windows-1254 (Turkish charset)
        response.encoding = 'windows-1254'
        html_content = response.text
        
        if "You could not pass the reCAPTCHA check" in html_content:
            return {
                "success": False,
                "error": "RECAPTCHA",
                "message": "reCAPTCHA block detected on university server. Please update cookies.txt with a fresh session."
            }
            
        soup = BeautifulSoup(html_content, "html.parser")
        tables = soup.find_all("table")
        
        if not tables:
            return {
                "success": False,
                "error": "NOT_FOUND",
                "message": f"No course quota details found for {abbr} {code}-{section}."
            }
            
        # Parse rows
        quota_data = []
        rows = tables[0].find_all("tr", class_=["schtd", "schtd2"])
        
        # Check if no rows but has error text
        if not rows:
            # Let's see if we have cell elements inside or if it's empty
            cells = tables[0].find_all("td")
            if cells and "no quota" in tables[0].text.lower():
                return {
                    "success": False,
                    "error": "NO_QUOTA",
                    "message": "Course does not have quota details configured."
                }
        
        for tr in rows:
            tds = tr.find_all("td")
            if len(tds) >= 4:
                dept = tds[0].get_text(strip=True)
                status = tds[1].get_text(strip=True)
                quota_val = tds[2].get_text(strip=True)
                current_val = tds[3].get_text(strip=True)
                
                # Check for Consent or Unlimited
                is_consent = "consent" in quota_val.lower()
                is_unlimited = "unlimited" in quota_val.lower()
                
                quota_num = 0
                current_num = 0
                
                try:
                    if not is_consent and not is_unlimited:
                        quota_num = int(quota_val)
                    current_num = int(current_val)
                except ValueError:
                    pass
                    
                quota_data.append({
                    "department": dept,
                    "status": status,
                    "quota": quota_val,
                    "current": current_val,
                    "quota_numeric": quota_num,
                    "current_numeric": current_num,
                    "is_consent": is_consent,
                    "is_unlimited": is_unlimited,
                    "available": (quota_num - current_num) if (not is_consent and not is_unlimited) else 0
                })
                
        if not quota_data:
            return {
                "success": False,
                "error": "PARSING_ERROR",
                "message": "Could not parse quota rows. The page format may have changed or the course does not exist."
            }
            
        return {
            "success": True,
            "course_id": f"{abbr}{code}-{section}",
            "term": donem,
            "data": quota_data
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": "CONNECTION_ERROR",
            "message": f"Failed to connect to Bogazici server: {str(e)}"
        }
