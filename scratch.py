#!/usr/bin/env python2

# import os
import time
import random
import hashlib
import binascii
import string
import array

def get_symbol(byte):
  symbols = '0123456789DFGJLNQSUVWZ'
  return symbols[byte % len(symbols)]

my_secret = 'WNpE1G982ylxlbdx3HoAiAigeigaRvkwruCgzZulUDxIbxKDEDkZtIWQlKNKzhm5wZYHdcDSf8awP5Hxa7crF1S929nYyxJ5joed23m9mTPiiuSNR13sz5hHgsoVZbL8'

def gen_code():
  t1 = time.time()
  time.sleep(random.random())
  randstr = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(128))
  t2 = time.time()
  code = ''
  counter = 0
  for byte in bytes(hashlib.md5(my_secret + str(t1) + randstr + str(t2)).digest()):
    if len(code) == 7:
      break
    if counter % 2:
      code += get_symbol(ord(byte)+ord(prev))
    counter += 1
    prev = byte
  return code

if __name__ == '__main__':
  print gen_code()
