# --- coding: utf-8 ---

import re

phone_re = re.compile(r'^\+?\d{8,15}$')
code_re = re.compile(r'^\w{6,7}$')
ip_re = re.compile(r'^(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')
mac_re = re.compile(r'^[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}$')

def get_phone(string):
  res = re.sub(r'[\(\)\s-]', r'', string)
  if not string or not phone_re.match(res):
    res = '0000000000'
  return res

def match_code(string):
  res = False
  if string and code_re.match(string):
    res = True
  return res

def check_ip(string):
  res = False
  if string and ip_re.match(string):
    res = True
  return res

def check_mac(string):
  res = False
  if string and mac_re.match(string):
    res = True
  return res
