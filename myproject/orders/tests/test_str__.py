from unittest import TestCase
from decimal import Decimal

from orders.models import Ingredient, IngredientCost


class Calculation_Test(TestCase):
    def setUp(self):
        self.ingredient = Ingredient.objects.create(name='Тест', unit='кг')
        self.cost = IngredientCost.objects.create(
            ingredient=self.ingredient,
            cost_per_unit=Decimal('100.00')
        )

    def test_calculate_total_cost_decimal_quantity(self):
        #дробное количество
        result = self.cost.calculate_total_cost(Decimal('2.5'))
        expected = Decimal('250.00')
        self.assertEqual(result, expected)