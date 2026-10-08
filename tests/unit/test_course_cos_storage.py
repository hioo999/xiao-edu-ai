from apps.api.app.courses.storage import CourseMaterialStore, TencentCosCourseBlobStore


class Body:
    def __init__(self, value: bytes) -> None:
        self.value = value

    def read(self) -> bytes:
        return self.value


class FakeCosClient:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.deleted: list[str] = []

    def put_object(self, *, Bucket, Key, Body, ContentType) -> None:
        assert Bucket == "edu-1250000000"
        assert ContentType == "application/pdf"
        self.objects[Key] = Body

    def get_object(self, *, Bucket, Key):
        assert Bucket == "edu-1250000000"
        return {"Body": Body(self.objects[Key])}

    def delete_object(self, *, Bucket, Key) -> None:
        assert Bucket == "edu-1250000000"
        self.deleted.append(Key)
        self.objects.pop(Key, None)


def test_course_material_store_persists_blobs_to_cos_and_downloads_through_store(tmp_path) -> None:
    client = FakeCosClient()
    store = CourseMaterialStore(tmp_path, TencentCosCourseBlobStore(client, "edu-1250000000"))

    material = store.save("course-1", "org-1", "lesson.pdf", "application/pdf", b"lesson")

    assert material.path.startswith("course-materials/org-1/course-1/")
    assert store.read(material) == b"lesson"
    store.delete(material.material_id, "org-1")
    assert client.deleted == [material.path]
