#!/usr/bin/env python2
# coding: utf-8

import paramiko
from mac import get_gateway, get_mac
from settings import ssh_username, ssh_password

port = 22

def auth_client(ip, mmac):
	gw = get_gateway(ip)
	mac = mmac
	if mmac == '00:00:00:00:00:00':
		mac = get_mac(ip)
	if not gw or mac == '00:00:00:00:00:00':
		return False
	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
	try:
		ssh.connect(hostname=gw, username=ssh_username, password=ssh_password, port=port, timeout=5)
	except:
		return False
	ssh.exec_command('hotcli add %s %s'%(ip, mac))
	ssh.exec_command('hotcli allow %s'%(ip))
	ssh.close()
	return True
