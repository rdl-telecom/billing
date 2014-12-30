#!/usr/bin/env python2
# -*- coding: utf-8 -*-

# from uuid import uuid4
from flask import jsonify, Response
import mysql.connector
import json
import io
from xmlutils import xml2json
from urlparse import urlparse, parse_qs
import datetime
from mac import get_mac
from check import get_phone, match_code
from scratch import gen_code

# local imports
import settings

from pprint import pprint

################################
#####  INTERNAL FUNCTIONS  #####

def url2json(url):
  tmp_json = parse_qs(urlparse(url).query)
  result = {}
  for param in tmp_json.iterkeys():
    result[param] = tmp_json[param][0]
  return result

def json_response(data, status=200):
  pprint(data)
  response = jsonify(data)
  response.status_code = status
  return response

#####
def db_connect():
  return mysql.connector.Connect(host=settings.db_host, port=settings.db_port, user=settings.db_user, password=settings.db_password, database=settings.db_name)

def db_disconnect(db):
  return db.close()

def db_query(db, query, fetch=True, full=False, commit=False, lastrow=False):
  cursor = db.cursor()
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
  pprint(result)
  cursor.close()
  return result

#####
def new_code():
  db = db_connect()
  generated = False
  code = gen_code()
  while not generated:
    try:
      db_query(db, 'insert into codes (key_value, used) values ("%s", 1);'%(code), commit=True, fetch=False)
      generated = True
    except:
      code = gen_code()
      pass
  db_disconnect(db)
  return code

#####
def get_order_id(ord_id):
  print 'get_order_id( ' + ord_id + ' )'
  res = None
  if type(ord_id) is str or type(ord_id) is unicode:
    res = int(ord_id[8:])
  if type(ord_id) is int:
    res = ord_id
  return res

#####
def get_services(db):
  result = db_query(db, 'select service from tariffs order by service group by service;', full=True)
  return result

def get_tariffs(service):
  db = db_connect()
  tariffs = db_query(db, 'select type, button_name, price, button_name_en, description, description_en from tariffs '
                         'where service="%s" order by price;'%(service.upper()), full=True
                    )
  db_disconnect(db)
  result = {}
  for i in range(len(tariffs)):
    result[str(i)] = {
      'Button' : tariffs[i][1] ,
      'Button_EN' : tariffs[i][3],
      'Tariff' : tariffs[i][0],
      'Sum' : tariffs[i][2],
      'Description' : tariffs[i][4],
      'Description_EN' : tariffs[i][5]
    }
  return result

def get_film_price(filmid):
  db = db_connect()
  [ name, price ] = db_query(db, 'select name, price from films where id=%s'%(filmid))
  db_disconnect(db)
  result = {
    '0' : {
          'Button' : '%s руб/24 часа'%(price),
          'Button_EN' : '%s rub/24 hours'%(price),
          'Tariff' : 'FILM',
          'Sum' : price,
          'Description' : 'Стоимость доступа к фильму "%s" в течение 24 часов составляет %s рублей (включая НДС)'%(name, price),
          'Description_EN' : 'The cost of access to "%s" film during 24 hours shall be %s rubles (VAT included)'%(name, price)
        },
    'URL' : settings.vidimax_base + '/#movie/' + filmid
  }
  pprint(result)
  return result

#####
def get_shopid_by_orderid(order_id):
  result = {}
  db = db_connect()
  res = db_query(db, 'select s.shop from orders o left join shops s on s.id = o.shop_id where o.order_id = "%s"'%(order_id))
  if res:
    [ result['ShopID'] ] = res
  db_disconnect(db)
  return result

####################################################################################################################################################
def get_active_sessions():
  db = db_connect()
  lines = db_query(db, 'select ords.id, ords.start_time, ords.session_time, tar.duration, ords.state_id from orders ords '
                       'left join tariffs tar on tariff_id = tar.id '
                       'where start_time is not null and state_id=0;', full=True
                   )
  result = {}
  pprint(lines)
  if lines != []:
    for ( order_id, start_time, session_time, duration, state_id ) in lines:
      result[str(order_id)] = {
        'start_time' : start_time,
        'session_time' : session_time,
        'duration' : duration,
        'state' : state_id
      }
  db_disconnect(db)
  return result

def start_session(order_id):
  db = db_connect()
  db_query(db, 'update orders set stop_time=null, start_time=now(), '
               'state_id=0 '
               'where id=%d'%(order_id), fetch=False, commit=True
          )
  db_disconnect(db)

def stop_session(order_id, by_user=False):
  if by_user: state_id = 1
  else: state_id = 2
  db = db_connect()
  db_query(db, 'update orders set stop_time = now(), '
               'state_id = %d, '
               'session_time = sec_to_time(unix_timestamp() - unix_timestamp(start_time) + time_to_sec(session_time)),'
               'start_time = null'
               'where id=%d'%(state_id, order_id), fetch=False, commit=True
          )
  db_disconnect(db)

def end_session(order_id):
  db = db_connect()
  db_query(db, 'update orders set stop_time=null, end_time=now(), state_id=3, '
               'session_time = sec_to_time(unix_timestamp() - unix_timestamp(start_time) + time_to_sec(session_time)), '
               'start_time=null '
               'where id=%d'%(order_id), fetch=False, commit=True
          )
  db_disconnect(db)

#####
def verify_user(usrname, passwd):
  db = db_connect()
  result = True
  if not db_query(db, 'select id from users where user="%s" and passwd=password("%s");'%(usrname, passwd)):
    result = False
  db_disconnect(db)
  return result

def user_ok(request_json):
  try:
    if not verify_user(request_json['login'], request_json['password']):
      raise ValueError
  except:
    return False
  return True

#####
def get_shop_id(db):
  [ res ] = db_query(db, 'select id from shops where shop="%s";'%(settings.shop_id))
  return res

def get_tariff(db, service, tariff, film_id):
  if not film_id:
    return db_query(db, 'select id, price from tariffs where service="%s" and type="%s";'%(service.upper(), tariff.upper()))
  elif tariff.upper() == 'FILM':
    return db_query(db, 'select t.id, f.price from tariffs t left join films f on f.id = %s where service="%s" and type="%s";'
                        %(film_id, 'VIDEOSVC', 'FILM')
                   )

#####
def add_device_counter(db, order_id):
  print 'add_device_counter'
  print order_id
  db_query(db, 'update orders set dev_count = dev_count + 1 where id=%d'%(order_id), fetch=False, commit=True)

def check_order(db, payment_info):
  result = True
  row = db_query(db, 'select price, payment_time from orders left join tariffs on tariff_id = tariffs.id '
           'left join shops on shop_id = shops.id '
           'where shop="%s" and order_id="%s";'
            %(payment_info['shop_id'], payment_info['order_id'])
          )
  if not row:
    return False
  [ summ, p_time ] = row
  if (payment_info['sum'] < summ) or p_time:
    return False
  return True

def add_client_order(db, client_id, order_id):
  [ ord_id ] = db_query(db, 'select id from orders where order_id="%s";'%(order_id))
  [ cnt ] = db_query(db, 'select count(*) from client_orders where client_id=%d and order_id=%d;'%(client_id, ord_id))
  if cnt != 1:
    client_order_id = db_query(db, 'insert into client_orders (client_id, order_id) values (%d, %d);'
                                 %(client_id, ord_id), commit=True, fetch=False, lastrow=True
                              )
  return client_order_id

def get_client_by_phone(db, ph):
  phone = get_phone(ph)
  res = db_query(db, 'select id from clients where phone = '
                     'case substr("%s",1,1) when "+" then "%s" '
                     'when "8" then concat("+7",substr("%s",2)) '
                     'when "7" then concat("+","%s") '
                     'else concat("+7","%s") end;'%(phone, phone, phone, phone, phone), full=True)
  if res == []:
    return None
  return res[0][0]

def add_client_phone(db, ph):
  phone = get_phone(ph)
  return db_query(db, 'insert into clients set phone = '
                       'case substr("%s",1,1) when "+" then "%s" '
                       'when "8" then concat("+7",substr("%s",2)) '
                       'when "7" then concat("+","%s") '
                       'else concat("+7","%s") end;'%(phone, phone, phone, phone, phone), commit=True, fetch=False, lastrow=True)

def find_code(db, code):
  res = db_query(db, 'select id, client_id, tariff_id from orders where code="%s" and payment_time<>null and end_time=null;'%(code))
  if not res:
    return None
  [ order_id, client_id, tariff_id ] = res
  result = {
    'order_id' : order_id,
    'client_id' : client_id,
    'tariff_id' : tariff_id
  }
  return result

def add_client_info(db, cl_info):
  print 'add_client_info'
  pprint(cl_info)
  db_query(db, 'insert into client_info (client_id, mac, ip, user_agent, lang, client_orders_id) values (%d, "%s", "%s", "%s", "%s", %d);'
            %(cl_info['client_id'], cl_info['mac'], cl_info['ip'], cl_info['user_agent'], cl_info['lang'], cl_info['order_id']), fetch=False, commit=True)

def began(db, order_id):
  [ res ] = db_query(db, 'select begin_time is not null from orders where id=%d'%(order_id))
  return res == 1

def started(db, order_id):
  [ res ] = db_query(db, 'select start_time is not null from orders where id=%d'%(order_id))
  return res == 1

def get_client_info(db, r_json):
  # getting mac on r_json['IPAddress']
  # if mac is changed then it's new client
  pprint('get_client_info:')
  pprint(r_json)
  if not match_code(r_json['Code']):
    return None
  ip_mac = get_mac(r_json['IPAddress'])
  print ip_mac
  info_list = db_query(db,
                'select ords.id, ords.client_id, ci.mac, ci.ip, ci.user_agent, ci.lang, ords.state_id from orders ords '
                'left join client_info ci on ords.client_id = ci.client_id and ords.id = ci.client_orders_id '
                'left join client_orders co on ci.client_id = co.client_id and ords.id = co.order_id '
                'where ords.code = "%s" order by ci.update_time desc limit 1;'
                %(r_json['Code'])
              )
  if not info_list:
    return None
  print 'passed'
  flag = False
  [ order_id, client_id, mac, ip, user_agent, lang, state ] = info_list
  if state == 10:
    state = 0
  elif state == 3:
    return None
  if 'FilmID' in r_json: # FilmID checking
    [ res ] = db_query(db, 'select id from orders where id = %d and client_films_id = %s'%(order_id, r_json['FilmID']))
    if not res: # so this order is not for this film
      return None
  else: # checking for not film
    [ res ] = db_query(db, 'select id from orders where id = %d and client_films_id is null'%(order_id))
    if not res: # so this order is for film not for internet
      return None
  if mac != ip_mac or ip != r_json['IPAddress'] or user_agent != r_json['UserAgent'] or lang != r_json['Lang']:
    ip = r_json['IPAddress']
    user_agent = r_json['UserAgent']
    mac = ip_mac
    lang = r_json['Lang']
    flag = True
  result = {
    'order_id' : order_id,
    'client_id' : client_id,
    'mac' : mac,
    'ip' : ip,
    'user_agent' : user_agent,
    'lang' : lang,
    'state' : state ,
    'changed' : flag
  }
  return result

def update_client_info(db, client_info, logout):
  if not logout:
    pprint(client_info)
    res = db_query(db, 'select id from client_info where client_id=%d and mac="%s" and user_agent="%s" and client_orders_id=%d;'
                    %(client_info['client_id'], client_info['mac'], client_info['user_agent'], client_info['order_id'])
                  )
    if not res:
      add_client_info(db, client_info)
    else:
      db_query(db, 'update client_info set ip="%s", lang="%s", update_time=now(), client_orders_id=%d where id=%d;'
                %(client_info['ip'], client_info['lang'], client_info['order_id'], res[0]),
               fetch=False, commit=True)
    query = 'update orders set '
    if not started(db, client_info['order_id']):
      if not began(db, client_info['order_id']):
        query += 'begin_time=now(), '
      query += 'start_time=now(), '
    query += 'state_id=0 where id=%d'%(client_info['order_id'])
    db_query(db, query, fetch=False, commit=True)
    add_device_counter(db, client_info['order_id'])
  elif started(db, client_info['order_id']):
    stop_session(order_id, by_user=True)
  return client_info

#####
def update_order(payment_info):
  db = db_connect()
  result = False
  pprint(payment_info)
  client_id = get_client_by_phone(db, payment_info['phone'])
  if not client_id:
    client_id = add_client_phone(db, payment_info['phone'])
  if check_order(db, payment_info):
    client_order_id = add_client_order(db, client_id, payment_info['order_id'])
    db_query(db, 'update orders set billnumber="%s", client_id=%d, payment_time="%s", code="%s" where order_id="%s";'
                 %(payment_info['uni_billnumber'], client_id, payment_info['date'], payment_info['approval_code'], payment_info['order_id']),
             commit=True, fetch=False)
    result = True
  db_disconnect(db)
  return result

#####
def is_scratch_code(db, code):
  result = None
  if match_code(code) and len(code) == settings.scratch_length:
    res = db_query(db, 'select service, type, price from tariffs '
                       'where id = (select tariff_id from codes where key_value="%s" and serial is not null and not used) '
		       'and (select id from orders where code="%s") is null;'%(code, code)
                  )
    if res:
      result = {
        'service' : res[0],
        'tariff' : res[1],
        'sum' : res[2]
      }
  return result

def scratch_set_used(db, code):
  db_query(db, 'update codes set used = 1 where key_value="%s"'%(code), fetch=False, commit=True)

def generate_scratch_payment(shop_id, order_id, summ, code):
  result = {
    'shop_id' : shop_id,
    'order_id' : order_id,
    'date' : datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'sum' : summ,
    'approval_code' : code,
    'phone' : '+00000000000',
    'uni_billnumber' : '0',
  }
  return result 
  
####################################################################################################################################################
def get_phones_to_sms():
  db = db_connect()
  result = db_query(db, 'select ords.id, cl.phone, ords.code from orders ords left join clients cl on cl.id = client_id '
                        'where sms_sent = 0 and code <> "" order by payment_time;', full=True
                   )
  db_disconnect(db)
  return result

def sms_sent(order_id, status=2):
  db = db_connect()
  db_query(db, 'update orders set sms_sent=%d where id=%d;'%(status, order_id), fetch=False, commit=True)
  db_disconnect(db)

####################################################################################################################################################
def get_first_data(service, tariff, film_id=None):
  def create_order(db, shop, tariff, film):
    if not film:
      result = db_query(db, 'insert into orders (shop_id, tariff_id) values ( %s, %s );'%(shop, tariff), fetch=False, commit=True, lastrow=True)
    else:
      result = db_query(db, 'insert into orders (shop_id, tariff_id, client_films_id) values (%s, %s, %s);'
                        %(shop, tariff, film), fetch=False, commit=True, lastrow=True
                       )
    return result
  db = db_connect()
  tariff_id, tariff_sum = get_tariff(db, service, tariff, film_id)
  shop_id = get_shop_id(db)
  if not (tariff_id and tariff_sum and shop_id):
    return None
  order_num = create_order(db, shop_id, tariff_id, film_id)
  if not order_num:
    return None
  order_id = '%s%020d'%(service.upper(), order_num)
  db_query(db, 'update orders set order_id="%s" where id=%d'%(order_id, order_num), fetch=False, commit=True)
  db_disconnect(db)
  result = {
    'ShopID' : settings.shop_id,
    'OrderID' : order_id,
    'Sum' : tariff_sum
  }
  return result

#####
def get_film_session(request_json):
  pprint('get_film_session')
  result = {
    'Result' : False
  }
  mac = get_mac(request_json['IPAddress'])
  db = db_connect()
  try: # checking user code
    res = db_query(db, 'select o.id from orders o cross join '
                       '(select client_orders_id from client_info where mac = "%s" and ip = "%s" order by update_time desc limit 1) s on s.client_orders_id = o.id '
                       'where client_films_id=%s and begin_time is not null and end_time is null;'
                       %(mac, request_json['IPAddress'], request_json['FilmID'])
                   )
    if res:
      result['Result'] = True
  except Exception as e:
    print e
    pass
  db_disconnect(db)
  return result

def get_session(request_json, update=False):
  pprint('get_session')
  pprint(request_json)
  is_film = False
  if 'FilmID' in request_json:
    is_film = True
  if is_film and not update:
    return get_film_session(request_json)
  result = {
    'Result' : False,
    'IPAddress' : '',
    'UserAgent' : '',
    'Logout' : 0
  }
  if is_film:
    result['URL'] = settings.vidimax_base + '/#movie/' + request_json['FilmID']
    print result['URL']
  db = db_connect()
  tar = is_scratch_code(db, request_json['Code'])
  if tar and not is_film: # i don't accept scratch card payment for films for a while
    fd = get_first_data(tar['service'], tar['tariff'])
    order_id = get_order_id(fd['OrderID'])
    sms_sent(order_id)
    update_order(generate_scratch_payment(fd['ShopID'], fd['OrderID'], fd['Sum'], request_json['Code']))
    scratch_set_used(db, request_json['Code'])
  try:
    client_info = get_client_info(db, request_json)
    pprint('client_info = get_client_info:')
    pprint(client_info)
    if client_info:
      result = {
        'Result' : True,
        'IPAddress' : client_info['ip'],
        'UserAgent' : client_info['user_agent'],
        'Logout' : client_info['state']
      }
      if is_film:
        result['URL'] = settings.vidimax_base + '/#play/' + request_json['FilmID']
        print result['URL']
      if client_info['changed']:
        print 'if update:'
        if update:
          update_client_info(db, client_info, False)
        else:
          result['Result'] = False
  except KeyError:
    print "KeyError"
    result = None
  db_disconnect(db)
  return result

#####
def parse_xml(xml):
  print 'parse_xml:'
  try:
    uni_result = json.loads(xml2json.xml2json(io.StringIO(xml)).get_json())['unitellerresult']
  except:
    return None
  pprint(uni_result)
  order = uni_result['orders']['order']
  dt = datetime.datetime.strptime(order['date'], '%d.%m.%Y %H:%M:%S')
  order['date'] = dt.strftime('%Y-%m-%d %H:%M:%S')
  result = {
    'shop_id' : uni_result['request']['shop_id'],
    'order_id' : order['ordernumber'],
    'sum' : order['total'],
    'date' : order['date'],
    'response_code' : order['response_code'],
    'description' : order['recommendation'],
    'approval_code' : order['approvalcode'],
    'phone' : order['phone'],
    'uni_billnumber' : order['billnumber'],
    'status' : order['status'],
    'need_confirm' : order['need_confirm']
  }
  if not match_code(result['approval_code']):
    result['approval_code'] = new_code()
  return result

if __name__ == '__main__':
  #print new_code()
  pprint(get_first_data('VIDEOSVC','FILM3'))
