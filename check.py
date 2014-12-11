# --- coding: utf-8 ---

import re

phone_re = re.compile(r'^\+?\d{8,15}$')
code_re = re.compile(r'^\w{6}$')

def get_phone(string):
  res = re.sub(r'[\(\)\s-]', r'', string)
  if not phone_re.match(res):
    res = 'INVALID'
  return res

def match_code(string):
  res = False
  if code_re.match(string):
    res = True
  return res
