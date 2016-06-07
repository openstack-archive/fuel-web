# Fuel-YAQL

Fuel-YAQL is a live YAQL master node console for Fuel to easy evaluate yaql
conditions user wanted to put into task.

How to use:

on Fuel master node, run

> manage.py yaql -c 'CLUSTER_ID'

where 'CLUSTER_ID' is id of existing cluster which you can get by run

> fuel env

command. Cluster id is required there to have an opportunity for use internal Fuel yaql
functions such as 'changed' or 'new'. After this fuel-yaql console will be opened:

> fuel-yaql >

there you can evaluate all functions and conditions you need just by entering
them, for example:

> fuel-yaql> changed($)

> true

This console has some internal commands. There they are:

> fuel-yaql> :show cluster

> Cluster id is: 1, name is: test

shows you the cluster you currently use.

> fuel-yaql> :show node

> Currently used node id is: master

shows you a node in this cluster for which conditions will be evaluated.

> fuel-yaql> :show nodes

> Cluster has nodes with ids: {1: 'controller'}

shows you all nodes in this cluster

> fuel-yaql> :use cluster 1

will switch contexts to another cluster

> fuel-yaql> :use node 1

will switch contexts to another node

> fuel-yaql> :show tasks

shows all tasks in 'deployment', 'error', 'ready' and 'pending' states for
currently selected cluster. In other words, this commands represents a
list of tasks which you can use as a context.

> fuel-yaql> :loadprevious task 5

will switch *old* context to a context of pointed task. It can be worthy if you
want to evaluate an expression not for the current cluster state, but for old one.

> fuel-yaql> :loadcurrent task 10

will switch *new* context to context of pointed task. It can be as worthy
as *:loadprevious* command. Maybe you should know that there is no
restriction to have old context really older than new context - you can switch
them as you want


Fuel itself has several internal yaql functions which are not included to base
yaql interpreter. There they are:

```changed()``` - will show you the difference between new and old contexts

```new()``` - returns you new context data

```old()``` - returns you old context data

```added()``` - returns the diff what was added between old and new context

```deleted()``` - returns the diff what was deleted between old and new contexts

```changedAll($.first, $.second, $.Nth)``` - returns True if all expressions in
parentheses returns non-False

```changedAny($.first, $.second, $.Nth)``` - returns True if any expression in
parentheses returns non-False


# Changelog

## 0.7

[*] Project moved and became a part of Fuel-nailgun

## 0.6

[*] internal fixes, tests added

## 0.5

[+] opportunity to run fuyaql with predefined contexts and expression and return
    a result

## 0.4

[*] internal fixes

## 0.3

[+] changelog

[+] switched to readline, so input line doesn't looks like telnet one

[+] internal commands autocomplit by Tab

[+] internal commands ':oldcontext task' and ':newcontext task' added

[*] not creating default existing context as a task anymore. It allows to not
  touch DB for a creating temporary task

## 0.2

[+] first usable version

## 0.1

[+] proof of concept created
