import os
import sqlite3
import csv
import re
from bs4 import BeautifulSoup
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

def parse_days(day_str):
    if not day_str or day_str == "TBA":
        return [day_str]
    days = []
    i = 0
    while i < len(day_str):
        # Look ahead for 2-letter day codes
        if day_str[i:i+2] in ['Th', 'St', 'Su']:
            days.append(day_str[i:i+2])
            i += 2
        else:
            days.append(day_str[i])
            i += 1
    return days

def parse_hours(hour_str, num_items):
    if not hour_str or hour_str == "TBA":
        return [hour_str] * num_items
    
    # Simple case
    if len(hour_str) == num_items:
        return list(hour_str)
    
    # Handle cases with 10, 11, 12, 13, 14
    # Calculate how many 2-digit numbers we need
    # x + y = num_items (Total items)
    # x + 2y = len(hour_str) (Total characters)
    # y = len(hour_str) - num_items
    num_2_digit = len(hour_str) - num_items
    
    res = []
    i = 0
    while len(res) < num_items and i < len(hour_str):
        # If we still need 2-digit numbers and current char is '1' 
        # (all 2-digit slots 10-14 start with 1)
        if num_2_digit > 0 and hour_str[i] == '1' and i + 1 < len(hour_str):
            res.append(hour_str[i:i+2])
            i += 2
            num_2_digit -= 1
        else:
            res.append(hour_str[i])
            i += 1
    return res

def parse_rooms(room_td, num_items):
    # Rooms are often separated by | or spaces between spans
    text = room_td.get_text(" | ", strip=True)
    if not text or text == "&nbsp;":
        return [""] * num_items
    
    parts = [p.strip() for p in text.split("|") if p.strip()]
    
    # Sometimes the number of room parts doesn't match num_items 
    # (e.g. one room for multiple slots)
    if len(parts) == 1 and num_items > 1:
        return parts * num_items
    
    if len(parts) < num_items:
        return parts + [""] * (num_items - len(parts))
    
    return parts[:num_items]

def process_file(file_path):
    try:
        # Extract term and dept from path: schedules/2024_2025-1/MATH.html
        path_parts = file_path.split(os.sep)
        term = path_parts[-2].replace("_", "/")
        dept_code = path_parts[-1].replace(".html", "")
        
        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
        
        rows = []
        for tr in soup.find_all("tr", class_=["schtd", "schtd2"]):
            tds = tr.find_all("td")
            if len(tds) < 15:
                continue
            
            code_sec = tds[0].get_text(strip=True)
            
            # Extract common fields
            days_str = tds[6].get_text(strip=True)
            hours_str = tds[7].get_text(strip=True)
            days = parse_days(days_str)
            num_slots = len(days)
            hours = parse_hours(hours_str, num_slots)
            rooms = parse_rooms(tds[10], num_slots)
            
            slot_title = tds[2].get_text(strip=True)
            instructor = tds[5].get_text(strip=True)

            # If no course code, it's a continuation of the previous course (like LAB/PS)
            if not code_sec and rows:
                for d, h, r in zip(days, hours, rooms):
                    rows[-1]["slots"].append({
                        "day": d, 
                        "hour": h, 
                        "room": r, 
                        "slot_title": slot_title,
                        "instructor": instructor
                    })
                continue

            if "." in code_sec:
                course_code, section = code_sec.rsplit(".", 1)
            else:
                course_code, section = code_sec, ""
                
            credits = tds[3].get_text(strip=True)
            ects = tds[4].get_text(strip=True)
            delivery = tds[8].get_text(strip=True)
            exam_loc = tds[9].get_text(strip=True)
            # tds[10] is Rooms
            exam_date = tds[11].get_text(strip=True)
            sl = tds[12].get_text(strip=True)
            req_dept = tds[13].get_text(strip=True)
            other_depts = tds[14].get_text(strip=True)
            
            course_data = {
                "term": term,
                "department": dept_code,
                "course_code": course_code,
                "section": section,
                "course_name": slot_title, # Main row title is the course name
                "instructor": instructor,
                "credits": credits,
                "ects": ects,
                "delivery_method": delivery,
                "exam_location": exam_loc,
                "exam_date": exam_date,
                "sl": sl,
                "required_for": req_dept,
                "departments": other_depts
            }
            
            slots = []
            for d, h, r in zip(days, hours, rooms):
                slots.append({
                    "day": d, 
                    "hour": h, 
                    "room": r, 
                    "slot_title": slot_title,
                    "instructor": instructor
                })
            
            rows.append({"course": course_data, "slots": slots})
            
        return rows
    except Exception as e:
        return f"ERROR: {file_path}: {str(e)}"

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    schedules_dir = os.path.join(script_dir, "schedules")
    db_path = os.environ.get("DB_PATH")
    if not db_path:
        db_path = os.path.abspath(os.path.join(script_dir, "..", "schedules.db"))
    csv_path = os.path.join(script_dir, "schedules.csv")
    
    if not os.path.exists(schedules_dir):
        print(f"[!] {schedules_dir} not found.")
        return

    all_files = []
    for root, dirs, filenames in os.walk(schedules_dir):
        for f in filenames:
            if f.endswith(".html"):
                all_files.append(os.path.join(root, f))
    
    print(f"[*] Found {len(all_files)} files to parse.")
    
    # Initialize DB
    if os.path.exists(db_path):
        os.remove(db_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            term TEXT,
            department TEXT,
            course_code TEXT,
            section TEXT,
            course_name TEXT,
            instructor TEXT,
            credits TEXT,
            ects TEXT,
            delivery_method TEXT,
            exam_location TEXT,
            exam_date TEXT,
            sl TEXT,
            required_for TEXT,
            departments TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE course_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER,
            day TEXT,
            hour TEXT,
            room TEXT,
            slot_title TEXT,
            instructor TEXT,
            FOREIGN KEY(course_id) REFERENCES courses(id)
        )
    """)
    
    # Process in parallel
    print(f"[*] Parsing files using {multiprocessing.cpu_count()} workers...")
    all_data = []
    with ProcessPoolExecutor() as executor:
        futures = {executor.submit(process_file, f): f for f in all_files}
        
        count = 0
        for future in as_completed(futures):
            res = future.result()
            if isinstance(res, list):
                all_data.extend(res)
            else:
                print(f"\n[!] {res}")
            
            count += 1
            if count % 100 == 0:
                print(f"\r[*] Progress: {count}/{len(all_files)} files parsed", end="", flush=True)
    
    print(f"\n[*] Inserting {len(all_data)} courses into database...")
    
    # Optimize SQLite settings
    cursor.execute("PRAGMA synchronous = OFF;")
    cursor.execute("PRAGMA journal_mode = MEMORY;")
    
    # Start explicit transaction
    cursor.execute("BEGIN TRANSACTION;")
    
    # Batch insertion
    for item in all_data:
        c = item["course"]
        cursor.execute("""
            INSERT INTO courses (
                term, department, course_code, section, course_name, 
                instructor, credits, ects, delivery_method, 
                exam_location, exam_date, sl, required_for, departments
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            c["term"], c["department"], c["course_code"], c["section"], 
            c["course_name"], c["instructor"], c["credits"], c["ects"], 
            c["delivery_method"], c["exam_location"], c["exam_date"], 
            c["sl"], c["required_for"], c["departments"]
        ))
        course_id = cursor.lastrowid
        
        for s in item["slots"]:
            cursor.execute("""
                INSERT INTO course_slots (course_id, day, hour, room, slot_title, instructor)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (course_id, s["day"], s["hour"], s["room"], s["slot_title"], s["instructor"]))
            
    conn.commit()
    
    # Generate CSV (Flattened)
    print(f"[*] Generating flattened CSV...")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "term", "department", "course_code", "section", "course_name", 
            "instructor", "credits", "ects", "delivery_method", 
            "exam_location", "exam_date", "sl", "required_for", "departments",
            "day", "hour", "room", "slot_title", "slot_instructor"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in all_data:
            base = item["course"]
            for s in item["slots"]:
                row = base.copy()
                # Rename slot instructor to avoid conflict with course instructor
                slot_data = s.copy()
                slot_data["slot_instructor"] = slot_data.pop("instructor")
                row.update(slot_data)
                writer.writerow(row)
                
    conn.close()
    print(f"[+] Success!")
    print(f"    - Database: {db_path}")
    print(f"    - CSV:      {csv_path}")

if __name__ == "__main__":
    main()
