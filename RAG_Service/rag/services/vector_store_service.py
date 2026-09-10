from threading import Lock

from django.conf import settings
from pymilvus import (
    AnnSearchRequest,
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    Function,
    FunctionType,
    RRFRanker,
    connections,
    utility,
)


class VectorStoreService:
    _collection = None
    _initialized = False
    _initialization_lock = Lock()

    @classmethod
    def get_collection(cls) -> Collection:
        if cls._initialized and cls._collection is not None:
            return cls._collection

        with cls._initialization_lock:
            if cls._initialized and cls._collection is not None:
                return cls._collection

            cls._connect()
            collection = cls._ensure_collection()
            cls._ensure_indexes(collection)
            collection.load()

            cls._collection = collection
            cls._initialized = True

            return collection

    @staticmethod
    def _connect() -> None:
        connections.connect(
            alias="default",
            host=settings.MILVUS_HOST,
            port=settings.MILVUS_PORT,
        )

    @classmethod
    def _ensure_collection(cls) -> Collection:
        collection_name = settings.MILVUS_COLLECTION

        if utility.has_collection(collection_name):
            collection = Collection(collection_name)
            cls._validate_collection_schema(collection)
            return collection

        fields = [
            FieldSchema(
                name="chunk_id",
                dtype=DataType.VARCHAR,
                is_primary=True,
                auto_id=False,
                max_length=64,
            ),
            FieldSchema(
                name="embedding",
                dtype=DataType.FLOAT_VECTOR,
                dim=settings.EMBEDDING_DIMENSION,
            ),
            FieldSchema(
                name="chunk_text",
                dtype=DataType.VARCHAR,
                max_length=65535,
                enable_analyzer=True,
            ),
            FieldSchema(
                name="sparse_embedding",
                dtype=DataType.SPARSE_FLOAT_VECTOR,
            ),
            FieldSchema(
                name="lecture_id",
                dtype=DataType.VARCHAR,
                max_length=64,
            ),
            FieldSchema(
                name="course_id",
                dtype=DataType.VARCHAR,
                max_length=64,
            ),
            FieldSchema(
                name="student_id",
                dtype=DataType.VARCHAR,
                max_length=64,
            ),
            FieldSchema(
                name="chunk_index",
                dtype=DataType.INT64,
            ),
            FieldSchema(
                name="source_type",
                dtype=DataType.VARCHAR,
                max_length=32,
            ),
            FieldSchema(
                name="created_at",
                dtype=DataType.INT64,
            ),
        ]

        schema = CollectionSchema(
            fields=fields,
            description="Lecture chunks for Moein RAG service",
        )

        schema.add_function(
            Function(
                name="chunk_text_bm25",
                input_field_names=["chunk_text"],
                output_field_names=["sparse_embedding"],
                function_type=FunctionType.BM25,
            )
        )

        return Collection(
            name=collection_name,
            schema=schema,
        )

    @staticmethod
    def _validate_collection_schema(collection: Collection) -> None:
        field_definitions = {
            field.to_dict()["name"]: field.to_dict()
            for field in collection.schema.fields
        }

        expected_types = {
            "chunk_id": DataType.VARCHAR,
            "embedding": DataType.FLOAT_VECTOR,
            "chunk_text": DataType.VARCHAR,
            "sparse_embedding": DataType.SPARSE_FLOAT_VECTOR,
            "lecture_id": DataType.VARCHAR,
            "course_id": DataType.VARCHAR,
            "student_id": DataType.VARCHAR,
            "chunk_index": DataType.INT64,
            "source_type": DataType.VARCHAR,
            "created_at": DataType.INT64,
        }

        missing_fields = [
            field_name
            for field_name in expected_types
            if field_name not in field_definitions
        ]

        if missing_fields:
            raise RuntimeError(
                "Existing Milvus collection is incompatible with "
                "hybrid search schema. Missing fields: "
                f"{', '.join(missing_fields)}. "
                "Recreate the collection before starting the RAG service."
            )

        for field_name, expected_type in expected_types.items():
            actual_type = field_definitions[field_name]["type"]

            if actual_type != expected_type:
                raise RuntimeError(
                    "Existing Milvus collection is incompatible with "
                    "hybrid search schema. "
                    f"Field '{field_name}' has an unexpected type. "
                    "Recreate the collection before starting the RAG service."
                )

        embedding_params = field_definitions["embedding"].get(
            "params",
            {},
        )

        if (
            embedding_params.get("dim")
            != settings.EMBEDDING_DIMENSION
        ):
            raise RuntimeError(
                "Existing Milvus collection is incompatible with "
                "the configured embedding dimension. "
                "Recreate the collection before starting the RAG service."
            )

        chunk_text_params = field_definitions["chunk_text"].get(
            "params",
            {},
        )

        if not chunk_text_params.get("enable_analyzer"):
            raise RuntimeError(
                "Existing Milvus collection is incompatible with "
                "hybrid search schema. The chunk_text analyzer is "
                "not enabled. Recreate the collection before starting "
                "the RAG service."
            )

        functions = [
            function.to_dict()
            for function in collection.schema.functions
        ]

        has_bm25_function = any(
            function.get("type") == FunctionType.BM25
            and function.get("input_field_names") == ["chunk_text"]
            and function.get("output_field_names")
            == ["sparse_embedding"]
            for function in functions
        )

        if not has_bm25_function:
            raise RuntimeError(
                "Existing Milvus collection is incompatible with "
                "hybrid search schema. The BM25 function is missing "
                "or invalid. Recreate the collection before starting "
                "the RAG service."
            )

    @staticmethod
    def _ensure_indexes(collection: Collection) -> None:
        indexed_fields = {
            index.to_dict().get("field")
            for index in collection.indexes
        }

        if "embedding" not in indexed_fields:
            collection.create_index(
                field_name="embedding",
                index_params={
                    "metric_type": settings.MILVUS_METRIC_TYPE,
                    "index_type": "AUTOINDEX",
                    "params": {},
                },
            )

        if "sparse_embedding" not in indexed_fields:
            collection.create_index(
                field_name="sparse_embedding",
                index_params={
                    "metric_type": "BM25",
                    "index_type": "SPARSE_INVERTED_INDEX",
                    "params": {
                        "inverted_index_algo": "DAAT_MAXSCORE",
                    },
                },
            )

    @classmethod
    def search_chunks(
        cls,
        query_embedding: list[float],
        query_text: str,
        limit: int = 5,
        student_id: str | None = None,
        course_id: str | None = None,
        lecture_id: str | None = None,
    ) -> list[dict]:
        collection = cls.get_collection()

        filters = []

        if student_id:
            filters.append(f'student_id == "{student_id}"')

        if course_id:
            filters.append(f'course_id == "{course_id}"')

        if lecture_id:
            filters.append(f'lecture_id == "{lecture_id}"')

        expr = " and ".join(filters) if filters else None

        dense_request = AnnSearchRequest(
            data=[query_embedding],
            anns_field="embedding",
            param={
                "metric_type": settings.MILVUS_METRIC_TYPE,
                "params": {},
            },
            limit=limit,
            expr=expr,
        )

        sparse_request = AnnSearchRequest(
            data=[query_text],
            anns_field="sparse_embedding",
            param={
                "metric_type": "BM25",
                "params": {},
            },
            limit=limit,
            expr=expr,
        )

        results = collection.hybrid_search(
            reqs=[
                dense_request,
                sparse_request,
            ],
            rerank=RRFRanker(),
            limit=limit,
            output_fields=[
                "chunk_text",
                "lecture_id",
                "course_id",
                "chunk_index",
                "source_type",
                "student_id",
            ],
        )

        normalized_results = []
        seen_chunk_ids = set()

        for hits in results:
            for hit in hits:
                chunk_id = hit.id

                if chunk_id in seen_chunk_ids:
                    continue

                seen_chunk_ids.add(chunk_id)

                normalized_results.append(
                    {
                        "chunk_id": chunk_id,
                        "chunk_text": hit.entity.get("chunk_text"),
                        "lecture_id": hit.entity.get("lecture_id"),
                        "course_id": hit.entity.get("course_id"),
                        "chunk_index": hit.entity.get("chunk_index"),
                        "source_type": hit.entity.get("source_type"),
                        "student_id": hit.entity.get("student_id"),
                        "score": hit.distance,
                    }
                )

        return normalized_results

    @classmethod
    def insert_chunks(cls, chunks: list[dict]) -> None:
        if not chunks:
            raise ValueError("Chunks list cannot be empty.")

        collection = cls.get_collection()

        collection.insert(chunks)
        collection.flush()
