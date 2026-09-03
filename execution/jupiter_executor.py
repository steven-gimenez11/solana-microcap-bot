# execution/jupiter_executor.py
"""
Jupiter executor placeholder. Intentionally disabled: must not request or use any private keys.
This file is prepared for future integration only.
"""
class JupiterExecutor:
    def __init__(self, client=None):
        self.enabled = False
        self.client = client

    def execute_order(self, *args, **kwargs):
        raise RuntimeError("Jupiter executor is disabled in this DRY-RUN version")
