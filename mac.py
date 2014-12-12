# --- coding: utf-8 ---

import sqlite3
from ipaddress import ip_address, ip_network
from settings import snmp_user, snmp_password
from pprint import pprint
from pysnmp.entity.rfc3413.oneliner import cmdgen, mibvar
from pysnmp.proto.rfc1902 import OctetString

from pprint import pprint

class Mac(OctetString):
  def prettyPrint(self):
    res = ''
    arr = bytearray(self._value)
    for i in range(len(arr)):
      res += '%02X'%arr[i]
      if i != 5: res += ':'
    return res

db_path = '/opt/modgud/3.0.0/etc/modgud/configuration.sqlite3'
db_query = 'select network, ip from bundles left join ranges on bundles.id=ranges.bundle_id where ranges.id >= 10000;'
snmp_oid_prefix = [ '1.3.6.1.2.1.3.1.1.2.13.1.', '1.3.6.1.2.1.3.1.1.2.12.1.' ]
snmp_command = '/usr/bin/snmpget'

def get_gateway(ip):
  print 'get_gateway:'
  print ip
  if not ip:
    return None
  address = ip_address(ip.decode('latin-1'))
  query = db_query
  con = sqlite3.connect(db_path)
  cur = con.cursor()
  cur.execute(query)
  res = cur.fetchall()
  con.close()
  gateway = None
  for net, gw in res:
    if address in ip_network(net).hosts():
      gateway = gw
      break
  return gateway

def snmp_get_mac(gw, ip):
  print 'snmp_get_mac:'
  print gw + ' -- ' + ip
  mac = None
  for prefix in snmp_oid_prefix:
    pprint( (prefix + ip).encode('latin-1'))
    try:
      errorIndication, errorStatus, errorIndex, varBind = cmdgen.CommandGenerator().getCmd(
                cmdgen.UsmUserData(snmp_user, snmp_password,
                                   authProtocol=cmdgen.usmHMACMD5AuthProtocol,
                                   privProtocol=cmdgen.usmDESPrivProtocol
                                  ),
                cmdgen.UdpTransportTarget((gw, 161)),
                mibvar.MibVariable((prefix + ip).encode('latin-1'))
      )
      if not (errorIndication or errorStatus):
        (var, val) = varBind[0]
        mac = Mac(val).prettyPrint()
      if mac:
        break
    except Exception as e:
      print 'snmp exception '
      print e
      pass
  return mac

def get_mac(ip):
  mac = '00:00:00:00:00:00'
  gw = get_gateway(ip)
  if gw:
    m = snmp_get_mac(gw, ip)
    if m:
      mac = m
  return mac
