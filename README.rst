Schema validation just got Pythonic
===============================================================================

**schema** is a library for validating Python data structures, such as those
obtained from config-files, forms, external services or command-line
parsing, converted from JSON/YAML (or something else) to Python data-types.


.. image:: https://secure.travis-ci.org/keleshev/schema.svg?branch=master
    :target: https://travis-ci.org/keleshev/schema

.. image:: https://img.shields.io/codecov/c/github/keleshev/schema.svg
    :target: http://codecov.io/github/keleshev/schema

Example
----------------------------------------------------------------------------

Here is a quick example to get a feeling of **schema**, validating a list of
entries with personal information:

.. code:: python

    >>> from schema import Schema, And, Use, Optional

    >>> schema = Schema([{'name': And(str, len),
    ...                   'age':  And(Use(int), lambda n: 18 <= n <= 99),
    ...                   Optional('gender'): And(str, Use(str.lower),
    ...                                           lambda s: s in ('squid', 'kid'))}])

    >>> data = [{'name': 'Sue', 'age': '28', 'gender': 'Squid'},
    ...         {'name': 'Sam', 'age': '42'},
    ...         {'name': 'Sacha', 'age': '20', 'gender': 'KID'}]

    >>> validated = schema.validate(data)

    >>> assert validated == [{'name': 'Sue', 'age': 28, 'gender': 'squid'},
    ...                      {'name': 'Sam', 'age': 42},
    ...                      {'name': 'Sacha', 'age' : 20, 'gender': 'kid'}]


If data is valid, ``Schema.validate`` will return the validated data
(optionally converted with `Use` calls, see below).

If data is invalid, ``Schema`` will raise ``SchemaError`` exception.
If you just want to check that the data is valid, ``schema.is_valid(data)`` will
return ``True`` or ``False``.


Installation
-------------------------------------------------------------------------------

Use `pip <http://pip-installer.org>`_ or easy_install::

    pip install schema

Alternatively, you can just drop ``schema.py`` file into your project—it is
self-contained.

- **schema** is tested with Python 2.6, 2.7, 3.2, 3.3, 3.4, 3.5, 3.6 and PyPy.
- **schema** follows `semantic versioning <http://semver.org>`_.

How ``Schema`` validates data
-------------------------------------------------------------------------------

Types
~~~~~

If ``Schema(...)`` encounters a type (such as ``int``, ``str``, ``object``,
etc.), it will check if the corresponding piece of data is an instance of that type,
otherwise it will raise ``SchemaError``.

.. code:: python

    >>> from schema import Schema

    >>> Schema(int).validate(123)
    123

    >>> Schema(int).validate('123')
    Traceback (most recent call last):
    ...
    SchemaUnexpectedTypeError: '123' should be instance of 'int'

    >>> Schema(object).validate('hai')
    'hai'

``object`` will logically match anything. ``Any()`` can be used similarly

Callables
~~~~~~~~~

If ``Schema(...)`` encounters a callable (function, class, or object with
``__call__`` method) it will call it, and if its return value evaluates to
``True`` it will continue validating, else—it will raise ``SchemaError``.

.. code:: python

    >>> import os

    >>> Schema(os.path.exists).validate('./')
    './'

    >>> Schema(os.path.exists).validate('./non-existent/')
    Traceback (most recent call last):
    ...
    SchemaError: exists('./non-existent/') should evaluate to True

    >>> Schema(lambda n: n > 0).validate(123)
    123

    >>> Schema(lambda n: n > 0).validate(-12)
    Traceback (most recent call last):
    ...
    SchemaError: <lambda>(-12) should evaluate to True

"Validatables"
~~~~~~~~~~~~~~

If ``Schema(...)`` encounters an object with method ``validate`` it will run
this method on corresponding data as ``data = obj.validate(data)``. This method
may raise ``SchemaError`` exception, which will tell ``Schema`` that that piece
of data is invalid, otherwise—it will continue validating.

An example of "validatable" is ``Regex``, that tries to match a string or a
buffer with the given regular expression (itself as a string, buffer or
compiled regex ``SRE_Pattern``):

.. code:: python

    >>> from schema import Regex
    >>> import re

    >>> Regex(r'^foo').validate('foobar')
    'foobar'

    >>> Regex(r'^[A-Z]+$', flags=re.I).validate('those-dashes-dont-match')
    Traceback (most recent call last):
    ...
    SchemaError: Regex(re.compile('^[A-Z]+$', re.IGNORECASE)) does not match 'those-dashes-dont-match'

For a more general case, you can use ``Use`` for creating such objects.
``Use`` helps to use a function or type to convert a value while validating it:

.. code:: python

    >>> from schema import Use

    >>> Schema(Use(int)).validate('123')
    123

    >>> Schema(Use(lambda f: open(f, 'a'))).validate('LICENSE-MIT')
    <open file 'LICENSE-MIT', mode 'a' at 0x...>

Dropping the details, ``Use`` is basically:

.. code:: python

    class Use(object):

        def __init__(self, callable_):
            self._callable = callable_

        def validate(self, data):
            try:
                return self._callable(data)
            except Exception as e:
                raise SchemaError('%r raised %r' % (self._callable.__name__, e))


Sometimes you need to transform and validate part of data, but keep original data unchanged.
``Const`` helps to keep your data safe:

.. code:: python

    >> from schema import Use, Const, And, Schema

    >> from datetime import datetime

    >> is_future = lambda date: datetime.now() > date

    >> to_json = lambda v: {"timestamp": v}

    >> Schema(And(Const(And(Use(datetime.fromtimestamp), is_future)), Use(to_json))).validate(1234567890)
    {"timestamp": 1234567890}

Now you can write your own validation-aware classes and data types.

Lists, similar containers
~~~~~~~~~~~~~~~~~~~~~~~~~

If ``Schema(...)`` encounters an instance of ``list``, ``tuple``, ``set`` or
``frozenset``, it will us ``List`` to validate contents of corresponding data
container against schemas listed inside that container:


.. code:: python

    >>> Schema([1, 0]).validate([1, 1, 0, 1])
    [1, 1, 0, 1]

    >>> Schema((int, float)).validate((5, 7, 8, 'not int or float here'))
    Traceback (most recent call last):
    ...
    SchemaError: Or(Schema(<type 'int'>), Schema(<type 'float'>)) did not validate 'not int or float here'
    'not int or float here' should be instance of 'float'

Dictionaries
~~~~~~~~~~~~

If ``Schema(...)`` encounters an instance of ``dict``, it will use ``Dict`` validate data
key-value pairs:

.. code:: python

    >>> d = Schema({'name': str,
    ...             'age': lambda n: 18 <= n <= 99}).validate({'name': 'Sue', 'age': 28})

    >>> assert d == {'name': 'Sue', 'age': 28}

You can specify keys as schemas too:

.. code:: python

    >>> schema = Schema({str: int,  # string keys should have integer values
    ...                  int: None})  # int keys should be always None

    >>> data = schema.validate({'key1': 1, 'key2': 2,
    ...                         10: None, 20: None})

    >>> schema.validate({'key1': 1,
    ...                   10: 'not None here'})
    Traceback (most recent call last):
    ...
    SchemaError: Key '10' error:
    None does not match 'not None here'

This is useful if you want to check certain key-values, but don't care
about others:

.. code:: python

    >>> schema = Schema({'<id>': int,
    ...                  '<file>': Use(open),
    ...                  str: object})  # don't care about other str keys

    >>> data = schema.validate({'<id>': 10,
    ...                         '<file>': 'README.rst',
    ...                         '--verbose': True})

You can mark a key as optional as follows:

.. code:: python

    >>> from schema import Optional
    >>> Schema({'name': str,
    ...         Optional('occupation'): str}).validate({'name': 'Sam'})
    {'name': 'Sam'}

``Optional`` keys can also carry a ``default``, to be used when no key in the
data matches:

.. code:: python

    >>> from schema import Optional
    >>> Schema({Optional('color', default='blue'): str,
    ...         str: str}).validate({'texture': 'furry'}
    ...       ) == {'color': 'blue', 'texture': 'furry'}
    True

Defaults are used verbatim, not passed through any validators specified in the
value.

default can also be a callable:

.. code:: python

    >>> from schema import Schema, Optional
    >>> Schema({Optional('data', default=dict): {}}).validate({}) == {'data': {}}
    True

Beware that any non ``Optional`` key is required: If you specify types, **schema** won't validate the empty dict:

.. code:: python

    >>> Schema({int:int}).is_valid({})
    False

To do that, you need ``Schema({Optional(int):int})``. This is differents for lists
lists, where ``Schema([int]).is_valid([])`` will return True.

You can mark a key as clean, meaning its value will be discarded:

.. code:: python

    >>> from schema import Clean
    >>> Schema({Clean('id'): int,
    ...         'name': str}).validate({'id': 1234, 'name': 'Eve'})
    {'name': 'Eve'}

``Clean`` and ``Optional`` can be combined together to discard useless values

.. code:: python

    >>> from schema import Clean, Optional
    >>> Schema({Clean(str): None,
    ...         Optional(str): int}).validate({'key1': 3, 'key2': None})
    {'key1': 3}

Avoid using ``Clean`` with required keys:

    >>> from schema import Clean
    >>> Schema({Clean('name'): None,
    ...         'name': str}).validate({'name': None})
    Traceback (most recent call last):
    ...
    SchemaMissingKeyError: Missing key: 'name'

Logic expressions
~~~~~~~~~~~~~~~~~

**schema** has classes ``And``, ``Or`` and ``Not`` that help validating
several schemas for the same data:

.. code:: python

    >>> from schema import And, Or

    >>> Schema({'age': And(int, lambda n: 0 < n < 99)}).validate({'age': 7})
    {'age': 7}

    >>> Schema({'password': And(str, lambda s: len(s) > 6)}).validate({'password': 'hai'})
    Traceback (most recent call last):
    ...
    SchemaError: Key 'password' error:
    <lambda>('hai') should evaluate to True

    >>> Schema(And(Or(int, float), lambda x: x > 0)).validate(3.1415)
    3.1415

    >>> And(str, Not('admin')).validate('admin')
    Traceback (most recent call last):
    ...
    SchemaForbiddenValueError: 'admin' matches forbidden value 'admin'

In a dictionary, you can also combine two keys in a "one or the other" manner. To do
so, use the `Or` class as a key:

.. code:: python
    >>> from schema import Or, Schema
    >>> schema = Schema({
    ...    Or("key1", "key2", only_one=True): str
    ... })

    >>> schema.validate({"key1": "test"}) # Ok
    {'key1': 'test'}

    >>> schema.validate({"key1": "test", "key2": "test"}) # SchemaError
    Traceback (most recent call last):
    ...
    SchemaOnlyOneAllowedError: There are multiple keys present from the Or('key1', 'key2') condition

Hooks
~~~~~~~~~~
You can define hooks to have specific behavior when validating key:value.
We have already seen ``Optional`` and ``Clean`` hooks.
The `Forbidden` class is another example of this.

You can mark a key as forbidden as follows:

.. code:: python

    >>> from schema import Forbidden
    >>> Schema({Forbidden('age'): object}).validate({'age': 50})
    Traceback (most recent call last):
    ...
    SchemaForbiddenKeyError: Forbidden key encountered: 'age' in {'age': 50}

A few things are worth noting. First, the value paired with the forbidden
key determines whether it will be rejected:

.. code:: python

    >>> Schema({Forbidden('age'): str, 'age': int}).validate({'age': 50})
    {'age': 50}

Note: if we hadn't supplied the 'age' key here, the call would have failed too, but with
SchemaWrongKeyError, not SchemaForbiddenKeyError.

Second, Forbidden has a higher priority than standard keys, and consequently than Optional.
This means we can do that:

.. code:: python

    >>> Schema({Forbidden('age'): object, Optional(str): object}).validate({'age': 50})
    Traceback (most recent call last):
    ...
    SchemaForbiddenKeyError: Forbidden key encountered: 'age' in {'age': 50}

To define you own hooks, you can pass a handler function. The following hook will
call `_my_function` if `key` is encountered.

.. code:: python

    from schema import Hook
    def _my_function(key, value, *args):
        print(key, value)

    Hook("key", handler=_my_function)

You can also inherit the ``Hook`` class. Here's an example where a `Deprecated` class is added to log warnings whenever a key is encountered:

.. code:: python

    from schema import Hook, Schema
    class Deprecated(Hook):

        def handle(self, key, *args):
            logging.warn(f"`{key}` is deprecated. " + (self._error or ""))

    Schema({Deprecated("test", "custom error message."): object}, ignore_extra_keys=True).validate({"test": "value"})
    ...
    WARNING: `test` is deprecated. custom error message.

Hooks have much more possibilities:

- ``handle(self, key, value, new, data)``: Called when the key and the value matches. Takes the transformed key, the transformed value, the new dict being built, and the data being validated. It can edit ``new``, and return ``None`` to continue matching the key with other schemas, ``True`` to add the key and the value to ``new``, and ``False`` to discard the key.
- ``handle(self, key, value, new, data)``: Called when the key matches but not the value. Takes the transformed key, the error raised, the new dict being built, and the data being validated. It can edit ``new``, and return ``None`` to continue matching the key with other schemas, ``True`` to add to raise the ``error``, and ``False`` to discard the key.
- ``priority``: The priority of this key, lowest number is called first. You can use ``COMPARABLE``, ``CALLABLE``, ``VALIDATOR``, ``TYPE``, ``DICT`` and ``ITERABLE`` constants. It can be a function.
- ``required``: If the key is required, default to ``False``,
- ``default``: The default value if the key hasn't been met, can be a function.
- ``reset``: A function to call once the dict has been matched, for extra validation.

Extra Keys
~~~~~~~~~~

The ``Schema(...)`` parameter ``ignore_extra_keys`` causes validation to ignore extra keys in a dictionary, and also to not return them after validating.

.. code:: python

    >>> schema = Schema({'name': str}, ignore_extra_keys=True)
    >>> schema.validate({'name': 'Sam', 'age': '42'})
    {'name': 'Sam'}

If you would like any extra keys returned, use ``object: object`` as one of the key/value pairs, which will match any key and any value.
Otherwise, extra keys will raise a ``SchemaError``.

User-friendly error reporting
-------------------------------------------------------------------------------

You can pass a keyword argument ``error`` to any of validatable classes
(such as ``Schema``, ``And``, ``Or``, ``Regex``, ``Use``) to report this error
instead of a built-in one.

.. code:: python

    >>> Schema(Use(int, error='Invalid year')).validate('XVII')
    Traceback (most recent call last):
    ...
    SchemaError: Invalid year

You can see all errors that occurred by accessing exception's ``exc.autos``
for auto-generated error messages, and ``exc.errors`` for errors
which had ``error`` text passed to them.

You can exit with ``sys.exit(exc.code)`` if you want to show the messages
to the user without traceback. ``error`` messages are given precedence in that
case.

A JSON API example
-------------------------------------------------------------------------------

Here is a quick example: validation of
`create a gist <http://developer.github.com/v3/gists/>`_
request from github API.

.. code:: python

    >>> gist = '''{"description": "the description for this gist",
    ...            "public": true,
    ...            "files": {
    ...                "file1.txt": {"content": "String file contents"},
    ...                "other.txt": {"content": "Another file contents"}}}'''

    >>> from schema import Schema, And, Use, Optional

    >>> import json

    >>> gist_schema = Schema(And(Use(json.loads),  # first convert from JSON
    ...                          # use basestring since json returns unicode
    ...                          {Optional('description'): basestring,
    ...                           'public': bool,
    ...                           'files': {basestring: {'content': basestring}}}))

    >>> gist = gist_schema.validate(gist)

    # gist:
    {u'description': u'the description for this gist',
     u'files': {u'file1.txt': {u'content': u'String file contents'},
                u'other.txt': {u'content': u'Another file contents'}},
     u'public': True}

Using **schema** with `docopt <http://github.com/docopt/docopt>`_
-------------------------------------------------------------------------------

Assume you are using **docopt** with the following usage-pattern:

    Usage: my_program.py [--count=N] <path> <files>...

and you would like to validate that ``<files>`` are readable, and that
``<path>`` exists, and that ``--count`` is either integer from 0 to 5, or
``None``.

Assuming **docopt** returns the following dict:

.. code:: python

    >>> args = {'<files>': ['LICENSE-MIT', 'setup.py'],
    ...         '<path>': '../',
    ...         '--count': '3'}

this is how you validate it using ``schema``:

.. code:: python

    >>> from schema import Schema, And, Or, Use
    >>> import os

    >>> s = Schema({'<files>': [Use(open)],
    ...             '<path>': os.path.exists,
    ...             '--count': Or(None, And(Use(int), lambda n: 0 < n < 5))})

    >>> args = s.validate(args)

    >>> args['<files>']
    [<open file 'LICENSE-MIT', mode 'r' at 0x...>, <open file 'setup.py', mode 'r' at 0x...>]

    >>> args['<path>']
    '../'

    >>> args['--count']
    3

As you can see, **schema** validated data successfully, opened files and
converted ``'3'`` to ``int``.

(Beta feature) Generating JSON schema
-------------------------------------------------------------------------------

You can also generate standard `draft-07 JSON schema <https://json-schema.org/>`_
or `Open API schema <https://swagger.io/specification/#schemaObject>`_
from a `Schema`.

.. code:: python

    >>> from schema import Optional, Schema
    >>> import json
    >>> s = Schema({"test": str,
    ...             "nested": {Optional("other"): str}
    ...             })
    >>> json_schema = json.dumps(s.json_schema("https://example.com/my-schema.json"))

    # json_schema
    {
        "type":"object",
        "properties": {
            "test": {"type": "string"},
            "nested": {
                "type":"object",
                "properties": {
                    "other": {"type": "string"}
                },
                "additionalProperties":false
            }
        },
        "required":[
            "test",
            "nested"
        ],
        "additionalProperties":false,
        "id":"https://example.com/my-schema.json",
        "$schema":"http://json-schema.org/draft-07/schema#"
    }

Please note that this is a beta feature, and some schema won't be rendered,
or will be illformed. In particular ``Use``  will never be rendered.
However, many optimizations are performed to compact the schema.

By default, JSON schema and Open API cross-compatible schemas are generated. However, it is possible to request a more specific schema.

.. code:: python

    >>> from schema import Or
    >>> s = Or(str, int, bool, None)

    >>> s.json_schema(target='json_schema')
    {'type': ['boolean', 'integer', 'null', 'string']}

    >>> s.json_schema(target='openapi')
    {'anyOf': [{'type': 'boolean'}, {'type': 'integer'}, {'type': 'string'}],
 'nullable': True}

It is possible to precise the JSON schema of any `Schema`:

    >>> from schema import And, Use
    >>> s = And(str, Use(lambda x: len(x) <= 10,
    ...                  json_schema={
    ...                               'type': 'string',
    ...                               'maxLength': 10,
    ...                  }))
    {'type': 'string', 'maxLength': 10}

Note that the two schemas have been compressed together.
