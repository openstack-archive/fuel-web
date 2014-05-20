import argparse
import math
import psycopg2
from time import sleep
from uuid import uuid4


def select_items(order, wait):
    conn = psycopg2.connect(host='localhost', user='nailgun',
                            database='nailgun', password='nailgun')
    curs = conn.cursor()
    if order == 'DESC':
        ids = ','.join(map(str, range(0, 10)))
        order = 'DESC'
    else:
        ids = ','.join(map(str, reversed(range(0, 10))))
        order = 'ASC'
    curs_name = uuid4()
    q = 'DECLARE "{0}" CURSOR WITHOUT HOLD FOR SELECT * FROM nodes ' \
        'WHERE id IN ({1}) ORDER BY ID {2} FOR UPDATE'.format(curs_name, ids, order)
    print "### query", q
    curs.execute(q)
    step = 3
    total = 8
    iterations = int(math.ceil(float(total) / step))
    for i in range(iterations):
        print "## iteration ", i
        curs.execute('FETCH {0} from "{1}"'.format(step, curs_name))
        for r in curs:
            print "###", r[0]
            sleep(wait)
    conn.commit()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--order', default='DESC')
    parser.add_argument('-w', '--wait', default=1)
    args = parser.parse_args()
    select_items(args.order, args.wait)
    print "ok"
