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
                valid_permission = False
                for r in roles:
                    if r in items:
                        valid_permission = True
                        break
                if not valid_permission:
                    await self.bad_permissions()
                return await f(self, *args, **kw)
            else:
                await self.bad_permissions()

        return func

    return wrap
