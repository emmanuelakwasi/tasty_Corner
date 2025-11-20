#!/usr/bin/env python3
"""
Script to view employee schedules in the SQLite database
"""
import sqlite3
import json
import os

# Database path
DB_PATH = os.path.join('data', 'employees.db')

def view_schedules():
    """View all employee schedules"""
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check if schedule column exists
    cursor.execute("PRAGMA table_info(employees)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'schedule' not in columns:
        print("Schedule column does not exist in employees table.")
        conn.close()
        return
    
    # Get all employees with their schedules
    cursor.execute("""
        SELECT employee_id, first_name, last_name, email, schedule 
        FROM employees 
        ORDER BY employee_id
    """)
    
    rows = cursor.fetchall()
    
    if not rows:
        print("No employees found in database.")
        conn.close()
        return
    
    print("=" * 100)
    print("EMPLOYEE SCHEDULES")
    print("=" * 100)
    
    for row in rows:
        print(f"\n{'─' * 100}")
        print(f"Employee ID: {row['employee_id']}")
        print(f"Name: {row['first_name']} {row['last_name']}")
        print(f"Email: {row['email']}")
        
        schedule_str = row['schedule']
        if schedule_str:
            try:
                schedule = json.loads(schedule_str)
                print(f"\nSchedule (JSON):")
                print(json.dumps(schedule, indent=2))
                
                print(f"\nSchedule (Formatted):")
                days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                for day in days:
                    day_data = schedule.get(day, {})
                    if day_data.get('enabled', False):
                        print(f"  {day.capitalize():12} : {day_data.get('start', 'N/A')} - {day_data.get('end', 'N/A')}")
                    else:
                        print(f"  {day.capitalize():12} : OFF")
            except json.JSONDecodeError:
                print(f"\nSchedule (Raw): {schedule_str}")
        else:
            print("\nSchedule: Not assigned")
    
    print(f"\n{'─' * 100}")
    print(f"Total employees: {len(rows)}")
    conn.close()

def view_schedule_sql():
    """Show SQL queries to view schedules"""
    print("\n" + "=" * 100)
    print("SQL QUERIES TO VIEW SCHEDULES")
    print("=" * 100)
    print("""
To view schedules using SQLite command line:

1. Open SQLite:
   sqlite3 data/employees.db

2. View all schedules:
   SELECT employee_id, first_name, last_name, schedule FROM employees;

3. View schedule for specific employee:
   SELECT employee_id, first_name, last_name, schedule 
   FROM employees 
   WHERE employee_id = '000001';

4. View only employees with schedules:
   SELECT employee_id, first_name, last_name, schedule 
   FROM employees 
   WHERE schedule IS NOT NULL AND schedule != '';

5. View schedule column structure:
   PRAGMA table_info(employees);

6. Pretty print a schedule (example):
   SELECT 
       employee_id,
       first_name,
       last_name,
       json_extract(schedule, '$.monday.enabled') as monday_enabled,
       json_extract(schedule, '$.monday.start') as monday_start,
       json_extract(schedule, '$.monday.end') as monday_end
   FROM employees
   WHERE employee_id = '000001';
""")

if __name__ == '__main__':
    view_schedules()
    view_schedule_sql()

