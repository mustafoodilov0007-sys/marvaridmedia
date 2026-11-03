"""To'lovlar: Click/Payme (Telegram Payments), Stars, chek — summa tekshiruvi, takroriy to'lovdan himoya, daromad hisobi."""

import os
import time
import unittest

from tests.harness import cleanup, make_app, message, press


class Pay(unittest.TestCase):
    def setUp(self):
        os.environ["PROVIDER_TOKEN"] = "398062629:TEST:999999999_F91D8F69C042267444B74CC0B3C747757EB0E065"
        self.app = make_app()
        from app.core import process_update
        self.run = process_update
        db = self.app.db
        for pl in db.list_plans():
            db.deactivate_plan(pl["id"])
        self.plan = db.add_plan(30, 10000, 50)

    def tearDown(self):
        os.environ.pop("PROVIDER_TOKEN", None)
        cleanup(self.app)

    def invoices(self):
        return [(a, k) for n, a, k in self.app.bot.sent if n == "send_invoice"]

    def pre_checkout(self, uid, payload, amount, currency="UZS"):
        self.app.bot.sent.clear()
        self.run(self.app, {"update_id": 1, "pre_checkout_query": {"id": "pq", "from": {"id": uid, "first_name": "A"},
                                                                    "currency": currency, "total_amount": amount, "invoice_payload": payload}})
        return [a for n, a, k in self.app.bot.sent if n == "answer_pre_checkout_query"][-1]

    def paid(self, uid, payload, amount, charge="CH1"):
        self.run(self.app, {"update_id": 1, "message": {"message_id": 1, "date": 0, "from": {"id": uid, "first_name": "A"},
                                                         "chat": {"id": uid, "type": "private"},
                                                         "successful_payment": {"currency": "UZS", "total_amount": amount, "invoice_payload": payload,
                                                                                "telegram_payment_charge_id": charge, "provider_payment_charge_id": "PR1"}}})

    def test_invoice_has_provider_token_and_tiyin(self):
        self.run(self.app, message(5, "/start"))
        self.run(self.app, press(5, f"pr:inv:{self.plan}"))
        (a, k), = self.invoices()
        self.assertEqual(k["currency"], "UZS")
        self.assertEqual(k["provider_token"], self.app.config.provider_token)
        self.assertEqual(a[4], [{"label": "Premium 1 oy", "amount": 1000000}])    # 10 000 so'm = 1 000 000 tiyin

    def test_full_payment_flow_and_idempotency(self):
        self.run(self.app, message(5, "/start"))
        payload = f"premp:{self.plan}:5"
        self.assertEqual(self.pre_checkout(5, payload, 1000000)[1], True)
        self.paid(5, payload, 1000000)
        self.assertGreater(self.app.db.premium_until(5), time.time() + 29 * 86400)
        p = self.app.db.q1("SELECT * FROM payments WHERE user_id=5")
        self.assertEqual((p["method"], p["amount"], p["currency"], p["status"]), ("provider", 10000, "UZS", "approved"))
        until = self.app.db.premium_until(5)
        self.paid(5, payload, 1000000)                          # Telegram qayta yuborsa — ikkinchi marta berilmaydi
        self.assertEqual(self.app.db.premium_until(5), until)
        self.assertEqual(self.app.db.val("SELECT COUNT(*) FROM payments WHERE user_id=5"), 1)
        from app import analytics
        self.assertEqual(analytics.build(self.app.db)["revenue"][-1]["premium_uzs"], 10000)

    def test_pre_checkout_rejects_bad_requests(self):
        ok = f"premp:{self.plan}:5"
        self.assertFalse(self.pre_checkout(5, ok, 999999)[1])             # summa mos emas
        self.assertFalse(self.pre_checkout(6, ok, 1000000)[1])            # boshqa odamning to'lovi
        self.assertFalse(self.pre_checkout(5, ok, 1000000, "USD")[1])     # noto'g'ri valyuta
        self.assertFalse(self.pre_checkout(5, "premp:9999:5", 1000000)[1])  # tarif yo'q
        self.app.db.deactivate_plan(self.plan)
        self.assertFalse(self.pre_checkout(5, ok, 1000000)[1])            # tarif o'chirilgan

    def test_disabled_without_token_or_when_toggled_off(self):
        self.app.set_setting("premium_provider", "")
        self.run(self.app, message(5, "/start"))
        self.run(self.app, press(5, f"pr:inv:{self.plan}"))
        self.assertEqual(self.invoices(), [])
        self.assertFalse(self.pre_checkout(5, f"premp:{self.plan}:5", 1000000)[1])
        self.app.set_setting("premium_provider", "1")
        self.app.config.provider_token = ""
        self.assertFalse(self.pre_checkout(5, f"premp:{self.plan}:5", 1000000)[1])

    def test_plan_menu_offers_provider_first(self):
        self.run(self.app, message(5, "/start"))
        self.run(self.app, press(5, f"pr:plan:{self.plan}"))
        data = [b.get("callback_data") for n, a, k in self.app.bot.sent if n == "edit_message_text"
                for x in list(a) + list(k.values()) if isinstance(x, dict) and "inline_keyboard" in x for row in x["inline_keyboard"] for b in row]
        self.assertEqual(data[0], f"pr:inv:{self.plan}")


if __name__ == "__main__":
    unittest.main()
