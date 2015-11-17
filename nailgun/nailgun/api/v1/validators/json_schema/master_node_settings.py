# -*- coding: utf-8 -*-

#    Copyright 2015 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from nailgun import consts

schema = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "title": "MasterNodeSettings",
    "description": "Serialized MasterNodeSettings object",
    "type": "object",
    "properties": {
        "settings": {
            "type": "object",
            "properties": {
                "ui_settings": {
                    "type": "object",
                    "required": [
                        "view_mode",
                        "filter",
                        "sort",
                        "filter_by_labels",
                        "sort_by_labels",
                        "search"
                    ],
                    "properties": {
                        "view_mode": {
                            "type": "string",
                            "description": "View mode of cluster nodes",
                            "enum": list(consts.NODE_VIEW_MODES),
                        },
                        "filter": {
                            "type": "object",
                            "description": ("Filters applied to node list and "
                                            "based on node attributes"),
                            "properties": dict(
                                (key, {"type": "array"})
                                for key in consts.NODE_LIST_FILTERS
                            ),
                        },
                        "sort": {
                            "type": "array",
                            "description": ("Sorters applied to node list and "
                                            "based on node attributes"),
                            # TODO(@jkirnosova): describe fixed list
                            # of possible node sorters
                            "items": [
                                {"type": "object"},
                            ],
                        },
                        "filter_by_labels": {
                            "type": "object",
                            "description": ("Filters applied to node list and "
                                            "based on node custom labels"),
                        },
                        "sort_by_labels": {
                            "type": "array",
                            "description": ("Sorters applied to node list and "
                                            "based on node custom labels"),
                            "items": [
                                {"type": "object"},
                            ],
                        },
                        "search": {
                            "type": "string",
                            "description": "Search value applied to node list",
                        },
                    }
                }
            },
        }
    }
}
