from django.db import migrations


ADMIN_PERMISSION_CODES = [
    "VIEW_STUDENTS",
    "EDIT_STUDENTS",
    "DELETE_STUDENTS",
    "VIEW_COURSES",
    "CREATE_COURSES",
    "EDIT_COURSES",
    "DELETE_COURSES",
]


def seed_admin_permissions(apps, schema_editor):
    AdminPermission = apps.get_model("account", "AdminPermission")
    db_alias = schema_editor.connection.alias

    for code in ADMIN_PERMISSION_CODES:
        AdminPermission.objects.using(db_alias).get_or_create(
            code=code
        )


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0009_adminpermission_user_admin_permissions"),
    ]

    operations = [
        migrations.RunPython(
            seed_admin_permissions,
            migrations.RunPython.noop,
        ),
    ]
