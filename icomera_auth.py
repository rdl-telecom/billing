#!/usr/bin/env python2
# coding: utf-8

import paramiko
from mac import get_gateway, get_mac
from settings import ssh_username, ssh_password, logs_dir
import logging

port = 22

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-20s %(levelname)-8s %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',
                    filename=logs_dir+'/auth.log',
                    filemode='aw')
logger = logging.getLogger('billing.auth')

def auth_client(ip, mmac):
    logger.debug('Entered auth_client; IP = %s, MAC = %s'%(ip, mmac))
    gw = get_gateway(ip)
    if not gw:
        logger.info('Cannot find gateway ( IP = %s )'%(ip))
        logger.debug('Returning "False"')
        return False
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        logger.debug('Connecting to %s'%(gw))
        ssh.connect(hostname=gw, username=ssh_username, password=ssh_password, port=port, timeout=7)
    except:
        logger.info('Unable to connect to host %s'%(gw));
        logger.debug('Returning "False"')
        return False
    mac = mmac
    if mmac == '00:00:00:00:00:00':
        ssh.exec_command('ping -c 1 %s'%(ip))
        mac = get_mac(ip)
        logger.debug('Tried to find mac fo %s: MAC = %s'%(ip, mac))
    if mac == '00:00:00:00:00:00':
        logger.info('Cannot find MAC ( IP = %s; MAC = %s; Gateway = %s )'%(ip, mac, gw))
    ssh.exec_command('hotcli add %s %s'%(ip, mac))
    ssh.exec_command('hotcli allow %s'%(ip))
    ssh.close()
    logger.info('User %s ( %s ) authenticated on %s'%(ip, mac, gw))
    logger.debug('Returning "True"')
    return True

def deny_client(ip):
    logger.debug('Trying to deny user %s'%ip)
    gw = get_gateway(ip)
    if not gw:
        logger.info('Cannot find gateway ( IP = %s )'%(ip))
        logger.debug('Returning "False"')
        return False
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        logger.debug('Connecting to %s'%(gw))
        ssh.connect(hostname=gw, username=ssh_username, password=ssh_password, port=port, timeout=7)
    except:
        logger.info('Unable to connect to host %s'%(gw));
        logger.debug('Returning "False"')
        return False
    ssh.exec_command('hotcli deny %s'%(ip))
    ssh.close()
    logger.info('User %s was denied on %s'%(ip, gw))
    logger.debug('Returning "True"')
    return True

