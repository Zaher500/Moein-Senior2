from threading import Lock

from django.conf import settings
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
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
            cls._ensure_index(collection)
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
            return Collection(collection_name)

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

        return Collection(
            name=collection_name,
            schema=schema,
        )

    @staticmethod
    def _ensure_index(collection: Collection) -> None:
        if collection.indexes:
            return

        collection.create_index(
            field_name="embedding",
            index_params={
                "metric_type": settings.MILVUS_METRIC_TYPE,
                "index_type": "AUTOINDEX",
                "params": {},
            },
        )

    @classmethod
    def search_chunks(
        cls,
        query_embedding: list[float],
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

        results = collection.search(
            data=[query_embedding],
            anns_field="embedding",
            param={
                "metric_type": settings.MILVUS_METRIC_TYPE,
                "params": {},
            },
            limit=limit,
            expr=expr,
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

        for hits in results:
            for hit in hits:
                normalized_results.append(
                    {
                        "chunk_id": hit.id,
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

        data = [
            [chunk["chunk_id"] for chunk in chunks],
            [chunk["embedding"] for chunk in chunks],
            [chunk["chunk_text"] for chunk in chunks],
            [chunk["lecture_id"] for chunk in chunks],
            [chunk["course_id"] for chunk in chunks],
            [chunk["student_id"] for chunk in chunks],
            [chunk["chunk_index"] for chunk in chunks],
            [chunk["source_type"] for chunk in chunks],
            [chunk["created_at"] for chunk in chunks],
        ]

        collection.insert(data)
        collection.flush()
