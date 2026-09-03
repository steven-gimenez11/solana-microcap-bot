class PaperExecutor:
    def enter(self, token, amount_usd=1.0):
        return {"mode":"DRY_RUN","amount_usd":amount_usd,"entry_price":token.get("price_usd"),"address":token.get("address")}