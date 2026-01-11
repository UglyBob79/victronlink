import os
import yaml

from schema_validator import SchemaValidator, SchemaError
from schemas.hardware import HARDWARE_SCHEMA

class ConfigParser:
    def __init__(self, app, folder):
        base = os.path.dirname(os.path.abspath(__file__))
        self.folder = os.path.join(base, folder)
        self.app = app

    def load_all(self):
        self.app.log("Loading configs...")
        
        configs = []

        for fname in os.listdir(self.folder):
            if not fname.endswith((".yaml", ".yml")):
                continue

            path = os.path.join(self.folder, fname)

            try:
                with open(path, "r") as f:
                    data = yaml.safe_load(f)

                if not data:
                    raise ValueError("Empty config file")

                # Validate
                SchemaValidator.validate(
                    data,
                    HARDWARE_SCHEMA,
                    path=fname,
                    log=self.app.log
                )

                # Normalize (very light!)
                normalized = self.normalize(data)

                configs.append(normalized)

            except SchemaError as e:
                self.app.log(
                    f"[ConfigParser] Schema error in {fname}: {e}",
                    level="ERROR",
                )

            except Exception as e:
                self.app.log(
                    f"[ConfigParser] Error loading {fname}: {e}",
                    level="ERROR",
                )

        return configs

    def normalize(self, data):
        """
        Perform light normalization after schema validation.
        No structural changes.
        """
        # Ensure setup exists
        data.setdefault("setup", [])

        # Ensure device_info.identifiers is a list
        identifiers = data.get("device_info", {}).get("identifiers")
        if isinstance(identifiers, str):
            data["device_info"]["identifiers"] = [identifiers]

        return data