import time
from .static_policy import StaticPolicy
from .dynamic_policy import DynamicPolicy

class DelegationHandler:
    def __init__(self):
        self.static_policy = StaticPolicy()
        self.dynamic_policy = DynamicPolicy()

    def validate_delegation(
        self,
        from_agent_id: str,
        to_agent_id: str,
        requested_cap: str,
        delegated_user: dict = None
    ) -> dict:
        # 检查委托方是否有委托权限
        from_agent_caps = self.static_policy.get_agent_capabilities(from_agent_id)
        if "delegate:*" not in from_agent_caps:
            return {
                "authorized": False,
                "reason": "DELEGATION_NOT_ALLOWED",
                "effective_permissions": []
            }

        # 检查被委托方是否有对应的能力
        to_agent_has_cap = self.static_policy.check_static_capability(to_agent_id, requested_cap)
        if not to_agent_has_cap:
            return {
                "authorized": False,
                "reason": "TARGET_AGENT_CAPABILITY_MISSING",
                "effective_permissions": []
            }

        # 如果有委托用户，计算有效权限
        if delegated_user:
            user_perms = self.dynamic_policy.get_user_permissions(delegated_user["user_id"])
            to_agent_caps = self.static_policy.get_agent_capabilities(to_agent_id)
            effective = self.dynamic_policy.calculate_effective_permissions(to_agent_caps, user_perms)
            
            # 检查请求的能力是否在有效权限内
            has_effective = self.static_policy._match_capability(requested_cap, effective)
            if not has_effective:
                return {
                    "authorized": False,
                    "reason": "USER_PERMISSION_MISSING",
                    "effective_permissions": effective
                }
            return {
                "authorized": True,
                "reason": "DELEGATION_ALLOWED",
                "effective_permissions": effective
            }
        
        return {
            "authorized": True,
            "reason": "DELEGATION_ALLOWED",
            "effective_permissions": [requested_cap]
        }

    def extend_trust_chain(self, existing_chain: list, from_agent_id: str, to_agent_id: str) -> list:
        new_chain = existing_chain.copy()
        new_chain.append({
            "agent_id": from_agent_id,
            "agent_type": "ai_agent",
            "action": "delegate",
            "target_agent_id": to_agent_id,
            "timestamp": int(time.time())
        })
        return new_chain
