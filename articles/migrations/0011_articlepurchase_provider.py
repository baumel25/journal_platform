# Adds the payment-provider choice (MTN MoMo / Orange Money) to ArticlePurchase

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('articles', '0010_article_view_count_download_count'),
    ]

    operations = [
        migrations.AddField(
            model_name='articlepurchase',
            name='provider',
            field=models.CharField(choices=[('mtn_momo', 'MTN Mobile Money'), ('orange_money', 'Orange Money')], default='mtn_momo', help_text='Payment method the reader chose', max_length=20),
        ),
    ]
