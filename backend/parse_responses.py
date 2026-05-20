import os
import json
import csv
import urllib.parse
from bs4 import BeautifulSoup

def parse_html_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, "html.parser")
    
    departments = []
    table = soup.find("table", class_="table-bordered")
    if table:
        for a in table.find_all("a", href=True):
            href = a["href"]
            if "/scripts/sch.asp?" in href:
                name = a.get_text(strip=True)
                
                # Parse URL to get kisaadi and bolum
                parsed_url = urllib.parse.urlparse(href)
                query_params = urllib.parse.parse_qs(parsed_url.query)
                
                kisaadi = query_params.get("kisaadi", [""])[0]
                bolum = query_params.get("bolum", [""])[0]
                
                departments.append({
                    "name": name,
                    "kisaadi": kisaadi,
                    "bolum": bolum
                })
                
    return departments

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    responses_dir = os.path.join(script_dir, "responses")
    json_output = os.path.join(script_dir, "departments_all.json")
    csv_output = os.path.join(script_dir, "departments_all.csv")
    
    if not os.path.exists(responses_dir):
        print(f"[!] Responses directory not found: {responses_dir}")
        return

    # Use a dictionary keyed by (kisaadi, bolum) to deduplicate
    unique_departments = {}
    html_files = [f for f in os.listdir(responses_dir) if f.endswith(".html")]
    
    if not html_files:
        print("[!] No HTML files found in the responses directory.")
        return

    print(f"[*] Processing {len(html_files)} files...")
    
    for filename in sorted(html_files):
        file_path = os.path.join(responses_dir, filename)
        depts = parse_html_file(file_path)
        
        for dept in depts:
            key = (dept["kisaadi"], dept["bolum"])
            # We keep the first name we find for this pair
            if key not in unique_departments:
                unique_departments[key] = dept["name"]

    # Convert to a flat list
    final_list = []
    for (kisaadi, bolum), name in sorted(unique_departments.items()):
        final_list.append({
            "name": name,
            "kisaadi": kisaadi,
            "bolum": bolum
        })

    # Save to JSON
    with open(json_output, "w", encoding="utf-8") as f:
        json.dump(final_list, f, indent=4, ensure_ascii=False)
    
    # Save to CSV
    with open(csv_output, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "kisaadi", "bolum"])
        writer.writeheader()
        writer.writerows(final_list)
    
    print(f"\n[+] Successfully combined data.")
    print(f"[+] Total Unique Departments: {len(final_list)}")
    print(f"[+] Saved to:")
    print(f"    - {json_output}")
    print(f"    - {csv_output}")

if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()
