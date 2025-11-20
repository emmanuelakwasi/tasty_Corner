#!/usr/bin/env python3
"""
Script to update employee schedules in the SQLite database
"""
import sqlite3
import json
import os
import sys

# Database path
DB_PATH = os.path.join('data', 'employees.db')

def get_default_schedule():
    """Get default schedule (Mon-Fri, 9AM-5PM)"""
    return {
        'monday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
        'tuesday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
        'wednesday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
        'thursday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
        'friday': {'enabled': True, 'start': '09:00', 'end': '17:00'},
        'saturday': {'enabled': False, 'start': '09:00', 'end': '17:00'},
        'sunday': {'enabled': False, 'start': '09:00', 'end': '17:00'}
    }

def update_schedule(employee_id, schedule_dict):
    """Update schedule for an employee"""
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return False
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Check if employee exists
    cursor.execute("SELECT employee_id FROM employees WHERE employee_id = ?", (employee_id,))
    if not cursor.fetchone():
        print(f"Employee with ID {employee_id} not found.")
        conn.close()
        return False
    
    # Convert schedule dict to JSON string
    schedule_json = json.dumps(schedule_dict)
    
    # Update schedule
    cursor.execute("UPDATE employees SET schedule = ? WHERE employee_id = ?", (schedule_json, employee_id))
    conn.commit()
    conn.close()
    
    print(f"Schedule updated successfully for employee {employee_id}")
    return True

def update_schedule_interactive():
    """Interactive function to update schedule"""
    print("=" * 80)
    print("UPDATE EMPLOYEE SCHEDULE")
    print("=" * 80)
    
    # Show all employees
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT employee_id, first_name, last_name FROM employees ORDER BY employee_id")
    employees = cursor.fetchall()
    
    if not employees:
        print("No employees found.")
        conn.close()
        return
    
    print("\nAvailable employees:")
    for emp in employees:
        print(f"  {emp['employee_id']}: {emp['first_name']} {emp['last_name']}")
    
    employee_id = input("\nEnter Employee ID: ").strip()
    
    # Get current schedule
    cursor.execute("SELECT schedule FROM employees WHERE employee_id = ?", (employee_id,))
    row = cursor.fetchone()
    
    if not row:
        print(f"Employee {employee_id} not found.")
        conn.close()
        return
    
    # Parse current schedule or use default
    current_schedule = {}
    if row['schedule']:
        try:
            current_schedule = json.loads(row['schedule'])
        except:
            current_schedule = get_default_schedule()
    else:
        current_schedule = get_default_schedule()
    
    print("\nCurrent schedule:")
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    for day in days:
        day_data = current_schedule.get(day, {})
        if day_data.get('enabled', False):
            print(f"  {day.capitalize():12}: {day_data.get('start', 'N/A')} - {day_data.get('end', 'N/A')} [ENABLED]")
        else:
            print(f"  {day.capitalize():12}: OFF")
    
    print("\nUpdate schedule (press Enter to keep current value):")
    new_schedule = {}
    
    for day in days:
        day_data = current_schedule.get(day, {})
        current_enabled = day_data.get('enabled', False)
        current_start = day_data.get('start', '09:00')
        current_end = day_data.get('end', '17:00')
        
        print(f"\n{day.capitalize()}:")
        enabled_input = input(f"  Enabled? (y/n) [{'y' if current_enabled else 'n'}]: ").strip().lower()
        enabled = enabled_input == 'y' if enabled_input else current_enabled
        
        if enabled:
            start_input = input(f"  Start time [current: {current_start}]: ").strip()
            start = start_input if start_input else current_start
            
            end_input = input(f"  End time [current: {current_end}]: ").strip()
            end = end_input if end_input else current_end
        else:
            start = current_start
            end = current_end
        
        new_schedule[day] = {
            'enabled': enabled,
            'start': start,
            'end': end
        }
    
    # Confirm update
    print("\nNew schedule:")
    for day in days:
        day_data = new_schedule.get(day, {})
        if day_data.get('enabled', False):
            print(f"  {day.capitalize():12}: {day_data.get('start', 'N/A')} - {day_data.get('end', 'N/A')}")
        else:
            print(f"  {day.capitalize():12}: OFF")
    
    confirm = input("\nConfirm update? (y/n): ").strip().lower()
    if confirm == 'y':
        update_schedule(employee_id, new_schedule)
    else:
        print("Update cancelled.")
    
    conn.close()

def show_sql_examples():
    """Show SQL examples for manual updates"""
    print("\n" + "=" * 80)
    print("SQL EXAMPLES FOR MANUAL UPDATES")
    print("=" * 80)
    print("""
To update schedules directly in SQLite:

1. Open SQLite:
   sqlite3 data/employees.db

2. Update entire schedule (replace with your JSON):
   UPDATE employees 
   SET schedule = '{"monday":{"enabled":true,"start":"09:00","end":"17:00"},"tuesday":{"enabled":true,"start":"09:00","end":"17:00"},"wednesday":{"enabled":true,"start":"09:00","end":"17:00"},"thursday":{"enabled":true,"start":"09:00","end":"17:00"},"friday":{"enabled":true,"start":"09:00","end":"17:00"},"saturday":{"enabled":false,"start":"09:00","end":"17:00"},"sunday":{"enabled":false,"start":"09:00","end":"17:00"}}'
   WHERE employee_id = '209228';

3. Update specific day using JSON functions (SQLite 3.38+):
   UPDATE employees
   SET schedule = json_set(
       schedule,
       '$.monday.enabled', 1,
       '$.monday.start', '10:00',
       '$.monday.end', '18:00'
   )
   WHERE employee_id = '209228';

4. Enable/disable a day:
   UPDATE employees
   SET schedule = json_set(schedule, '$.monday.enabled', 1)
   WHERE employee_id = '209228';

5. View before updating:
   SELECT employee_id, first_name, last_name, schedule 
   FROM employees 
   WHERE employee_id = '209228';

6. Verify update:
   SELECT employee_id, 
          json_extract(schedule, '$.monday.enabled') as monday_enabled,
          json_extract(schedule, '$.monday.start') as monday_start,
          json_extract(schedule, '$.monday.end') as monday_end
   FROM employees 
   WHERE employee_id = '209228';
""")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == '--sql':
            show_sql_examples()
        else:
            print("Usage: python update_schedule.py [--sql]")
            print("  --sql  : Show SQL examples for manual updates")
    else:
        update_schedule_interactive()

