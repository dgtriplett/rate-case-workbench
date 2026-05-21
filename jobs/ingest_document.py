"""Databricks Job: ingest one uploaded document.

Triggered by the app on upload (`backend/services/ingest.py:trigger_ingest_job`).
Reads the file from a UC Volume, extracts text (PDF/DOCX/TXT), chunks it, writes
to a Delta table, and triggers a Vector Search delta-sync index refresh.

Args: <document_id> <volume_uri>
"""
from __future__ import annotations

import io
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Iterable

logging.basicConfig(level=logging.INFO, format="%(levelname)s :: %(message)s")
log = logging.getLogger("ingest")


CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


def _read_file(uri: str) -> bytes:
    # In a Databricks Job, UC Volume paths are mounted as POSIX paths
    if uri.startswith("/Volumes/"):
        with open(uri, "rb") as f:
            return f.read()
    raise ValueError(f"Unsupported URI: {uri}")


def _extract_text(name: str, data: bytes) -> tuple[str, int]:
    lower = name.lower()
    if lower.endswith(".pdf"):
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        pages = [p.extract_text() or "" for p in reader.pages]
        return "\n\n".join(pages), len(pages)
    if lower.endswith(".docx"):
        from docx import Document
        doc = Document(io.BytesIO(data))
        return "\n\n".join(p.text for p in doc.paragraphs), 1
    return data.decode("utf-8", errors="replace"), 1


def _chunks(text: str) -> Iterable[tuple[int, int, int, str]]:
    n = len(text)
    i = 0
    idx = 0
    while i < n:
        end = min(i + CHUNK_SIZE, n)
        yield idx, i, end, text[i:end]
        idx += 1
        if end == n:
            return
        i = max(end - CHUNK_OVERLAP, 0)


def main(document_id: str, uri: str) -> None:
    from pyspark.sql import SparkSession
    from pyspark.sql.types import IntegerType, StringType, StructField, StructType, TimestampType

    catalog = os.environ.get("CATALOG", "grid_ops_demo_catalog")
    schema = os.environ.get("KNOWLEDGE_SCHEMA", "rcw_knowledge")
    chunks_table = f"{catalog}.{schema}.chunks"
    docs_table = f"{catalog}.{schema}.documents"

    spark = SparkSession.builder.getOrCreate()

    name = os.path.basename(uri)
    log.info("reading %s", uri)
    data = _read_file(uri)
    log.info("read %d bytes", len(data))

    text, page_count = _extract_text(name, data)

    rows = []
    for chunk_index, start, end, body in _chunks(text):
        rows.append(
            (
                f"{document_id}:{chunk_index}",
                document_id,
                chunk_index,
                body,
                start,
                end,
                page_count,
            )
        )

    schema_chunks = StructType(
        [
            StructField("id", StringType(), False),
            StructField("document_id", StringType(), False),
            StructField("chunk_index", IntegerType(), False),
            StructField("text", StringType(), True),
            StructField("char_start", IntegerType(), True),
            StructField("char_end", IntegerType(), True),
            StructField("page_count", IntegerType(), True),
        ]
    )
    df = spark.createDataFrame(rows, schema=schema_chunks)
    spark.sql(
        f"CREATE TABLE IF NOT EXISTS {chunks_table} ("
        f"id STRING NOT NULL, document_id STRING NOT NULL, chunk_index INT, text STRING, "
        f"char_start INT, char_end INT, page_count INT, case_id STRING, jurisdiction STRING, "
        f"document_title STRING, source_kind STRING, classification STRING, page INT) "
        f"USING DELTA"
    )
    df.createOrReplaceTempView("chunk_upsert")
    spark.sql(
        f"MERGE INTO {chunks_table} t USING chunk_upsert s ON t.id = s.id "
        f"WHEN MATCHED THEN UPDATE SET t.text = s.text, t.char_start = s.char_start, t.char_end = s.char_end "
        f"WHEN NOT MATCHED THEN INSERT (id, document_id, chunk_index, text, char_start, char_end, page_count) "
        f"VALUES (s.id, s.document_id, s.chunk_index, s.text, s.char_start, s.char_end, s.page_count)"
    )

    log.info("merged %d chunks into %s", len(rows), chunks_table)

    # Mark document indexed via the documents Delta mirror (will CDC to/from Lakebase later)
    spark.sql(
        f"CREATE TABLE IF NOT EXISTS {docs_table} ("
        f"id STRING NOT NULL, title STRING, kind STRING, uri STRING, page_count INT, "
        f"case_id STRING, jurisdiction STRING, classification STRING, indexed_at TIMESTAMP) "
        f"USING DELTA"
    )
    spark.sql(
        f"MERGE INTO {docs_table} t USING (SELECT '{document_id}' AS id, '{name}' AS title, "
        f"{page_count} AS page_count, current_timestamp() AS indexed_at) s ON t.id = s.id "
        f"WHEN MATCHED THEN UPDATE SET t.page_count = s.page_count, t.indexed_at = s.indexed_at "
        f"WHEN NOT MATCHED THEN INSERT (id, title, page_count, indexed_at) "
        f"VALUES (s.id, s.title, s.page_count, s.indexed_at)"
    )
    log.info("done")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit("usage: ingest_document.py <document_id> <volume_uri>")
    main(sys.argv[1], sys.argv[2])
