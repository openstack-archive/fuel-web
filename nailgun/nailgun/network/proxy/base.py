from nailgun.db import db
from nailgun.network.proxy import utils


class BaseProxy(object):

    def get(self, obj_id, lock_for_update=False):
        q = db().query(self.model)
        if lock_for_update:
            q = q.with_for_update()
        return q.get(obj_id)

    def get_all(self):
        return db().query(self.model)

    def create(self, data):
        new_obj = self.model()
        for key, value in data.items():
            setattr(new_obj, key, value)
        db().add(new_obj)
        db().flush()
        return new_obj

    def filter(self, data):
        q = utils.Query(self.model, data)
        return q.render()

    def update(self, instance, data):
        instance.update(data)
        db().add(instance)
        db().flush()
        return instance

    def delete(self, instance):
        db().delete(instance)
        db().flush()

    def bulk_delete(self, ids):
        db().query(self.model).filter(
            self.model.id.in_(ids)).delete('fetch')
