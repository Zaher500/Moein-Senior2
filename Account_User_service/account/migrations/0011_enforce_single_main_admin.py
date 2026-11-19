
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0010_seed_admin_permissions"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                CREATE UNIQUE INDEX unique_main_admin_role
                ON `Account` (
                    (CASE
                        WHEN `role` = 'MAIN_ADMIN' THEN 1
                        ELSE NULL
                    END)
                );
            """,
            reverse_sql="""
                DROP INDEX unique_main_admin_role ON `Account`;
            """,
        ),
    ]
