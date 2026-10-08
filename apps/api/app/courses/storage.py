from dataclasses import dataclass
from pathlib import Path
import secrets
import sqlite3
import os
from typing import Protocol


@dataclass(frozen=True)
class CourseMaterial:
    material_id: str
    course_id: str
    organization_id: str
    filename: str
    content_type: str
    size: int
    path: str


class CourseBlobStore(Protocol):
    def save(self, key: str, content: bytes, content_type: str) -> str: ...
    def read(self, path: str) -> bytes: ...
    def delete(self, path: str) -> None: ...


class TencentCosCourseBlobStore:
    def __init__(self, client: object, bucket: str, prefix: str = "course-materials") -> None:
        self._client, self._bucket, self._prefix = client, bucket, prefix.strip("/")

    def save(self, key: str, content: bytes, content_type: str) -> str:
        object_key = f"{self._prefix}/{key}"
        self._client.put_object(Bucket=self._bucket, Key=object_key, Body=content, ContentType=content_type)
        return object_key

    def read(self, path: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=path)
        body = response.get("Body")
        if body is None or not callable(getattr(body, "read", None)):
            raise FileNotFoundError(path)
        return body.read()

    def delete(self, path: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=path)


class CourseMaterialStore:
    """Filesystem blobs plus a local SQLite manifest, ready to swap to COS later."""

    def __init__(self, root: str | Path, blob_store: CourseBlobStore | None = None) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._metadata_path = self._root / "course-materials.sqlite3"
        self._blob_store = blob_store
        self._initialize_storage()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._metadata_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize_storage(self) -> None:
        with self._connect() as connection:
            connection.execute("""
                create table if not exists course_materials (
                    material_id text primary key, course_id text not null, organization_id text not null,
                    filename text not null, content_type text not null, size integer not null, path text not null
                )
            """)

    @staticmethod
    def _material(row: sqlite3.Row) -> CourseMaterial:
        return CourseMaterial(row["material_id"], row["course_id"], row["organization_id"], row["filename"], row["content_type"], row["size"], row["path"])

    def save(self, course_id: str, organization_id: str, filename: str, content_type: str, content: bytes) -> CourseMaterial:
        material_id = secrets.token_urlsafe(12)
        safe_name = Path(filename).name or "course-material"
        normalized_type = content_type or "application/octet-stream"
        key = f"{organization_id}/{course_id}/{material_id}-{safe_name}"
        if self._blob_store:
            path = self._blob_store.save(key, content, normalized_type)
        else:
            destination = self._root / f"{material_id}-{safe_name}"
            destination.write_bytes(content)
            path = str(destination)
        material = CourseMaterial(material_id, course_id, organization_id, safe_name, normalized_type, len(content), path)
        with self._connect() as connection:
            connection.execute("insert into course_materials values (?, ?, ?, ?, ?, ?, ?)", (material.material_id, material.course_id, material.organization_id, material.filename, material.content_type, material.size, material.path))
        return material

    def list_for_course(self, course_id: str, organization_id: str) -> list[CourseMaterial]:
        with self._connect() as connection:
            rows = connection.execute("select * from course_materials where course_id = ? and organization_id = ? order by rowid desc", (course_id, organization_id)).fetchall()
        return [self._material(row) for row in rows]

    def get(self, material_id: str, organization_id: str) -> CourseMaterial:
        with self._connect() as connection:
            row = connection.execute("select * from course_materials where material_id = ? and organization_id = ?", (material_id, organization_id)).fetchone()
        if row is None:
            raise KeyError(material_id)
        return self._material(row)

    def delete(self, material_id: str, organization_id: str) -> None:
        material = self.get(material_id, organization_id)
        self._delete_blob(material.path)
        with self._connect() as connection:
            connection.execute("delete from course_materials where material_id = ? and organization_id = ?", (material_id, organization_id))

    def delete_for_course(self, course_id: str, organization_id: str) -> int:
        materials = self.list_for_course(course_id, organization_id)
        for material in materials:
            self._delete_blob(material.path)
        with self._connect() as connection:
            connection.execute("delete from course_materials where course_id = ? and organization_id = ?", (course_id, organization_id))
        return len(materials)

    def read(self, material: CourseMaterial) -> bytes:
        if self._blob_store:
            return self._blob_store.read(material.path)
        return Path(material.path).read_bytes()

    def _delete_blob(self, path: str) -> None:
        if self._blob_store:
            self._blob_store.delete(path)
        else:
            Path(path).unlink(missing_ok=True)


class PostgresCourseMaterialStore(CourseMaterialStore):
    """PostgreSQL manifest for course files stored on a shared volume or COS mount."""

    def __init__(self, root: str | Path, database_url: str, blob_store: CourseBlobStore | None = None) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL course material store requires psycopg") from exc
        self._psycopg, self._database_url = psycopg, database_url
        self._blob_store = blob_store
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("create table if not exists runtime_course_materials (material_id text primary key, course_id text not null, organization_id text not null, filename text not null, content_type text not null, size integer not null, path text not null)")

    def _connect_postgres(self):
        return self._psycopg.connect(self._database_url)

    def save(self, course_id: str, organization_id: str, filename: str, content_type: str, content: bytes) -> CourseMaterial:
        material_id = secrets.token_urlsafe(12)
        safe_name = Path(filename).name or "course-material"
        normalized_type = content_type or "application/octet-stream"
        key = f"{organization_id}/{course_id}/{material_id}-{safe_name}"
        if self._blob_store:
            path = self._blob_store.save(key, content, normalized_type)
        else:
            destination = self._root / f"{material_id}-{safe_name}"
            destination.write_bytes(content)
            path = str(destination)
        material = CourseMaterial(material_id, course_id, organization_id, safe_name, normalized_type, len(content), path)
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("insert into runtime_course_materials values (%s,%s,%s,%s,%s,%s,%s)", (material.material_id, material.course_id, material.organization_id, material.filename, material.content_type, material.size, material.path))
        return material

    @staticmethod
    def _material(row: tuple[object, ...]) -> CourseMaterial:
        return CourseMaterial(str(row[0]), str(row[1]), str(row[2]), str(row[3]), str(row[4]), int(row[5]), str(row[6]))

    def list_for_course(self, course_id: str, organization_id: str) -> list[CourseMaterial]:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select material_id, course_id, organization_id, filename, content_type, size, path from runtime_course_materials where course_id = %s and organization_id = %s order by material_id desc", (course_id, organization_id))
            return [self._material(row) for row in cursor.fetchall()]

    def get(self, material_id: str, organization_id: str) -> CourseMaterial:
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("select material_id, course_id, organization_id, filename, content_type, size, path from runtime_course_materials where material_id = %s and organization_id = %s", (material_id, organization_id))
            row = cursor.fetchone()
        if row is None:
            raise KeyError(material_id)
        return self._material(row)

    def delete(self, material_id: str, organization_id: str) -> None:
        material = self.get(material_id, organization_id)
        self._delete_blob(material.path)
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("delete from runtime_course_materials where material_id = %s and organization_id = %s", (material_id, organization_id))

    def delete_for_course(self, course_id: str, organization_id: str) -> int:
        materials = self.list_for_course(course_id, organization_id)
        for material in materials:
            self._delete_blob(material.path)
        with self._connect_postgres() as connection, connection.cursor() as cursor:
            cursor.execute("delete from runtime_course_materials where course_id = %s and organization_id = %s", (course_id, organization_id))
        return len(materials)


def build_course_blob_store() -> CourseBlobStore | None:
    bucket = os.getenv("TENCENT_COS_BUCKET", "").strip()
    if not bucket:
        return None
    region = os.getenv("TENCENT_COS_REGION", "").strip()
    secret_id = os.getenv("TENCENT_COS_SECRET_ID", "").strip()
    secret_key = os.getenv("TENCENT_COS_SECRET_KEY", "").strip()
    if not all((region, secret_id, secret_key)):
        raise RuntimeError("Tencent COS requires region, secret id, and secret key")
    try:
        from qcloud_cos import CosConfig, CosS3Client
    except ImportError as exc:
        raise RuntimeError("Tencent COS support requires cos-python-sdk-v5") from exc
    client = CosS3Client(CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key))
    return TencentCosCourseBlobStore(client, bucket, os.getenv("TENCENT_COS_COURSE_PREFIX", "course-materials"))
