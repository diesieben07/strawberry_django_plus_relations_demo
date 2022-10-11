from strawberry_django_plus import gql
import typing as tp
from . import models


@gql.django.type(models.ModelA)
class TypeA:
    name_a: str
    count_a: int

    @staticmethod
    @gql.django.field(prefetch_related='children')
    def children_names(root: models.ModelA) -> list[str]:
        return [child.name for child in root.children.all()]


@gql.django.type(models.ModelB)
class TypeB:
    name_b: str


AOrB = gql.union('AOrB', types=(TypeA, TypeB))


@gql.django.type(models.HasRelations)
class HasRelationsType:
    @staticmethod
    @gql.django.field(select_related=('ref_a', 'ref_b'), only=('ref_a', 'ref_b', 'ref_a__id', 'ref_b__id'))
    def ref(root: models.HasRelations) -> AOrB | None:
        return root.ref_a or root.ref_b

    ref_a: TypeA | None = gql.django.field()

    @staticmethod
    @gql.django.field(only='ref_a__count_a')
    def count(root: models.HasRelations) -> int:
        return root.ref_a.count_a if root.ref_a else 0


@gql.type
class Query:
    @gql.django.field
    def has_relations(self) -> list[HasRelationsType]:
        return models.HasRelations.objects.all()
