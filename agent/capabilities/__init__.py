
from agent.capabilities.llm import LLMCapability
from agent.config.prompts import get_labels

class CapabilityRouter:

    def __init__(self, config: dict):
        self.config = config
        self._capabilities = {}
        self._init_capabilities()

    def _init_capabilities(self):
        self._capabilities["llm"] = LLMCapability(self.config)

    def get(self, name: str):
        return self._capabilities.get(name)

    def execute(self, capability_name: str, **kwargs):
        cap = self._capabilities.get(capability_name)
        if not cap:
            EL = get_labels("errors.llm", self.config.get("language", "zh"))
            raise ValueError(EL["unknown_capability"].format(name=capability_name))
        return cap.execute(**kwargs)
