from unittest import TestCase
#from django.test import TestCase
from decimal import Decimal
from orders.models import Ingredient, IngredientCost


class SimpleCalculationTest(TestCase):
    def test_calculate_total_cost(self):
        #объекты для теста
        ingredient = Ingredient.objects.create(name='Сахар', unit='кг')
        cost = IngredientCost.objects.create(
            ingredient=ingredient,
            cost_per_unit=Decimal('80.50')
        )

        #  целое количество
        result1 = cost.calculate_total_cost(2)
        self.assertEqual(result1, Decimal('161.00'))

        # дробное количество
        result2 = cost.calculate_total_cost(Decimal('1.5'))
        self.assertEqual(result2, Decimal('120.75'))

        #  тип результата
        self.assertIsInstance(result1, Decimal)