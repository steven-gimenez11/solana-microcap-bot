from config import settings


class PaperExecutor:
    """Thin adapter over Store's persistent paper portfolio engine."""

    def __init__(self, store):
        self.store = store

    def enter(self, token, amount_usd=None, reason="candidate"):
        amount = min(float(amount_usd or settings.max_position_usd), settings.max_position_usd)
        created = self.store.create_paper_trade(token.get("address"), token, reason=reason, amount_usd=amount)
        return {"mode": "DRY_RUN", "created": created, "amount_usd": amount, "address": token.get("address")}

    def update(self, token):
        return self.store.update_paper_trade(token.get("address"), token)
