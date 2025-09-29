from pymilvus import connections, utility, Collection
import os

from config.settings import settings

connections.connect(
    uri=settings.MILVUS_URI,
    token=settings.MILVUS_TOKEN,
)

print("Collections:", utility.list_collections())
print("Documents in collection_test_123:",
      Collection("collection_test_123").num_entities)