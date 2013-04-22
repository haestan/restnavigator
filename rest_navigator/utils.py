from __future__ import print_function
from __future__ import unicode_literals

from functools import wraps

import exc


def fix_scheme(url):
    '''Prepends the http:// scheme if necessary to a url. Fails if a scheme
    other than http is used'''
    splitted = url.split('://')
    if len(splitted) == 2:
        if splitted[0] == 'http':
            return url
        else:
            raise exc.WileECoyoteException(
                'Bad scheme! Got: {}, expected http'.format(splitted[0]))
    elif len(splitted) == 1:
        return 'http://' + url
    else:
        raise exc.ZachMorrisException('Too many schemes!')


def slice_process(slc):
    '''Returns dictionaries for different slice syntaxes.'''
    if slc.step is None:
        if slc.start is not None and slc.stop is not None:
            return {slc.start: slc.stop}
        if slc.start is not None and slc.stop is None:
            return {slc.start: ''}
        if slc.start is None and slc.stop is None:
            return {None:None}  # a sentinel indicating 'No further expanding please'
        # maybe more slice types later if there is a good reason
    raise ValueError('Unsupported slice syntax')


def autofetch(fn):
    '''A decorator used by Navigators that fetches the resource if necessary prior
    to calling the function
    '''

    @wraps(fn)
    def wrapped(self, *args, **kwargs):
        if self.response is None:
            self.GET()
        return fn(self, *args, **kwargs)
    return wrapped


def normalize_getitem_args(args):
    '''Turns the arguments to __getitem__ magic methods into a uniform list of
    dictionaries and strings (and Ellipsis)
    '''
    if not isinstance(args, tuple):
        args = args,
    kwargs = {}
    slugs = []
    for arg in args:
        if isinstance(arg, basestring):
            slugs.append(arg)
        elif isinstance(arg, slice):
            kwargs.update(slice_process(arg))
        elif isinstance(arg, Ellipsis):
            slugs.append(Ellipsis)
        else:
            raise TypeError(
                'Brackets cannot contain objects of type {.__name__}'
                .format(type(arg)))
    return slugs, kwargs
