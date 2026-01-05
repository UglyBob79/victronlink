import logging

# TODO Can we change the data structure to be ONE?
class Registry:
    def __init__(self, app):
        self.app = app

        # A global registry
        self.registry = {}
        # A special registry, with sub-registries per parent key
        self.parent_registry = {}

    def add(self, key, value, parent=None):
        self.app.log(f"Add {key}->{value} to parent {parent}")
        if parent:
            if parent not in self.parent_registry:
                self.parent_registry[parent] = {}
            self.parent_registry[parent][key] = value
        else:
            self.registry[key] = value

    def resolve_placeholders(self, value, parent=None):
        """
        Resolve placeholders using registry or a specific parent registry.
        """
        if parent:
            mapping = self.parent_registry.get(parent, {})
        else:
            mapping = self.registry

        return self.resolve_placeholders_recursive(value, mapping)

    def resolve_placeholders_recursive(self, value, mapping=None):
        """
        Resolving placeholders in a string using a mapper. This
        one uses recursion to handle that string has lists or dicts
        internally.
        """
        mapping = mapping or self.registry

        if isinstance(value, str):
            return value.format_map(SafeDict(mapping))

        elif isinstance(value, list):
            return [self.resolve_placeholders_recursive(v, mapping) for v in value]

        elif isinstance(value, dict):
            return {k: self.resolve_placeholders_recursive(v, mapping) for k, v in value.items()}

        else:
            # Numbers, booleans, None, etc
            return value

    def print_reg(self):
        self.app.log(f"Registry: {self.registry}")
        self.app.log(f"Parent Registry: {self.parent_registry}")

class SafeDict(dict):
    def __missing__(self, key):
        return '{' + key + '}'