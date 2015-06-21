from bson import ObjectId
from tornado import gen
import time

class Log(object):
    _log = None

    def __init__(self, db):
        self.log = db.log
        self.log.ensure_index('t')
        
    def info(self, text, *args, **kwargs):
        t = kwargs.pop('_type', 'i')
        json = {
            '_id': ObjectId(),
            't': t,
            'text': text,
            'args': args,
            'kwargs': kwargs,
        }
        print 'Log.info(%s | %s | %s)' % (text, ', '.join(map(str, args)), ', '.join(map(lambda kv: '%s=%s'%kv, kwargs.items())))
        self.db.insert(json)
        
    def action(self, action, ref_id, uid, **kwargs):
        self.info(text=action, ref_id=ref_id, uid=uid, _type='a', **kwargs)
        
    def debug(self, text, *args, **kwargs):
        kwargs['_type'] = 'd'
        self.info(text, *args, **kwargs)

    def error(self, text, *args, **kwargs):
        kwargs['_type'] = 'e'
        self.info(text, *args, **kwargs)

    @classmethod
    def get_log(cls, db=None):
        if not cls._log:
            if not db:
                raise Exception('No log initialized, but db not provided!')
            cls._log = Log(db)
        return cls._log
