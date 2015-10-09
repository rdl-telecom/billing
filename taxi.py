#coding: utf-8
import requests
from settings import taxi_url, taxi_pid
from billing import save_taxi_order
from mac import get_mac
import datetime
from mysql.connector.conversion import MySQLConverter

datetime_format = '%Y-%m-%d %H:%M:%S'

send_format = {
    'vgt_pid' : 'integer',
    'vgt_cprice' : 'integer',
    'vgt_phone' : 'phone',
    'vgt_data' : 'datetime',
    'vgt_comment' : 'bigtext',
    'default' : 'string'
}

def get_phone(string):
    phone = '+%s'%''.join(x for x in list(string) if x.isdigit())
    if 7 < len(phone) < 16:
        return phone
    return None

def format_value(fmt, value):
    result = None
    if fmt == 'integer':
        try:
            result = int(value)
        except:
            result = 0
    elif fmt == 'phone':
        result = get_phone(value)
    elif fmt == 'datetime':
        try:
            result = datetime.datetime.strptime(value, datetime_format).strftime(datetime_format)
        except:
            result = ''
    else:
        try:
            result = ''
            if value:
                conv = MySQLConverter()
                result = conv.escape(value.encode('utf-8')).decode('utf-8')
                if fmt == 'string':
                    result = result[:256]
                elif fmt == 'text':
                    result = result[:65536]
        except Exception as e:
            print 'format_value: value = "%s", format = %s. error: %s'%(value, fmt, e)
            result = ''
    return result

def format_send_data(data):
    for key, value in data.iteritems():
        fmt = send_format.get(key, send_format['default'])
        data[key] = format_value(fmt, value)

def test_phone(r_json):
    result = True
    if 'Phone' not in r_json or not get_phone(r_json['Phone']):
        result = False
    return result

def fill_send_data(r_json):
    result = {
        'vgt_pid' : taxi_pid,
        'vgt_phone' : r_json['Phone'],
        'vgt_from' : r_json.get('Source', None),
        'vgt_dest' : r_json.get('Destination', None),
        'vgt_cprice' : r_json.get('Price', None),
        'vgt_ctype' : r_json.get('Type', None),
        'vgt_data' : r_json.get('Date', None),
        'vgt_add' : r_json.get('AddressFrom', r_json.get('TrainNumber', None)),
        'vgt_add2' : r_json.get('AddressTo', None),
        'vgt_name' : r_json.get('Name', None),
        'vgt_email' : r_json.get('Email', None),
        'vgt_tab' : r_json.get('TableText', None),
        'vgt_comment' : r_json.get('Comment', None)
    }
    return result

def send_data(send_data):
    try:
        result = requests.post(taxi_url, data=send_data)
        if result.text != 'OK':
            raise Exception('error returned: %s'%result.text)
    except Exception as e:
        print 'send_data: exception: %s'%str(e)
        return False
    return True

def process_taxi_order(r_json):
    result = False
    try:
        print r_json
        if test_phone(r_json):
            client_info = {
                'ip' : r_json['IPAddress'],
                'mac' : get_mac(r_json['IPAddress']),
                'direction' : r_json['Direction'],
                'train' : r_json.get('TrainNumber', None)
            }
            data = fill_send_data(r_json)
            format_send_data(data)
            client_info.update(data)
            save_taxi_order(client_info)
            print data
            if send_data(data):
                result = True
    except Exception as e:
        print 'process_taxi_order: exception: %s'%e
    return result
