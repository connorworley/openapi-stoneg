import yaml

import openapi_typed as oa
from stone.backend import CodeBackend # type: ignore
from stone.ir import data_types # type: ignore
from stone.ir.api import ApiNamespace, ApiRoute # type: ignore


def type_to_schema_declaration(
    namespace: ApiNamespace,
    typ: data_types.DataType,
) -> oa.Schema:
    if isinstance(typ, (data_types.Alias, data_types.Struct, data_types.Union)):
        ref = f"#/components/schemas/{typ.name}"
        if typ.namespace != namespace:
            ref = f"{typ.namespace.name}.yaml{ref}"
        return {"$ref": ref} # type: ignore

    return type_to_schema_definition(namespace, typ)

def type_to_schema_definition(
    namespace: ApiNamespace,
    typ: data_types.DataType,
) -> oa.Schema:
    result = oa.Schema()
    if isinstance(typ, data_types.Boolean):
        return {
            "type": "boolean",
        }
    elif isinstance(typ, data_types.Float32):
        result = {
            "type": "number",
            "format": "double",
        }
        if typ.min_value is not None:
            result["minimum"] = typ.min_value
        if typ.max_value is not None:
            result["maximum"] = typ.max_value
        return result
    elif isinstance(typ, data_types.Float64):
        result = {
            "type": "number",
            "format": "double",
        }
        if typ.min_value is not None:
            result["minimum"] = typ.min_value
        if typ.max_value is not None:
            result["maximum"] = typ.max_value
        return result
    elif isinstance(typ, data_types.Int32):
        result = {
            "type": "integer",
            "format": "int32",
        }
        if typ.min_value is not None:
            result["minimum"] = typ.min_value
        if typ.max_value is not None:
            result["maximum"] = typ.max_value
        return result
    elif isinstance(typ, data_types.Int64):
        result = {
            "type": "integer",
            "format": "int64",
        }
        if typ.min_value is not None:
            result["minimum"] = typ.min_value
        if typ.max_value is not None:
            result["maximum"] = typ.max_value
        return result
    elif isinstance(typ, data_types.UInt32):
        result = {
            "type": "integer",
            "format": "uint32",
        }
        if typ.min_value is not None:
            result["minimum"] = typ.min_value
        if typ.max_value is not None:
            result["maximum"] = typ.max_value
        return result
    elif isinstance(typ, data_types.UInt64):
        result = {
            "type": "integer",
            "format": "uint64",
        }
        if typ.min_value is not None:
            result["minimum"] = typ.min_value
        if typ.max_value is not None:
            result["maximum"] = typ.max_value
        return result
    elif isinstance(typ, data_types.List):
        result = {
            "type": "array",
            "items": type_to_schema_declaration(namespace, typ.data_type),
        }
        if typ.min_items is not None:
            result["minItems"] = typ.min_items
        if typ.max_items is not None:
            result["maxItems"] = typ.max_items
        return result
    elif isinstance(typ, data_types.String):
        result = {
            "type": "string",
        }
        if typ.min_length is not None:
            result["minLength"] = typ.min_length
        if typ.max_length is not None:
            result["maxLength"] = typ.max_length
        # if typ.pattern is not None:
        #     result["pattern"] = typ.pattern
        return result
    elif isinstance(typ, data_types.Timestamp):
        return {
            "type": "string",
        }
    elif isinstance(typ, data_types.Void):
        return {}
    elif isinstance(typ, data_types.Nullable):
        result = type_to_schema_declaration(namespace, typ.data_type)
        result["nullable"] = True
        return result
    elif isinstance(typ, data_types.Struct):
        result = {
            "type": "object",
            "required": [
                field.name
                for field in typ.fields
                if not isinstance(field.data_type, data_types.Nullable)
            ],
            "properties": {
                field.name: type_to_schema_declaration(namespace, field.data_type)
                for field in typ.fields
            },
        }
        if typ.parent_type is not None:
            result = {
                "allOf": [
                    result,
                    type_to_schema_declaration(namespace, typ.parent_type),
                ],
            }
        return result
    elif isinstance(typ, data_types.Union):
        return {
            "oneOf": [
                {
                    "allOf": [
                        {
                            "type": "object",
                            "required": [".tag"],
                            "properties": {
                                ".tag": {
                                    "type": "string",
                                },
                            },
                        },
                        type_to_schema_declaration(namespace, variant.data_type) if isinstance(variant.data_type, (data_types.Alias, data_types.Struct, data_types.Union))
                        else {
                            "type": "object",
                            "required": [variant.name],
                            "properties": {
                                variant.name: type_to_schema_declaration(namespace, variant.data_type),
                            }
                        },
                    ],
                }
                for variant in typ.fields
            ],
            "discriminator": {
                "propertyName": ".tag",
            },
        }
    raise ValueError(f"unhandled type {type(typ)}")



def route_to_path(
    namespace: ApiNamespace,
    route: ApiRoute,
) -> oa.PathItem:
    return {
        "post": {
            "description": route.doc,
            **(
                {
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": type_to_schema_declaration(namespace, route.arg_data_type),
                            },
                        },
                    },
                }
                if not isinstance(route.arg_data_type, data_types.Void) else {}
            ),
            "responses": {
                "200": {
                    **(
                        {
                            "content": {
                                "application/json": {
                                    "schema": type_to_schema_declaration(namespace, route.result_data_type),
                                },
                            },
                        }
                        if not isinstance(route.result_data_type, data_types.Void) else {}
                    ),
                },
                "409": {
                    **(
                        {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "error": type_to_schema_declaration(namespace, route.error_data_type),
                                            "error_summary": {
                                                "type": "string",
                                            },
                                        },
                                    },
                                },
                            },
                        }
                        if not isinstance(route.error_data_type, data_types.Void) else {}
                    ),
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
        "paths": {
            route_name_to_path_name(namespace.name, route_name, route_version): route_to_path(namespace, route)
            for route_name, _routes_by_version in namespace.routes_by_name.items()
            for route_version, route in _routes_by_version.at_version.items()
        },
        "components": {
            "schemas": {
                data_type_name: type_to_schema_definition(namespace, data_type)
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
                                        "scopes": [],
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
