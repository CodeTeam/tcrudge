import operator

import peewee


class BaseModel(peewee.Model):
    async def _update(self, manager, data):
        """
        By default set all given attributes
        """
        for k, v in data.items():
            setattr(self, k, v)
        await manager.update(self)
        return self

    @classmethod
    async def _create(cls, manager, data):
        """
        By default create instance with all given attributes
        """
        return await manager.create(cls, **data)

    async def _delete(self, manager):
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
