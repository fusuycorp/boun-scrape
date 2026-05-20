import requests
from bs4 import BeautifulSoup
import os
import sys

def load_cookies(cookie_string):
    cookies = {}
    for line in cookie_string.split(';'):
        if '=' in line:
            name, value = line.strip().split('=', 1)
            cookies[name] = value
    return cookies

def fetch_term(session, term, viewstate, generator, validation):
    url = "https://registration.bogazici.edu.tr/buis/General/schedule.aspx?p=semester"
    
    data = {
        "__VIEWSTATE": viewstate,
        "__VIEWSTATEGENERATOR": generator,
        "__EVENTVALIDATION": validation,
        "ctl00$cphMainContent$ddlSemester": term,
        "ctl00$cphMainContent$btnSearch": "Go"
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:149.0) Gecko/20100101 Firefox/149.0",
        "Referer": url,
        "Origin": "https://registration.bogazici.edu.tr",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    try:
        response = session.post(url, data=data, headers=headers)
        response.raise_for_status()
        
        # Force encoding to Windows-1254 for Turkish characters
        response.encoding = 'windows-1254'
        
        # Check for reCAPTCHA warning in the HTML content
        if "You could not pass the reCAPTCHA check" in response.text:
            print(f"Warning: reCAPTCHA block encountered for term {term}. Your cookies might be expired.")
            return None
            
        return response.text
    except Exception as e:
        print(f"Error fetching term {term}: {e}")
        return None

def parse_html(html_content):
    soup = BeautifulSoup(html_content, "html.parser")
    
    # Extract hidden fields
    vs_node = soup.find("input", {"id": "__VIEWSTATE"})
    gen_node = soup.find("input", {"id": "__VIEWSTATEGENERATOR"})
    val_node = soup.find("input", {"id": "__EVENTVALIDATION"})
    
    viewstate = vs_node.get("value", "") if vs_node else ""
    generator = gen_node.get("value", "") if gen_node else ""
    validation = val_node.get("value", "") if val_node else ""
    
    # Extract terms
    select = soup.find("select", {"id": "ctl00_cphMainContent_ddlSemester"})
    terms = [option.get("value") for option in select.find_all("option") if option.get("value")] if select else []
    
    # Extract departments
    departments = []
    table = soup.find("table", class_="table-bordered")
    if table:
        for a in table.find_all("a", href=True):
            if "/scripts/sch.asp?" in a["href"]:
                departments.append({
                    "name": a.get_text(strip=True),
                    "url": a["href"]
                })
                
    return {
        "viewstate": viewstate,
        "generator": generator,
        "validation": validation,
        "terms": terms,
        "departments": departments
    }

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    seed_file = os.path.join(script_dir, "response.html")
    cookie_file = os.path.join(script_dir, "cookies.txt")
    
    if not os.path.exists(seed_file):
        print(f"{seed_file} not found. Please run request.sh first.")
        return

    # Load cookies if provided
    cookies = {}
    if os.path.exists(cookie_file):
        with open(cookie_file, "r") as f:
            cookie_content = f.read().strip()
            cookies = load_cookies(cookie_content)
        
        print(f"[*] Loaded {len(cookies)} cookies from cookies.txt:")
        for name, value in cookies.items():
            # Show name and a masked version of the value
            masked_value = value[:8] + "..." if len(value) > 12 else value
            print(f"    - {name}: {masked_value}")
    else:
        print("[!] Warning: cookies.txt not found. Scraping will likely fail due to reCAPTCHA.")

    with open(seed_file, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    data = parse_html(html_content)
    terms_to_process = data['terms']
    print(f"[*] Found {len(terms_to_process)} terms in seed file.")
    
    responses_dir = os.path.join(script_dir, "responses")
    os.makedirs(responses_dir, exist_ok=True)
    
    session = requests.Session()
    if cookies:
        session.cookies.update(cookies)
        
        # Validate cookies
        print("[*] Validating session...")
        test_url = "https://registration.bogazici.edu.tr/buis/General/schedule.aspx?p=semester"
        try:
            val_resp = session.get(test_url, timeout=10)
            if "You could not pass the reCAPTCHA check" in val_resp.text:
                print("[!] Session validation failed: reCAPTCHA block detected.")
                print("[!] Please update cookies.txt with a fresh session from your browser.")
                # Ask to continue anyway
                if os.environ.get("AUTO_CONFIRM") == "1":
                    choice = 'y'
                else:
                    choice = input("[?] Continue anyway? (y/N): ").strip().lower()
                if choice != 'y':
                    return
            else:
                print("[+] Session validation successful.")
        except Exception as e:
            print(f"[!] Error validating session: {e}")
            return

    # Confirmation
    print("\n--- Scrape Plan ---")
    print(f"Total Terms: {len(terms_to_process)}")
    print(f"Output Dir:  {responses_dir}")
    print(f"Cookies:     {'Loaded' if cookies else 'None'}")
    print("-------------------\n")
    
    if os.environ.get("AUTO_CONFIRM") == "1":
        confirm = 'y'
    else:
        confirm = input("[?] Start scraping? (y/N): ").strip().lower()
    if confirm != 'y':
        print("[*] Operation cancelled.")
        return

    current_viewstate = data['viewstate']
    current_generator = data['generator']
    current_validation = data['validation']
    
    for term in terms_to_process:
        print(f"[>] Processing term: {term}...", end=" ", flush=True)
        
        term_html = fetch_term(session, term, current_viewstate, current_generator, current_validation)
        
        if term_html:
            safe_term = term.replace("/", "_")
            file_path = os.path.join(responses_dir, f"{safe_term}.html")
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(term_html)
            
            term_data = parse_html(term_html)
            print(f"Done. Found {len(term_data['departments'])} departments.")
            
            # Update tokens for next request if available
            if term_data['viewstate']:
                current_viewstate = term_data['viewstate']
            if term_data['generator']:
                current_generator = term_data['generator']
            if term_data['validation']:
                current_validation = term_data['validation']
        else:
            print("Failed (reCAPTCHA or Error).")

if __name__ == "__main__":
    main()
