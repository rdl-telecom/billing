#!bin/python

import sys
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from db import *

import datetime
from settings import okko_report_from, okko_report_to, okko_smtp_passwd, okko_smtp_server, okko_smtp_server_port, okko_smtp_ssl

DATE_FMT='%Y-%m-%d'

def get_watches(start, end):

    def date_to_str(dt):
        return dt.strftime('%Y-%m-%d %H:%M:%S')

    def get_train_id(train_info):
        (ip, direction) = train_info
        num = ''
        if ip[:5] != '10.10': # hardcode here and below
            num = ip.replace('.', '-')
        else:
            num = '{0:03}'.format(int(ip.split('.')[2])/2 + 1)
        return '/'.join((num, direction.lower()))


    query = 'select v.external_order_id, v.type, o.first_ip, \
             o.payment_time, o.refund_time, o.direction, v.name, v.price \
             from vidimax v left join orders o on v.id = o.client_films_id \
             where v.external_order_id is not null and o.payment_time between "%s" and "%s";'

    db = db_connect()
    res = db_query(db, query%(date_to_str(start), date_to_str(end)), full=True)
    db_disconnect(db)

    result = [ '"order_id","type","train_id","date","direction","name","price"' ]
    base_line = '"%s","%s","%s","%s","%s","%s",%s'

    for oid, typ, ip, pt, rt, dr, nam, pri in res:
        tr = get_train_id((ip, dr))
        result.append(base_line%(oid, typ, tr, date_to_str(pt), dr, nam, pri))
        if rt: # refund
            result.append(base_line%(oid, 'refund', tr, date_to_str(rt), dr, nam, -pri))

    return '\n'.join(result)

def send_mail(attachment):
    msg = MIMEMultipart()
    msg['Subject'] = 'RDL report'
    msg['From'] = okko_report_from
    msg['To'] = ', '.join(okko_report_to)
    msg.preamble = 'See <report.csv> attachment file'
    msg.add_header('Content-Disposition', 'attachment', filename='report.csv')
#    msg.attach(MIMEText('See report in report.csv attachment file', _subtype='plain'))
    msg.attach(MIMEText(attachment, _subtype='csv', _charset='utf-8'))

    if okko_smtp_ssl:
        smtp = smtplib.SMTP_SSL(okko_smtp_server, okko_smtp_server_port)
    else:
        smtp = smtplib.SMTP(okko_smtp_server, okko_smtp_server_port)

    smtp.login(okko_report_from, okko_smtp_passwd)
    smtp.sendmail(okko_report_from, okko_report_to, msg.as_string())
    smtp.quit()
    


if __name__ == '__main__':
    e = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    start = e - datetime.timedelta(days=1)
    end = e - datetime.timedelta(microseconds=1)

    send_mail(get_watches(start, end))
