from tornado.web import HTTPError as _HTTPError


class HTTPError(_HTTPError):
    """
    Custom HTTPError class
    Expands kwargs with body argument
    Usage:
    raise HTTPError(400, b'Something bad happened')
    """
    def __init__(self, status_code=500, log_message=None, *args, **kwargs):
        super(HTTPError, self).__init__(status_code, log_message, *args, **kwargs)
        self.body = kwargs.get('body')
