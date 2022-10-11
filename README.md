Demonstration for https://github.com/blb-ventures/strawberry-django-plus/issues/131

Observe the difference in SQL queries, only the 2nd case is properly optimized.

1. Querying on `ref`:
```graphql
query {
  hasRelations {
    ref {
      ...on TypeA {
        nameA
      }
    }
  }
}
```

```sql
SELECT "demonstration_hasrelations"."id",
       "demonstration_hasrelations"."ref_a_id",
       "demonstration_hasrelations"."ref_b_id",
       "demonstration_modela"."id",
       "demonstration_modelb"."id"
  FROM "demonstration_hasrelations"
  LEFT OUTER JOIN "demonstration_modela"
    ON ("demonstration_hasrelations"."ref_a_id" = "demonstration_modela"."id")
  LEFT OUTER JOIN "demonstration_modelb"
    ON ("demonstration_hasrelations"."ref_b_id" = "demonstration_modelb"."id");

-- The following query runs 3 times!

SELECT "demonstration_modela"."id",
       "demonstration_modela"."name_a"
  FROM "demonstration_modela"
 WHERE "demonstration_modela"."id" = '1'
 LIMIT 21;
 ```
 
 2. Querying on `refA`:
 ```graphql
 query {
  hasRelations {
    refA {
      nameA
    }
  }
}
```

```sql
SELECT "demonstration_hasrelations"."id",
       "demonstration_hasrelations"."ref_a_id",
       "demonstration_modela"."id",
       "demonstration_modela"."name_a"
  FROM "demonstration_hasrelations"
  LEFT OUTER JOIN "demonstration_modela"
    ON ("demonstration_hasrelations"."ref_a_id" = "demonstration_modela"."id")
```
