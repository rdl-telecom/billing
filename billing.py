# -*- coding: utf-8 -*-

# from uuid import uuid4
from flask import jsonify, Response
import json
import io
from xmlutils import xml2json
from urlparse import urlparse, parse_qs
import datetime
import time
from mac import get_mac
from check import get_phone, match_code
from scratch import gen_code
from vidimax import update_order_id, get_price, get_subs_info
from db import db_connect, db_disconnect, db_query
from icomera_auth import auth_client, deny_client
# local imports
import settings
import tariffs
from service.sms import send_sms

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
def get_code(order_id):
    result = None
    db = db_connect()
    res = db_query(db, 'select code from orders where order_id="%s"'%(order_id))
    db_disconnect(db)
    if res:
        [ result ] = res
    return result

def new_code():
    db = db_connect()
    generated = False
    while not generated:
        try:
            code = gen_code()
            db_query(db, 'insert into codes (key_value, used) values ("%s", 1);'%(code), commit=True, fetch=False)
            generated = True
        except:
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

def get_filmid_by_orderid(order_id):
    result = {}
    if order_id[:8] == 'VIDEOSVC':
        db = db_connect()
        res = db_query(db, 'select client_films_id from orders where order_id="%s"'%(order_id))
        if res:
            result['FilmID'] = res[0]
        db.close()
    return result

#####
def get_shopid_by_orderid(order_id):
    result = {}
    db = db_connect()
    res = db_query(db, 'select s.shop from orders o left join shops s on s.id = o.shop_id where o.order_id = "%s"'%(order_id))
    if res:
        result['ShopID'] = res[0]
    db_disconnect(db)
    return result

####################################################################################################################################################
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
def get_active_sessions():
    db = db_connect()
    lines = db_query(db, 'select ords.id, ords.direction, tariff_id, ords.start_time, ords.session_time, '
                                             'ords.client_films_id, tar.duration, ords.state_id from orders ords '
                                             'left join tariffs tar on tariff_id = tar.id '
                                             'where start_time is not null and state_id=0;', full=True
                                     )
    result = {}
    if lines != []:
        for ( order_id, direction, tariff_id, start_time, session_time, is_film, dur, state_id ) in lines:
            print order_id, direction, dur
            duration = dur
            if direction and not is_film:
                duration = tariffs.get_duration(direction, tariff_id)
#                else:
#                    duration = tariffs.get_direction_trip_duration(direction)
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

def unauth_user(db, order_id):
    res = db_query(db, 'select ip from client_info where client_orders_id=%s'%(order_id), full=True)
    for line in res:
            ip = line[0]
            attempts = 100 # hardcode
            while not deny_client(ip) and attempts > 0:
                    time.sleep(10)
                    attempts -= 1

def end_session(order_id):
    db = db_connect()
    db_query(db, 'update orders set stop_time=null, end_time=now(), state_id=3, '
                             'session_time = sec_to_time(unix_timestamp() - unix_timestamp(start_time) + time_to_sec(session_time)), '
                             'start_time=null '
                             'where id=%d'%(order_id), fetch=False, commit=True
                    )
    unauth_user(db, order_id)
    db_disconnect(db)

#####
def get_shop(payment_system=None):
    res = settings.shop_id
    if payment_system == 'PLATRON':
        res = '00006866'
    if payment_system == 'SCRATCH':
        res = 'FFFFFFFF'
    return res

def get_shop_id(db, payment_system=None):
    shop = get_shop(payment_system)
    [ res ] = db_query(db, 'select id from shops where shop="%s";'%(shop))
    return res


def get_tariff(db, service, tariff, film_id, new_model=False):
    serv = service.upper()
    tar = tariff.upper()
    if not film_id:
        if tar in ['ONEHOUR', 'ONEDAY']:
            return db_query(db, 'select id, price from tariffs where service="%s" and type="%s";'%(serv, tar))
        else:
            res = tariffs.get_tariff(serv, tar)
            if res:
                return res
            else:
                return tariffs.get_tariff(serv, '1HOUR') #hardcode 
    elif tariff.upper() == 'FILM':
        query = 'select t.id, f.price from tariffs t left join films f on f.id = %s where service="%s" and type="%s";'
        if new_model:
            query = 'select id, (select price from vidimax where id=%s) from tariffs where service="%s" and type="%s";'
        return db_query(db, query%(film_id, 'VIDEOSVC', 'FILM'))

#####
def add_device_counter(db, order_id):
    print 'add_device_counter', order_id
    ( current, ) = db_query(db, 'select dev_count from orders where id=%s'%(order_id))
    result = True
    if current < 2: # hardcode
        db_query(db, 'update orders set dev_count = dev_count + 1 where id=%d'%(order_id), fetch=False, commit=True)
        result = True
    return result

def check_order(db, payment_info):
    result = True
    row = db_query(db, 'select direction, price, payment_time, tariff_id, client_films_id from orders left join tariffs on tariff_id = tariffs.id '
                     'left join shops on shop_id = shops.id '
                     'where shop="%s" and order_id="%s";'
                        %(payment_info['shop_id'], payment_info['order_id'])
                    )
    if not row:
        return False
    [ direction, s, p_time, tariff_id, is_film ] = row
    summ = s
    if direction and is_film == 0:
        summ = tariffs.get_price(direction, tariff_id)
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
                                         'when "9" then concat("+7","%s") '
                                         'else concat("+","%s") end;'%(phone, phone, phone, phone, phone), full=True)
    if res == []:
        return None
    return res[0][0]

def add_client_phone(db, ph):
    phone = get_phone(ph)
    return db_query(db, 'insert into clients set phone = '
                                             'case substr("%s",1,1) when "+" then "%s" '
                                             'when "8" then concat("+7",substr("%s",2)) '
                                             'when "9" then concat("+7","%s") '
                                             'else concat("+","%s") end;'%(phone, phone, phone, phone, phone),    commit=True, fetch=False, lastrow=True)

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

def is_new_model(db, order_id):
    [ res ] = db_query(db, 'select new_model from orders where id = %s'%(order_id))
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
    url = None
    ext_oid = None
    if 'FilmID' in r_json: # FilmID checking
        new_model = is_new_model(db, order_id)
        if not new_model:
            res = db_query(db, 'select id from orders where id = %d and client_films_id = %s'%(order_id, r_json['FilmID']))
        else:
            res = db_query(db, 'select o.id, v.success_url, v.external_order_id \
                                                    from orders o cross join vidimax v on o.id = v.order_id and o.client_films_id = v.id where o.id = %d'
                                                    %(order_id)
                                        )
        if not res: # so this order is not for this film
            return None
        if new_model:
            url = res[1]
            ext_oid = res[2]
    else: # checking for not film
        res = db_query(db, 'select id from orders where id = %d and client_films_id = 0'%(order_id))
        if not res: # so this order is for film not for internet
            return None
    if mac != ip_mac or ip != r_json['IPAddress']:
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
        'state' : state,
        'changed' : flag
    }
    if url:
        result['url'] = url
    if ext_oid:
        result['external_order_id'] = ext_oid
    return result

def update_client_info(db, client_info, logout):
    result = client_info
    if not logout:
        pprint(client_info)
        res = db_query(db, 'select id from client_info where client_id=%d and mac="%s" and client_orders_id=%d;'
                                        %(client_info['client_id'], client_info['mac'], client_info['order_id'])
                                    )
        if not res: # new client device
            if add_device_counter(db, client_info['order_id']):
                add_client_info(db, client_info)
            else:
                return None
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
    elif started(db, client_info['order_id']):
        stop_session(order_id, by_user=True)
    return result

#####
def update_order(payment_info):
    db = db_connect()
    result = False
    pprint(payment_info)
    client_id = get_client_by_phone(db, payment_info['phone'])
    if not client_id:
        client_id = add_client_phone(db, payment_info['phone'])
    code = payment_info['approval_code']
    if check_order(db, payment_info):
        if not code:
            code = new_code()
        client_order_id = add_client_order(db, client_id, payment_info['order_id'])
        db_query(db, 'update orders set billnumber="%s", client_id=%d, payment_time="%s", code="%s" where order_id="%s";'
                                 %(payment_info['uni_billnumber'], client_id, payment_info['date'], code, payment_info['order_id']),
                         commit=True, fetch=False)
        result = True
        if not settings.testing:
            send_sms(payment_info['phone'], code)
            sms_sent(payment_info['order_id'])
    db_disconnect(db)
    return result

#####
def refund_payment(payment_info):
    db = db_connect()
    result = False
    pprint(payment_info)
    try:
        db_query(db, 'update orders set refund_id="%s", end_time=now(), refund_time="%s", state_id=4 where order_id="%s";'
                                 %(payment_info['refund_id'], payment_info['date'], payment_info['order_id']),
                         commit=True, fetch=False)
        order_id=int(payment_info['order_id'][8:])
        unauth_user(db, order_id)
        result = True
    except Exception as e:
        print e
    db_disconnect(db)
    return result

#####
def is_vip_code(db, code):
    result = False
    if match_code(code) and db_query(db, 'select vip from codes where key_value="%s" and now() between activated and expires'%(code)):
        result = True
    return result

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
    
def is_vip_client(db, ip, mac):
    res = db_query(db, 'select now() between c.activated and c.expires from vip_clients v left join codes c on c.key_value = v.code where ip="%s" and mac="%s";'
                                                 %(ip, mac))
    return res != None

def add_vip_client(db, code, ip, mac):
    db_query(db, 'insert into vip_clients values (0, "%s", "%s", "%s", now());'%(code.upper(), ip, mac), fetch=False, commit=True)

####################################################################################################################################################
def get_phones_to_sms():
    db = db_connect()
    result = db_query(db, 'select ords.id, cl.phone, ords.code from orders ords left join clients cl on cl.id = client_id '
                                                'where (sms_sent = 0 or (sms_sent = 1 and unix_timestamp(now()) - unix_timestamp(payment_time) > 600)) '
                                                'and code <> "" order by payment_time;', full=True, quiet=True
                                     )
    db_disconnect(db)
    return result

def sms_sent(order_id, status=2):
    db = db_connect()
    db_query(db, 'update orders set sms_sent=%d where id=%d;'%(status, order_id), fetch=False, commit=True)
    db_disconnect(db)

def get_client_codes(direction, phone, ip):
    result = {}
    try:
        mac = get_mac(ip).replace(':','')
        if settings.check_mac and mac == '0'*12:
            raise ValueError('No MAC address for %s'%(ip))
        db = db_connect()
        res = db_query(db, "select o.code, s.state, "
                           "substr(o.order_id, 1, 8) as service, "
                           "if(substr(o.order_id, 1, 8)='INTERNET', "
                                  "if(o.direction is null, t.button_name, tt.button_ru), "
                                  "if(o.new_model=1,v.name,f.name)) as tariff_ru, "
                           "if(substr(o.order_id, 1, 8)='INTERNET', "
                                  "if(o.direction is null, t.button_name_en, tt.button_en), "
                                  "if(o.new_model=1,v.name,f.name)) as tariff_en, "
                           "time(if(o.begin_time is not null, now() - o.begin_time, '00:00:00')) as elapsed, "
                           "if(o.dev_count > 1, 0, 2-o.dev_count) as devices "
                           "from orders o "
                           "left outer join tariffs t on t.id = o.tariff_id "
                           "left outer join tariffs.tariffs_description tt on tt.tariff_id = o.tariff_id "
                           "left join clients c on c.id = o.client_id "
                           "left join states s on s.id = o.state_id "
                           "left outer join films f on f.id = o.client_films_id "
                           "left outer join vidimax v on v.id = o.client_films_id "
                           "where o.payment_time is not null and o.code <> '' and o.end_time is null and o.state_id <> 3 " # hardcode
                           "and o.dev_count < 2 and o.direction='%s' and c.phone='%s' and o.first_mac=x'%s'"%(direction, phone, mac),
                           full=True)
        count = 0
        for code, state, service, tariff_name_ru, tariff_name_en, elapsed, dev_remained in res:
            code_info = {
                'Code': code,
                'Status': state,
                'Service': service,
                'TariffName_RU': unicode(tariff_name_ru),
                'TariffName_EN': unicode(tariff_name_en),
                'DevicesRemained': dev_remained
            }
            if elapsed:
                code_info['Elapsed'] = str(elapsed)
            result[str(count)] = code_info
            count += 1
    except Exception as e:
        print e
    return result

def get_code_by_billnumber(direction, ip, order, billnumber):
    result = {}
    res = None
    try:
        mac = get_mac(ip).replace(':','')
        if mac == '0'*12:
            raise ValueError('No MAC address for %s'%(ip))
        db = db_connect()
        res = db_query(db, "select o.code from orders o "
                                             "where o.payment_time is not null and o.code <> '' and o.end_time is null and o.state_id <> 3 " # hardcode
                                             "and o.dev_count < 2 and o.direction='%s' and o.billnumber='%s' and o.first_mac=x'%s' and o.order_id='%s'"
                                             %(direction, billnumber, mac, order),
                                    )
    except Exception as e:
        print e
    if not res:
        r = False
        code = None
    else:
        r = True
        code = res[0]
    result = {
        'Code': code,
        'Result': r
    }
    return result

####################################################################################################################################################
def get_first_data(service, tariff, film_id=None, payment_system=None, new_model=False, direction=None, ip=None, partner=None):
    def get_partner_id(db, partner):
        result = None
        res = db_query(db, 'select id from partners where name="%s"'%partner)
        if res:
            result = res[0]
        return result
    def create_order(db, shop, tariff, film, direction=None, ip=None, partner_id=None):
        mac = get_mac(ip).replace(':','') or '000000000000'
        print mac
        if not film:
            oid = db_query(db, "insert into orders (shop_id, tariff_id, first_mac, first_ip) values ( %s, %s , x'%s', '%s');"%(shop, tariff, mac, ip), fetch=False, commit=True, lastrow=True)
        else:
            query = "insert into orders (shop_id, tariff_id, client_films_id, first_mac, first_ip) values (%s, %s, %s, x'%s', '%s');"
            if new_model:
                query = "insert into orders (shop_id, tariff_id, client_films_id, new_model, first_mac, first_ip) values (%s, %s, %s, 1, x'%s', '%s');" # hardcode
            oid = db_query(db, query%(shop, tariff, film, mac, ip), fetch=False, commit=True, lastrow=True)
            if new_model:
                update_order_id(db, film, oid)
        if direction:
            print 'adding direction "%s" to order %s'%(direction, oid)
            db_query(db, 'update orders set direction="%s" where id=%s;'%(direction, oid), fetch=False, commit=True)
        if partner_id:
            print 'adding partner id = %d to order %s'%(partner_id, oid)
            db_query(db, 'update orders set partner_id=%d where id=%s;'%(partner_id, oid), fetch=False, commit=True)
        return oid
    db = db_connect()
    tariff_id, tariff_sum = get_tariff(db, service, tariff, film_id, new_model)
    shop = get_shop(payment_system)
    shop_id = get_shop_id(db, payment_system)
    if partner:
        partner_id = get_partner_id(db, partner)
    if not (tariff_id and tariff_sum and shop_id):
        return None
    order_num = create_order(db, shop_id, tariff_id, film_id, direction, ip, partner_id)
    if not order_num:
        return None
    order_id = '%s%020d'%(service.upper(), order_num)
    db_query(db, 'update orders set order_id="%s" where id=%d'%(order_id, order_num), fetch=False, commit=True)
    if not film_id:
        if not direction:
            [ desc, desc_en ] = db_query(db, 'select t.button_name, t.button_name_en from orders o left join tariffs t on t.id = o.tariff_id where o.id = %d;'
                                                                        %(order_num)
                                                                    )
        else:
            [ desc, desc_en ] = tariffs.get_descriptions(tariff_id)
    else: # is film
        if new_model:
            price = get_price(db, film_id)
            desc = '%s руб / 24 часа'%(price)             # hardcode
            desc_en = '%s rub / 24 hours'%(price)
        else:
            [ price ] = db_query(db, 'select price from films where id = %s;'%(film_id))
            desc = '%s руб / 24 часа'%(price)
            desc_en = '%s rub / 24 hours'%(price)
    db_disconnect(db)
    result = {
        'ShopID' : shop,
        'OrderID' : order_id,
        'Sum' : tariff_sum,
        'Description' : desc,
        'Description_EN' : desc_en
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
        print "checking"
        res = db_query(db, 'select o.id from orders o cross join '
                                             '(select client_orders_id from client_info where mac = "%s" and ip = "%s" order by update_time desc) s on s.client_orders_id = o.id '
                                             'where client_films_id=%s and begin_time is not null and end_time is null limit 1;'
                                             %(mac, request_json['IPAddress'], request_json['FilmID'])
                                     )
        if res:
            result['Result'] = True
    except Exception as e:
        print e
        pass
    db_disconnect(db)
    return result

def get_user_subscriptions(ip, ua):
    def get_subs_list(db, client_id):
        subs = []
        res = db_query(db, 'select order_id, client_films_id, first_ip, direction \
                                                from orders where client_id=%s and new_model=1 and state_id=0;'%(client_id), full=True)
        if res:
            for [ order_id, film_id, first_ip, direction ] in res:
                subs_info = get_subs_info(db, film_id, (first_ip, direction))
                if subs_info not in subs:
                    subs.append(subs_info)
        return subs
        
    pprint('get_user_subscriptions:')
    pprint(ip)
    pprint(ua)
    result = {}
    mac = get_mac(ip)
    db = db_connect()
    vip_client = is_vip_client(db, ip, mac)
    if vip_client:
        return { "VIP" : True } 
    client_ids = db_query(db, 'select client_id as id from client_info where ip="%s" and mac="%s" group by client_id'%(ip, mac), full=True)
    if client_ids:
        print 'client found', client_ids
        result['UserID'] = client_ids[0][0] # in every way
        result['Subscriptions'] = []
        if len(client_ids) > 1:
            print "fucking fuck! this should not have happened but happened"
        for client in client_ids:
            result['Subscriptions'] += get_subs_list(db, client)
    db_disconnect(db)
    pprint(result)
    return result

def get_session(request_json, update=False):
    pprint('get_session')
    pprint(request_json)
    is_film = False
    if 'FilmID' in request_json:
        is_film = True
    result = {
        'Result' : False,
        'IPAddress' : '',
        'UserAgent' : '',
        'Logout' : 0
    }
    if is_film:
        result['URL'] = settings.vidimax_base + '/#movie/' + request_json['FilmID']
        if int(request_json['FilmID']) == 694: # hardcode
            result['URL'] = settings.vidimax_base
        print result['URL']
    db = db_connect()
    mac = get_mac(request_json['IPAddress'])
    vip_client = is_vip_client(db, request_json['IPAddress'], mac)
    if vip_client: # vip client
        print "is vip client"
        if is_film:
            result['URL'] = settings.vidimax_base + '/#movie/' + request_json['FilmID']
            if int(request_json['FilmID']) == 694: # hardcode
                result['URL'] = settings.vidimax_base
#            result['URL'] = settings.vidimax_base + '/#play/' + request_json['FilmID']
            result['Result'] = True
            return result
    if 'Code' in request_json:
        if is_vip_code(db, request_json['Code']):
            print "is vip code"
            if not vip_client:
                add_vip_client(db, request_json['Code'], request_json['IPAddress'], mac)
            auth_client(request_json['IPAddress'], mac)
            result['Result'] = True
            return result
        else:
            tar = is_scratch_code(db, request_json['Code'])
            if tar and not is_film: # i don't accept scratch card payment for films for a while
                fd = get_first_data(tar['service'], tar['tariff'], None, 'SCRATCH')
                order_id = get_order_id(fd['OrderID'])
                sms_sent(order_id)
                update_order(generate_scratch_payment(fd['ShopID'], fd['OrderID'], fd['Sum'], request_json['Code']))
                scratch_set_used(db, request_json['Code'])
    if is_film and not update:
        return get_film_session(request_json)
    try:
        pprint('client_info = get_client_info:')
        client_info = get_client_info(db, request_json)
        pprint(client_info)
        if client_info:
            result = {
                'Result' : True,
                'IPAddress' : client_info['ip'],
                'UserAgent' : client_info['user_agent'],
                'Logout' : client_info['state']
            }
            if is_film:
                if 'external_order_id' in client_info: # not vidimax
                    result['URL'] = client_info.get('url', settings.vidimax_base)
                else:
                    result['URL'] = settings.vidimax_base + '/#movie/' + request_json['FilmID']
                    if int(request_json['FilmID']) == 694: # hardcode
                        result['URL'] = settings.vidimax_base
                print result['URL']
            else:
                auth_client(client_info['ip'], client_info['mac'])
            if client_info['changed']:
                print 'if update:'
                if update and update_client_info(db, client_info, False):
                        auth_client(client_info['ip'], mac)
                else:
                    result['Result'] = False
    except KeyError as e:
        print 'KeyError: ' + str(e)
        result = None
    db_disconnect(db)
    return result

#####
def parse_xml(xml):
    print 'parse_xml:'
    try:
        xml = json.loads(xml2json.xml2json(io.StringIO(xml)).get_json())
    except:
        return None
    result = None
    if 'unitellerresult' in xml:                                # Uniteller
        uni_result=xml['unitellerresult']
        pprint(uni_result)
        order = uni_result['orders']['order']
        dt = datetime.datetime.strptime(order['date'], '%d.%m.%Y %H:%M:%S')
        order['date'] = dt.strftime('%Y-%m-%d %H:%M:%S')
        result = {
            'type' : 'uniteller',
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
    elif 'request' in xml:                                     # Platron
        platron_res=xml['request']
        pprint(platron_res)
        result = {
            'type' : 'platron',
            'shop_id' : '00006866',
            'order_id' : platron_res['pg_order_id'],
            'sum' : platron_res['pg_amount'],
            'date' : platron_res['pg_payment_date'],
            'phone' : platron_res['pg_user_phone'],
            'uni_billnumber' : platron_res['pg_payment_id'],
            'status' : platron_res['pg_result'],
            'can_reject' : platron_res['pg_can_reject'],
            'approval_code' : '',
	    'salt' : platron_res['pg_salt'],
	    'sig' : platron_res['pg_sig'],
        }
    else:
        return None
    if not match_code(result['approval_code']):
        result['approval_code'] = get_code(result['order_id'])
#        if not result['approval_code']:
#            if result['type'] == 'platron' and result['status'] == 1:
#            result['approval_code'] = new_code()
    return result

#####
def parse_refund_xml(xml):
    print 'parse_xml:'
    try:
        xml = json.loads(xml2json.xml2json(io.StringIO(xml)).get_json())
    except:
        return None
    result = None
    if 'request' in xml:                                     # Platron
        platron_res=xml['request']
        pprint(platron_res)
        result = {
            'type' : 'platron',
            'shop_id' : '00006866',
            'order_id' : platron_res['pg_order_id'],
            'sum' : platron_res['pg_amount'],
            'date' : platron_res['pg_refund_date'],
            'refund_id' : platron_res['pg_refund_id'],
	    'salt' : platron_res['pg_salt'],
	    'sig' : platron_res['pg_sig'],
        }
    else:
        return None
    return result

def add_film_watch(request_json):
    result = False
    pprint(request_json)
    db = db_connect()
    ip = request_json['IPAddress']
    mac = get_mac(ip)
    film_id = request_json['FilmID']
    name = request_json['Name']
    user_id = request_json.get('UserID', '0')
    user_agent = request_json.get('UserAgent', '')
    db_query(db, 'insert into watches (ip, mac, film_id, name, ua, user_id) values ("%s", "%s", %s, "%s", "%s", %s);'
                                        %(ip, mac, film_id, name, user_agent, user_id),
                                        commit=True, fetch=False
                    )
    result = True
    db_disconnect(db)
    return { "Result" : result }

def save_taxi_order(data):
    print 'save_taxi_order:'
    print data
    db = db_connect()
    query = '''insert into taxi values (
            0, now(), "%(direction)s", "%(ip)s", "%(mac)s", "%(vgt_name)s", "%(vgt_phone)s", "%(vgt_email)s",
            "%(train)s", "%(vgt_from)s", "%(vgt_dest)s", "%(vgt_ctype)s", %(vgt_cprice)s, "%(vgt_data)s",
            "%(vgt_add)s", "%(vgt_add2)s", "%(vgt_tab)s", "%(vgt_comment)s", %(accept_offer)s
            );'''%data
    print query
    db_query(db, query, commit=True, fetch=False)
    db_disconnect(db)
    pass

def get_time(string):
    if type(string) not in ( str, unicode ):
        return None
    datefmt = '%Y-%m-%d %H:%M:%S'
    tm = string.upper().replace('T', ' ')
    result = None
    try:
        result = datetime.datetime.strptime(tm, datefmt).strftime(datefmt)
    except:
        print 'Incorrect detetime string: "%s"'%string
    return result

def get_trains_list(after=None):
    db = db_connect()
    result = { 'Trains' : [] }
    datefmt = '%Y-%m-%d %H:%M:%S'
    query = 'select number, start, end, inactive, added, updated from trains'
    if get_time(after):
        query += ' where updated >= "%s"'%after
    res = db_query(db, query, full=True)
    db_disconnect(db)
    for number, start, end, inactive, added, updated in res:
        el = {
            'TrainNumber' : number,
            'StartStation' : start,
            'EndStation' : end,
            'State' : inactive,
            'Added' : added.strftime(datefmt),
            'Updated' : updated.strftime(datefmt)
        }
        result['Trains'].append(el)
    return result

def get_stats(begin, end):
    db = db_connect()
    now = datetime.datetime.now()
    datefmt = '%Y-%m-%d %H:%M:%S'

    begin_str = get_time(begin) or now.strftime('%Y-%m-%d 00:00:00') # hardcode
    end_str = get_time(end) or now.strftime(datefmt)

    query = 'select order_id, phone, code, price, price*0.10, payment_time, refund_time \
            from orders o left join clients c on o.client_id=c.id \
            left join tariffs.tariffs_tariff t on o.tariff_id=t.id \
            where partner_id=1 and payment_time between "%s" and "%s"'%(begin_str, end_str) # hardcode

    res = db_query(db, query, full=True)

    db_disconnect(db)
    result = {
        'Statistics' : []
    }
    if res:
        for (oid, phone, code, price, fee, p_time, r_time) in res:
            tmp = {
                'orderId' : oid,
                'phone' : phone,
                'code' : code,
                'price' : int(price),
                'fee' : float(fee),
                'paymentTime' : p_time.strftime(datefmt)
            }
            result['Statistics'].append(tmp)
            if r_time:
                result['Statistics']['refundTime'] = r_time.strftime(datefmt)
    return result

def get_train_direction(train):
    db = db_connect()
    query = 'select abbr from trains where number="%s"'%train
    res = db_query(db, query)
    db_disconnect(db)
    result = {}
    if res:
        result['Direction'] = res[0]
    return result
