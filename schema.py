"""schema is a library for validating Python data structures, such as those
obtained from config-files, forms, external services or command-line
parsing, converted from JSON/YAML (or something else) to Python data-types."""

import re
import copy

try:
    from contextlib import ExitStack
except ImportError:
    from contextlib2 import ExitStack

try: basestring
except: basestring = str

__version__ = '0.8.0'
__all__ = [
    "BaseSchema",
    "Schema",
    "Dict",
    "List",
    "Any",
    "And",
    "Or",
    "Regex",
    "Optional",
    "Use",
    "Hook",
    "Clean",
    "Forbidden",
    "Const",
    "Not",
    "SchemaError",
    "SchemaWrongKeyError",
    "SchemaMissingKeyError",
    "SchemaForbiddenKeyError",
    "SchemaUnexpectedTypeError",
    "SchemaOnlyOneAllowedError",
    "SchemaWrongLengthError",
    "SchemaForbiddenValueError",

]


class SchemaError(Exception):
    """Error during Schema validation."""

    def __init__(self, autos, errors=None):
        self.autos = autos if type(autos) is list else [autos]
        self.errors = errors if type(errors) is list else [errors]
        Exception.__init__(self, self.code)

    def prepend(self, auto, error):
        """
        Prepends an auto and error in this exception
        """
        self.autos.insert(0, auto)
        self.errors.insert(0, error)
        self.args = (self.code,)

    @property
    def code(self):
        """
        Removes duplicates values in auto and error list.
        parameters.
        """

        def uniq(seq):
            """
            Utility function that removes duplicate.
            """
            seen = set()
            # This way removes duplicates while preserving the order.
            return [x for x in seq if x not in seen and not seen.add(x)]

        data_set = uniq(i for i in self.autos if i is not None)
        error_list = uniq(i for i in self.errors if i is not None)
        if error_list:
            return "\n".join(error_list)
        return "\n".join(data_set)


class SchemaWrongKeyError(SchemaError):
    """Error Should be raised when an unexpected key is detected within the
    data set being."""

    pass


class SchemaMissingKeyError(SchemaError):
    """Error should be raised when a mandatory key is not found within the
    data set being validated"""

    pass


class SchemaOnlyOneAllowedError(SchemaError):
    """Error should be raised when an only_one Or key has multiple matching candidates"""

    pass


class SchemaForbiddenKeyError(SchemaError):
    """Error should be raised when a forbidden key is found within the
    data set being validated, and its value matches the value that was specified"""

    pass


class SchemaUnexpectedTypeError(SchemaError):
    """Error should be raised when a type mismatch is detected within the
    data set being validated."""

    pass


class SchemaWrongLengthError(SchemaError):
    """Error should be raised when a the length of the data is wrong."""

    pass


class SchemaForbiddenValueError(SchemaError):
    """Error should be raised when a forbidden value is found"""

    pass


OPTIONS = {'ignore_extra_keys', 'regex_lib'}
DEFAULT_CLS = {}
def schema_class(name=None):
    """Decorator for naming BaseSchema subclasses"""
    if isinstance(name, type):
        name = getattr(name, 'SCHEMA_CLASS', None)
    def aux(cls):
        cls.SCHEMA_CLASS = name
        if name:
            DEFAULT_CLS[name] = cls
            OPTIONS.add(name)
        return cls
    return aux

class BaseSchema(object):
    """The base class of all Schema classes"""

    # Marker for an optional part of the validation Schema
    _MARKER = object()

    def __init__(self, error=None, name=None, json_schema=_MARKER,
        options=None, **_options):
        """
        Takes
        - error: a human readable error
        - name: the name of the schema
        - json_schema: the JSON_schema of this schema
        - options: a dict of options to propagate
        default options are (and can be passed by as argument)
        - ignore_extra_keys: if dict objects should ignore unmatched keys
        - regex_lib: the lib to use for regex, must provide compile function
        - schema, list, dict, ...: the class to use instead of the default ones
        """
        self._error = error
        self._name = name
        if json_schema is not self._MARKER:
            self._json_schema = json_schema
        if not set(_options) <= OPTIONS:
            diff = set(_options) - OPTIONS
            raise TypeError('unknown parameter%s %s' % (_plural_s(diff),
                ', '.join('"%s"' % option for option in options)))
        if options is None: options = {}
        elif not isinstance(options, dict):
            raise TypeError('options must be a "dict", got "%s"' % type(options))
        schema_class = getattr(self, 'SCHEMA_CLASS', None)
        if schema_class: _options.setdefault(schema_class, type(self))
        if _options:
            self.options = options.copy()
            self.options.update(_options)
        else:
            self.options = options

    def is_valid(self, data):
        """
        Returns whether the given data has passed all the validations
        that were specified in the given schema.
        """
        try:
            self.validate(data)
        except SchemaError:
            return False
        else:
            return True

    def validate(self, data):
        """
        The function to validate data
        """
        self._raise_error('no validation method', data)

    def _raise_error(self, message, data, cls=SchemaError):
        """
        Raises a well formatted error
        """
        e = self._error
        message = self._prepend_schema_name(message)
        raise cls(message, e.format(data) if e else None)

    def _prepend_schema_name(self, message):
        """
        If a custom schema name has been defined, prepends it to the error
        message that gets raised when a schema error occurs.
        """
        if self._name:
            message = "{0!r} {1!s}".format(self._name, message)
        return message

    def _generate_cls(self, cls, *args,
            name=True, error=True, options=True, **kwargs):
        """
        Generates a new instance of any Schema class
        Enables to replace some classes by user custom classes
        """
        if not isinstance(cls, type):
            cls = self.options.get(cls) or DEFAULT_CLS[cls]
        if name is True: kwargs['name'] = self._name
        elif name: kwargs['name'] = name
        if error is True: kwargs['error'] = self._error
        elif error: kwargs['error'] = error
        if options is True: kwargs['options'] = self.options
        elif options: kwargs['options'] = options
        return cls(*args, **kwargs)

    def json_schema(self, schema_id=None, **kwargs):
        """
        Generates a draft-07 / OpenAPI JSON schema
        Takes
        - schema_id: the id of the JSON schema
        - target: used to specialize the schema for JSON schema ('json_schema')
            or Swagger OpenAPI ('openapi')
        - any other argument will be forwarded
        Returns
        - None if the schema doesn't make sense
        - True if the schema matches everything
        - False if the schema does not match anything
        - a dict for a JSON schema
        """
        if hasattr(self, '_json_schema'):
            return self._json_schema_aux(schema_id, self._json_schema)
        return self._json_schema_aux(schema_id, None)

    def _json_schema_aux(self, schema_id, schema_dict):
        """
        Called to eventually deal with schema_id
        """
        if schema_id:
            if schema_dict is True: schema_dict = {}
            if not isinstance(schema_dict, dict):
                raise TypeError(
                    'schema %r cannot be converted to JSON schema' % self)
            schema_dict.update({
                "id": schema_id,
                "$schema": "http://json-schema.org/draft-07/schema#"
            })
        return schema_dict



@schema_class('and')
class And(BaseSchema):
    """
    Utility function to combine validation directives in AND Boolean fashion.
    """

    def __init__(self, *args, **kwargs):
        super(And, self).__init__(**kwargs)
        self._args = [schema if isinstance(schema, BaseSchema)
            else self._generate_cls('schema', schema) for schema in args]

        resets = [schema.reset for schema in self._args
            if hasattr(schema, 'reset')]
        if resets and not hasattr(self, 'reset'):
            self.reset = lambda: (reset() for reset in resets) and None

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__,
            ", ".join(repr(a) for a in self._args))

    def validate(self, data):
        """
        Validate data using defined sub schema/expressions ensuring all
        values are valid.
        :param data: to be validated with sub defined schemas.
        :return: returns validated data
        """
        for schema in self._args:
            data = schema.validate(data)
        return data

    def json_schema(self, schema_id=None, **kwargs):
        if hasattr(self, '_json_schema'):
            return self._json_schema_aux(schema_id, self._json_schema)
        schema_dict = self.merge_json_schemas(
            (s.json_schema(**kwargs) for s in self._args), **kwargs)
        return self._json_schema_aux(schema_id, schema_dict)

    @staticmethod
    def merge_json_schemas(schemas, **kwargs):
        """
        Merges a list of JSON schemas in a AND statement.
        Removes superfluous type schemas.
        Merges all {'not': ...} schemas in a {'not': {'anyOf': [...]}} schema.
        Merges all other schemas in a {'allOf': [...]} schema.
        """
        allOf = [] # all sub schemas
        types = {} # all the types met
        notAnyOf = [] # all not
        false = False # if nothing is matched
        # to call on every sub scehma
        def aux(schema):
            nonlocal false
            if schema is None or schema == {} or schema is True:
                return
            elif schema is False:
                false = True
                return
            keys = set(schema)
            # allOf, recursive call
            if keys <= {'allOf', 'not'}:
                for s in schema.get('allOf', ()): aux(s)
                if 'not' in schema:
                    notAnyOf.append(schema['not'])
            # a simple type, add it to types
            elif keys == {'type'}:
                type_ = schema['type']
                if not type_: return
                elif isinstance(type_, basestring): type_ = (type_,)
                else: type_ = tuple(sorted(set(type_)))
                types.setdefault(type_, True)
            # another schema, append it to allOf
            else:
                # if type is found, disable it from types
                if schema.get('type'):
                    type_ = schema['type']
                    if isinstance(type_, basestring): type_ = (type_,)
                    else: type_ = tuple(sorted(set(type_)))
                    types[type_] = False
                allOf.append(schema)
        # call on every sub schema
        for schema in schemas: aux(schema)
        if false: return False
        # add every type
        for t, b in sorted(types.items()):
            if not b: continue
            if len(t) == 1: t, = t
            allOf.append(dict(type=t))
        # treat notAnyOf
        notAnyOf = Or.merge_json_schemas(notAnyOf, **kwargs)
        # nothing possible
        if notAnyOf == {} or notAnyOf is True: return False
        # no condition to match
        elif not allOf:
            if notAnyOf is False: return True
            elif notAnyOf is not None: return {'not': notAnyOf}
            else: return None
        # merge allOf and notAnyOf
        elif notAnyOf is not None and notAnyOf is not False:
            return {'allOf': allOf, 'not': notAnyOf}
        # only one allOf, return it
        elif len(allOf) == 1: return allOf[0]
        # return allOf array
        else: return dict(allOf=allOf)


@schema_class('or')
class Or(BaseSchema):
    """
    Utility function to combine validation directives in a OR Boolean
    fashion.
    """

    def __init__(self, *args, **kwargs):
        self.only_one = kwargs.pop("only_one", False)
        super(Or, self).__init__(**kwargs)
        self._args = [schema if isinstance(schema, BaseSchema)
            else self._generate_cls('schema', schema) for schema in args]
        self.match_count = 0
        self._resets = [schema.reset for schema in self._args
            if hasattr(schema, 'reset')]

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__,
            ", ".join(repr(a) for a in self._args))

    def reset(self):
        failed = self.match_count > 1 and self.only_one
        self.match_count = 0
        if failed:
            raise SchemaOnlyOneAllowedError(["There are multiple keys present " + "from the %r condition" % self])
        for reset in self._resets: reset()

    def validate(self, data):
        """
        Validate data using sub defined schema/expressions ensuring at least
        one value is valid.
        :param data: data to be validated by provided schema.
        :return: return validated data if not validation
        """
        x = None
        for schema in self._args:
            try:
                validation = schema.validate(data)
                self.match_count += 1
                if self.match_count > 1 and self.only_one:
                    break
                return validation
            except SchemaError as _x:
                x = _x
        if x:
            x.prepend(
                "%r did not validate %r" % (self, data),
                self._error.format(data) if self._error else None
            )
            raise x
        raise SchemaError(
            ["%r did not validate %r" % (self, data)],
            [self._error.format(data) if self._error else None],
        )

    def json_schema(self, schema_id=None, **kwargs):
        if hasattr(self, '_json_schema'):
            return self._json_schema_aux(schema_id, self._json_schema)
        schema_dict = self.merge_json_schemas(
            (s.json_schema(**kwargs) for s in self._args), **kwargs)
        return self._json_schema_aux(schema_id, schema_dict,)

    @staticmethod
    def merge_json_schemas(schemas, target=None, **kwargs):
        """
        Merges a list of JSON schemas in a OR statement.
        Merges all {'const': ...} and {'enum': [...]} schemas together
        Merges all {'type': ...} together
        Merges all other schemas in a {'anyOf': [...]} schema
        """
        anyOf = [] # all sub schemas
        enum = [] # the "enum" sub schema
        types = set() # the matchable types
        # cannot add bool directly to enum, else they'll merge with 1 and 0
        true, false, null, empty = False, False, False, False
        # to call on every sub scehma
        def aux(schema):
            nonlocal true, false, null, empty
            if schema is None or schema is False:
                return
            elif schema == {} or schema is True:
                empty = True
                return
            keys = set(schema)
            if schema.get('nullable', False):
                null = True
                keys.remove('nullable')
                schema = {k: schema[k] for k in keys}
            # a const or enum, append it to enum
            if keys == {'const'} or keys == {'enum'}:
                for const in schema.get('enum', (schema.get('const'),)):
                    if const is True: true = True
                    elif const is False: false = True
                    elif const is None: null = True
                    else: enum.append(const)
            # a boolean, extend enum
            elif keys == {'type'}:
                type_ = schema['type']
                if isinstance(type_, basestring): types.add(type_)
                else: types.update(type_)
            # anyOf, recursive call
            elif keys == {'anyOf'}:
                for s in schema['anyOf']: aux(s)
            # another schema, append it to anyOf
            else: anyOf.append(schema)
        # call on every sub schema
        for schema in schemas: aux(schema)
        if empty: return True
        # try to compress enum
        try: enum = sorted(set(enum))
        except TypeError: pass
        # treat special types
        if 'boolean' in types:
            true, false = True, True
            types.remove('boolean')
        if 'null' in types:
            null = True
            types.remove('null')

        if target == 'json_schema':
            # no enum, better add them to types
            if true is false and not enum:
                if true and false: types.add('boolean')
                if null: types.add('null')
            # add them to enum
            else:
                if true: enum.append(True)
                if false: enum.append(False)
                if null: enum.append(None)
        elif target == 'openapi':
            # no enum, better add them to types
            if true and false and not enum:
                types.add('boolean')
            # add them to enum
            else:
                if true: enum.append(True)
                if false: enum.append(False)
        else:
            # no enum, better add boolean to types
            if true and false and not null and not enum:
                types.add('boolean')
            else:
                if true: enum.append(True)
                if false: enum.append(False)
                if null: enum.append(None)
        if target == 'json_schema':
            if types:
                if len(types) == 1: types = types.pop()
                else: types = sorted(types)
                anyOf.append(dict(type=types))
            if len(enum) == 1:
                anyOf.append(dict(const=enum[0]))
            elif enum: anyOf.append(dict(enum=enum))
        else:
            if types: anyOf.extend(dict(type=t) for t in sorted(types))
            if enum: anyOf.append(dict(enum=enum))

        # add null as nullable
        if target == 'openapi' and null:
            if not anyOf: return dict(enum=[None])
            if len(anyOf) == 1: return dict(anyOf[0], nullable=True)
            else: return dict(anyOf=anyOf, nullable=True)
        else:
            if not anyOf: return None
            elif len(anyOf) == 1: return anyOf[0]
            else: return dict(anyOf=anyOf)


@schema_class('regex')
class Regex(BaseSchema):
    """
    Enables schema.py to validate string using regular expressions.
    """

    def __init__(self, pattern, flags=0, **kwargs):
        super(Regex, self).__init__(**kwargs)
        if hasattr(pattern, 'search'):
            self._pattern = pattern
        else:
            regex_lib = self.options.get('regex_lib', re)
            self._pattern = regex_lib.compile(pattern, flags=flags)

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self._pattern)

    def validate(self, data):
        """
        Validated data using defined regex.
        :param data: data to be validated
        :return: return validated data.
        """
        e = self._error

        try:
            if self._pattern.search(data):
                return data
            else:
                raise SchemaError("%r does not match %r" % (self, data), e)
        except TypeError:
            raise SchemaError("%r is not string nor buffer" % data, e)

    def keys(self, item, comparable_keys, type_keys, global_keys):
        type_keys.setdefault(basestring, []).append(item)

    def json_schema(self, schema_id=None, **kwargs):
        """
        Generates a {'type': 'string', 'regex': ...} schema
        """
        if hasattr(self, '_json_schema'):
            return self._json_schema_aux(schema_id, self._json_schema)
        return self._json_schema_aux(schema_id, dict(
            type='string', regex=self._pattern.pattern))


@schema_class('use')
class Use(BaseSchema):
    """
    For more general use cases, you can use the Use class to transform
    the data while it is being validate.
    """

    def __init__(self, callable_, **kwargs):
        super(Use, self).__init__(**kwargs)
        if not callable(callable_):
            raise TypeError("Expected a callable, not %r" % callable_)
        self._callable = callable_

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self._callable)

    def validate(self, data):
        try:
            return self._callable(data)
        except SchemaError as x:
            x.prepend(None, self._error.format(data) if self._error else None)
            raise x
        except BaseException as x:
            f = _callable_str(self._callable)
            raise SchemaError("%s(%r) raised %r" % (f, data, x), self._error.format(data) if self._error else None)


COMPARABLE, CALLABLE, VALIDATOR, TYPE, DICT, ITERABLE = range(10, 70, 10)

def _priority(s):
    """Return priority for a given object."""
    if type(s) in (list, tuple, set, frozenset):
        return ITERABLE
    if type(s) is dict:
        return DICT
    if issubclass(type(s), type):
        return TYPE
    if hasattr(s, "validate"):
        return VALIDATOR
    if callable(s):
        return CALLABLE
    else:
        return COMPARABLE


@schema_class('list')
class Any(BaseSchema):
    """
    Always validates any data, equivalend to `object`
    """
    priority = 100

    def validate(self, data):
        return data

    def __repr__(self):
        return "%s" % (self.__class__.__name__)

    def json_schema(self, schema_id=None, **kwargs):
        if hasattr(self, '_json_schema'):
            return self._json_schema_aux(schema_id, self._json_schema)
        return self._json_schema_aux(schema_id, True)


@schema_class('dict')
class Dict(BaseSchema):
    """
    Reprensents a python dict
    """
    priority = DICT

    def __init__(self, schemas, error=None,
            min_length=0, max_length=float('inf'), length=None, **kwargs):
        """
        schemas can be a dict or a iterable over couples
        min_length, max_length and length control the size of the dict
        """
        super(Dict, self).__init__(error=error, **kwargs)
        # save ignore_extra_keys
        self._ignore_extra_keys = self.options.get('ignore_extra_keys', False)
        # save min_length and max_length
        if length is not None:
            self._min_length = length
            self._max_length = length
        else:
            self._min_length = min_length
            self._max_length = max_length


        comparable_keys = {} # a dict of lists of tuples for comparable keys
        type_keys = {} # a dict of lists of tuples for type keys
        global_keys = [] # a list of tuples for all other keys
        priorities = {} # the priority of each key
        self._required = set() # all the required keys
        self._default = set() # all the keys with a default value
        self._reset = [] # all the keys with a reset function
        self._schemas = {} # for display
        self._all_keys = [] # for json_shcema
        self._key_names = {} # for errors message

        if isinstance(schemas, dict): schemas = schemas.items()
        for key, schema in schemas:
            if not isinstance(schema, BaseSchema):
                schema = self._generate_cls('schema', schema, name=False)
            self._schemas[key] = schema
            if not isinstance(key, BaseSchema):
                key_name = key
                key = self._generate_cls('schema', key, name=False)
                self._key_names[key] = key_name
            item = (key, schema)
            self._all_keys.append(item)
            flavor = _priority(key)
            # if possible, use the keys function to put it at the right place
            if hasattr(key, 'keys'):
                key.keys(item, comparable_keys, type_keys, global_keys)
            else: global_keys.append(item)
            # get priority
            if hasattr(key, 'priority'):
                priority = key.priority
                if callable(priority): priority = priority()
            else: priority = flavor
            priorities[key] = priority
            # check for required
            if getattr(key, 'required', True):
                self._required.add(key)
            # check for default
            if hasattr(key, 'default'):
                self._default.add(key)
            # check for reset function
            if hasattr(key, 'reset'):
                self._reset.append(key)
        # the sorting criteria
        sortkey = lambda item: priorities[item[0]]
        # sort the global keys
        global_keys.sort(key=sortkey)
        self._global_keys = global_keys
        # for each type keys, add the subtype keys and the global keys, and sort
        self._type_keys = {}
        for key in type_keys:
            items = []
            for t in key.__mro__:
                items.extend(type_keys.get(t, ()))
            items.extend(self._global_keys)
            seen = set()
            self._type_keys[key] = sorted((item for item in items
                if item[0] not in seen and not seen.add(item[0])),
                key=sortkey)
        # for each comparable key, add the first type keys, or the global keys
        self._comparable_keys = {}
        for key, items in comparable_keys.items():
            for t in type(key).__mro__:
                if t not in self._type_keys: continue
                items.extend(self._type_keys[t])
                break
            else: items.extend(self._global_keys)
            seen = set()
            self._comparable_keys[key] = sorted((item for item in items
                if item[0] not in seen and not seen.add(item[0])),
                key=sortkey)

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self._schemas)

    def validate(self, data):
        """
        Validates a dict.
        Check each key and value, call the hooks if needed, check for required
        keys and default values
        """
        # check that this is a dict
        if not isinstance(data, dict):
            message = "%r should be instance of dict" % (data)
            self._raise_error(message, data, SchemaUnexpectedTypeError)
        # check the length
        if not self._min_length <= len(data) <= self._max_length:
            message = "%r should have a length between %s and %s (is %s)" % (data, self._min_length, self._max_length, len(data))
            self._raise_error(message, data, SchemaWrongLengthError)

        e = self._error
        exitstack = ExitStack()
        new = type(data)() # the data to return
        coverage = set() # which keys have been seen
        wrong_keys = [] # which keys are extra
        # call reset of all keys once finished
        for skey in self._reset:
            exitstack.callback(skey.reset)

        with exitstack:
            # treat the simple values first
            data_items = sorted(data.items(),
                key=lambda value: isinstance(value[1],
                    (dict, list, tuple, set, frozenset)))
            for key, value in data_items:
                # look for the best list of schemas
                sitems = self._comparable_keys.get(key, None)
                if sitems is None:
                    for t in type(key).__mro__:
                        sitems = self._type_keys.get(t, None)
                        if sitems is not None: break
                    else: sitems = self._global_keys

                for skey, svalue in sitems:
                    # check if the key schema matches the key
                    try:
                        nkey = skey.validate(key)
                    except SchemaError:
                        continue
                    # check if the value schema matches the value
                    try:
                        nvalue = svalue.validate(value)
                    # it doesn't match, try to call catch, else continue
                    except SchemaError as x:
                        if hasattr(skey, 'catch'):
                            action = skey.catch(nkey, x, new, data)
                        else: action = True
                        if action is True:
                            message = "Key '%s' error:" % nkey
                            message = self._prepend_schema_name(message)
                            x.prepend(message, e)
                            raise x
                        elif action is False: break
                    # it matches, try to call handle, else sve the key/value
                    else:
                        coverage.add(skey)
                        if hasattr(skey, 'handle'):
                            action = skey.handle(nkey, nvalue, new, data)
                        else: action = True
                        if action is True:
                            new[nkey] = nvalue
                            break
                        elif action is False: break
                # no key has matched
                else: wrong_keys.append(key)
        # check that all required keys have been seen
        if not self._required <= coverage:
            missing_keys = self._required - coverage
            s_missing_keys = ", ".join(repr(self._key_names.get(k, k)) \
                for k in sorted(missing_keys, key=repr))
            message = "Missing key%s: %s" % (_plural_s(missing_keys), s_missing_keys)
            self._raise_error(message, data, SchemaMissingKeyError)
        # check if extra keys are authorized
        if not self._ignore_extra_keys and wrong_keys:
            s_wrong_keys = ", ".join(repr(k) for k in sorted(wrong_keys, key=repr))
            message = "Wrong key%s %s in %r" % \
                (_plural_s(wrong_keys), s_wrong_keys, data)
            self._raise_error(message, data, SchemaWrongKeyError)
        # get the default value of all unseen keys
        for skey in self._default - coverage:
            default = skey.default
            if callable(default):
                new[skey._schema] = default()
            else: new[skey._schema] = default

        return new

    def json_schema(self, schema_id=None, **kwargs):
        """
        Generates a JSON schema for this object.
        Creates a 'properties' field for comparable keys.
        Creates a 'patternProperties' field for regex keys.
        Creates a 'additionalProperties' field for other keys.
        Several identical keys are merged together.
        """
        if hasattr(self, '_json_schema'):
            return self._json_schema_aux(schema_id, self._json_schema)

        props = {} # a dict of list of tuples for properties
        patternProps = {} # a dict of list of tuples for patternProperties
        addProps = [] # a list of tuples for additionalProperties
        requiredProps = set() # for required

        for key, schema in self._all_keys:
            key_dict = key.json_schema(**kwargs)
            schema = schema.json_schema(**kwargs)
            if schema is None or schema is False: continue
            required = getattr(key, 'required', True)
            # let _json_schema_key put the right key at the right place
            self._json_schema_key(key, key_dict, schema, required,
                props, patternProps, addProps, requiredProps, **kwargs)
        # create the JSON schema
        schema_dict = dict(type='object')
        if requiredProps: schema_dict['required'] = sorted(requiredProps)
        # create properties
        properties = {}
        for const, items in props.items():
            schema = self._json_schema_values(items, **kwargs)
            if schema is not False: properties[const] = schema
        if properties: schema_dict['properties'] = properties
        # create patternProperties
        properties = {}
        for regex, items in patternProps.items():
            schema = self._json_schema_values(items, **kwargs)
            if schema is not False: properties[regex] = schema
        if properties: schema_dict['patternProperties'] = properties
        # create additionalProperties
        if self._ignore_extra_keys:
            schema_dict['additionalProperties'] = True
        else:
            schema = self._json_schema_values(addProps, **kwargs)
            schema_dict['additionalProperties'] = schema
        # create minProperties and maxProperties
        if self._min_length:
            schema_dict['minProperties'] = self._min_length
        if self._max_length != float('inf'):
            schema_dict['maxProperties'] = self._max_length

        return self._json_schema_aux(schema_id, schema_dict)


    def _json_schema_key(self, key, json_schema, schema, required,
        props, patternProps, addProps, requiredProps, **kwargs):
        """
        Puts the (key, schema) tuple in the right structure(s)
        """
        if json_schema == {} or json_schema is True:
            addProps.append((key, True))
            return
        elif json_schema is None or json_schema is False:
            return
        keys = set(json_schema)
        # a {'type': ...} schema
        # most other fields are ignored in this case
        # goes either in addProps, either in patternProps
        if 'type' in json_schema:
            type_ = json_schema['type']
            # type is a list, recursive call, but without required
            if not isinstance(type_, basestring):
                for t in type_:
                    self._json_schema_key(key, dict(type=t), schema, False,
                        props, patternProps, addProps, requiredProps, **kwargs)
            # string, either any key or a regex
            elif type_ == 'string':
                if 'regex' in json_schema:
                    patternProps.setdefault(json_schema['regex'], []) \
                        .append((key, schema))
                else: addProps.append((key, schema))
            # boolean, let's be ncie and convert it to string
            elif type_ == 'boolean':
                patternProps.setdefault(r'^(true|false)$', []) \
                    .append((key, schema))
            # integer, let's be ncie and convert it to string (>= 0 and > 0 too)
            elif type_ == 'integer':
                if 'minimum' in json_schema:
                    minimum = json_schema['minimum']
                elif 'exclusiveMinimum' in json_schema:
                    minimum = json_schema['exclusiveMinimum'] + 1
                else: minimum = None
                patternProps.setdefault({
                        0: r'^([1-9][0-9]*|0)$',
                        1: r'^([1-9][0-9]*)$',
                    }.get(minimum, r'^(-?[1-9][0-9]*|0)$'), []) \
                        .append((key, schema))
            # ignore other cases
            # else:
            #     raise TypeError('key %r cannot be converted to JSON schema' % key)
        # a {'anyOf': [...]} schema, recursive call but without required
        elif keys == {'anyOf'}:
            if getattr(key, 'required', True):
                key = Optional(key)
            for item in json_schema['anyOf']:
                self._json_schema_key(key, item, schema, False,
                    props, patternProps, addProps, requiredProps, **kwargs)
        # a {'const': ...} or {'enum': ...} schema, goes to props
        elif keys == {'const'} or keys == {'enum'}:
            enum = json_schema.get('enum', (json_schema.get('const'),))
            for const in enum:
                # bool and int are nicely converted to string
                if isinstance(const, bool):
                    const = 'true' if const else 'false'
                elif isinstance(const, int): const = str(const)
                # rest is ignored
                elif not isinstance(const, basestring):
                    # raise TypeError('key %r is not a valid JSON schema key' % const)
                    return
                props.setdefault(const, []).append((key, schema))
                if required and len(enum) == 1: requiredProps.add(const)
        # else:
        #     raise TypeError('key %r cannot be converted to JSON schema' % key)

    def _json_schema_values(self, items, **kwargs):
        """
        Merges all values of a same key.
        Forbidden keys are treated differently
        """
        anyOf, notAnyOf = [], []
        for key, schema in items:
            if isinstance(key, Forbidden):
                notAnyOf.append(schema)
            else: anyOf.append(schema)

        anyOf = Or.merge_json_schemas(anyOf, **kwargs)
        notAnyOf = Or.merge_json_schemas(notAnyOf, **kwargs)
        # cannot match anything
        if notAnyOf == {} or notAnyOf is True: return False
        elif anyOf is None or anyOf is False: return False
        # no forbidden key
        elif notAnyOf is None or notAnyOf is False: return anyOf
        # merge normal keys and forbidden keys
        elif set(anyOf) == {'anyOf'}:
            return {'anyOf': anyOf['anyOf'], 'not': notAnyOf}
        else: return {'allOf': [anyOf], 'not': notAnyOf}


@schema_class('list')
class List(BaseSchema):
    """
    Represents an iterable python type (most often a list)
    """
    priority = ITERABLE

    def __init__(self, schema, *args,
        min_length=0, max_length=float('inf'), length=None, **kwargs):
        """
        If passed a list/tuple/set/forzenset, matches only this type.
        If passed a multiple values, matches any iterable type
        min_length, max_length and length control the size of the dict
        """
        super(List, self).__init__(**kwargs)
        if isinstance(schema, (list, tuple, set, frozenset)):
            self._type = type(schema)
            if len(schema) == 1:
                schema, = schema
                if isinstance(schema, BaseSchema): self._schema = schema
                else: self._schema = self._generate_cls('schema', schema)
            elif schema: self._schema = self._generate_cls('or', *schema)
            else: self._schema = self._generate_cls('any')
        else:
            self._type = (list, tuple, set, frozenset)
            if args: self._schema = self._generate_cls('or', schema, *args)
            elif isinstance(schema, BaseSchema): self._schema = schema
            else: self._schema = self._generate_cls('schema', schema)
        if length is not None:
            self._min_length = length
            self._max_length = length
        else:
            self._min_length = min_length
            self._max_length = max_length

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self._schema)

    def validate(self, data):
        """
        Validates the list, by checking its type, its length and its items
        """
        if not isinstance(data, self._type):
            message = "%r should be instance of %r" % (data, self._type)
            self._raise_error(message, data, SchemaUnexpectedTypeError)

        if not self._min_length <= len(data) <= self._max_length:
            message = "%r should have a length between %s and %s (is %s)" % (data, self._min_length, self._max_length, len(data))
            self._raise_error(message, data, SchemaWrongLengthError)

        schema = self._schema
        return type(data)(schema.validate(item) for item in data)

    def keys(self, item, comparable_keys, type_keys, global_keys):
        if type(self._type) is tuple:
            for t in self._type:
                type_keys.setdefault(t, []).append(item)
        else: type_keys.setdefault(self._type, []).append(item)

    def json_schema(self, schema_id=None, **kwargs):
        """
        Generates a JSON schema as {'type': 'array', 'items': ...}
        """
        if hasattr(self, '_json_schema'):
            return self._json_schema_aux(schema_id, self._json_schema)

        schema_dict = self._schema.json_schema(**kwargs)
        if schema_dict is not None:
            if schema_dict == {} or schema_dict is True:
                schema_dict = dict(type='array')
            else: schema_dict = dict(type='array', items=schema_dict)
            if self._min_length:
                schema_dict['minItems'] = self._min_length
            if self._max_length != float('inf'):
                schema_dict['maxItems'] = self._max_length
        return self._json_schema_aux(schema_id, schema_dict)


@schema_class('schema')
class Schema(BaseSchema):
    """
    Represents a generic schema.
    Will Generate a Dict or List if passed a dict or a list
    """
    def __init__(self, schema, **kwargs):
        super(Schema, self).__init__(**kwargs)
        flavor = _priority(schema)
        self.priority = getattr(schema, 'priority', flavor)
        if flavor == ITERABLE:
            self._flavor = VALIDATOR
            self._schema = self._generate_cls('list', schema)
        elif flavor == DICT:
            self._flavor = VALIDATOR
            self._schema = self._generate_cls('dict', schema)
        else:
            self._flavor = flavor
            self._schema = schema

        if hasattr(self._schema, 'reset') and not hasattr(self, 'reset'):
            self.reset = self._schema.reset

    def __repr__(self):
        return "%s(%r)" % (self.__class__.__name__, self._schema)

    def validate(self, data):
        """
        Validates the schema depending on its type
        """
        e = self._error
        schema = self._schema
        flavor = self._flavor
        # validators are just called
        if flavor == VALIDATOR:
            try:
                return self._schema.validate(data)
            except SchemaError as x:
                x.prepend(None, e)
                raise x
            except BaseException as x:
                message = "%r.validate(%r) raised %r" % (schema, data, x)
                return self._raise_error(message, data)
        # types are matched
        elif flavor == TYPE:
            if isinstance(data, schema) and not \
                (isinstance(data, bool) and schema is int):
                    return data
            else:
                message = "%r should be instance of %r" % (data, schema.__name__)
                return self._raise_error(message, data, SchemaUnexpectedTypeError)
        # callabled are called too
        elif flavor == CALLABLE:
            f = _callable_str(schema)
            try:
                if schema(data):
                    return data
            except SchemaError as x:
                x.prepend(None, e)
                raise x
            except BaseException as x:
                message = "%s(%r) raised %r" % (f, data, x)
                return self._raise_error(message, data, SchemaError)
            message = "%s(%r) should evaluate to True" % (f, data)
            return self._raise_error(message, data, SchemaError)
        # else it should be a comparable
        elif schema == data:
            return data
        else:
            message = "%r does not match %r" % (schema, data)
            return self._raise_error(message, data, SchemaError)

    def keys(self, item, comparable_keys, type_keys, global_keys):
        """
        Puts item in the right structure depending on the type of schema
        """
        schema = self._schema
        flavor = self._flavor
        if hasattr(schema, 'keys'):
            schema.keys(item, comparable_keys, type_keys, global_keys)
        elif flavor == TYPE:
            type_keys.setdefault(schema, []).append(item)
        elif flavor == COMPARABLE:
            comparable_keys.setdefault(schema, []).append(item)
        else: global_keys.append(item)

    def json_schema(self, schema_id=None, target=None, **kwargs):
        """
        Generate a JSON schema depending on the type of schema
        """
        if hasattr(self, '_json_schema'):
            return self._json_schema_aux(schema_id, self._json_schema)

        schema = self._schema
        flavor = _priority(schema)

        schema_dict = None
        # look for json_schema in the schema
        if hasattr(schema, 'json_schema'):
            schema_dict = schema.json_schema
            if callable(schema_dict):
                schema_dict = schema_dict(target=target, **kwargs)
            else: schema_dict = copy.deepcopy(schema_dict)
        # types are converted to the right {'type': ...}
        if flavor == TYPE:
            if issubclass(schema, bool):
                schema_dict = dict(type='boolean')
            elif issubclass(schema, int):
                schema_dict = dict(type='integer')
            elif issubclass(schema, float):
                schema_dict = dict(type='number')
            elif issubclass(schema, basestring):
                schema_dict = dict(type='string')
            elif issubclass(schema, dict):
                schema_dict = dict(type='object')
            elif issubclass(schema, (list, tuple, set, frozenset)):
                schema_dict = dict(type='array')
            elif schema is object:
                schema_dict = True
        # comparable are converted to {'const':...} or {'enum':[...]}
        elif flavor == COMPARABLE:
            if target == 'json_schema':
                schema_dict = dict(const=schema)
            else: schema_dict = dict(enum=[schema])
        # the rest is ignored
        return self._json_schema_aux(schema_id, schema_dict)


class Hook(Schema):
    """
    A hook for special actions on keys
    """
    def __init__(self, schema, required=False, **kwargs):
        """
        Takes:
        - schema: the schema to match as a key
        - required: if the key is required (default: False)
        - priority: the priority of the key (default: automatic)
        - handler: the function to replace handle
        """
        handler = kwargs.pop('handler', None)
        if handler: self.handle = handler
        self.priority = kwargs.pop('priority', _priority(schema) + 1)
        self.required = required
        super(Hook, self).__init__(schema, **kwargs)

    def handle (self, key, value, new, data):
        """Called when both the key and the value are matched
        Takes:
        - key: the transformed key
        - value: the transformed value
        - new: the new dict being built, can be edited
        - data: the data being processed
        Returns:
        - None to continue the matching of the key
        - False to stop the matching of the key and discard it
        - True to stop the matching of the key and save it"""
        return None

    def catch (self, key, error, new, data):
        """Called when the key is match bot not the value
        Takes:
        - key: the transformed key
        - error: the error when matching the value
        - new: the new dict being built, can be edited
        - data: the data being processed
        Returns:
        - None to continue the matching of the key
        - False to stop the matching of the key and discard it
        - True to raise the error"""
        return None

    def json_schema(self, **kwargs):
        """
        By default, this schema is ignored
        """
        return BaseSchema.json_schema(self, **kwargs)


@schema_class('optional')
class Optional(Hook):
    """
    Creates a an optional key for a dict
    """
    def __init__(self, schema, **kwargs):
        kwargs.setdefault('priority', _priority(schema) - 1)
        default = kwargs.pop("default", self._MARKER)
        super(Optional, self).__init__(schema, **kwargs)
        if default is not self._MARKER:
            if _priority(self._schema) != COMPARABLE:
                raise TypeError(
                    "Optional keys with defaults must have simple, "
                    "predictable values, like literal strings or ints. "
                    '"%r" is too complex.' % (self._schema,)
                )
            self.default = default

    def handle (self, *args):
        return True

    def catch (self, *args):
        return True

    def json_schema(self, **kwargs):
        """
        This schema is generated
        """
        return Schema.json_schema(self, **kwargs)


@schema_class('forbidden')
class Forbidden(Hook):
    """
    Creates a forbidden key for a dict
    """
    def handle(self, key, value, new, data):
        """
        Raises when matched
        """
        message = "Forbidden key encountered: %r in %r" % (key, data)
        self._raise_error(message, data, SchemaForbiddenKeyError)

    def json_schema(self, **kwargs):
        """
        This schema is generated, but its value will be used as a {'not': ...}
        """
        return Schema.json_schema(self, **kwargs)


@schema_class('clean')
class Clean(Hook):
    """
    Creates an optional key that will be discarded form the dict
    """
    def handle (self, *args):
        return False

    def json_schema(self, **kwargs):
        """
        This schema is generated
        """
        return Schema.json_schema(self, **kwargs)


@schema_class('const')
class Const(Schema):
    """
    Applies a schema but restores the original data
    """
    def validate(self, data):
        super(Const, self).validate(data)
        return data


@schema_class('not')
class Not(Schema):
    """
    Matches the contrary of a schema
    """
    def validate(self, data):
        try: super(Not, self).validate(data)
        except SchemaError: return data
        else:
            message = '%r matches forbidden value %r' % (data, self._schema)
            return self._raise_error(message, data, SchemaForbiddenValueError)

    def json_schema(self, schema_id=None, **kwargs):
        """
        Generates a JSON schema. consecutive 'not' are merged.
        """
        if hasattr(self, '_json_schema'):
            return self._json_schema_aux(schema_id, self._json_schema)

        schema_dict = super(Not, self).json_schema(**kwargs)
        if schema_dict is not None:
            if schema_dict == {}: schema_dict = False
            elif isinstance(schema_dict, bool): schema_dict = not schema_dict
            elif set(schema_dict) == {'not'}: schema_dict = schema_dict['not']
            else: schema_dict = {'not': schema_dict}
        return self._json_schema_aux(schema_id, schema_dict)


def _callable_str(callable_):
    if hasattr(callable_, "__name__"):
        return callable_.__name__
    return str(callable_)


def _plural_s(sized):
    return "s" if len(sized) > 1 else ""
