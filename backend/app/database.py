import os
import sqlite3
from typing import Dict, Any, List, Tuple

# Default database path pointing to the existing schedules.db in the parent scraper folder
DEFAULT_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "schedules.db"))
DB_PATH = os.environ.get("DB_PATH", DEFAULT_DB_PATH)

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Ensure basic tables exist in case of fresh setup."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS courses (
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
        CREATE TABLE IF NOT EXISTS course_slots (
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
    conn.commit()
    conn.close()

def get_db_stats() -> Dict[str, int]:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM courses")
        total_courses = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM course_slots")
        total_slots = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT department) FROM courses")
        total_departments = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT term) FROM courses")
        total_terms = cursor.fetchone()[0]
        
        return {
            "total_courses": total_courses,
            "total_slots": total_slots,
            "total_departments": total_departments,
            "total_terms": total_terms
        }
    except Exception as e:
        print(f"Error fetching DB stats: {e}")
        return {
            "total_courses": 0,
            "total_slots": 0,
            "total_departments": 0,
            "total_terms": 0
        }
    finally:
        conn.close()

def get_unique_terms() -> List[str]:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT term FROM courses ORDER BY term DESC")
        return [row["term"] for row in cursor.fetchall() if row["term"]]
    except Exception:
        return []
    finally:
        conn.close()

def get_unique_departments() -> List[str]:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT department FROM courses ORDER BY department ASC")
        return [row["department"] for row in cursor.fetchall() if row["department"]]
    except Exception:
        return []
    finally:
        conn.close()

def query_courses(
    term: str = None,
    department: str = None,
    search: str = None,
    day: str = None,
    page: int = 1,
    limit: int = 50
) -> Tuple[List[Dict[str, Any]], int]:
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        conditions = []
        params = []
        
        if term:
            conditions.append("term = ?")
            params.append(term)
            
        if department:
            conditions.append("department = ?")
            params.append(department)
            
        if search:
            search_cond = "(course_code LIKE ? OR course_name LIKE ? OR instructor LIKE ?)"
            conditions.append(search_cond)
            search_wildcard = f"%{search}%"
            params.extend([search_wildcard, search_wildcard, search_wildcard])
            
        if day:
            # Join with slots to filter by day
            conditions.append("courses.id IN (SELECT DISTINCT course_id FROM course_slots WHERE day = ?)")
            params.append(day)
            
        where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""
        
        # Count total courses matching query
        count_sql = f"SELECT COUNT(*) FROM courses{where_clause}"
        cursor.execute(count_sql, params)
        total_count = cursor.fetchone()[0]
        
        # Query matching courses
        offset = (page - 1) * limit
        query_sql = f"""
            SELECT * FROM courses 
            {where_clause} 
            ORDER BY term DESC, department ASC, course_code ASC, section ASC 
            LIMIT ? OFFSET ?
        """
        query_params = params + [limit, offset]
        cursor.execute(query_sql, query_params)
        courses_rows = cursor.fetchall()
        
        courses_list = []
        for row in courses_rows:
            course = dict(row)
            # Fetch slots for this course
            cursor.execute("SELECT * FROM course_slots WHERE course_id = ?", (course["id"],))
            slots = [dict(s_row) for s_row in cursor.fetchall()]
            course["slots"] = slots
            courses_list.append(course)
            
        return courses_list, total_count
    except Exception as e:
        print(f"Error querying courses: {e}")
        return [], 0
    finally:
        conn.close()
