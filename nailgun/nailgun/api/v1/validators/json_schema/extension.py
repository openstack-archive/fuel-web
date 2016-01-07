from nailgun.api.v1.validators.json_schema import base_types


single_schema = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "title": "Extension",
    "description": "Serialized Nailgun extension information",
    "type": "string",
}

collection_schema = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "title": "Extension collection",
    "description": "Serialized Nailgun extension information",
    "type": base_types.STRINGS_ARRAY,
}
