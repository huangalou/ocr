import os

from boto3 import client as boto3_client

_client = None


def get_s3_client():
    global _client
    if _client is None:
        _client = boto3_client(
            "s3",
            endpoint_url=f"http://{os.environ['MINIO_HOST']}:{os.environ['MINIO_PORT']}",
            aws_access_key_id=os.environ["MINIO_ROOT_USER"],
            aws_secret_access_key=os.environ["MINIO_ROOT_PASSWORD"],
        )
    return _client


def upload_image(bucket: str, key: str, data: bytes, content_type: str = "image/jpeg"):
    client = get_s3_client()
    client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)


def download_image(bucket: str, key: str) -> bytes:
    client = get_s3_client()
    resp = client.get_object(Bucket=bucket, Key=key)
    return resp["Body"].read()
