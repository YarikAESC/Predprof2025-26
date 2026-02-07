from unittest import TestCase
from orders.models import ComboSet
class Remaining_Orders_Test(TestCase):
    def test_Remaining_orders(self):


        combo = ComboSet(max_orders=9, orders_used=7)
        self.assertEqual(combo.remaining_orders, 2)

        combo2 = ComboSet(max_orders=10, orders_used=3)
        self.assertEqual(combo2.remaining_orders, 7)

        combo3 = ComboSet(max_orders=5, orders_used=5)
        self.assertEqual(combo3.remaining_orders, 0)