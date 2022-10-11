from collections import defaultdict
import contextvars
import dataclasses
from typing import (
    Any,
    Callable,
    Collection,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    cast,
)

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.db import models
from django.db.models import Prefetch
from django.db.models.constants import LOOKUP_SEP
from django.db.models.fields.reverse_related import (
    ManyToManyRel,
    ManyToOneRel,
    OneToOneRel,
)
from django.db.models.manager import BaseManager
from django.db.models.query import QuerySet
from graphql.language.ast import OperationType
from graphql.type.definition import GraphQLResolveInfo, get_named_type
from strawberry.extensions.base_extension import Extension
from strawberry.lazy_type import LazyType
from strawberry.schema.schema import Schema
from strawberry.types.execution import ExecutionContext
from strawberry.types.info import Info
from strawberry.types.nodes import InlineFragment, Selection, convert_selections
from strawberry.types.types import TypeDefinition
from strawberry.utils.await_maybe import AwaitableOrValue
from strawberry_django.fields.types import resolve_model_field_name
from typing_extensions import TypeAlias, assert_never, assert_type

from strawberry_django_plus.descriptors import ModelProperty
from strawberry_django_plus.relay import Connection, Edge, NodeType
from strawberry_django_plus.utils import resolvers
from strawberry_django_plus.utils.inspect import (
    PrefetchInspector,
    get_django_type,
    get_model_fields,
    get_possible_type_definitions,
    get_selections,
)
from strawberry_django_plus.utils.typing import TypeOrSequence
from strawberry_django_plus.optimizer import OptimizerStore, OptimizerConfig


def gql_django_optimize_relations(optimize_relations: Collection[str]):
    def apply(field):
        setattr(field, 'optimize_relations', optimize_relations)
        return field
    return apply


def custom_get_model_hints(
    model: Type[models.Model],
    schema: Schema,
    type_def: TypeDefinition,
    selection: Selection,
    *,
    info: GraphQLResolveInfo,
    config: Optional["OptimizerConfig"] = None,
    prefix: str = "",
    model_cache: Optional[Dict[Type[models.Model], List[Tuple[int, "OptimizerStore"]]]] = None,
    level: int = 0,
) -> "OptimizerStore | None":
    store = OptimizerStore()
    model_cache = model_cache or {}
    typename = schema.config.name_converter.from_object(type_def)

    # In case this is a relay field, find the selected edges/nodes, the selected fields
    # are actually inside edges -> node selection...
    if type_def.concrete_of and issubclass(type_def.concrete_of.origin, Connection):
        n_type = type_def.type_var_map[NodeType]
        if isinstance(n_type, LazyType):
            n_type = n_type.resolve_type()

        n_type_def = cast(TypeDefinition, n_type._type_definition)  # type:ignore

        for edges in get_selections(selection, typename=typename).values():
            if edges.name != "edges":
                continue

            e_type = Edge._type_definition.resolve_generic(Edge[n_type])  # type:ignore
            e_typename = schema.config.name_converter.from_object(e_type._type_definition)
            for node in get_selections(edges, typename=e_typename).values():
                if node.name != "node":
                    continue

                new_store = custom_get_model_hints(
                    model=model,
                    schema=schema,
                    type_def=n_type_def,
                    selection=node,
                    info=info,
                    config=config,
                    prefix=prefix,
                    model_cache=model_cache,
                    level=level,
                )
                if new_store is not None:
                    store |= new_store

        return store

    fields = {schema.config.name_converter.get_graphql_name(f): f for f in type_def.fields}
    model_fields = get_model_fields(model)

    dj_type = get_django_type(type_def.origin)
    if (
        dj_type is None
        or not issubclass(model, dj_type.model)
        or getattr(dj_type, "disable_optimization", False)
    ):
        return None

    dj_type_store = getattr(dj_type, "store", None)
    if dj_type_store:
        store |= dj_type_store

    # Make sure that the model's pk is always selected when using only
    pk = model._meta.pk
    if pk is not None:
        store.only.append(pk.attname)

    for f_selection in get_selections(selection, typename=typename).values():
        field = fields.get(f_selection.name, None)
        if not field:
            continue

        # Do not optimize the field if the user asked not to
        if getattr(field, "disable_optimization", False):
            continue

        # Add annotations from the field if they exist
        field_store = getattr(field, "store", None)
        if field_store is not None:
            store |= field_store.with_prefix(prefix, info=info) if prefix else field_store

        # Then from the model property if one is defined
        model_attr = getattr(model, field.python_name, None)
        if model_attr is not None and isinstance(model_attr, ModelProperty):
            attr_store = model_attr.store
            store |= attr_store.with_prefix(prefix, info=info) if prefix else attr_store

        # Lastly, from the django field itself
        model_fieldnames: Collection[str] = getattr(field, 'optimize_relations', None)
        if model_fieldnames is None:
            model_fieldnames = (getattr(field, "django_name", field.python_name), )
        for model_fieldname in model_fieldnames:
            model_field = model_fields.get(model_fieldname, None)
            if model_field is None:
                continue
            path = f"{prefix}{model_fieldname}"

            if isinstance(model_field, (models.ForeignKey, OneToOneRel)):
                store.only.append(path)
                store.select_related.append(path)

                # If adding a reverse relation, make sure to select its pointer to us,
                # or else this might causa a refetch from the database
                if isinstance(model_field, OneToOneRel):
                    remote_field = model_field.remote_field
                    store.only.append(f"{path}{LOOKUP_SEP}{resolve_model_field_name(remote_field)}")

                for f_type_def in get_possible_type_definitions(field.type):
                    f_model = model_field.related_model
                    f_store = custom_get_model_hints(
                        f_model,
                        schema,
                        f_type_def,
                        f_selection,
                        info=info,
                        config=config,
                        model_cache=model_cache,
                        level=level + 1,
                    )
                    if f_store is not None:
                        model_cache.setdefault(f_model, []).append((level, f_store))
                        store |= f_store.with_prefix(path, info=info)
            elif isinstance(model_field, GenericForeignKey):
                # There's not much we can do to optimize generic foreign keys regarding
                # only/select_related because they can be anything. Just prefetch_related them
                store.prefetch_related.append(model_fieldname)
            elif isinstance(
                model_field, (models.ManyToManyField, ManyToManyRel, ManyToOneRel, GenericRelation)
            ):
                f_types = list(get_possible_type_definitions(field.type))
                if len(f_types) > 1:
                    # This might be a generic foreign key. In this case, just prefetch it
                    store.prefetch_related.append(model_fieldname)
                elif len(f_types) == 1:
                    remote_field = model_field.remote_field
                    remote_model = remote_field.model
                    f_store = custom_get_model_hints(
                        remote_model,
                        schema,
                        f_types[0],
                        f_selection,
                        info=info,
                        config=config,
                        model_cache=model_cache,
                        level=level + 1,
                    )

                    if f_store is not None:
                        if (
                            (config is None or config.enable_only)
                            and f_store.only
                            and not isinstance(remote_field, ManyToManyRel)
                        ):
                            # If adding a reverse relation, make sure to select its pointer to us,
                            # or else this might causa a refetch from the database
                            if isinstance(model_field, GenericRelation):
                                f_store.only.append(model_field.object_id_field_name)
                                f_store.only.append(model_field.content_type_field_name)
                            else:
                                f_store.only.append(remote_field.attname or remote_field.name)

                        path_lookup = f"{path}{LOOKUP_SEP}"
                        if store.only and f_store.only:
                            extra_only = [o for o in store.only or [] if o.startswith(path_lookup)]
                            store.only = [o for o in store.only if o not in extra_only]
                            f_store.only.extend(o[len(path_lookup) :] for o in extra_only)

                        if store.select_related and f_store.select_related:
                            extra_sr = [
                                o for o in store.select_related or [] if o.startswith(path_lookup)
                            ]
                            store.select_related = [
                                o for o in store.select_related if o not in extra_sr
                            ]
                            f_store.select_related.extend(o[len(path_lookup) :] for o in extra_sr)

                        model_cache.setdefault(remote_model, []).append((level, f_store))

                        # We need to use _base_manager here instead of _default_manager because we
                        # are getting related objects, and not querying it directly
                        f_qs = f_store.apply(
                            remote_model._base_manager.all(),  # type:ignore
                            info=info,
                            config=config,
                        )
                        f_prefetch = Prefetch(path, queryset=f_qs)
                        f_prefetch._optimizer_sentinel = _sentinel  # type:ignore
                        store.prefetch_related.append(f_prefetch)
            else:
                store.only.append(path)

    # DJango keeps track of known fields. That means that if one model select_related or
    # prefetch_related another one, and later another one select_related or prefetch_related the
    # model again, if the used fields there where not optimized in this call django would have
    # to fetch those again. By mergint those with us we are making sure to avoid that
    for inner_level, inner_store in model_cache.get(model, []):
        if inner_level > level and inner_store:
            # We only want the only/select_related from this. prefetch_related is something else
            store.only.extend(inner_store.only)
            store.select_related.extend(inner_store.select_related)

    return store
