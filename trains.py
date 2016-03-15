import sqlite3

from settings import trains_file

query = 'select name, network from bundles b, ranges r where b.id = r.bundle_id and b.id=%s and r.network not like "10.253.%%";'

directions = {
    'St.' : 'spb',
    'Belgorod' : 'blg',
    'Nice' : 'nice',
    'Strizh' : 'nng',
    'Lev' : 'hel'
}

def get_train(train_id):
    name = '<invalid>'
    try:
        con = sqlite3.connect(trains_file)
        cur = con.cursor()
        cur.execute(query%train_id)
        (bname, network) = cur.fetchone()
        d = bname.split()[0]
        direction = d[:3].lower()
        if d in directions.keys():
            direction = directions[d]
        num = '{0:03}'.format(int(network.split('.')[2])/2 + 1)
        name = '/'.join((num, direction.lower()))
        return name

    except Exception, e:
        print e
    finally:
        con.close()
    return name
