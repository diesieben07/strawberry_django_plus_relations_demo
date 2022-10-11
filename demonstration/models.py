from django.db import models


class ModelA(models.Model):
    name_a = models.TextField()
    count_a = models.IntegerField()


class ChildrenOfA(models.Model):
    name = models.TextField()
    parent = models.ForeignKey(ModelA, related_name='children', on_delete=models.CASCADE)


class ModelB(models.Model):
    name_b = models.TextField()


class HasRelations(models.Model):
    ref_a = models.ForeignKey(ModelA, null=True, on_delete=models.CASCADE)
    ref_b = models.ForeignKey(ModelB, null=True, on_delete=models.CASCADE)
