"""
Module containing decorators.
"""


def perm_roles(items):
    """
    Check roles from input list. Auth logic is up to user.
    """

    def wrap(f):
        async def func(self, *args, **kw):
            auth = await self.is_auth()
            if auth:
                roles = await self.get_roles()
                valid_permission = any(r in items for r in roles)
                if not valid_permission:
                    await self.bad_permissions()
                return await f(self, *args, **kw)
            else:
                await self.bad_permissions()

        return func

    return wrap
