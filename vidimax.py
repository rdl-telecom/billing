# coding: utf-8
from hashlib import md5
from db import db_connect, db_query, db_disconnect

salt = 'securemonkey^%'

def check_sign(rj):
  sign = md5(':'.join((rj['id'], rj['type'], rj['price'], rj['ts'], salt)))
  return sign.hexdigest() == rj['sign']

def add_film_info(rj):
  result = None
  db = db_connect()
  try:
    result = db_query(db, 'insert into vidimax values (null, null, {film_id}, "{type}", "{name}", {price});'\
                .format(film_id=rj['id'], type=rj['type'], name=rj['name'], price=int(int(rj['price'])/100)),
                commit=True, lastrow=True)
  except Exception as e:
    print e
    pass
  finally:
    db_disconnect(db)
  return result

def update_order_id(db, film_id, order_id):
  db_query(db, 'update vidimax set order_id={order} where id={id};'.format(order=order_id, id=film_id), commit=True)

def get_price(db, film_id):
  [ result ] = db_query(db, 'select price from vidimax where id={id}'.format(id=film_id))
  return result

def get_subs_info(db, id):
  result = {}
  res = db_query(db, 'select film_id, type, name, price*100 from vidimax where id={id};'.format(id=id))
  if res:
    result = {
      'id': res[0],
      'type': res[1],
      'name': res[2],
      'price': res[3]
    }
  return result
