import operator
import genson
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
    
    @classmethod
    def to_schema(cls, excluded=[]):
        schema = genson.Schema.create_default_schema()
        excluded += getattr(cls._meta, "excluded", [])
        for field, type_field in cls._meta.fields.items():
            if field not in excluded:
                schema.add_object(
                    {
                        field: type_field.get_column_type()
                    }
                )
                if not type_field.null:
                    schema.add_object(
                        {
                            field: None
                        }
                    )
                    schema.add_schema(
                        {
                            "required": [field]
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
