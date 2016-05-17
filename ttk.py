import requests

from service.sms import send_sms
from check import check_mac, match_code, get_phone
from settings import MAC_URLS, ADD_USER_URL, CHECK_CODE_URL, testing, sms_send_settings


def find_mac(mac):
    result = False
    if check_mac(mac):
        for url in MAC_URLS:
            r = requests.get(url%mac)
            if r.json()['status'] == 'active':
                result = True
                break
    return result

def add_user_device(phone, mac):
    result = False
    ph = get_phone(phone)
    if check_mac(mac) and ph:
        r = requests.get(ADD_USER_URL%(ph, mac))
        code = r.json()['code']
        if not testing and code != '----':
            send_sms(phone, code)
        result = r.json()['result']
    return result

def check_user_code(mac, code):
    result = False
    if check_mac(mac):
        print 'check_user_code:', CHECK_CODE_URL%(mac, code)
        r = requests.get(CHECK_CODE_URL%(mac, code))
        result = r.json()['result']
    return result
