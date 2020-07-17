import sys
from functools import partial
from typing import Any, Callable, Dict, Type, TypeVar, Union

import openapi_typed as oa
import yaml
from stone.backend import CodeBackend
from stone.ir import data_types
from stone.ir.api import ApiNamespace, ApiRoute


def _numeric_to_schema_def(
    typ: Union[
        data_types.Float32,
        data_types.Float64,
        data_types.Int32,
        data_types.Int64,
        data_types.UInt32,
        data_types.UInt64,
    ],
) -> oa.Schema:
    schema = {
        data_types.Float32: oa.Schema(type="number", format="float"),
        data_types.Float64: oa.Schema(type="number", format="double"),
        data_types.Int32:   oa.Schema(type="integer", format="int32"),
        data_types.Int64:   oa.Schema(type="integer", format="int64"),
        data_types.UInt32:  oa.Schema(type="integer", format="uint64"),
        data_types.UInt64:  oa.Schema(type="integer", format="uint64"),
    }[type(typ)]

    if typ.min_value is not None:
        schema['minimum'] = typ.min_value
    if typ.max_value is not None:
        schema['maximum'] = typ.max_value

    return schema


def _list_to_schema_def(
    namespace: ApiNamespace,
    typ: data_types.List,
) -> oa.Schema:
    schema = oa.Schema(
        type="array",
        items=type_to_schema_decl(namespace, typ.data_type),
    )

    if typ.min_items is not None:
        schema['minItems'] = typ.min_items
    if typ.max_items is not None:
        schema['maxItems'] = typ.max_items

    return schema


def _string_to_schema_def(typ: data_types.String) -> oa.Schema:
    schema = oa.Schema(type="string")

    if typ.min_length is not None:
        schema['minLength'] = typ.min_length
    if typ.max_length is not None:
        schema['maxLength'] = typ.max_length

    return schema


def _timestamp_to_schema_def(typ: data_types.Timestamp) -> oa.Schema:
    print("WARNING: Timestamps are not properly supported", file=sys.stderr)
    return oa.Schema(type="string")


def _nullable_to_schema_def(
    namespace: ApiNamespace,
    typ: data_types.Nullable,
) -> oa.Schema:
    schema = oa.Schema(
        allOf=[type_to_schema_decl(namespace, typ.data_type)],
    )
    schema['nullable'] = True
    return schema


def _struct_to_schema_def(
    namespace: ApiNamespace,
    typ: data_types.Struct,
) -> oa.Schema:
    schema = oa.Schema(
        type="object",
        properties={
            field.name: type_to_schema_decl(namespace, field.data_type)
            for field in typ.fields
        },
        required=[
            field.name
            for field in typ.fields
            if not isinstance(field.data_type, data_types.Nullable)
        ],
    )
    if typ.parent_type is not None:
        schema["allOf"] = [
            type_to_schema_decl(namespace, typ.parent_type),
        ]
    if typ.has_enumerated_subtypes():
        return oa.Schema(
            type="object",
            properties={
                "file": type_to_schema_decl(namespace, typ.get_enumerated_subtypes()[0].data_type),
            },
            required=["file"],
        )

        subtypes_schema = oa.Schema(
            oa.Schema(
                anyOf=[
                    oa.Schema(
                        type="object",
                        properties={
                            variant.name: type_to_schema_decl(namespace, variant.data_type),
                        },
                        required=[variant.name],
                    )
                    for variant in typ.get_enumerated_subtypes()
                ],
            ),
        )

        schema = oa.Schema(
            oneOf=[
                schema,
                subtypes_schema,
            ],
        )
    return schema


def _union_to_schema_def(
    namespace: ApiNamespace,
    typ: data_types.Union,
) -> oa.Schema:
    schema = oa.Schema(
        oa.Schema(
            type="object",
            properties={
                ".tag": oa.Schema(type="string"),
            },
            required=[".tag"],
        ),
    )

    if any(not isinstance(variant.data_type, data_types.Void) for variant in typ.all_fields):
        schema["oneOf"] = [
            oa.Schema(
                type="object",
                properties={
                    variant.name: type_to_schema_decl(namespace, variant.data_type),
                },
                required=[variant.name],
            )
            for variant in typ.all_fields
            if not isinstance(variant.data_type, data_types.Void)
        ]
        schema["discriminator"] = oa.Discriminator(
            propertyName=".tag",
        )

    return schema


def type_to_schema_decl(
    namespace: ApiNamespace,
    typ: data_types.DataType,
) -> Union[oa.Reference, oa.Schema]:
    if isinstance(typ, data_types.UserDefined):
        return oa.Reference({
            "$ref": f"{typ.namespace.name}.yaml#/components/schemas/{typ.name}",
        })
    return type_to_schema_def(namespace, typ)


def type_to_schema_def(
    namespace: ApiNamespace,
    typ: data_types.DataType,
) -> oa.Schema:
        if isinstance(typ, data_types.Boolean):
            return oa.Schema(type="boolean")
        if isinstance(
            typ,
            (
                data_types.Float32, data_types.Float64,
                data_types.Int32, data_types.Int64,
                data_types.UInt32, data_types.UInt64,
            ),
        ):
            return _numeric_to_schema_def(typ)
        if isinstance(typ, data_types.List):
            return _list_to_schema_def(namespace, typ)
        if isinstance(typ, data_types.String):
            return _string_to_schema_def(typ)
        if isinstance(typ, data_types.Timestamp):
            return _timestamp_to_schema_def(typ)
        if isinstance(typ, data_types.Void):
            return oa.Schema()
        if isinstance(typ, data_types.Nullable):
            return _nullable_to_schema_def(namespace, typ)
        if isinstance(typ, data_types.Struct):
            return _struct_to_schema_def(namespace, typ)
        if isinstance(typ, data_types.Union):
            return _union_to_schema_def(namespace, typ)

        raise ValueError(f"Unsupported type: {type(typ)}")


def route_to_path(
    namespace: ApiNamespace,
    route: ApiRoute,
) -> oa.PathItem:
    return {
        "post": {
            "description": route.doc or "",
            **({
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {
                        "schema": type_to_schema_decl(namespace, route.arg_data_type),
                    },
                },
            }} if route.arg_data_type is not None and not isinstance(route.arg_data_type, data_types.Void) else {}),
            "responses": {
                "200": {
                    "description": "",
                    "content": {
                        "application/json": {
                            "schema": type_to_schema_decl(namespace, route.result_data_type),
                        },
                    } if route.result_data_type is not None and not isinstance(route.result_data_type, data_types.Void) else {},
                },
                "409": {
                    "description": "",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "error": type_to_schema_decl(namespace, route.error_data_type),
                                    "error_summary": {
                                        "type": "string",
                                    },
                                },
                            },
                        },
                    } if route.error_data_type is not None and not isinstance(route.error_data_type, data_types.Void) else {},
                },
            },
        },
    }


def route_name_to_path_name(namespace_name, route_name, route_version):
    base_path = f"/{namespace_name}/{route_name}"
    if route_version == 1:
        return base_path
    return f"{base_path}_v{route_version}"


def namespace_to_spec(namespace):
    return {
        "openapi": "3.0.0",
        "info": {
            "title": namespace.name,
            "version": "0.1.0",
        },
        "paths": {
            route_name_to_path_name(namespace.name, route_name, route_version): route_to_path(namespace, route)
            for route_name, _routes_by_version in namespace.routes_by_name.items()
            for route_version, route in _routes_by_version.at_version.items()
        },
        "components": {
            "schemas": {
                data_type_name: type_to_schema_def(namespace, data_type)
                for data_type_name, data_type in namespace.data_type_by_name.items()
            },
        },
    }


def escape_path(path):
    return path.replace('/', '~1')


class OpenApiBackend(CodeBackend):
    def generate(self, api):
        for namespace in api.namespaces.values():
            with open(f"spec/{namespace.name}.yaml", "w") as f:
                yaml.dump(namespace_to_spec(namespace), f)

        with open(f"spec/_master.yaml", "w") as f:
            yaml.dump(
                oa.OpenAPIObject(
                    openapi="3.0.0",
                    info={
                        "title": "Dropbox APIv2",
                        "version": "0.1.0",
                    },
                    servers=[
                        {"url": "https://api.dropbox.com/2"},
                    ],
                    paths={
                        route_name_to_path_name(namespace.name, route_name, route_version): {
                            "$ref": f"{namespace.name}.yaml#/paths/{escape_path(route_name_to_path_name(namespace.name, route_name, route_version))}",
                        }
                        for namespace in api.namespaces.values()
                        for route_name, _routes_by_version in namespace.routes_by_name.items()
                        for route_version, route in _routes_by_version.at_version.items()
                    },
                    components={
                        "securitySchemes": {
                            "oauth2": {
                                "type": "oauth2",
                                "flows": {
                                    "authorizationCode": {
                                        "authorizationUrl": "https://www.dropbox.com/oauth2/authorize",
                                        "tokenUrl": "https://api.dropboxapi.com/oauth2/token",
                                        "scopes": {},
                                    },
                                },
                            },
                        },
                    },
                    security=[
                        {
                            "oauth2": [],
                        },
                    ],
                ),
                f,
            )
