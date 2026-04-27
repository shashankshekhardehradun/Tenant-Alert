"""BigQuery load helpers for raw parquet files."""

from __future__ import annotations

from collections.abc import Sequence

from google.cloud import bigquery


def load_parquet_to_table(
    source_uri: str,
    *,
    project_id: str,
    dataset_id: str,
    table_id: str,
    write_disposition: str = bigquery.WriteDisposition.WRITE_APPEND,
    schema: Sequence[bigquery.SchemaField] | None = None,
    partition_field: str | None = None,
    clustering_fields: Sequence[str] | None = None,
) -> str:
    """Load a parquet object from GCS into BigQuery and return the table id."""
    client = bigquery.Client(project=project_id)
    destination = f"{project_id}.{dataset_id}.{table_id}"
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition=write_disposition,
        schema=list(schema) if schema else None,
        autodetect=schema is None,
    )
    if partition_field:
        job_config.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.DAY,
            field=partition_field,
        )
    if clustering_fields:
        job_config.clustering_fields = list(clustering_fields)
    load_job = client.load_table_from_uri(source_uri, destination, job_config=job_config)
    load_job.result()
    return destination
