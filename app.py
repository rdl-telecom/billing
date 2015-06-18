#!bin/python
# -*- coding: utf-8 -*-
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

from flask import Flask, Response, jsonify, request, redirect, url_for
import json
from billing import json_response, user_ok, get_first_data, parse_xml, url2json, update_order, get_session, get_tariffs, get_shopid_by_orderid, get_film_price, get_filmid_by_orderid
from werkzeug.contrib.fixers import LighttpdCGIRootFix, HeaderRewriterFix
from icomera_auth import auth_client
from vidimax import check_sign, add_film_info

from pprint import pprint
import logging
from settings import logs_dir, default_shop

app = Flask(__name__)
app.wsgi_app = LighttpdCGIRootFix(app.wsgi_app)
app.wsgi_app = HeaderRewriterFix(app.wsgi_app, remove_headers=['Date'], add_headers=[('X-Powered-By', 'WSGI'), ('Server', 'Noname Server')]) 

#logging.basicConfig(level=logging.DEBUG,
#                    format='%(asctime)s %(name)-20s %(levelname)-8s %(message)s',
#					datefmt='%Y-%m-%d %H:%M:%S',
#                    filename=logs_dir+'/app.log',
#                    filemode='aw')
#logger = logging.getLogger('billing.app')

#log_handler = logging.FileHandler(logs_dir + '/app.debug.log')
#app.logger.addHandler(log_handler)
#app.logger.setLevel(logging.DEBUG)

#####   /ShopID   #####
@app.route('/ShopID', methods = [ 'GET' ])
def api_shopid():
  r_json = url2json(request.url)
  if not user_ok(r_json):
    return json_response({},status=401)
  try:
    data = get_shopid_by_orderid(r_json['OrderID'])
  except Exception as e:
    print e
    return json_response({}, status=400)
  resp_status = 200
  if data == {}:
    resp_status = 400
  return json_response(data, status=resp_status)

#####  /GetTariffs  #####
@app.route('/GetTariffs', methods = [ 'GET' ])
def api_gettariffs():
  r_json = url2json(request.url)
  if not user_ok(r_json):
    return json_response({},status=401)
  try:
    if 'Service' in r_json:
      data = get_tariffs(r_json['Service'])
    elif 'FilmID' in r_json:
      data = get_film_price(r_json['FilmID'])
    else:
      raise Exception
  except:
    return json_response({}, status=400)
  resp_status = 200
  if data == {}:
    resp_status = 400
  return json_response(data, status=resp_status)
#####################

#####  /OrderID  #####
@app.route('/OrderID', methods = [ 'GET' ])
def api_old_orderid():
  r_json = url2json(request.url)
  if not user_ok(r_json):
    return json_response({},status=401)
  try:
    code_of_service = r_json['CodeOfService']
    tariff = r_json['Tariff']
    film_id = None
    if 'FilmID' in r_json:
      film_id = r_json['FilmID']
    payment_system = default_shop
    if 'Shop' in r_json:
      payment_system = r_json['Shop'].upper()
  except:
    return json_response({}, status=400)
  data = get_first_data(code_of_service, tariff, film_id, payment_system)
  status = 200
  if data == None:
    status = 400
  return json_response(data, status)
######################

#####  /GenerateOrder  #####
@app.route('/GenerateOrder', methods = [ 'get' ])
def api_orderid():
  r_json = url2json(request.url)
  if not user_ok(r_json):
    return json_response({'error':'Login required'},status=401)
  for param in [ 'id', 'type', 'name', 'price', 'ts', 'sign' ]:
    if param not in r_json:
      return json_response({'error':'Incorrect parameters'}, status=400)
  if not check_sign(r_json):
    return json_response({'error':'Wrong sign'}, status=400)
  film_id = add_film_info(r_json)
  if not film_id:
    return json_response({'error':'Already present'}, status=400)
  payment_system = default_shop
  if 'Shop' in r_json:
    payment_system = r_json['Shop'].upper()
  data = get_first_data('VIDEOSVC', 'FILM', film_id, payment_system, new_model=True)
  status = 200
  if data == None:
    status = 400
    data = {'error':'Add order error'}
  return json_response(data, status)

########################
#####  /FullXML  #####
@app.route('/FullXML', methods = [ 'POST' ])
def api_fullxml():
  result = False
  if request.headers['Content-Type'] != 'application/json':
    return json_response({}, status=400)
  r_json = request.get_json()
  if not user_ok(r_json):
    return json_response({},status=401)
  payment = parse_xml(r_json['XML'])
#  f = open('/tmp/log.txt','w')
#  f.write(payment)
#  f.close()
  data = {}
  if payment:
    if payment['type'] == 'uniteller':
      if (payment['status'].upper() == 'AUTHORIZED' or payment['status'].upper() == 'PAID') and update_order(payment):
        result = True
    elif payment['type'] == 'platron':
      data['Signature'] = payment['sig']
      data['Salt'] = payment['salt']
      if payment['status'] == '1' and update_order(payment):
        result = True
  data['Result'] = result
  return json_response(data)
######################

#####   /Auth   #####
@app.route('/Auth', methods = [ 'GET', 'POST' ])
def api_auth():
  if request.method == 'GET':
    r_json = url2json(request.url)
  else:
    r_json = request.get_json()
#   pprint(r_json)
  if not user_ok(r_json):
    return json_response({},status=401)
  if request.method == 'GET':
  # GET method
#     print 'GET'
    res = get_session(r_json)
    if not res:
      return json_response({} , status=400)
    return json_response(res, status=200)
  else:
  # POST method
#     print 'POST'
    res = get_session(r_json, update=True)
    if not res:
      return json_response({} , status=400)
    return json_response(res, status=200)
######################

#####   /Allow   #####
@app.route('/Allow', methods = [ 'GET' ])
def api_allow():
  r_json = url2json(request.url)
  if not ('IP' in r_json):
    return json_response({}, status=400)
  if not user_ok(r_json):
    return json_response({},status=401)
  mac = '00:00:00:00:00:00'
  if 'MAC' in r_json:
    mac = r_json['MAC']
  res = auth_client(r_json['IP'], mac)
  result = {
    'Result' : res
  }
  return json_response(result, status=200)
######################

#####  /GetFilmID  #####
@app.route('/GetFilmID', methods = [ 'GET' ])
def api_get_film_id():
  r_json = url2json(request.url)
  if not ('OrderID' in r_json):
    return json_response({}, status=400)
  if not user_ok(r_json):
    return json_response({},status=401)
  result = get_filmid_by_orderid(r_json['OrderID'])
  return json_response(result, status=200)

#####  APPLICATION  #####
if __name__ == '__main__':
#  app.logger.debug('app started in standalone mode')
#  app.run(host='0.0.0.0', debug=True)
#  app.run(debug=True,host='0.0.0.0',port=2910)
  app.run(debug=True,host='0.0.0.0',port=8000)
#  app.run(debug=True, port=8000)
#  app.run()
