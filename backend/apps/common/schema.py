"""Reusable drf-spectacular annotations for non-model endpoints.

Most report, dashboard, and lifecycle endpoints return ad-hoc dictionaries. These
decorators keep the generated schema honest (the response is an object or a file)
without forcing every view into a serializer it does not need at runtime.
"""

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema

object_response = extend_schema(responses=OpenApiTypes.OBJECT)
pdf_response = extend_schema(responses={(200, "application/pdf"): OpenApiTypes.BINARY})
download_response = extend_schema(
    responses={(200, "application/octet-stream"): OpenApiTypes.BINARY}
)
binary_upload = extend_schema(request=OpenApiTypes.BINARY, responses=OpenApiTypes.OBJECT)
json_view = extend_schema(request=OpenApiTypes.OBJECT, responses=OpenApiTypes.OBJECT)
