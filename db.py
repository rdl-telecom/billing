import mysql.connector
import settings
from pprint import pprint

def db_connect():
  return mysql.connector.Connect(host=settings.db_host, port=settings.db_port, user=settings.db_user, password=settings.db_password, database=settings.db_name)

def db_disconnect(db):
  return db.close()

def db_query(db, query, fetch=True, full=False, commit=False, lastrow=False, quiet=False):
  cursor = db.cursor()
  if not quiet:
    pprint(query)
  cursor.execute(query)
  result = None
  if commit:
    db.commit()
  if fetch:
    if full:
      result = cursor.fetchall()
    else:
      result = cursor.fetchone()
  if lastrow:
    result = cursor.lastrowid
  if not quiet:
    pprint(result)
  cursor.close()
  return result
