#!/usr/bin/env python2
# coding: utf-8

import paramiko
from mac import get_gateway
from settings import ssh_username, ssh_password

port = 22

def auth_client(gw, ip, mac):
	gw = get_gateway(ip)
	client_ip = ip
	if not gw:
		gw = ip
		client_ip = None
	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
	ssh.connect(hostname=gw, username=ssh_username, password=ssh_password, port=port)
	client.exec_command('hotcli allow %s')
	ssh.close()
	return True