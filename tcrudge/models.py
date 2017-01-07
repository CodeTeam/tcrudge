"""
Module contains basic model class.
"""

import operator
import peewee

from tcrudge.utils.schema import Schema


class BaseModel(peewee.Model):
    """
    Basic abstract ORM model.
    """

    async def _update(self, app, data):
        """
        By default method sets all given attributes.

        :returns: updated self instance.
        """
        for k, v in data.items():
            setattr(self, k, v)
        await app.objects.update(self)
        return self

    @classmethod
    async def _create(cls, app, data):
        """
        By default method creates instance with all given attributes.

        :returns: created object.
        """
        return await app.objects.create(cls, **data)

    async def _delete(self, app):
        """
        By default model deletion is not allowed.
        """
        raise AttributeError

    @classmethod
    def to_schema(cls, excluded=None):
        """
        Generates JSON schema from ORM model. User can exclude some fields
        from serialization, by default the only fields to exclude are
        pagination settings.

        :param excluded: Excluded parameters.
        :type excluded: list or tuple.
        :return: JSON schema.
        :rtype: dict.
        """
        if not excluded:
            excluded = []
        schema = Schema.create_default_schema()
        excluded += getattr(cls._meta, "excluded", [])
        for field, type_field in cls._meta.fields.items():
            if field not in excluded:
                schema.add_object(
                        {
                            field: type_field.get_column_type()
                        }
                )
                if not type_field.null:
                    schema.add_schema(
                            {
                                "required": [field]
                            }
                    )
                else:
                    schema.add_object(
                            {
                                field: None
                            }
                    )
        return schema.to_dict()


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
