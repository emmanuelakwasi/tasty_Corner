#!/usr/bin/env python3
"""
SQLite Database Viewer - View and edit employees.db in a readable format
"""
import sqlite3
import json
import os
import sys

DB_PATH = os.path.join('data', 'employees.db')

def view_all_data():
    """View all employee data in a readable format"""
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get table structure
    cursor.execute("PRAGMA table_info(employees)")
    columns = [row[1] for row in cursor.fetchall()]
    
    print("=" * 100)
    print("EMPLOYEES DATABASE VIEWER")
    print("=" * 100)
    print(f"\nDatabase: {DB_PATH}")
    print(f"Columns: {', '.join(columns)}")
    print("\n" + "=" * 100)
    
    # Get all employees
    cursor.execute("SELECT * FROM employees ORDER BY employee_id")
    rows = cursor.fetchall()
    
    if not rows:
        print("\nNo employees found in database.")
        conn.close()
        return
    
    for idx, row in enumerate(rows, 1):
        print(f"\n{'─' * 100}")
        print(f"EMPLOYEE #{idx}")
        print(f"{'─' * 100}")
        
        for col in columns:
            value = row[col]
            
            # Format schedule nicely
            if col == 'schedule' and value:
                try:
                    schedule = json.loads(value)
                    print(f"\n{col.upper()}:")
                    print("  " + json.dumps(schedule, indent=4))
                    
                    # Also show formatted
                    print("\n  Formatted Schedule:")
                    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                    for day in days:
                        day_data = schedule.get(day, {})
                        if day_data.get('enabled', False):
                            print(f"    {day.capitalize():12}: {day_data.get('start', 'N/A')} - {day_data.get('end', 'N/A')}")
                        else:
                            print(f"    {day.capitalize():12}: OFF")
                except:
                    print(f"{col.upper()}: {value}")
            else:
                print(f"{col.upper()}: {value}")
        
        print()
    
    print("=" * 100)
    print(f"Total employees: {len(rows)}")
    conn.close()

def export_to_text():
    """Export database to a readable text file"""
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return
    
    output_file = 'employees_database_export.txt'
    
    # Redirect output to file
    original_stdout = sys.stdout
    with open(output_file, 'w', encoding='utf-8') as f:
        sys.stdout = f
        view_all_data()
    sys.stdout = original_stdout
    
    print(f"\nDatabase exported to: {output_file}")
    print(f"You can now open this file in any text editor!")

def show_table_structure():
    """Show the database table structure"""
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 100)
    print("DATABASE TABLE STRUCTURE")
    print("=" * 100)
    
    cursor.execute("PRAGMA table_info(employees)")
    columns = cursor.fetchall()
    
    print("\nTable: employees")
    print("-" * 100)
    print(f"{'Column Name':<20} {'Type':<15} {'Not Null':<10} {'Default':<20} {'PK':<5}")
    print("-" * 100)
    
    for col in columns:
        print(f"{col[1]:<20} {col[2]:<15} {str(bool(col[3])):<10} {str(col[4]):<20} {str(bool(col[5])):<5}")
    
    conn.close()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == '--export':
            export_to_text()
        elif sys.argv[1] == '--structure':
            show_table_structure()
        else:
            print("Usage:")
            print("  python db_viewer.py           - View all data")
            print("  python db_viewer.py --export - Export to text file")
            print("  python db_viewer.py --structure - Show table structure")
    else:
        view_all_data()

