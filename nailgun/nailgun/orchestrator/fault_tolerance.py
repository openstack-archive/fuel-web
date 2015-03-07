# -*- coding: UTF-8 -*-


ALLOWED_TO_FAIL = [{'name': 'compute', 'setting': 'max_computes_to_fail'}]


def for_provision(nodes, cluster_attrs):
    may_fail = []
    for role in ALLOWED_TO_FAIL:
        uids = []
        for node in nodes:
            if role['name'] in node.roles:
                uids.append(node.uid)
        percentage = cluster_attrs.get(role['setting'], 0)
        may_fail.append({'uids' : uids,
                         'percentage' : int(percentage)})
    return may_fail
