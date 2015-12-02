# coding: utf-8
from hashlib import md5
from db import db_connect, db_query, db_disconnect
from settings import secret_key as salt
from mysql.connector.conversion import MySQLConverter

def check_sign(rj):
  if 'externalOrderId' in rj:
    ext_oid = rj['externalOrderId']
    success_url = rj.get('successUrl', '')
    cancel_url = rj.get('cancelUrl', '')
    string = ':'.join((rj['id'], rj['type'], rj['price'], ext_oid, success_url, cancel_url, rj['ts'], salt))
    print string
    sign = md5(':'.join((rj['id'], rj['type'], rj['price'], ext_oid, success_url, cancel_url, rj['ts'], salt)))
  else:
    sign = md5(':'.join((rj['id'], rj['type'], rj['price'], rj['ts'], salt)))
  print sign.hexdigest(), '==', rj['sign']
  return sign.hexdigest() == rj['sign']

def add_film_info(rj):
  result = None
  ext_oid = None
  if 'externalOrderId' in rj:
    conv = MySQLConverter()
    ext_oid = rj['externalOrderId']
    success_url = conv.escape(rj.get('successUrl', None))
    cancel_url = conv.escape(rj.get('cancelUrl', None))
  db = db_connect()
  try:
    if not ext_oid:
      result = db_query(db, 'insert into vidimax (film_id, type, name, price) values ({film_id}, "{type}", "{name}", {price});'\
                .format(film_id=rj['id'], type=rj['type'], name=rj['name'], price=int(int(rj['price'])/100)),
                commit=True, lastrow=True)
    else:
      query = 'insert into vidimax values (null, null, "{external_oid}", {film_id}, "{type}", "{name}", {price}, '.format(
                external_oid=ext_oid, film_id=rj['id'], type=rj['type'], name=rj['name'], price=int(int(rj['price'])/100)
              )
      if success_url:
        query += '"{0}", '.format(success_url)
      else:
        query += 'null, '
      if cancel_url:
        query += '"{0}");'.format(cancel_url)
      else:
        query += 'null);'

      result = db_query(db, query, commit=True, lastrow=True)
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

def get_subs_info(db, video_id, train_info=None):
  def get_train_id(train_info):
    (ip, direction) = train_info
    num = ''
    if ip[:5] != '10.10': # hardcode here and below
      num = ip.replace('.', '-')
    else:
      num = '{0:03}'.format(int(ip.split('.')[2])/2 + 1)
    return '/'.join((num, direction.lower()))

  result = {}
  res = db_query(db, 'select v.film_id, v.type, v.name, v.price*100, o.order_id, v.external_order_id from vidimax v \
                      left join orders o on v.order_id = o.id where v.id={id};'.format(id=video_id))
  if res:
    result = {
      'id': res[0],
      'type': res[1],
      'name': res[2],
      'price': res[3],
      'orderId': res[4]
    }
    if res[5]:
      result['externalOrderId'] = res[5]
    if train_info:
      result['trainId'] = get_train_id(train_info)
  return result
