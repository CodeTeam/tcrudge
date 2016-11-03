import operator

import peewee


class BaseModel(peewee.Model):
    async def _update(self, app, data):
        """
        By default set all given attributes
        """
        for k, v in data.items():
            setattr(self, k, v)
        await app.objects.update(self)
        return self

    @classmethod
    async def _create(cls, app, data):
        """
        By default create instance with all given attributes
        """
        return await app.objects.create(cls, **data)

    async def _delete(self, app):
        """
        By default do not allow to delete model
        """
        raise AttributeError


# Operator mapping
FILTER_MAP = {
    # <
    'lt': operator.lt,
    # >
    'gt': operator.gt,
    # <=
    'lte': operator.le,
    # >=
    'gte': operator.ge,
    # !=
    'ne': operator.ne,
    # LIKE
    'like': operator.mod,
    # ILIKE
    'ilike': operator.pow,
    # IN
    'in': operator.lshift,
    # ISNULL
    'isnull': operator.rshift
}
