import strawberry_django_plus.optimizer
from strawberry_django_plus import gql

import demonstration.schema

schema = gql.Schema(
    query=demonstration.schema.Query,
    extensions=(
        strawberry_django_plus.optimizer.DjangoOptimizerExtension,
    )
)
