from db import DB
import datetime
# coding: utf-8

db = DB()

def microseconds_to_timedelta(usecs):
    return datetime.timedelta(microseconds=usecs)

def get_tariff(service, tariff):
    return db.query('select id, price from tariffs_tariff where service="{0}" and name="{1}"'.format(service, tariff))

def get_list_by_service_and_direction(service, direction):
    tariffs = db.query('select t.id - 1, t.name, t.price, d.button_ru, d.button_en, d.description_ru, d.description_en \
                        from tariffs_directiontariff dt \
                        left join tariffs_tariff t on dt.tariff_id = t.id \
                        left join tariffs_description d on t.id = d.tariff_id \
                        left join tariffs_direction dir on dt.direction_id = dir.id \
                        where t.service="{0}" and dir.abbr="{1}" order by t.price;'.format(service.upper(), direction.upper()), fetchall=True
                      )
    result = {}
    for i, name, price, b_ru, b_en, d_ru, d_en in tariffs:
        result[str(i)] = {
            'Button' : b_ru,
            'Button_EN' : b_en,
            'Tariff' : name,
            'Sum' : price,
            'Description' : d_ru,
            'Description_EN' : d_en
        }
    return result

def get_descriptions(tariff_id):
    return db.query('select button_ru, button_en from tariffs_description where tariff_id={0}'.format(tariff_id))

def get_duration(direction, tariff_id):
    (usecs, ) = db.query('select if(t.duration <> 0, t.duration, d.duration) from tariffs_directiontariff dt \
                      left join tariffs_direction d on dt.direction_id=d.id \
                      right join tariffs_tariff t on t.id=dt.tariff_id \
                      where d.abbr="{0}" and t.id={1};'.format(direction, tariff_id)
                    )
    return microseconds_to_timedelta(usecs)

def get_price(direction, tariff_id):
    result = db.query('select t.price from tariffs_directiontariff dt \
                       left join tariffs_direction d on dt.direction_id=d.id \
                       right join tariffs_tariff t on t.id=dt.tariff_id \
                       where d.abbr="{0}" and t.id={1};'.format(direction, tariff_id)
                     )
    if result:
        result = result[0]
    return result
