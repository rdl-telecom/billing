#!bin/python
#coding: utf-8

from db import *
import datetime
import json
import requests
from settings import report_url, report_username, report_password
import sys

date_fmt = '%Y-%m-%d %H:%M:%S'

ids = '(74430,75894,76055,76577,77028,77526,77944,78005,79203,79515,79693,80909,81625,82089,82358,82442,82534,83903,84237,84251,84432,84536,84925,85901,86229,86260,87585,87595,87877,88225)'

def get_payments(db, tfrom, tto):
    query = '''select o.id, o.order_id, o.client_id, v.price*100, v.type, v.film_id, v.name, 
unix_timestamp(o.begin_time), unix_timestamp(o.end_time), unix_timestamp(o.payment_time)
from orders o left join vidimax v on v.id=o.client_films_id
where o.new_model = 1 and billnumber > 0 and refund_time is null
and payment_time >= '%s' and payment_time < '%s';'''%(tfrom.strftime(date_fmt), tto.strftime(date_fmt))
    res = db_query(db, query, full=True)
    return res
    
def get_watches(db, order_id, ptype):
    result = []
    if ptype == 'svod':
        query = '''select w.film_id, w.name, unix_timestamp(w.watch_time) from orders
o left join client_info ci on o.client_id = ci.client_id and o.id = ci.client_orders_id
left join watches w on ci.ip = w.ip and ci.mac = w.mac and ci.user_agent = w.ua
where w.film_id is not null and o.id = %s and w.watch_time between o.begin_time and o.end_time;'''%order_id
    else:
        query = '''select w.film_id, w.name, unix_timestamp(w.watch_time) from orders
o left join client_info ci on o.client_id = ci.client_id and o.id = ci.client_orders_id
left join watches w on ci.ip = w.ip and ci.mac = w.mac and ci.user_agent = w.ua
left join vidimax v on v.id = o.client_films_id and v.film_id = w.film_id
where w.film_id is not null and v.film_id is not null
and o.id = %s and w.watch_time between o.begin_time and o.end_time;'''%order_id

    res = db_query(db, query, full=True)
    if res:
        for fid, name, ts in res:
            watch = {
                "id": fid,
                "name": name,
                "watchDate": ts
            }
            result.append(watch)
    return result

def generate_report(time_from, time_to):
    result = []
    print time_from, '--', time_to
    db = db_connect()
    for oid, order, client, price, ptype, film_id, name, start, end, payment in get_payments(db, time_from, time_to):
        tariff_id = 0
        if ptype == 'svod':
            tariff_id = film_id
        payment = {
            "operationId": order,
            "userId": client,
            "price": price,
            "type": ptype,
            "tariffId": tariff_id, 
            "paymentDate" : payment,
            "startDate": start,
            "stopDate": end,
            "watches": get_watches(db, oid, ptype)
        }
        if ptype == 'tvod':
            payment['contentId'] = film_id
        result.append(payment)
    db_disconnect(db)
    print time_from, '--', time_to
    return result



if __name__ == '__main__':
    if len(sys.argv) < 2:
        print """
Usage:
    %s YYYY-MM-DD
        YYYY-MM-DD - report day
"""%sys.argv[0]
        sys.exit(0)

    report_date = sys.argv[1]
    f = datetime.datetime.strptime('%s01 00:00:00'%report_date[:-2], date_fmt)
    t = datetime.datetime.strptime('%s 00:00:00'%report_date, date_fmt)
    if f.day == 1:
        if f.month == 1:
            f = f.replace(month=12)
        else:
            f = f.replace(month=f.month-1)
    r = generate_report(f, t)

    headers = {'content-type': 'application/json', 'encoding' : 'utf-8'}
    payload = json.dumps(r, ensure_ascii=False, sort_keys=True).encode('utf-8')
    text = json.dumps(r, ensure_ascii=False, indent=4, sort_keys=True)
    import io
    with io.open('/var/log/lighttpd/vidimax_report_%s.json'%report_date, 'w', encoding='utf8') as json_file:
        json_file.write(unicode(text))
    print text
    
    response = requests.post(report_url, auth=(report_username, report_password), data=payload, headers=headers)

    if response.status_code == 200:
        print response.json()['resultCode'], response.json()['resultMessage']
    else:
        print response.status_code
        print response.text
