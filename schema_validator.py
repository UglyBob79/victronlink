class SchemaError(Exception):
    pass

def _noop(*args, **kwargs):
    pass

class SchemaValidator:
    @staticmethod
    def validate(data, schema, *, path="root", log=None):
        log = log or _noop

        if not isinstance(schema, dict):
            raise RuntimeError("Schema must be a dict")
        SchemaValidator._validate_node(data, schema, path, log)

    @staticmethod
    def _validate_node(data, schema, path, log):
        log(f"Validating {path}")

        if not isinstance(data, dict):
            raise TypeError(f"{path} must be a dict")

        for key, rules in schema.items():
            if rules.get("required") and key not in data:
                raise ValueError(f"Missing required field {path}.{key}")

        for key, value in data.items():
            if key not in schema:
                raise ValueError(f"Unknown field {path}.{key}")

            rules = schema[key]
            expected_type = rules.get("type")

            if expected_type and not isinstance(value, expected_type):
                raise TypeError(
                    f"{path}.{key} must be {expected_type}, got {type(value)}"
                )

            if isinstance(value, dict) and "schema" in rules:
                SchemaValidator._validate_node(
                    value, rules["schema"], f"{path}.{key}", log
                )

            if isinstance(value, list):
                elem_schema = rules.get("elements")
                if elem_schema:
                    for i, item in enumerate(value):
                        if not isinstance(item, dict):
                            raise TypeError(
                                f"{path}.{key}[{i}] must be a dict"
                            )
                        SchemaValidator._validate_node(
                            item, elem_schema, f"{path}.{key}[{i}]", log
                        )