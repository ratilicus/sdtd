'''
Simple Validation Form based on jsonschema
by: Adam Dybczak (RaTilicus)

Usage:
class LoginForm(SchemaForm)
    schema={
        'type': 'object',
        'properties': {
            'username': {'type': 'string', 'minLength': 1},
            'password': {'type': 'string', 'minLength': 4},
        },
        'required': ['username', 'password'],
    }
    flatten=['username', 'password']
    
    
form = LoginForm({'username': ['some@email.com'], 'password': ['some password']})
if form.is_valid():
    print form.cleaned_data  # -> {'username': 'some@email.com', 'password': 'some password'}
else:
    print form.errors  # -> [('field name', 'validation error message'), ...]

'''

from jsonschema import Draft4Validator

__all__ = ['SchemaForm']

class SchemaForm(object):
    ''' Generates Form based on schema

    - schema: jsonschema compatible schema
    - flatten: list of fields to flatten before running through form validation
                flattening grabs the first evement in a value if it's a list or tuple
                ie. {'username': ['some@email.com']} -> {'username': 'some@email.com'}
    '''
    schema = {}
    flatten = []
    def __init__(self, data, *args, **kwargs):
        self.cleaned_data = {}
        self.errors = []

        # get only the fields in the schema and flatten where specified
        self.data = {}
        for k, v in self.schema['properties'].items():
            if k in data:
                kv = data[k]
                if isinstance(kv, (list, tuple)) and k in self.flatten:
                    self.data[k] = kv[0]
                else:
                    self.data[k] = kv
            elif 'default' in v:
                self.data[k] = v['default']

        # validate data based on schema
        validator = Draft4Validator(self.schema)
        self.errors = [
            ((e.message.split("'", 2)[1], u'Required Field')
             if e.validator == 'required' else
             ('.'.join(e.path), e.message))
            for e in validator.iter_errors(self.data)]

        if not self.errors:
            self.cleaned_data = self.clean(self.data, data, *args, **kwargs)
            
    def clean(self, data, org_data, *args, **kwargs):
        '''
        clean the data
        - override this to do:
            - custom validation (add values to self.errors to invalidate form)
            - value conversion (modify return data)
        '''
        return data

    def is_valid(self):
        return not bool(self.errors)


