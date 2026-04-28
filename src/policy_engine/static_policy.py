import yaml
import os

class StaticPolicy:
    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "config", "agents.yaml"
        )
        self.agent_config = self._load_config()

    def _load_config(self) -> dict:
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        return {}

    def get_agent_capabilities(self, agent_id: str) -> list:
        return self.agent_config.get(agent_id, {}).get("capabilities", [])

    def get_agent_info(self, agent_id: str) -> dict:
        return self.agent_config.get(agent_id, {})

    def check_static_capability(self, agent_id: str, requested_cap: str) -> bool:
        capabilities = self.get_agent_capabilities(agent_id)
        return self._match_capability(requested_cap, capabilities)

    def _match_capability(self, requested: str, capabilities: list) -> bool:
        for cap in capabilities:
            if cap == "*:*":
                return True
            if cap == requested:
                return True
            if cap.endswith(":*"):
                prefix = cap[:-2]
                if requested.startswith(prefix):
                    return True
        return False
