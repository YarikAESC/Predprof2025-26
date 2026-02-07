from unittest import TestCase
from orders.models import ComboSet
from decimal import Decimal
class Total_Paid_Test(TestCase):
    def test_total_paid(self):

        combo = ComboSet(total_price=Decimal('1000.00'), max_orders=5)
        self.assertEqual(combo.total_paid, Decimal('5000.00'))

        combo2 = ComboSet(total_price=Decimal('500.50'), max_orders=2)
        self.assertEqual(combo2.total_paid, Decimal('1001.00'))