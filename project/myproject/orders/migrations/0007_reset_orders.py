
from django.db import migrations

def reset_orders(apps, schema_editor):
    Order = apps.get_model('orders', 'Order')
    Order.objects.all().delete()

class Migration(migrations.Migration):
    dependencies = [
       ('orders', '0006_alter_order_status_transaction'),
    ]
    
    operations = [
        migrations.RunPython(reset_orders),
    ]
