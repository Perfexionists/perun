"""
:Author: Pierre Barbier de Reuille <pierre.barbierdereuille@gmail.com>

Module contained a variety of small useful functions.
"""

from collections import OrderedDict
from keyword import iskeyword as _iskeyword
from operator import itemgetter as _itemgetter
import sys
import inspect

import numpy as np


_epsilon = np.sqrt(np.finfo(float).eps)

# Find the largest float available for this numpy
if hasattr(np, "float128"):
    large_float = np.float128
elif hasattr(np, "float96"):
    large_float = np.float96
else:
    large_float = np.float64


def finite(val):
    return val is not None and np.isfinite(val)


def make_ufunc(nin=None, nout=1):
    """
    Decorator used to create a ufunc using `np.frompyfunc`. Note that the
    returns array will always be of dtype 'object'. You should use the `out` if
    you know the wanted type for the output.

    :param int nin: Number of input. Default is found by using
        ``inspect.getargspec``
    :param int nout: Number of output. Default is 1.
    """

    def f(fct):
        if nin is None:
            Nin = len(inspect.getargspec(fct).args)
        else:
            Nin = nin
        return np.frompyfunc(fct, Nin, nout)

    return f


def numpy_trans(fct):
    """
    Decorator to create a function taking a single array-like argument and
    return a numpy array of same shape.

    The function is called as:

        fct(z, out=out)

    This decorator garanties that z and out are ndarray of same shape and out is
    at least a float.
    """

    def f(z, out=None):
        z = np.asanyarray(z)
        if out is None:
            out = np.empty(z.shape, dtype=type(z.dtype.type() + 0.0))
            arg_out = out
        else:
            arg_out = out.reshape(z.shape)
        fct(z, out=arg_out)
        return out

    return f


def numpy_trans_idx(fct):
    """
    Decorator to create a function taking a single array-like argument and
    return a numpy array of same shape. In addition, if the input as no
    dimension, the function will still receive a 1D array, allowing for
    indexing.

    The function is called as:

        fct(z, out=out)

    This decorator garanties that z and out are at least 1D ndarray of same
    shape and out is at least a float.

    It also ensure the output is the shape of the initial input (even if it has
    no dimension)
    """

    def f(z, out=None):
        z = np.asanyarray(z)
        real_shape = z.shape
        if len(real_shape) == 0:
            z = z.reshape(1)
        if out is None:
            out = np.empty(z.shape, dtype=type(z.dtype.type() + 0.0))
        else:
            out.shape = z.shape
        out = fct(z, out=out)
        out.shape = real_shape
        return out

    return f


def numpy_method_idx(fct):
    """
    Decorator to create a function taking a single array-like argument and
    return a numpy array of same shape. In addition, if the input as no
    dimension, the function will still receive a 1D array, allowing for
    indexing.

    The function is called as:

        fct(self, z, out=out)

    This decorator garanties that z and out are at least 1D ndarray of same
    shape and out is at least a float.

    It also ensure the output is the shape of the initial input (even if it has
    no dimension)
    """

    def f(self, z, out=None):
        z = np.asanyarray(z)
        real_shape = z.shape
        if len(real_shape) == 0:
            z = z.reshape(1)
        if out is None:
            out = np.empty(z.shape, dtype=type(z.dtype.type() + 0.0))
        else:
            out.shape = z.shape
        out = fct(self, z, out=out)
        out.shape = real_shape
        return out

    return f


def namedtuple(typename, field_names, verbose=False, rename=False):
    """Returns a new subclass of tuple with named fields.

    >>> Point = namedtuple('Point', 'x y')
    >>> Point.__doc__                   # docstring for the new class
    'Point(x, y)'
    >>> p = Point(11, y=22)             # instantiate with positional args or keywords
    >>> p[0] + p[1]                     # indexable like a plain tuple
    33
    >>> x, y = p                        # unpack like a regular tuple
    >>> x, y
    (11, 22)
    >>> p.x + p.y                       # fields also accessable by name
    33
    >>> d = p._asdict()                 # convert to a dictionary
    >>> d['x']
    11
    >>> Point(**d)                      # convert from a dictionary
    Point(x=11, y=22)
    >>> p._replace(x=100)               # _replace() is like str.replace() but targets named fields
    Point(x=100, y=22)

    """

    # Parse and validate the field names.  Validation serves two purposes,
    # generating informative error messages and preventing template injection attacks.
    if isinstance(field_names, str):
        # names separated by whitespace and/or commas
        field_names = field_names.replace(",", " ").split()
    field_names = tuple(map(str, field_names))
    forbidden_fields = {
        "__init__",
        "__slots__",
        "__new__",
        "__repr__",
        "__getnewargs__",
    }
    if rename:
        names = list(field_names)
        seen = set()
        for i, name in enumerate(names):
            need_suffix = (
                not all(c.isalnum() or c == "_" for c in name)
                or _iskeyword(name)
                or not name
                or name[0].isdigit()
                or name.startswith("_")
                or name in seen
            )
            if need_suffix:
                names[i] = "_%d" % i
            seen.add(name)
        field_names = tuple(names)
    for name in (typename,) + field_names:
        if not all(c.isalnum() or c == "_" for c in name):
            raise ValueError(
                "Type names and field names can only contain alphanumeric characters "
                f"and underscores: {name}"
            )
        if _iskeyword(name):
            raise ValueError(f"Type names and field names cannot be a keyword: {name}")
        if name[0].isdigit():
            raise ValueError(f"Type names and field names cannot start with a number: {name}")
    seen_names = set()
    for name in field_names:
        if name.startswith("__"):
            if name in forbidden_fields:
                raise ValueError(f"Field names cannot be on of {', '.join(forbidden_fields)}")
        elif name.startswith("_") and not rename:
            raise ValueError(f"Field names cannot start with an underscore: {name}")
        if name in seen_names:
            raise ValueError(f"Encountered duplicate field name: {name}")
        seen_names.add(name)

    # Create and fill-in the class template
    numfields = len(field_names)
    argtxt = repr(field_names).replace("'", "")[1:-1]  # tuple repr without parens or quotes
    reprtxt = ", ".join("%s=%%r" % name for name in field_names)
    template = """class %(typename)s(tuple):
        '%(typename)s(%(argtxt)s)' \n
        __slots__ = () \n
        _fields = %(field_names)r \n
        def __new__(_cls, %(argtxt)s):
            'Create new instance of %(typename)s(%(argtxt)s)'
            return _tuple.__new__(_cls, (%(argtxt)s)) \n
        @classmethod
        def _make(cls, iterable, new=tuple.__new__, len=len):
            'Make a new %(typename)s object from a sequence or iterable'
            result = new(cls, iterable)
            if len(result) != %(numfields)d:
                raise TypeError('Expected %(numfields)d arguments, got %%d' %% len(result))
            return result \n
        def __repr__(self):
            'Return a nicely formatted representation string'
            return '%(typename)s(%(reprtxt)s)' %% self \n
        def _asdict(self):
            'Return a new OrderedDict which maps field names to their values'
            return OrderedDict(zip(self._fields, self)) \n
        def _replace(_self, **kwds):
            'Return a new %(typename)s object replacing specified fields with new values'
            result = _self._make(map(kwds.pop, %(field_names)r, _self))
            if kwds:
                raise ValueError('Got unexpected field names: %%r' %% kwds.keys())
            return result \n
        def __getnewargs__(self):
            'Return self as a plain tuple.  Used by copy and pickle.'
            return tuple(self) \n\n""" % dict(
        numfields=numfields,
        field_names=field_names,
        typename=typename,
        argtxt=argtxt,
        reprtxt=reprtxt,
    )
    for i, name in enumerate(field_names):
        template += "        %s = _property(_itemgetter(%d), doc='Alias for field number %d')\n" % (
            name,
            i,
            i,
        )
    if verbose:
        print(template)

    # Execute the template string in a temporary namespace and
    # support tracing utilities by setting a value for frame.f_globals['__name__']
    namespace = dict(
        _itemgetter=_itemgetter,
        __name__="namedtuple_%s" % typename,
        OrderedDict=OrderedDict,
        _property=property,
        _tuple=tuple,
    )
    try:
        exec(template, namespace)
    except SyntaxError as exc:
        raise SyntaxError(f"{exc.msg}:\n{template}") from exc
    result = namespace[typename]

    # For pickling to work, the __module__ variable needs to be set to the frame
    # where the named tuple is created.  Bypass this step in enviroments where
    # sys._getframe is not defined (Jython for example) or sys._getframe is not
    # defined for arguments greater than 0 (IronPython).
    try:
        result.__module__ = sys._getframe(1).f_globals.get("__name__", "__main__")
    except (AttributeError, ValueError):
        pass

    return result


def approx_jacobian(x, func, epsilon, *args):
    """
    Approximate the Jacobian matrix of callable function func

    :param ndarray x: The state vector at which the Jacobian matrix is desired
    :param callable func: A vector-valued function of the form f(x,*args)
    :param ndarray epsilon: The peturbation used to determine the partial derivatives
    :param tuple args: Additional arguments passed to func

    :returns: An array of dimensions (lenf, lenx) where lenf is the length
         of the outputs of func, and lenx is the number of

    .. note::

         The approximation is done using forward differences

    """
    x0 = np.asarray(x)
    x0 = np.asfarray(x0, dtype=x0.dtype)
    epsilon = x0.dtype.type(epsilon)
    f0 = func(*((x0,) + args))
    jac = np.zeros([len(x0), len(f0)], dtype=x0.dtype)
    dx = np.zeros(len(x0), dtype=x0.dtype)
    for i in range(len(x0)):
        dx[i] = epsilon
        jac[i] = (func(*((x0 + dx,) + args)) - f0) / epsilon
        dx[i] = 0.0
    return jac.transpose()
