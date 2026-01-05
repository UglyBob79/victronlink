import os
import yaml

class ConfigParser:
    def __init__(self, app, folder):
        base = os.path.dirname(os.path.abspath(__file__))
        self.folder = os.path.join(base, folder)
        self.app = app

    def load_all(self):
        configs = []

        for fname in os.listdir(self.folder):
            if not fname.endswith((".yaml", ".yml")):
                continue

            path = os.path.join(self.folder, fname)

            try:
                with open(path, "r") as f:
                    data = yaml.safe_load(f)

                normalized = self.normalize(data, fname)
                configs.append(normalized)

            except Exception as e:
                # Do NOT stop everything — just log the error
                self.app.log(f"[ConfigParser] Error in {fname}: {e}", level="ERROR")
                continue

        return configs

    def normalize(self, data, filename):
        """Ensure each config has the mandatory structure."""
        required_fields = ["type", "device_info", "entities"]

        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing '{field}' in {filename}")

        # Ensure 'setup' always exists, even if empty
        if "setup" not in data:
            data["setup"] = []

        # Normalize identifiers → list
        if isinstance(data["device_info"].get("identifiers"), str):
            data["device_info"]["identifiers"] = [data["device_info"]["identifiers"]]

        # Ensure entities is a list
        if not isinstance(data["entities"], list):
            raise ValueError(f"'entities' must be a list in {filename}")

        return data