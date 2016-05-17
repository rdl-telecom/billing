import requests

from settings import JASMIN_URL, JASMIN_USER, JASMIN_PASS, phone_number, sms_text

def send_sms(phone, code):
    ph = phone
    if phone[0] == '+':
        ph = phone[1:]
    data = {
        'username': JASMIN_USER,
        'password': JASMIN_PASS,
        'from': phone_number,
        'to': ph,
        'content': sms_text%code
    }
    requests.post(JASMIN_URL, data=data)
