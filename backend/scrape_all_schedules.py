import requests
import os
import json
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Thread-local storage for sessions to avoid sharing one session across threads
thread_local = threading.local()
recaptcha_triggered = threading.Event()

def get_session(cookies):
    if not hasattr(thread_local, "session"):
        thread_local.session = requests.Session()
        if cookies:
            thread_local.session.cookies.update(cookies)
    return thread_local.session

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

def parse_departments_from_html(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    soup = BeautifulSoup(html_content, "html.parser")
    
    departments = []
    table = soup.find("table", class_="table-bordered")
    if table:
        for a in table.find_all("a", href=True):
            href = a["href"]
            if "/scripts/sch.asp?" in href:
                parsed_url = urlparse(href)
                params = parse_qs(parsed_url.query)
                departments.append({
                    "kisaadi": params.get("kisaadi", [""])[0],
                    "bolum": params.get("bolum", [""])[0],
                    "name": a.get_text(strip=True)
                })
    return departments

def scrape_worker(term, dept, cookies, base_url, term_dir):
    if recaptcha_triggered.is_set():
        return None

    kisaadi = dept["kisaadi"]
    bolum = dept["bolum"]
    output_path = os.path.join(term_dir, f"{kisaadi}.html")

    if os.path.exists(output_path) and os.environ.get("FORCE_REFRESH") != "1":
        return "SKIPPED"

    session = get_session(cookies)
    params = {
        "donem": term,
        "kisaadi": kisaadi,
        "bolum": bolum
    }
    target_url = urljoin(base_url, "/scripts/sch.asp")
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:149.0) Gecko/20100101 Firefox/149.0",
        "Referer": "https://registration.bogazici.edu.tr/buis/General/schedule.aspx?p=semester"
    }
    
    try:
        response = session.get(target_url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        response.encoding = 'windows-1254'
        
        if "You could not pass the reCAPTCHA check" in response.text:
            recaptcha_triggered.set()
            return "RECAPTCHA"
            
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(response.text)
        return "SUCCESS"
    except Exception as e:
        return f"ERROR: {str(e)}"

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    responses_dir = os.path.join(script_dir, "responses")
    cookie_file = os.path.join(script_dir, "cookies.txt")
    base_site_url = "https://registration.bogazici.edu.tr/"

    if not os.path.exists(responses_dir):
        print(f"[!] {responses_dir} not found. Run scraper.py first.")
        return

    cookies = load_cookies(cookie_file)
    if cookies:
        print(f"[*] Loaded {len(cookies)} cookies.")
    else:
        print("[!] No cookies loaded. Scrape will fail.")

    if os.environ.get("FORCE_REFRESH") == "1":
        print("[!] Force refresh enabled — cached department files will be re-downloaded.")

    html_files = sorted([f for f in os.listdir(responses_dir) if f.endswith(".html")], reverse=True)
    print(f"[*] Found {len(html_files)} terms to process.")
    
    # Gather all tasks across all terms
    all_tasks = []
    for filename in html_files:
        term = filename.replace(".html", "").replace("_", "/")
        file_path = os.path.join(responses_dir, filename)
        departments = parse_departments_from_html(file_path)
        
        safe_term = term.replace("/", "_")
        term_dir = os.path.join(script_dir, "schedules", safe_term)
        os.makedirs(term_dir, exist_ok=True)
        
        for dept in departments:
            all_tasks.append((term, dept, term_dir))

    print(f"[*] Total tasks to process: {len(all_tasks)}")
    
    max_workers = 50  # Adjust based on server tolerance
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scrape_worker, t, d, cookies, base_site_url, td): (t, d) for t, d, td in all_tasks}
        
        completed = 0
        skipped = 0
        for future in as_completed(futures):
            term, dept = futures[future]
            status = future.result()
            
            if status == "SUCCESS":
                completed += 1
            elif status == "SKIPPED":
                skipped += 1
            elif status == "RECAPTCHA":
                print(f"\n[!] reCAPTCHA block detected during {term}/{dept['kisaadi']}. Stopping pool...")
                executor.shutdown(wait=False, cancel_futures=True)
                break
            else:
                print(f"\n[!] Error for {term}/{dept['kisaadi']}: {status}")

            if (completed + skipped) % 10 == 0:
                print(f"\r[*] Progress: {completed + skipped}/{len(all_tasks)} (Success: {completed}, Skipped: {skipped})", end="", flush=True)

    if recaptcha_triggered.is_set():
        print("\n[!] Scrape halted due to reCAPTCHA. Please update cookies.txt and restart.")
    else:
        print(f"\n[+] Exhaustive scrape complete. Processed {len(all_tasks)} tasks.")

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
