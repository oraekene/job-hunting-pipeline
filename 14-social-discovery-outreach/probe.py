print("PROBE OK")
import os
print("cwd:", os.getcwd())
import sqlite3
DB = os.path.join(r'C:\Users\rotim\AppData\Local\hermes\skills\job-hunting', 'shared', 'applications.db')
c = sqlite3.connect(DB)
print("db ok, social_outreach rows:", c.execute('SELECT COUNT(*) FROM social_outreach').fetchone()[0])
c.close()
