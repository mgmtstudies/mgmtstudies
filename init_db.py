import sqlite3

# Database file se connect ya create karein
conn = sqlite3.connect('database.db')
cursor = conn.cursor()

# Ek nayi table banana bacho ke data k liye
cursor.execute('''
    CREATE TABLE IF NOT EXISTS students (
        roll_no TEXT PRIMARY KEY,
        name TEXT,
        father_name TEXT
    )
''')

# ⚠️ YAHAN APNE BACHON KA REAL DATA DAAL SAKTE HO
# Format: ('RollNo', 'Name', 'Father Name')
mock_students = [
    ('101', 'Rahul Vashisth', 'Sh. Satish Kumar'),
    ('102', 'Amit Kumar', 'Sh. Ram Chander'),
    ('103', 'Kavita Kumari', 'Sh. Rajender Singh')
]

# Data insert karna
cursor.executemany("INSERT OR REPLACE INTO students VALUES (?, ?, ?)", mock_students)

conn.commit()
conn.close()
print("Database successfully ban gaya h aur sample data insert ho gaya h!")