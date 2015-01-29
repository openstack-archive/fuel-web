.. _ostf-api-doc:

OSTF REST API interface
=======================

Fuel OSTF module provides not only testing, but also RESTful
interface, a means for interaction with the components.

In terms of REST, all types of OSTF entities are managed by three HTTP verbs:
GET, POST and PUT.

The following basic URL is used to make requests to OSTF::

    {ostf_host}:{ostf_port}/v1/{requested_entity}/{cluster_id}

Currently, you can get information about testsets, tests and testruns
via GET request on the corresponding URLs for ostf_plugin.

To get information about testsets, make a GET request on the following URL::

    {ostf_host}:{ostf_port}/v1/testsets/{cluster_id}

To get information about tests, make a GET request on the following URL::

    {ostf_host}:{ostf_port}/v1/tests/{cluster_id}

To get information about executed tests, make the following GET
requests:

- for the whole set of testruns::

    {ostf_host}:{ostf_port}/v1/testruns/

- for the particular testrun::

    {ostf_host}:{ostf_port}/v1/testruns/{testrun_id}

- for the list of testruns executed on the particular cluster::

    {ostf_host}:{ostf_port}/v1/testruns/last/{cluster_id}

To start test execution, make a POST request on the following URL::

    {ostf_host}:{ostf_port}/v1/testruns/

The body must consist of JSON data structure with testsets and the list
of tests belonging to it that must be executed. It should also have
metadata with the information about the cluster
(the key with the "cluster_id" name is used to store the parameter's value)::

    [
        {
            "testset": "test_set_name",
            "tests": ["module.path.to.test.1", ..., "module.path.to.test.n"],
            "metadata": {"cluster_id": id}
        },

        ...,

        {...}, # info for another testrun
        {...},

        ...,

        {...}
    ]

If succeeded, OSTF adapter returns attributes of created testrun entities
in JSON format. If you want to launch only one test, put its id
into the list. To launch all tests, leave the list empty (by default).
Example of the response::

    [
        {
            "status": "running",
            "testset": "sanity",
            "meta": null,
            "ended_at": "2014-12-12 15:31:54.528773",
            "started_at": "2014-12-12 15:31:41.481071",
            "cluster_id": 1,
            "id": 1,
            "tests": [.....info on tests.....]
        },

        ....
    ]

You can also stop and restart testruns. To do that, make a PUT request on
testruns. The request body must contain the list of the testruns and
tests to be stopped or restarted. Example::

        [
            {
                "id": test_run_id,
                "status": ("stopped" | "restarted"),
                "tests": ["module.path.to.test.1", ..., "module.path.to.test.n"]
            },

            ...,

            {...}, # info for another testrun
            {...},

            ...,

            {...}
        ]

If succeeded, OSTF adapter returns attributes of the processed testruns
in JSON format. Its structure is the same as for POST request, described
above.
