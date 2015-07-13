import mysql.connector
import settings
from pprint import pprint


class DB:
    connected = False
    _db = None

    def __init__(self):
        self.connect()

    def connect(self):
        self._db = mysql.connector.Connect(host=settings.db_host,
                                        port=settings.db_port,
                                        user=settings.db_user,
                                        password=settings.db_pass,
                                        database=settings.db_name
                                      )
        self.connected = True

    def disconnect(self):
        self.connected = False
        self._db.close()

    def query(self, query, fetch=True, fetchall=False, commit=False, lastrow=False):
        try:
            cursor = self._db.cursor()
        except:
            self.connect()
            cursor = self._db.cursor()
        pprint(query)
        cursor.execute(query)
        result = None
        if commit:
            db.commit()
        if fetch:
            if fetchall:
                result = cursor.fetchall()
            else:
                result = cursor.fetchone()
        if lastrow:
            result = cursor.lastrowid
        pprint(result)
        cursor.close()
        return result
