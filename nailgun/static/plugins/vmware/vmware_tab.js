/*
 * Copyright 2015 Mirantis, Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License"); you may
 * not use this file except in compliance with the License. You may obtain
 * a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 * WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 * License for the specific language governing permissions and limitations
 * under the License.
 **/

define(
[
    'react',
    'jquery',
    'i18n',
    'underscore',
    'dispatcher',
    'utils',
    'views/controls',
    'component_mixins',
    'plugins/vmware/vmware_models'
], function(React, $, i18n, _, dispatcher, utils, controls, componentMixins, vmwareModels) {
    'use strict';

    var Field = React.createClass({
        onChange: function(name, value) {
            var currentValue = this.props.model.get(name);
            if (currentValue.current) {
                currentValue.current.id = value;
                currentValue.current.label = value;
            } else {
                currentValue = value;
            }
            this.props.model.set(name, currentValue);
            this.setState({model: this.props.model});
            _.defer(function() {dispatcher.trigger('vcenter_model_update');});
        },
        render: function() {
            var metadata = this.props.metadata,
                value = this.props.model.get(metadata.name);
            return (
                <controls.Input
                    {... _.pick(metadata, 'name', 'type', 'label', 'description')}
                    value={metadata.type == 'select' ? value.current.id : value}
                    checked={value}
                    toggleable={metadata.type == 'password'}
                    onChange={this.onChange}
                    disabled={this.props.disabled}
                    error={(this.props.model.validationError || {})[metadata.name]}
                >
                    {metadata.type == 'select' && value.options.map(function(value) {
                        return <option key={value.id} value={value.id}>{value.label}</option>;
                    })}
                </controls.Input>
            );
        }
    });

    var FieldGroup = React.createClass({
        render: function() {
            var restrictions = this.props.model.testRestrictions();
            var metadata = _.filter(this.props.model.get('metadata'), vmwareModels.isRegularField);
            var fields = metadata.map(function(meta) {
                return (
                    <Field
                        key={meta.name}
                        model={this.props.model}
                        metadata={meta}
                        disabled={this.props.disabled}
                        disableWarning={restrictions.disable[meta.name]}
                    />
                );
            }, this);
            return (
                <div>
                    {fields}
                </div>
            );
        }
    });

    var GenericSection = React.createClass({
        render: function() {
            if (!this.props.model) return null;
            return (
                <div className='col-xs-12 forms-box'>
                    <h3>
                        {this.props.title}
                        {this.props.tooltipText &&
                            <controls.Tooltip text={this.props.tooltipText} placement='right'>
                                <i className='glyphicon glyphicon-warning-sign tooltip-icon' />
                            </controls.Tooltip>
                        }
                    </h3>
                    <FieldGroup model={this.props.model} disabled={this.props.disabled}/>
                </div>
            );
        }
    });

    var NovaCompute = React.createClass({
        render: function() {
            if (!this.props.model) return null;

            // add nodes of 'compute-vmware' type to targetNode select
            var targetNode = this.props.model.get('target_node') || {};
            var nodes = this.props.cluster.get('nodes').filter(function(node) {
                return node.hasRole('compute-vmware');
            });

            targetNode.options = [];
            if (targetNode.current.id == 'controllers' || !this.props.isLocked) {
                targetNode.options.push({id: 'controllers', label: 'controllers'});
            } else {
                targetNode.options.push({id: 'invalid', label: 'Select node'});
            }
            nodes.forEach(function(node) {
                targetNode.options.push({
                    id: node.get('hostname'),
                    label: node.get('name') + ' (' + node.get('mac').substr(9) + ')'
                });
            });

            this.props.model.set('target_node', targetNode);

            return (
                <div className='nova-compute'>
                    <h4>
                        <div className='btn-group'>
                            <button
                                className='btn btn-link'
                                disabled={this.props.disabled}
                                onClick={_.bind(function() {this.props.onAdd(this.props.model);}, this)}
                            >
                                <i className='glyphicon glyphicon-plus-sign' />
                            </button>
                            {!this.props.isRemovable &&
                                <button
                                    className='btn btn-link'
                                    disabled={this.props.disabled}
                                    onClick={_.bind(function() {this.props.onRemove(this.props.model);}, this)}
                                >
                                    <i className='glyphicon glyphicon-minus-sign' />
                                </button>
                            }
                        </div>
                        {i18n('vmware.nova_compute')}
                    </h4>
                    <FieldGroup model={this.props.model} disabled={this.props.disabled}/>
                </div>
            );
        }
    });

    var AvailabilityZone = React.createClass({
        addNovaCompute: function(current) {
            var collection = this.props.model.get('nova_computes'),
                index = collection.indexOf(current),
                newItem = current.clone();
            var targetNode = _.cloneDeep(newItem.get('target_node'));
            if (this.props.isLocked) {
                targetNode.current = {id: 'invalid'};
            }
            newItem.set('target_node', targetNode);
            collection.add(newItem, {at: index + 1});
            collection.parseRestrictions();
            this.setState({model: this.props.model});
            _.defer(function() {dispatcher.trigger('vcenter_model_update'); });
        },
        removeNovaCompute: function(current) {
            var collection = this.props.model.get('nova_computes');
            collection.remove(current);
            this.setState({model: this.props.model});
            _.defer(function() { dispatcher.trigger('vcenter_model_update'); });
        },
        renderFields: function() {
            var model = this.props.model,
                meta = model.get('metadata');
            meta = _.filter(meta, vmwareModels.isRegularField);
            return (
                <FieldGroup model={model} disabled={this.props.isLocked || this.props.disabled}/>
            );
        },
        renderComputes: function(actions) {
            var novaComputes = this.props.model.get('nova_computes'),
                isSingleInstance = novaComputes.length == 1,
                disabled = actions.disable.nova_computes,
                cluster = this.props.cluster;

            return (
                <div className='col-xs-offset-1'>
                    <h3>
                        {i18n('vmware.nova_computes')}
                    </h3>
                    {novaComputes.map(function(compute) {
                        return (
                            <NovaCompute
                                key={compute.cid}
                                model={compute}
                                onAdd={this.addNovaCompute}
                                onRemove={this.removeNovaCompute}
                                isRemovable={isSingleInstance}
                                disabled={disabled.result || this.props.disabled}
                                isLocked={this.props.isLocked}
                                cluster={cluster}
                            />
                        );
                    }, this)}
                </div>
            );
        },
        render: function() {
            var restrictActions = this.props.model.testRestrictions();

            return (
                <div>
                    {this.renderFields(restrictActions)}
                    {this.renderComputes(restrictActions)}
                </div>
            );
        }
    });

    var AvailabilityZones = React.createClass({
        render: function() {
            if (!this.props.collection) return null;
            return (
                <div className='col-xs-12 forms-box'>
                    <h3>
                        {i18n('vmware.availability_zones')}
                        {this.props.tooltipText &&
                            <controls.Tooltip text={this.props.tooltipText} placement='right'>
                                <i className='glyphicon glyphicon-warning-sign tooltip-icon' />
                            </controls.Tooltip>
                        }
                    </h3>
                    {this.props.collection.map(function(model) {
                        return <AvailabilityZone key={model.cid} model={model} disabled={this.props.disabled} cluster={this.props.cluster} isLocked={this.props.isLocked}/>;
                    }, this)}
                </div>
            );
        }
    });

    var UnassignedNodesWarning = React.createClass({
        render: function() {
            if (!this.props.errors || !this.props.errors.unassigned_nodes) return null;
            return (
                <div className='alert alert-danger'>
                    <div>
                        {i18n('vmware.unassigned_nodes')}
                    </div>
                    <ul className='unassigned-node-list'>
                        {
                            this.props.errors.unassigned_nodes.map(function(node) {
                                return (
                                    <li className='unassigned-node'>
                                        <span className='unassigned-node-name'>{node.get('name')}</span>
                                        &nbsp;
                                        ({node.get('mac')})
                                    </li>
                                );
                            })
                        }
                    </ul>
                </div>
            );
        }
    });

    var VCenter = React.createClass({
        mixins: [
            componentMixins.unsavedChangesMixin
        ],
        statics: {
            isVisible: function(cluster) {
                return cluster.get('settings').get('common.use_vcenter').value;
            },
            fetchData: function(options) {
                if (!options.cluster.get('vcenter_defaults')) {
                    var defaultModel = new vmwareModels.VCenter({id: options.cluster.id});
                    defaultModel.loadDefaults = true;
                    options.cluster.set({vcenter_defaults: defaultModel});
                }
                return $.when(
                    options.cluster.get('vcenter').fetch({cache: true}),
                    options.cluster.get('vcenter_defaults').fetch({cache: true})
                );
            }
        },
        onModelSync: function() {
            this.model.parseRestrictions();
            this.actions = this.model.testRestrictions();
            if (!this.model.loadDefaults) {
                this.json = JSON.stringify(this.model.toJSON());
            }
            this.model.loadDefaults = false;
            this.setState({model: this.model});
        },
        componentDidMount: function() {
            this.clusterId = this.props.cluster.id;
            this.model = this.props.cluster.get('vcenter');
            this.model.on('sync', this.onModelSync, this);
            this.defaultModel = this.props.cluster.get('vcenter_defaults');
            this.defaultModel.parseRestrictions();
            this.defaultsJson = JSON.stringify(this.defaultModel.toJSON());
            this.setState({model: this.model, defaultModel: this.defaultModel});

            this.model.setModels({
                cluster: this.props.cluster,
                settings: this.props.cluster.get('settings'),
                networking_parameters: this.props.cluster.get('networkConfiguration').get('networking_parameters')
            });

            this.onModelSync();
            dispatcher.on('vcenter_model_update', _.bind(function() {
                if (this.isMounted()) {
                    this.forceUpdate();
                }
            }, this));
        },
        componentWillUnmount: function() {
            this.defaultModel.off('sync', null, this);
            this.model.off('sync', null, this);
            dispatcher.off('vcenter_model_update');
        },
        getInitialState: function() {
            return {model: null};
        },
        readData: function() {
            return this.model.fetch();
        },
        onLoadDefaults: function() {
            this.model.loadDefaults = true;
            this.model.fetch().done(_.bind(function() {
                this.model.loadDefaults = false;
            }, this));
        },
        applyChanges: function() {
            return this.model.save();
        },
        revertChanges: function() {
            return this.readData();
        },
        hasChanges: function() {
            return this.detectChanges(this.json, JSON.stringify(this.model.toJSON()));
        },
        detectChanges: function(oldJson, currentJson) {
            var old, current;
            try {
                old = JSON.parse(oldJson);
                current = JSON.parse(currentJson);
            } catch (error) {
                return false;
            }
            var oldData = JSON.stringify(old, function(key, data) {
                if (key == 'target_node') {
                    delete data.options;
                }
                return data;
            });
            var currentData = JSON.stringify(current, function(key, data) {
                if (key == 'target_node') {
                    delete data.options;
                }
                return data;
            });
            return oldData != currentData;
        },
        isSavingPossible: function() {
            return !this.state.model.validationError;
        },
        render: function() {
            if (!this.state.model || !this.actions) {
                return null;
            }

            var model = this.state.model,
                currentJson = JSON.stringify(this.model.toJSON()),
                editable = this.props.cluster.isAvailableForSettingsChanges(),
                hide = this.actions.hide || {},
                disable = this.actions.disable || {};

            model.isValid();
            var hasChanges = this.detectChanges(this.json, currentJson);
            var hasDefaultsChanges = this.detectChanges(this.defaultsJson, currentJson);
            var saveDisabled = !hasChanges || !this.isSavingPossible(),
                defaultsDisabled = !hasDefaultsChanges;

            return (
                <div className='row'>
                    <div className='title'>{i18n('vmware.title')}</div>
                    <UnassignedNodesWarning errors={model.validationError}/>
                    {!hide.availability_zones.result &&
                        <AvailabilityZones
                            collection={model.get('availability_zones')}
                            disabled={disable.availability_zones.result}
                            tooltipText={disable.availability_zones.message}
                            isLocked={!editable}
                            cluster={this.props.cluster}
                        />
                    }
                    {!hide.network.result &&
                        <GenericSection
                            model={model.get('network')}
                            title={i18n('vmware.network')}
                            disabled={!editable || disable.network.result}
                            tooltipText={disable.network.message}
                        />
                    }
                    {!hide.glance.result &&
                        <GenericSection
                            model={model.get('glance')}
                            title={i18n('vmware.glance')}
                            disabled={!editable || disable.glance.result}
                            tooltipText={disable.glance.message}
                        />
                    }
                    <div className='col-xs-12 page-buttons content-elements'>
                        <div className='well clearfix'>
                            <div className='btn-group pull-right'>
                                <button className='btn btn-default btn-load-defaults' onClick={this.onLoadDefaults} disabled={!editable || defaultsDisabled}>
                                    {i18n('vmware.reset_to_defaults')}
                                </button>
                                <button className='btn btn-default btn-revert-changes' onClick={this.revertChanges} disabled={!hasChanges}>
                                    {i18n('vmware.cancel')}
                                </button>
                                <button className='btn btn-success btn-apply-changes' onClick={this.applyChanges} disabled={saveDisabled}>
                                    {i18n('vmware.apply')}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            );
        }
    });
    return VCenter;
});
