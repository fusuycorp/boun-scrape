import requests
import os
import json
import time
from urllib.parse import urljoin

def load_cookies(cookie_file):
    if not os.path.exists(cookie_file):
        return {}
    with open(cookie_file, "r") as f:
        cookie_string = f.read().strip()
    
    cookies = {}
    for line in cookie_string.split(';'):
        if '=' in line:
            name, value = line.strip().split('=', 1)
            cookies[name] = value
    return cookies

def scrape_department(session, term, kisaadi, bolum, base_url):
    # Construct the URL
    params = {
        "donem": term,
        "kisaadi": kisaadi,
        "bolum": bolum
    }
    # Note: The site uses /scripts/sch.asp
    target_url = urljoin(base_url, "/scripts/sch.asp")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:149.0) Gecko/20100101 Firefox/149.0",
        "Referer": "https://registration.bogazici.edu.tr/buis/General/schedule.aspx?p=semester"
    }
    
    try:
        response = session.get(target_url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Force encoding to Windows-1254 for Turkish characters
        response.encoding = 'windows-1254'
        
        if "You could not pass the reCAPTCHA check" in response.text:
            return "RECAPTCHA", None
            
        return "SUCCESS", response.text
    except Exception as e:
        return "ERROR", str(e)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    deps_file = os.path.join(script_dir, "departments_all.json")
    cookie_file = os.path.join(script_dir, "cookies.txt")
    base_site_url = "https://registration.bogazici.edu.tr/"

    if not os.path.exists(deps_file):
        print(f"[!] {deps_file} not found. Run parse_responses.py first.")
        return

    with open(deps_file, "r", encoding="utf-8") as f:
        departments = json.load(f)

    # Get term from user
    term = input("[?] Enter the term to scrape (e.g., 2024/2025-1): ").strip()
    if not term:
        print("[!] Term is required.")
        return

    # Load cookies
    cookies = load_cookies(cookie_file)
    if cookies:
        print(f"[*] Loaded {len(cookies)} cookies.")
    else:
        print("[!] No cookies loaded. Scrape might fail.")

    # Create output directory
    safe_term = term.replace("/", "_")
    output_dir = os.path.join(script_dir, "schedules", safe_term)
    os.makedirs(output_dir, exist_ok=True)

    session = requests.Session()
    if cookies:
        session.cookies.update(cookies)

    print(f"\n[*] Starting scrape for {len(departments)} departments for term {term}...")
    
    count = 0
    for dept in departments:
        name = dept["name"]
        kisaadi = dept["kisaadi"]
        bolum = dept["bolum"]
        
        print(f"[>] ({count+1}/{len(departments)}) Fetching {kisaadi} ({name})...", end=" ", flush=True)
        
        status, result = scrape_department(session, term, kisaadi, bolum, base_site_url)
        
        if status == "SUCCESS":
            file_path = os.path.join(output_dir, f"{kisaadi}.html")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(result)
            print("Done.")
        elif status == "RECAPTCHA":
            print("FAILED (reCAPTCHA block).")
            print("[!] Session expired. Please update cookies.txt and try again.")
            break
        else:
            print(f"FAILED (Error: {result}).")
        
        count += 1
        # Small delay to be polite
        time.sleep(0.5)

    print(f"\n[+] Scraping complete. Files saved in {output_dir}")

if __name__ == "__main__":
    main()
