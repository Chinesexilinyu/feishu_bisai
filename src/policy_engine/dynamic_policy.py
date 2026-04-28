import yaml
import os

class DynamicPolicy:
    def __init__(self, user_perm_path: str = None):
        self.user_perm_path = user_perm_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config", "users.yaml"
        )
        self.user_permissions = self._load_config()

    def _load_config(self) -> dict:
        if os.path.exists(self.user_perm_path):
            with open(self.user_perm_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        return {}

    def get_user_permissions(self, user_id: str) -> list:
        return self.user_permissions.get(user_id, {}).get("permissions", [])

    def calculate_effective_permissions(self, agent_capabilities: list, user_permissions: list) -> list:
        effective = []
        for cap in agent_capabilities:
            if cap.endswith(":*"):
                prefix = cap[:-2]
                matching = [p for p in user_permissions if p.startswith(prefix)]
                effective.extend(matching)
            elif cap in user_permissions:
                effective.append(cap)
        return list(set(effective))
