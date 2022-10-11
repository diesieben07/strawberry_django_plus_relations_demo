from django.contrib import admin
from . import models

admin.site.register(
    (models.ModelA, models.ModelB, models.ChildrenOfA, models.HasRelations)
)
